"""
test_image_engine.py
====================
Unit and integration tests for the image-engine microservice.

Validates:
  - Strict source_type provenance enforcement ("DEMO_SYNTHETIC" vs "USER_UPLOADED")
  - All four defect classes: pothole, crack, surface_deterioration, no_visible_defect
  - Computer vision detection and bounding box generation
  - Timeline degradation score and progression summary phrasing
  - FastAPI endpoints: GET /health, POST /analyze-image, POST /timeline
"""

from __future__ import annotations

import io
import base64
import pytest
import numpy as np
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from models import (
    AnalyzeImageResponse,
    CaptureRecord,
    DefectClass,
    Severity,
    SourceType,
    TimelineRequest,
)
from detector import ComputerVisionDetector
from timeline import compute_timeline_progression
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_test_image(defect_type: str = "none") -> Image.Image:
    """Create a synthetic test image for CV detection."""
    # Base asphalt road texture (gray)
    img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    draw = ImageDraw.Draw(img)

    if defect_type == "pothole":
        # Draw dark, localized circular depression
        draw.ellipse([80, 80, 220, 220], fill=(20, 20, 20))
    elif defect_type == "crack":
        # Draw thin, high-contrast jagged line
        points = [(50, 20), (100, 80), (130, 160), (180, 220), (240, 280)]
        for i in range(len(points) - 1):
            draw.line([points[i], points[i + 1]], fill=(10, 10, 10), width=4)
    elif defect_type == "surface_deterioration":
        # Draw speckled noise pattern
        for x in range(30, 270, 8):
            for y in range(30, 270, 8):
                if (x + y) % 16 == 0:
                    draw.rectangle([x, y, x + 4, y + 4], fill=(40, 40, 40))

    return img


# ---------------------------------------------------------------------------
# Provenance & Data Contract Tests
# ---------------------------------------------------------------------------
def test_source_type_enum_values():
    assert SourceType.DEMO_SYNTHETIC == "DEMO_SYNTHETIC"
    assert SourceType.USER_UPLOADED == "USER_UPLOADED"

    # Ensure no other values allowed
    with pytest.raises(ValueError):
        SourceType("GOVERNMENT_OFFICIAL")


def test_defect_classes_enumeration():
    assert DefectClass.POTHOLE == "pothole"
    assert DefectClass.CRACK == "crack"
    assert DefectClass.SURFACE_DETERIORATION == "surface_deterioration"
    assert DefectClass.NO_VISIBLE_DEFECT == "no_visible_defect"


# ---------------------------------------------------------------------------
# Detector Unit Tests
# ---------------------------------------------------------------------------
def test_detector_clean_surface():
    detector = ComputerVisionDetector()
    img = _create_test_image("none")
    defect, conf, sev, boxes, ann = detector.detect(img)

    assert defect == DefectClass.NO_VISIBLE_DEFECT
    assert sev == Severity.NONE
    assert conf >= 0.80
    assert ann.size == img.size


def test_detector_pothole():
    detector = ComputerVisionDetector()
    img = _create_test_image("pothole")
    defect, conf, sev, boxes, ann = detector.detect(img)

    assert defect == DefectClass.POTHOLE
    assert sev in (Severity.MEDIUM, Severity.HIGH)
    assert len(boxes) > 0
    assert boxes[0].label == "pothole"


def test_detector_crack():
    detector = ComputerVisionDetector()
    img = _create_test_image("crack")
    defect, conf, sev, boxes, ann = detector.detect(img)

    assert defect in (DefectClass.CRACK, DefectClass.SURFACE_DETERIORATION)
    assert sev != Severity.NONE
    assert len(boxes) > 0


def test_yolov8_detector_execution():
    from detector import YOLOv8Detector
    yolo_det = YOLOv8Detector()
    assert "YOLOv8" in yolo_det.name
    img = _create_test_image("pothole")
    defect, conf, sev, boxes, ann = yolo_det.detect(img)
    assert defect in [DefectClass.POTHOLE, DefectClass.SURFACE_DETERIORATION, DefectClass.CRACK]
    assert conf > 0.0
    assert ann.size == img.size


def test_get_detector_factory():
    from detector import get_detector, ComputerVisionDetector, YOLOv8Detector
    d_cv = get_detector(backend="cv_heuristic", force_reload=True)
    assert isinstance(d_cv, ComputerVisionDetector)
    d_auto = get_detector(backend="auto", force_reload=True)
    assert isinstance(d_auto, YOLOv8Detector)


