"""
test_nlp_similarity.py
======================
Unit and integration tests for nlp-similarity service:
- Cleaner (work-code prefix stripping)
- Reasoning generation
- Similarity indexer (FAISS / cosine matching)
- FastAPI endpoints (/health, /projects/{id}/similar)
"""

from __future__ import annotations

import pytest
import numpy as np
from fastapi.testclient import TestClient

from cleaner import clean_work_description
from reasoning import generate_similarity_reason
from indexer import NLPSimilarityIndex
from main import app, get_index


# ---------------------------------------------------------------------------
# Cleaner Tests
# ---------------------------------------------------------------------------
def test_clean_work_description_standard_prefix():
    raw = "WS/MP559/2023-2024/92788 - Construction of Community Hall at Village Rampur"
    expected = "Construction of Community Hall at Village Rampur"
    assert clean_work_description(raw) == expected


def test_clean_work_description_colon_separator():
    raw = "RD/MP100/2022-2023/12345: Construction of CC Road in Ward 4"
    expected = "Construction of CC Road in Ward 4"
    assert clean_work_description(raw) == expected


def test_clean_work_description_secondary_format():
    raw = "MP559/92788 - Providing and fixing solar street lights"
    expected = "Providing and fixing solar street lights"
    assert clean_work_description(raw) == expected


def test_clean_work_description_tagged_prefix():
    raw = "WORK CODE: 54321 - Installation of Mark II hand pump"
    expected = "Installation of Mark II hand pump"
    assert clean_work_description(raw) == expected


def test_clean_work_description_no_prefix():
    raw = "Construction of boundary wall for Government High School"
    assert clean_work_description(raw) == raw


def test_clean_work_description_empty_and_none():
    assert clean_work_description(None) == ""
    assert clean_work_description("") == ""
    assert clean_work_description("   ") == ""


# ---------------------------------------------------------------------------
# Reasoning Tests
# ---------------------------------------------------------------------------
def test_generate_similarity_reason_domain_phrases():
    q = "Construction of community hall in Gram Panchayat"
    t = "Renovation and painting of community hall near temple"
    reason = generate_similarity_reason(q, t, 0.88)
    assert "community hall" in reason


def test_generate_similarity_reason_high_score_wording():
    q = "Construction of CC road from main road to school"
    t = "Construction of CC road from main road to village centre"
    reason = generate_similarity_reason(q, t, 0.94)
    assert "Near-identical" in reason or "cc road" in reason


# ---------------------------------------------------------------------------
# Indexer & Similarity Tests (Using synthetic sample records)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sample_projects():
    return [
        {
            "id": "proj-hall-1",
            "work": "WS/MP559/2023-2024/92788 - Construction of Community Hall at Gram Rampur",
            "state": "Madhya Pradesh",
            "constituency": "Rewa",
            "block": "Sirmaur",
            "village": "Rampur",
            "allocation_amount": 1500000.0,
        },
        {
            "id": "proj-hall-2",
            "work": "WS/MP559/2023-2024/92789 - Construction of Community Hall at Sirmaur Village",
            "state": "Madhya Pradesh",
            "constituency": "Rewa",
            "block": "Sirmaur",
            "village": "Sirmaur",
            "allocation_amount": 1600000.0,
        },
        {
            "id": "proj-hall-bihar",
            "work": "Construction of Community Hall and boundary wall",
            "state": "Bihar",
            "constituency": "Patna Sahib",
            "block": "Danapur",
            "village": "Danapur",
            "allocation_amount": 2000000.0,
        },
        {
            "id": "proj-road-1",
            "work": "RD/MP100/2022-2023/10001 - Construction of CC road from main road to primary school",
            "state": "Madhya Pradesh",
            "constituency": "Rewa",
            "block": "Sirmaur",
            "village": "Rampur",
            "allocation_amount": 800000.0,
        },
        {
            "id": "proj-road-2",
            "work": "Construction of cement concrete CC road in ward no 5",
            "state": "Maharashtra",
            "constituency": "Nagpur South",
            "block": "Nagpur",
            "village": None,
            "allocation_amount": 950000.0,
        },
        {
            "id": "proj-water-1",
            "work": "Installation of solar drinking water borewell system",
            "state": "Rajasthan",
            "constituency": "Dausa",
            "block": "Sikrai",
            "village": "Geejgarh",
            "allocation_amount": 450000.0,
        },
    ]


