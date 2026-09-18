"""
test_audit_assistant.py
=======================
Tests for the AI Audit Assistant endpoint:
1. Safe parameterized query translation (zero string-interpolated SQL).
2. Grounded answers derived solely from retrieved data with citations.
3. Tone compliance (never claims fraud, uses 'flagged for review' / 'anomaly indicator').
4. Safe explicit refusal for unmappable questions without guessing.
5. SQL injection safety.
6. Kill-switch / disable toggle.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

import main
from main import app

client = TestClient(app)


def test_assistant_status():
    """Verify assistant status endpoint reports active state."""
    response = client.get("/api/v1/assistant/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["service"] == "MPLADS AI Audit Assistant"


def test_expensive_road_projects_punjab():
    """
    Test target query: 'Show unusually expensive road projects in Punjab'.
    Must translate to safe parameters, retrieve Punjab road records,
    and cite underlying project IDs.
    """
    payload = {"question": "Show unusually expensive road projects in Punjab"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "EXPENSIVE_PROJECTS"
    assert data["records_found"] >= 1
    assert len(data["citations"]) >= 1

    citation = data["citations"][0]
    assert citation["state"] == "Punjab"
    assert citation["project_id"] == "88888888-0000-0000-0001-000000000001"
    assert "Rs." in data["answer"]
    assert data["safe_audit_language"] is True

    # Check tone: no accusatory words
    answer_lower = data["answer"].lower()
    assert "fraud" not in answer_lower
    assert "scam" not in answer_lower


def test_constituencies_most_pending():
    """
    Test target query: 'Which constituencies have the most pending projects?'.
    Must aggregate pending/ongoing projects by constituency with citations.
    """
    payload = {"question": "Which constituencies have the most pending projects?"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "PENDING_PROJECTS"
    assert data["records_found"] >= 1
    assert len(data["citations"]) >= 1

    # Answer must explicitly mention constituencies and numbers from database
    assert "constituenc" in data["answer"].lower()
    assert data["safe_audit_language"] is True


def test_why_was_project_flagged():
    """
    Test target query: 'Why was project feaa76a4-cbf6-5482-8e84-ecb5600c3f9d flagged?'.
    Must retrieve the specific anomaly reason for Demo Case 2.
    """
    target_id = "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d"
    payload = {"question": f"Why was project {target_id} flagged for review?"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "PROJECT_FLAG_REASON"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["project_id"] == target_id
    assert "financial" in data["answer"].lower() or "allocation" in data["answer"].lower()
    assert "flagged for review" in data["answer"].lower() or "anomaly indicator" in data["answer"].lower()


def test_why_was_project_x_flagged():
    """Test natural language shorthand: 'Why was project X flagged?'"""
    payload = {"question": "Why was project X flagged?"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "PROJECT_FLAG_REASON"
    assert len(data["citations"]) >= 1


def test_unmappable_question_safe_refusal():
    """
    Out-of-scope question must be explicitly refused rather than guessed.
    """
    payload = {"question": "What will the weather forecast be tomorrow in Mumbai?"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "UNSUPPORTED"
    assert data["records_found"] == 0
    assert len(data["citations"]) == 0
    assert "cannot safely map your question" in data["answer"]


def test_sql_injection_attempt_is_safe():
    """
    Adversarial input with SQL injection payload must not execute raw SQL or error out.
    """
    payload = {"question": "Show road projects in Punjab'; DROP TABLE project; --"}
    response = client.post("/api/v1/assistant/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    # It must either map safely to Punjab road projects or be refused; never crash
    assert data["safe_audit_language"] is True


def test_audit_tone_compliance():
    """
    Ensures that even if an underlying text contains accusatory language,
    the tone guard sanitizes it to audit-compliant terminology.
    """
    from audit_assistant import sanitize_audit_tone
    raw = "The contractor committed fraud and this scam is fraudulent."
    sanitized = sanitize_audit_tone(raw)
    assert "fraud" not in sanitized.lower()
    assert "scam" not in sanitized.lower()
    assert "anomaly indicator" in sanitized or "flagged for review" in sanitized


def test_disable_toggle(monkeypatch):
    """Verify assistant can be completely disabled via ENABLE_AUDIT_ASSISTANT."""
    monkeypatch.setattr(main, "ENABLE_AUDIT_ASSISTANT", False)

    response = client.post(
        "/api/v1/assistant/query",
        json={"question": "Show road projects in Punjab"},
    )
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