# ---------------------------------------------------------------------------
# Timeline Engine Tests
# ---------------------------------------------------------------------------
def test_timeline_worsening_progression():
    captures = [
        CaptureRecord(
            capture_date="2022-09-01",
            defect_class=DefectClass.NO_VISIBLE_DEFECT,
            severity=Severity.NONE,
            source_type=SourceType.DEMO_SYNTHETIC,
        ),
        CaptureRecord(
            capture_date="2023-03-01",
            defect_class=DefectClass.CRACK,
            severity=Severity.MEDIUM,
            source_type=SourceType.DEMO_SYNTHETIC,
        ),
        CaptureRecord(
            capture_date="2023-09-01",
            defect_class=DefectClass.POTHOLE,
            severity=Severity.HIGH,
            source_type=SourceType.DEMO_SYNTHETIC,
        ),
    ]

    res = compute_timeline_progression("proj-101", captures)
    assert res.project_id == "proj-101"
    assert res.total_captures == 3
    assert res.timespan_months == pytest.approx(12.0, 0.5)
    assert res.degradation_score >= 0.70
    assert res.current_severity == Severity.HIGH
    assert "increased from none to high over 3 captures spanning 12" in res.progression_summary
    assert SourceType.DEMO_SYNTHETIC in res.source_types_present


def test_timeline_single_capture():
    captures = [
        CaptureRecord(
            capture_date="2023-08-15",
            defect_class=DefectClass.POTHOLE,
            severity=Severity.HIGH,
            source_type=SourceType.USER_UPLOADED,
        ),
    ]

    res = compute_timeline_progression("proj-single", captures)
    assert res.total_captures == 1
    assert res.timespan_months == 0.0
    assert "Single capture on 2023-08-15 identified pothole at high severity." in res.progression_summary
    assert res.source_types_present == [SourceType.USER_UPLOADED]


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------
def test_api_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "image-engine"
    assert data["source_type_mandatory"] is True
    assert data["ready"] is True


def test_api_analyze_image_multipart_upload(client):
    img = _create_test_image("pothole")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"image": ("test_road.jpg", buf, "image/jpeg")}
    data = {
        "project_id": "test-uuid-1234",
        "capture_date": "2023-10-15",
        "source_type": "DEMO_SYNTHETIC",
    }

    resp = client.post("/analyze-image", files=files, data=data)
    assert resp.status_code == 200
    res = resp.json()

    assert res["project_id"] == "test-uuid-1234"
    assert "image_id" in res
    assert res["capture_date"] == "2023-10-15"
    assert res["inspection_status"] == "requires_human_review"
    assert res["source_type"] == "DEMO_SYNTHETIC"
    assert res["defect_class"] in [d.value for d in DefectClass]
    assert res["severity"] in [s.value for s in Severity]
    assert res["annotated_image_url"].startswith("/static/annotated/")
    assert "CRITICAL NOTICE" in res["disclaimer"]


def test_api_analyze_image_base64_json(client):
    img = _create_test_image("none")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64_str = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

    payload = {
        "project_id": "test-uuid-5678",
        "capture_date": "2023-11-20",
        "image_url": b64_str,
        "source_type": "USER_UPLOADED",
    }

    resp = client.post("/analyze-image", json=payload)
    assert resp.status_code == 200
    res = resp.json()

    assert res["project_id"] == "test-uuid-5678"
    assert res["source_type"] == "USER_UPLOADED"
    assert res["inspection_status"] == "requires_human_review"


def test_api_timeline_endpoint(client):
    payload = {
        "project_id": "proj-api-test",
        "captures": [
            {
                "capture_date": "2023-01-10",
                "defect_class": "no_visible_defect",
                "severity": "none",
                "source_type": "DEMO_SYNTHETIC",
            },
            {
                "capture_date": "2023-07-10",
                "defect_class": "crack",
                "severity": "medium",
                "source_type": "DEMO_SYNTHETIC",
            },
        ],
    }

    resp = client.post("/timeline", json=payload)
    assert resp.status_code == 200
    res = resp.json()

    assert res["project_id"] == "proj-api-test"
    assert 0.0 <= res["degradation_score"] <= 1.0
    assert "Defect severity increased from none to medium" in res["progression_summary"]
    assert res["total_captures"] == 2
    assert "CRITICAL NOTICE" in res["disclaimer"]