@pytest.fixture(scope="module")
def populated_index(sample_projects):
    index = NLPSimilarityIndex()
    index.load_from_records(sample_projects)
    return index


def test_indexer_finds_similar_community_halls(populated_index):
    res = populated_index.get_similar("proj-hall-1", top_k=3)

    assert res.project_id == "proj-hall-1"
    assert res.cleaned_work == "Construction of Community Hall at Gram Rampur"
    assert len(res.similar_projects) > 0

    # Ensure self is excluded
    result_ids = [p.similar_project_id for p in res.similar_projects]
    assert "proj-hall-1" not in result_ids

    # Top result should be the other community hall in MP
    top_match = res.similar_projects[0]
    assert top_match.similar_project_id in ["proj-hall-2", "proj-hall-bihar"]
    assert top_match.similarity_score > 0.65

    # Check geography comparisons for proj-hall-2
    hall2_match = next((p for p in res.similar_projects if p.similar_project_id == "proj-hall-2"), None)
    if hall2_match:
        assert hall2_match.same_state is True
        assert hall2_match.same_constituency is True
        assert hall2_match.same_village_or_block is True
        assert hall2_match.allocation_difference == pytest.approx(100000.0, 0.01)

    # Check geography comparisons for proj-hall-bihar
    hall_bihar_match = next((p for p in res.similar_projects if p.similar_project_id == "proj-hall-bihar"), None)
    if hall_bihar_match:
        assert hall_bihar_match.same_state is False
        assert hall_bihar_match.same_constituency is False
        assert hall_bihar_match.allocation_difference == pytest.approx(500000.0, 0.01)


def test_missing_project_raises_key_error(populated_index):
    with pytest.raises(KeyError):
        populated_index.get_similar("non-existent-uuid")


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------
def test_api_health(populated_index):
    # Bind the populated index to app
    global_index = get_index()
    global_index.project_ids = populated_index.project_ids
    global_index.id_to_idx = populated_index.id_to_idx
    global_index.metadata = populated_index.metadata
    global_index.embeddings = populated_index.embeddings
    global_index.faiss_index = populated_index.faiss_index
    global_index._is_loaded = True

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "nlp-similarity"
    assert data["index_size"] >= 6
    assert data["is_ready"] is True


def test_api_similar_projects(populated_index):
    global_index = get_index()
    global_index.project_ids = populated_index.project_ids
    global_index.id_to_idx = populated_index.id_to_idx
    global_index.metadata = populated_index.metadata
    global_index.embeddings = populated_index.embeddings
    global_index.faiss_index = populated_index.faiss_index
    global_index._is_loaded = True

    client = TestClient(app)
    resp = client.get("/projects/proj-hall-1/similar?top_k=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "proj-hall-1"
    assert data["cleaned_work"] == "Construction of Community Hall at Gram Rampur"
    assert len(data["similar_projects"]) == 2
    assert "human_review_notice" in data

    # Verify fields required by specification
    first = data["similar_projects"][0]
    for req_field in [
        "similar_project_id",
        "similarity_score",
        "similarity_reason",
        "same_state",
        "same_constituency",
        "same_village_or_block",
        "allocation_difference",
    ]:
        assert req_field in first


def test_api_similar_projects_404():
    client = TestClient(app)
    resp = client.get("/projects/unknown-uuid-0000/similar")
    assert resp.status_code == 404
