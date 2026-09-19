"""
tests/test_risk_aggregator.py
=============================
Integration tests for the risk-aggregator service.
Verifies endpoints, role-based filtering, and PATCH actions.
"""

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "risk-aggregator"


def test_dashboard_stats(client):
    res = client.get("/api/v1/dashboard/stats")
    assert res.status_code == 200
    data = res.json()
    assert data["total_projects"] >= 5
    assert data["total_allocation"] > 0
    assert len(data["status_distribution"]) > 0
    assert len(data["risk_distribution"]) == 3


def test_list_projects(client):
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 5
    assert len(data["data"]) >= 5


def test_list_projects_search(client):
    res = client.get("/api/v1/projects", params={"search": "playfields"})
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert "playfields" in data["data"][0]["work"].lower()


def test_project_detail_official(client):
    pid = "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d"
    res = client.get(f"/api/v1/projects/{pid}", params={"role": "official"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == pid
    assert data["risk_score"] is not None
    assert data["risk_score"] > 0.9
    assert data["financial_analysis"] is not None
    assert data["financial_analysis"]["ratio_vs_median"] > 100
    assert len(data["flags"]) >= 1
    assert data["flags"][0]["score"] is not None


def test_project_detail_citizen_role_redaction(client):
    pid = "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d"
    res = client.get(f"/api/v1/projects/{pid}", params={"role": "citizen"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == pid
    # Citizen view must have risk_score redacted to None
    assert data["risk_score"] is None
    # Flags must have raw score and reviewer_id redacted to None
    for flag in data["flags"]:
        assert flag["score"] is None
        assert flag["reviewer_id"] is None


def test_patch_anomaly_flag(client):
    fid = "77777777-0000-0000-0002-000000000001"
    payload = {"review_status": "confirmed", "reviewer_id": "test-auditor-123"}
    res = client.patch(f"/api/v1/anomaly-flags/{fid}", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["review_status"] == "confirmed"


def test_works_near_me_only_demo_projects(client):
    res = client.get("/api/v1/map/works-near-me")
    assert res.status_code == 200
    items = res.json()
    # Exactly the 5 seeded demo projects
    assert len(items) == 5
    for item in items:
        assert item["source_type"] == "DEMO_SYNTHETIC"
        assert item["lat"] is not None
        assert item["lng"] is not None


def test_administrative_map(client):
    res = client.get("/api/v1/map/administrative")
    assert res.status_code == 200
    states = res.json()
    assert len(states) >= 3
    for s in states:
        assert len(s["constituencies"]) >= 1


def test_project_risk_single_stage_approval(client):
    pid = "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d"
    res = client.get(f"/projects/{pid}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid
    assert data["overall_risk_score"] >= 0.7
    assert data["risk_level"] == "high"
    assert len(data["risk_factors"]) >= 1
    assert any(f["type"] == "financial" and f["score"] >= 0.7 for f in data["risk_factors"])
    assert len(data["stage_indicator"]) == 1
    assert data["stage_indicator"][0]["stage"] == "approval_process"
    assert data["stage_indicator"][0]["flagged"] is True
    assert "irregularities in how the project was proposed or sanctioned" in data["stage_indicator"][0]["overview"]
    assert data["note"] is None


def test_project_risk_single_stage_delivery(client):
    pid = "b503d0a8-c311-5409-b365-5ade19ce3e2f"
    res = client.get(f"/projects/{pid}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid
    assert len(data["stage_indicator"]) == 1
    assert data["stage_indicator"][0]["stage"] == "execution_delivery"
    assert data["stage_indicator"][0]["flagged"] is True
    assert "issues in how the work was actually carried out" in data["stage_indicator"][0]["overview"]
    assert data["note"] is None


def test_project_risk_multi_stage(client):
    pid = "e7becbea-467f-5e0d-a910-fe1e740972ba"
    res = client.get(f"/projects/{pid}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid
    assert len(data["stage_indicator"]) == 2
    stages = [s["stage"] for s in data["stage_indicator"]]
    assert "approval_process" in stages
    assert "execution_delivery" in stages
    assert data["note"] == "Multiple process stages show flagged patterns; review both."


def test_project_risk_low_risk_empty_stage_indicator(client):
    pid = "ce266c84-add9-59bb-b4ac-9fe61e2bf98d"
    res = client.get(f"/projects/{pid}/risk")
    assert res.status_code == 200
    data = res.json()
    assert data["project_id"] == pid
    assert data["risk_level"] == "low"
    assert data["stage_indicator"] == []
    assert data["note"] is None


def test_project_risk_not_found(client):
    res = client.get("/projects/00000000-0000-0000-0000-000000000000/risk")
    assert res.status_code == 404
