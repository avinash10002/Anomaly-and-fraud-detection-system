"""
tests/test_api.py
=================
FastAPI endpoint-level tests using TestClient.
DB and cost-estimator calls are patched; BenchmarkStore is injected
with synthetic data so tests run fully offline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import benchmarks as bm_module
from tests.conftest import _make_synthetic_df


# ---------------------------------------------------------------------------
# Fixture: TestClient with synthetic store pre-loaded
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Patch the module-level singleton store and the DB lookup,
    then return a TestClient.  The cost-estimator is also patched
    to return None (unavailable) by default.
    """
    # Pre-load the singleton with synthetic data (no DB)
    store = bm_module.get_store()
    if not store.is_loaded:
        store.load_from_dataframe(_make_synthetic_df())

    with (
        patch("main.DB_URL", "postgresql://fake/fake"),
        patch("main.call_cost_estimator", new_callable=AsyncMock, return_value=None),
    ):
        from main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_ok(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_has_benchmarks_summary(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "benchmarks" in data
        assert data["benchmarks"]["loaded"] is True


# ---------------------------------------------------------------------------
# GET /benchmarks/{category}/{state}
# ---------------------------------------------------------------------------

class TestBenchmarksEndpoint:

    def test_known_group_returns_200(self, client):
        resp = client.get("/benchmarks/road/Bihar")
        assert resp.status_code == 200

    def test_known_group_has_median(self, client):
        resp = client.get("/benchmarks/road/Bihar")
        data = resp.json()
        assert "median" in data
        assert data["median"] > 0

    def test_unknown_group_returns_404(self, client):
        resp = client.get("/benchmarks/flying_saucer/Neverland")
        assert resp.status_code == 404

    def test_disclaimer_in_benchmark_response(self, client):
        resp = client.get("/benchmarks/road/Bihar")
        assert "disclaimer" in resp.json()


# ---------------------------------------------------------------------------
# POST /analyze — inline mode (no project_id, no DB)
# ---------------------------------------------------------------------------

class TestAnalyzeInline:

    def _post(self, client, payload: dict):
        return client.post("/analyze", json=payload)

    def test_normal_allocation_returns_200(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   1_800_000,
            "include_cost_estimate": False,
        })
        assert resp.status_code == 200

    def test_normal_allocation_not_flagged(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   1_800_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        assert data["flag_label"] == "within expected range"
        assert not data["is_flagged"]

    def test_extreme_allocation_flagged(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   50_000_000,  # 50M vs median ≈ 1.8M
            "include_cost_estimate": False,
        })
        data = resp.json()
        assert data["is_flagged"], f"Expected flagged. Score={data['anomaly_score']}"
        assert data["flag_label"] in (
            "flagged for review",
            "financial anomaly indicator — borderline",
        )

    def test_response_has_mandatory_disclaimer(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   1_800_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        assert "disclaimer" in data
        assert "Financial anomaly indicators" in data["disclaimer"]

    def test_response_has_percentage_deviation(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   1_800_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        assert "percentage_deviation" in data
        assert isinstance(data["percentage_deviation"], float)

    def test_reason_text_cites_rupee_amounts(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   50_000_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        assert "₹" in data["reason_text"]
        assert "median" in data["reason_text"].lower()

    def test_no_fraud_language_in_response(self, client):
        resp = self._post(client, {
            "category":            "road",
            "state":               "Bihar",
            "allocation_amount":   50_000_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        # Scan only reason_text and flag_label, NOT the disclaimer
        # (disclaimer intentionally says "not a determination of fraud or misconduct")
        full_text = (
            data.get("reason_text", "") + " " +
            data.get("flag_label", "")
        ).lower()
        for word in ["fraud", "criminal", "illegal", "corrupt"]:
            assert word not in full_text, f"Forbidden word '{word}' in response"

    def test_comparison_group_returned(self, client):
        resp = self._post(client, {
            "category":            "drainage",
            "state":               "Bihar",
            "allocation_amount":   900_000,
            "include_cost_estimate": False,
        })
        data = resp.json()
        cg = data.get("comparison_group", {})
        assert cg.get("category") == "drainage"
        assert cg.get("sample_count", 0) > 0

    def test_unknown_state_falls_back(self, client):
        """Unknown state → fallback to category-level benchmark, not 500."""
        resp = self._post(client, {
            "category":            "road",
            "state":               "FantasyLand",
            "allocation_amount":   1_800_000,
            "include_cost_estimate": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison_group"]["is_fallback"] is True

    def test_completely_unknown_category_returns_200(self, client):
        resp = self._post(client, {
            "category":            "rocket propulsion",
            "state":               "Bihar",
            "allocation_amount":   1_000_000,
            "include_cost_estimate": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == "low"
        assert not data["is_flagged"]


# ---------------------------------------------------------------------------
# POST /analyze — validation errors
# ---------------------------------------------------------------------------

class TestAnalyzeValidation:

    def test_missing_all_fields_returns_422(self, client):
        resp = client.post("/analyze", json={})
        assert resp.status_code == 422

    def test_negative_amount_returns_422(self, client):
        resp = client.post("/analyze", json={
            "category":          "road",
            "state":             "Bihar",
            "allocation_amount": -1_000,
        })
        assert resp.status_code == 422

    def test_zero_amount_returns_422(self, client):
        resp = client.post("/analyze", json={
            "category":          "road",
            "state":             "Bihar",
            "allocation_amount": 0,
        })
        assert resp.status_code == 422

    def test_missing_category_returns_422(self, client):
        resp = client.post("/analyze", json={
            "state":             "Bihar",
            "allocation_amount": 1_000_000,
        })
        assert resp.status_code == 422

    def test_missing_state_returns_422(self, client):
        resp = client.post("/analyze", json={
            "category":          "road",
            "allocation_amount": 1_000_000,
        })
        assert resp.status_code == 422
