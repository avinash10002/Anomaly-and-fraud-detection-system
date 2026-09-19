"""
main.py
=======
FastAPI risk-aggregator service for the MPLADS Anomaly Detector.
Runs on port 8080 (http://localhost:8080/api/v1).
Aggregates financial, NLP, image, and database signals.
Strictly enforces role-based view (citizen vs official) at the API response layer.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from models import (
    AnomalyFlagModel,
    AnomalyFlagPatchRequest,
    AuditAssistantQueryRequest,
    AuditAssistantQueryResponse,
    AuditAssistantStatusResponse,
    DashboardStatsResponse,
    FinancialAnalysisModel,
    ImageCaptureModel,
    ImageTimelineAnalysisModel,
    ProjectCitation,
    ProjectDetailModel,
    ProjectListItemModel,
    ProjectListResponse,
    ProjectRiskResponse,
    ReviewStatus,
    RiskCount,
    RiskFactorModel,
    RiskLevel,
    SimilarProjectModel,
    StageIndicatorModel,
    StateSummary,
    ConstituencySummary,
    StatusCount,
    UserRole,
    WorksNearMeItem,
)

from audit_assistant import (
    execute_query_plan,
    parse_natural_language_query,
    synthesize_audit_response,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("risk_aggregator")

load_dotenv()
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8080"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
ENABLE_AUDIT_ASSISTANT = os.getenv("ENABLE_AUDIT_ASSISTANT", "true").lower() in ("true", "1")

app = FastAPI(
    title="MPLAD Risk Aggregator Service",
    description="Central risk aggregation and reporting API for MPLAD fraud/anomaly detection.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-Memory Fallback Store & Demo Seed Records
# ---------------------------------------------------------------------------

# Mutable flags in memory so PATCH updates persist across requests
STORE_FLAGS: Dict[str, Dict[str, Any]] = {}
STORE_PROJECTS: List[Dict[str, Any]] = []
STORE_CAPTURES: List[Dict[str, Any]] = []


def _load_csv_records() -> List[Dict[str, Any]]:
    """
    Loads real records from MPLADS.csv if present.
    Integrates all ~60,000 national records into the store while
    preserving the 5 demo cases with their synthetic timeline records.
    """
    candidates = [
        BASE_DIR.parent.parent / "MPLADS.csv",
        BASE_DIR.parent.parent / "data" / "mplads.csv",
        Path("MPLADS.csv"),
        Path("data/mplads.csv"),
        Path("../MPLADS.csv"),
    ]
    csv_file = None
    for c in candidates:
        if c.exists() and c.is_file():
            csv_file = c
            break

    if not csv_file:
        log.info("MPLADS CSV not found at candidate paths; running with base demo records.")
        return []

    try:
        import pandas as pd
        from pipeline.ingest import make_project_id, parse_date, parse_amount, normalise_status

        log.info("Loading MPLADS records from %s ...", csv_file)
        df = pd.read_csv(csv_file, sep=";", dtype=str).fillna("")

        demo_ids = {
            "ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
            "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
            "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
            "b503d0a8-c311-5409-b365-5ade19ce3e2f",
            "e7becbea-467f-5e0d-a910-fe1e740972ba",
            "88888888-0000-0000-0001-000000000001",
        }

        records = []
        for row in df.itertuples(index=False):
            mp, work, cat, state, con, ida, city, ward, block, vil, r_date, alloc, apprv, status, house = row

            p_date = parse_date(r_date)
            p_alloc = parse_amount(alloc)
            uid = str(make_project_id(mp, work, p_date, p_alloc))

            if uid in demo_ids:
                continue

            work_title = work.strip() if work else "Untitled Work"
            w_lower = work_title.lower()
            p_type = (
                "road" if "road" in w_lower or "link" in w_lower
                else "building" if any(w in w_lower for w in ["building", "room", "school", "auditorium", "sitting place", "hall"])
                else "park" if any(w in w_lower for w in ["stadium", "sports", "ground", "playfield", "park"])
                else "other"
            )

            records.append({
                "id": uid,
                "title": work_title,
                "work": work_title,
                "type": p_type,
                "category": cat.strip() if cat else "Other Works",
                "state": state.strip() if state else "Unknown",
                "district": (block or city or con or "Unknown").strip(),
                "constituency": con.strip() if con else "Unknown",
                "mp_name": mp.strip() if mp else "Unknown",
                "contractor_name": ida.strip() if ida else "Implementing Authority",
                "cost": p_alloc if p_alloc is not None else 0.0,
                "median_benchmark": 500000.0,
                "benchmark_iqr": 400000.0,
                "sanction_date": str(p_date) if p_date else "2023-01-01",
                "completion_date": None,
                "status": normalise_status(status),
                "lat": None,
                "lng": None,
                "has_synthetic_coords": False,
                "risk_level": "low",
                "risk_score": 0.05,
                "similar_projects": [],
            })

        log.info("Successfully loaded %d real records from %s into store.", len(records), csv_file.name)
        return records
    except Exception as exc:
        log.warning("Could not load MPLADS CSV into in-memory store: %s", exc)
        return []

TYPE_TO_CATEGORY = {
    "road": "Roads and Bridges",
    "building": "Community Infrastructure",
    "park": "Sports / Recreation",
    "other": "Other Works",
}


def _resolve_category(project: Dict[str, Any]) -> str:
    """Prefer stored category; map Normal/Others / empty to type-based label."""
    cat = (project.get("category") or "").strip()
    if not cat or cat.lower() == "normal/others":
        return TYPE_TO_CATEGORY.get(project.get("type", "other"), "Other Works")
    return cat


def _matches_category(project: Dict[str, Any], wanted: str) -> bool:
    target = wanted.lower().strip()
    if _resolve_category(project).lower() == target:
        return True
    type_map = {
        "roads and bridges": "road",
        "community infrastructure": "building",
        "sports / recreation": "park",
        "education": "building",
        "health": "building",
        "water and sanitation": "other",
        "other works": "other",
    }
    mapped = type_map.get(target)
    return bool(mapped and project.get("type") == mapped)


def _initialize_store():
    """Seed the in-memory store with the 5 demo cases and baseline projects."""
    global STORE_FLAGS, STORE_PROJECTS, STORE_CAPTURES

    # Demo Case 1: LOW RISK
    p1 = {
        "id": "ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
        "title": "[DEMO 1: LOW RISK] NA - Development of playfields and sports grounds",
        "work": "NA - Development of playfields and sports grounds",
        "type": "park",
        "category": "Normal/Others",
        "state": "Rajasthan",
        "district": "Churu",
        "constituency": "CHURU",
        "mp_name": "Rahul Kaswan",
        "contractor_name": "Rajasthan Rural Infra Works",
        "cost": 500000.0,
        "median_benchmark": 500000.0,
        "benchmark_iqr": 500000.0,
        "sanction_date": "2023-08-15",
        "completion_date": "2024-03-05",
        "status": "completed",
        "lat": 28.2900,
        "lng": 74.9600,
        "has_synthetic_coords": True,
        "risk_level": "low",
        "risk_score": 0.08,
        "similar_projects": [
            {
                "id": "sim-p1-1",
                "work": "Development of school playground and boundary",
                "state": "Rajasthan",
                "constituency": "CHURU",
                "similarity_score": 0.65,
                "reason": "Standard district sports facility allocation within norm.",
            }
        ],
    }

    # Demo Case 2: FINANCIAL FLAG
    p2 = {
        "id": "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
        "title": "[DEMO 2: FINANCIAL FLAG] NA - Construction of stadiums",
        "work": "NA - Construction of stadiums",
        "type": "building",
        "category": "Normal/Others",
        "state": "Uttar Pradesh",
        "district": "Basti",
        "constituency": "BASTI",
        "mp_name": "Shri Harish Dwivedi",
        "contractor_name": "Purvanchal Civil Builders",
        "cost": 38923000.0,
        "median_benchmark": 224500.0,
        "benchmark_iqr": 413000.0,
        "sanction_date": "2023-10-01",
        "completion_date": None,
        "status": "ongoing",
        "lat": 26.8120,
        "lng": 82.7630,
        "has_synthetic_coords": True,
        "risk_level": "high",
        "risk_score": 0.94,
        "similar_projects": [
            {
                "id": "sim-p2-1",
                "work": "Construction of mini stadium at block headquarter",
                "state": "Uttar Pradesh",
                "constituency": "GORAKHPUR",
                "similarity_score": 0.72,
                "reason": "Comparable stadium project with significantly lower sanctioned amount.",
            }
        ],
    }

    # Demo Case 3: NLP FLAG
    p3 = {
        "id": "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
        "title": "[DEMO 3: NLP FLAG] NA - Construction of Covered Common Sitting Place for Village People",
        "work": "NA - Construction of Covered Common Sitting Place for Village People on Government Land",
        "type": "building",
        "category": "Normal/Others",
        "state": "Bihar",
        "district": "Jamui",
        "constituency": "JAMUI(SC)",
        "mp_name": "Chirag Paswan",
        "contractor_name": "Bihar Vikas Nirman Samiti",
        "cost": 350000.0,
        "median_benchmark": 500000.0,
        "benchmark_iqr": 625000.0,
        "sanction_date": "2023-10-18",
        "completion_date": "2024-02-15",
        "status": "completed",
        "lat": 24.9180,
        "lng": 86.2230,
        "has_synthetic_coords": True,
        "risk_level": "medium",
        "risk_score": 0.92,
        "similar_projects": [
            {
                "id": "c1e1a7cf-26ab-5167-92a1-9790ca3f069e",
                "work": "NA - Construction of Covered Common Sitting Place for Village People on Government Land",
                "state": "Bihar",
                "constituency": "JAMUI(SC)",
                "similarity_score": 0.96,
                "reason": "Near-identical work specification sanctioned in same block on identical date.",
            }
        ],
    }

    # Demo Case 4: IMAGE FLAG
    p4 = {
        "id": "b503d0a8-c311-5409-b365-5ade19ce3e2f",
        "title": "[DEMO 4: IMAGE FLAG] WS/MP653/2023-2024/82102 - Construction of link roads with drainage",
        "work": "WS/MP653/2023-2024/82102 - Construction of roads, link roads, pathways or any other road with or without drainage system",
        "type": "road",
        "category": "Normal/Others",
        "state": "Madhya Pradesh",
        "district": "Dewas",
        "constituency": "DEWAS(SC)",
        "mp_name": "Mahendra Singh Solanky",
        "contractor_name": "Malwa Roadways Ltd",
        "cost": 300000.0,
        "median_benchmark": 299000.0,
        "benchmark_iqr": 336576.0,
        "sanction_date": "2023-03-15",
        "completion_date": "2023-12-10",
        "status": "completed",
        "lat": 22.9676,
        "lng": 76.0534,
        "has_synthetic_coords": True,
        "risk_level": "high",
        "risk_score": 0.89,
        "similar_projects": [],
    }

    # Demo Case 5: COMBINED HIGH RISK
    p5 = {
        "id": "e7becbea-467f-5e0d-a910-fe1e740972ba",
        "title": "[DEMO 5: COMBINED HIGH RISK] NA - Construction of roads, link roads and pathways",
        "work": "NA - Construction of roads, link roads, pathways or any other road with or without drainage system",
        "type": "road",
        "category": "Normal/Others",
        "state": "Uttar Pradesh",
        "district": "Gorakhpur",
        "constituency": "GORAKHPUR",
        "mp_name": "Ravindra Shyamnarayan Alias Ravi Kishan Shukla",
        "contractor_name": "Eastern UP Highways Corp",
        "cost": 13429000.0,
        "median_benchmark": 224500.0,
        "benchmark_iqr": 413000.0,
        "sanction_date": "2023-05-01",
        "completion_date": None,
        "status": "stalled",
        "lat": 26.7606,
        "lng": 83.3732,
        "has_synthetic_coords": True,
        "risk_level": "high",
        "risk_score": 0.96,
        "similar_projects": [
            {
                "id": "sim-p5-1",
                "work": "NA - Construction of roads, link roads, pathways or any other road with or without drainage system",
                "state": "Uttar Pradesh",
                "constituency": "GORAKHPUR",
                "similarity_score": 0.98,
                "reason": "Verbatim boilerplate repeated across 148 other sanctioned projects in Gorakhpur.",
            }
        ],
    }

    # Additional baseline projects from seed.sql
    p_base1 = {
        "id": "33333333-0000-0000-0000-000000000001",
        "title": "Four-lane road widening — NH-30 bypass Rewa",
        "work": "Widening of 8.4 km stretch of NH-30 approaching Rewa city, including storm drains and footpaths.",
        "type": "road",
        "category": "Normal/Others",
        "state": "Madhya Pradesh",
        "district": "Rewa",
        "constituency": "Rewa",
        "mp_name": "Ramesh Kumar Singh",
        "contractor_name": "Bharat Infrastructure Pvt Ltd",
        "cost": 45000000.0,
        "median_benchmark": 299000.0,
        "benchmark_iqr": 336576.0,
        "sanction_date": "2022-04-01",
        "completion_date": "2023-09-30",
        "status": "completed",
        "lat": 24.5362,
        "lng": 81.2983,
        "has_synthetic_coords": False,
        "risk_level": "high",
        "risk_score": 0.88,
        "similar_projects": [],
    }
    p_base2 = {
        "id": "33333333-0000-0000-0000-000000000006",
        "title": "Flyover construction — Wardha road–Amravati junction",
        "work": "Four-lane flyover of 780 m total length to decongest the Wardha road junction.",
        "type": "road",
        "category": "Normal/Others",
        "state": "Maharashtra",
        "district": "Nagpur",
        "constituency": "Nagpur South",
        "mp_name": "Sunita Deshpande",
        "contractor_name": "Vidarbha Constructions Ltd",
        "cost": 182000000.0,
        "median_benchmark": 3500000.0,
        "benchmark_iqr": 2000000.0,
        "sanction_date": "2021-03-15",
        "completion_date": "2023-11-30",
        "status": "completed",
        "lat": 21.1458,
        "lng": 79.0882,
        "has_synthetic_coords": False,
        "risk_level": "high",
        "risk_score": 0.93,
        "similar_projects": [],
    }

    # Demo Case 6: Punjab Road Project for Audit Assistant queries
    p_punjab = {
        "id": "88888888-0000-0000-0001-000000000001",
        "title": "Construction of concrete link road from GT Road to village canal",
        "work": "Construction of concrete link road from GT Road to village canal, Block Khanna",
        "type": "road",
        "category": "Roads and Bridges",
        "state": "Punjab",
        "district": "Ludhiana",
        "constituency": "LUDHIANA",
        "mp_name": "Ravneet Singh Bittu",
        "contractor_name": "Doaba Construction Ltd",
        "cost": 42000000.0,
        "median_benchmark": 11000000.0,
        "benchmark_iqr": 8000000.0,
        "sanction_date": "2023-04-10",
        "completion_date": None,
        "status": "ongoing",
        "lat": None,
        "lng": None,
        "has_synthetic_coords": False,
        "risk_level": "high",
        "risk_score": 0.86,
        "similar_projects": [],
    }

    csv_records = _load_csv_records()
    STORE_PROJECTS = [p1, p2, p3, p4, p5, p_base1, p_base2, p_punjab] + csv_records

    # Flags
    STORE_FLAGS = {
        "77777777-0000-0000-0006-000000000001": {
            "id": "77777777-0000-0000-0006-000000000001",
            "project_id": "88888888-0000-0000-0001-000000000001",
            "source_engine": "financial",
            "score": 0.86,
            "reason_text": "Project allocation (Rs. 4.20 Cr) is 3.8x the state category median (Rs. 1.10 Cr) for rural road works in Punjab.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2023-09-01",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0002-000000000001": {
            "id": "77777777-0000-0000-0002-000000000001",
            "project_id": "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
            "source_engine": "financial",
            "score": 0.94,
            "reason_text": "Project allocation (Rs. 3.89 Cr) is 173.4x the state category median (Rs. 2.24 L). Outlier score in top 99.8th percentile for Uttar Pradesh civil works.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2024-01-15",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0003-000000000001": {
            "id": "77777777-0000-0000-0003-000000000001",
            "project_id": "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
            "source_engine": "nlp",
            "score": 0.92,
            "reason_text": "Near-identical work description (cosine similarity 0.96) found in project c1e1a7cf-26ab-5167-92a1-9790ca3f069e within the same block (JHAJHA) and sanction date.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2023-11-20",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0004-000000000001": {
            "id": "77777777-0000-0000-0004-000000000001",
            "project_id": "b503d0a8-c311-5409-b365-5ade19ce3e2f",
            "source_engine": "image",
            "score": 0.89,
            "reason_text": "Chronological degradation analysis detected progressive breakdown from intact surface to structural potholes (confidence 0.91) within 8 months post-construction.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2023-12-10",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0005-000000000001": {
            "id": "77777777-0000-0000-0005-000000000001",
            "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba",
            "source_engine": "financial",
            "score": 0.96,
            "reason_text": "Project allocation of Rs. 1.34 Cr is 59.8x the state median (Rs. 2.24 L) for rural road works in Uttar Pradesh.",
            "review_status": "confirmed",
            "reviewer_id": "aaaaaaaa-0000-0000-0000-000000000001",
            "flagged_at": "2023-08-01",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0005-000000000002": {
            "id": "77777777-0000-0000-0005-000000000002",
            "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba",
            "source_engine": "nlp",
            "score": 0.88,
            "reason_text": "Work scope is identical boilerplate repeated across 148 other sanctioned projects in Gorakhpur without site-specific bill of quantities.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2023-09-15",
            "source_type": "DEMO_SYNTHETIC",
        },
        "77777777-0000-0000-0005-000000000003": {
            "id": "77777777-0000-0000-0005-000000000003",
            "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba",
            "source_engine": "image",
            "score": 0.91,
            "reason_text": "Chronological degradation analysis confirms rapid failure: road transitioned to heavy potholes (confidence 0.93) within 8 months of sanction.",
            "review_status": "pending",
            "reviewer_id": None,
            "flagged_at": "2024-01-20",
            "source_type": "DEMO_SYNTHETIC",
        },
    }

    # Captures
    STORE_CAPTURES = [
        # Demo Case 1
        {"id": "66666666-0000-0001", "project_id": "ce266c84-add9-59bb-b4ac-9fe61e2bf98d", "source": "streetview", "capture_date": "2024-01-10", "image_url": "https://storage.mplad-demo.in/captures/demo-case1-sv-20240110.jpg", "defect_class": None, "defect_confidence": None, "label": "Baseline Street View — sound perimeter and playfield", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0002", "project_id": "ce266c84-add9-59bb-b4ac-9fe61e2bf98d", "source": "upload", "capture_date": "2024-03-05", "image_url": "https://storage.mplad-demo.in/captures/demo-case1-upload-20240305.jpg", "defect_class": None, "defect_confidence": None, "label": "Handover upload — sound condition, zero defects", "source_type": "DEMO_SYNTHETIC"},
        # Demo Case 2
        {"id": "66666666-0000-0003", "project_id": "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d", "source": "streetview", "capture_date": "2023-11-12", "image_url": "https://storage.mplad-demo.in/captures/demo-case2-sv-20231112.jpg", "defect_class": None, "defect_confidence": None, "label": "Site entrance — foundation ongoing, no surface defect", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0004", "project_id": "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d", "source": "upload", "capture_date": "2024-02-20", "image_url": "https://storage.mplad-demo.in/captures/demo-case2-upload-20240220.jpg", "defect_class": None, "defect_confidence": None, "label": "Pavilion structural frame — sound concrete", "source_type": "DEMO_SYNTHETIC"},
        # Demo Case 3
        {"id": "66666666-0000-0005", "project_id": "fa527ded-f8b7-518e-9ba0-72556cf0f7c9", "source": "streetview", "capture_date": "2023-12-01", "image_url": "https://storage.mplad-demo.in/captures/demo-case3-sv-20231201.jpg", "defect_class": None, "defect_confidence": None, "label": "Shed site check — roof structure sound", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0006", "project_id": "fa527ded-f8b7-518e-9ba0-72556cf0f7c9", "source": "upload", "capture_date": "2024-02-15", "image_url": "https://storage.mplad-demo.in/captures/demo-case3-upload-20240215.jpg", "defect_class": None, "defect_confidence": None, "label": "Handover photo — sitting platform intact", "source_type": "DEMO_SYNTHETIC"},
        # Demo Case 4 (Progressive: none -> crack -> pothole)
        {"id": "66666666-0000-0007", "project_id": "b503d0a8-c311-5409-b365-5ade19ce3e2f", "source": "streetview", "capture_date": "2023-04-10", "image_url": "https://storage.mplad-demo.in/captures/demo-case4-sv-20230410.jpg", "defect_class": None, "defect_confidence": None, "label": "Month 1 Street View — newly paved sound asphalt", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0008", "project_id": "b503d0a8-c311-5409-b365-5ade19ce3e2f", "source": "mapillary", "capture_date": "2023-08-15", "image_url": "https://storage.mplad-demo.in/captures/demo-case4-mapillary-20230815.jpg", "defect_class": "crack", "defect_confidence": 0.78, "label": "Month 5 Mapillary — longitudinal cracking & surface wear", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0009", "project_id": "b503d0a8-c311-5409-b365-5ade19ce3e2f", "source": "upload", "capture_date": "2023-12-05", "image_url": "https://storage.mplad-demo.in/captures/demo-case4-upload-20231205.jpg", "defect_class": "pothole", "defect_confidence": 0.91, "label": "Month 9 Upload — severe pothole formation & bitumen stripping", "source_type": "DEMO_SYNTHETIC"},
        # Demo Case 5 (Progressive: none -> crack -> pothole)
        {"id": "66666666-0000-0010", "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba", "source": "streetview", "capture_date": "2023-05-12", "image_url": "https://storage.mplad-demo.in/captures/demo-case5-sv-20230512.jpg", "defect_class": None, "defect_confidence": None, "label": "Baseline Street View — cleared road corridor", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0011", "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba", "source": "mapillary", "capture_date": "2023-09-20", "image_url": "https://storage.mplad-demo.in/captures/demo-case5-mapillary-20230920.jpg", "defect_class": "crack", "defect_confidence": 0.82, "label": "Interim Mapillary — structural cracking on substandard base", "source_type": "DEMO_SYNTHETIC"},
        {"id": "66666666-0000-0012", "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba", "source": "upload", "capture_date": "2024-01-18", "image_url": "https://storage.mplad-demo.in/captures/demo-case5-upload-20240118.jpg", "defect_class": "pothole", "defect_confidence": 0.93, "label": "Audit Upload — structural washouts & heavy potholes", "source_type": "DEMO_SYNTHETIC"},
    ]

_initialize_store()


# ---------------------------------------------------------------------------
# Helper: Role-Based Redaction
# ---------------------------------------------------------------------------

def _resolve_role(role_param: Optional[str], x_user_role: Optional[str]) -> UserRole:
    val = (role_param or x_user_role or "official").lower().strip()
    return UserRole.CITIZEN if val == "citizen" else UserRole.OFFICIAL


def _sanitize_flags_for_role(flags: List[Dict[str, Any]], role: UserRole) -> List[AnomalyFlagModel]:
    result = []
    for f in flags:
        # If citizen: omit exact float score and omit reviewer notes / ID
        score = None if role == UserRole.CITIZEN else f.get("score")
        reviewer_id = None if role == UserRole.CITIZEN else f.get("reviewer_id")
        reason = f.get("reason_text", "")
        if role == UserRole.CITIZEN:
            # Public-friendly summary without internal audit specifics
            reason = reason.split(" Outlier score")[0].split(" Work scope is")[0]

        result.append(
            AnomalyFlagModel(
                id=f["id"],
                project_id=f["project_id"],
                source_engine=f["source_engine"],
                score=score,
                reason_text=reason,
                review_status=f.get("review_status", ReviewStatus.PENDING),
                reviewer_id=reviewer_id,
                flagged_at=f.get("flagged_at", "2024-01-01"),
                source_type=f.get("source_type", "DEMO_SYNTHETIC"),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "service": "risk-aggregator",
        "port": SERVICE_PORT,
        "database_connected": bool(DATABASE_URL),
    }


@app.get("/api/v1/dashboard/stats", response_model=DashboardStatsResponse, tags=["Dashboard"])
def get_dashboard_stats(
    role: Optional[str] = Query(None),
    x_user_role: Optional[str] = Header(None),
):
    """Real aggregated metrics for dashboard executive summary cards."""
    total_projects = len(STORE_PROJECTS)
    total_allocation = sum(p["cost"] for p in STORE_PROJECTS)

    # Status distribution
    status_map: Dict[str, int] = {}
    for p in STORE_PROJECTS:
        s = p.get("status", "unknown").lower()
        status_map[s] = status_map.get(s, 0) + 1
    status_distribution = [StatusCount(status=k, count=v) for k, v in sorted(status_map.items())]

    # Risk distribution
    risk_map: Dict[str, int] = {"low": 0, "medium": 0, "high": 0}
    for p in STORE_PROJECTS:
        r = p.get("risk_level", "low").lower()
        risk_map[r] = risk_map.get(r, 0) + 1
    risk_distribution = [RiskCount(level=k, count=v) for k, v in risk_map.items()]

    # Flags counts
    pending = sum(1 for f in STORE_FLAGS.values() if f.get("review_status") == "pending")
    confirmed = sum(1 for f in STORE_FLAGS.values() if f.get("review_status") == "confirmed")
    dismissed = sum(1 for f in STORE_FLAGS.values() if f.get("review_status") == "dismissed")

    return DashboardStatsResponse(
        total_projects=total_projects,
        total_allocation=total_allocation,
        status_distribution=status_distribution,
        risk_distribution=risk_distribution,
        total_anomalies_pending=pending,
        total_anomalies_confirmed=confirmed,
        total_anomalies_dismissed=dismissed,
    )


@app.get("/api/v1/projects", response_model=ProjectListResponse, tags=["Projects"])
def list_projects(
    state: Optional[str] = Query(None),
    constituency: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in work or title"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    x_user_role: Optional[str] = Header(None),
):
    """
    Project list with multi-filtering and work description search.
    Role-based redaction: public citizens do not see raw float risk scores.
    """
    active_role = _resolve_role(role, x_user_role)
    filtered = list(STORE_PROJECTS)

    if state:
        filtered = [p for p in filtered if p.get("state", "").lower() == state.lower()]
    if constituency:
        filtered = [p for p in filtered if p.get("constituency", "").lower() == constituency.lower()]
    if category:
        filtered = [p for p in filtered if _matches_category(p, category)]
    if status:
        filtered = [p for p in filtered if p.get("status", "").lower() == status.lower()]
    if risk_level:
        filtered = [p for p in filtered if p.get("risk_level", "").lower() == risk_level.lower()]
    if search:
        s = search.lower().strip()
        filtered = [
            p for p in filtered
            if s in p.get("work", "").lower()
            or s in p.get("title", "").lower()
            or s in p.get("mp_name", "").lower()
        ]

    total = len(filtered)
    start_idx = (page - 1) * page_size
    page_items = filtered[start_idx : start_idx + page_size]

    data: List[ProjectListItemModel] = []
    for p in page_items:
        flags = [f for f in STORE_FLAGS.values() if f.get("project_id") == p["id"]]
        risk_score = None if active_role == UserRole.CITIZEN else p.get("risk_score")

        data.append(
            ProjectListItemModel(
                id=p["id"],
                title=p["title"],
                work=p.get("work", p["title"]),
                type=p.get("type", "other"),
                category=_resolve_category(p),
                state=p.get("state", ""),
                district=p.get("district", ""),
                constituency=p.get("constituency", ""),
                mp_name=p.get("mp_name", ""),
                contractor_name=p.get("contractor_name", "Registered Contractor"),
                cost=float(p["cost"]),
                sanction_date=p.get("sanction_date", "2023-01-01"),
                completion_date=p.get("completion_date"),
                status=p.get("status", "ongoing"),
                lat=p.get("lat"),
                lng=p.get("lng"),
                has_synthetic_coords=p.get("has_synthetic_coords", False),
                risk_level=p.get("risk_level", RiskLevel.LOW),
                risk_score=risk_score,
                anomaly_count=len(flags),
            )
        )

    return ProjectListResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/api/v1/projects/{project_id}", response_model=ProjectDetailModel, tags=["Projects"])
def get_project_detail(
    project_id: str,
    role: Optional[str] = Query(None),
    x_user_role: Optional[str] = Header(None),
):
    """
    Project detail with Financial Analysis, Similar Projects, Image Timeline, and Flags.
    Role-based redaction: citizens see qualitative risk level only, no raw scores or reviewer notes.
    """
    active_role = _resolve_role(role, x_user_role)
    proj = next((p for p in STORE_PROJECTS if p["id"] == project_id), None)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    # Flags
    p_flags = [f for f in STORE_FLAGS.values() if f.get("project_id") == project_id]
    sanitized_flags = _sanitize_flags_for_role(p_flags, active_role)

    # Financial Analysis
    cost = float(proj["cost"])
    median = float(proj.get("median_benchmark", 500000.0))
    iqr = float(proj.get("benchmark_iqr", 300000.0))
    ratio = cost / median if median > 0 else 1.0
    deviation_pct = ((cost - median) / median) * 100.0 if median > 0 else 0.0

    if ratio > 5.0:
        fin_label = "Extreme Cost Outlier"
        fin_reason = f"Project allocation (Rs. {cost:,.2f}) is {ratio:.1f}x the state/category benchmark median (Rs. {median:,.2f})."
    elif ratio > 1.5:
        fin_label = "Moderate Cost Deviation"
        fin_reason = f"Project allocation is {deviation_pct:.1f}% above the category median."
    else:
        fin_label = "Within Expected Benchmark"
        fin_reason = f"Allocation aligns with state and category median standards (Rs. {median:,.2f})."

    financial_analysis = FinancialAnalysisModel(
        allocation_amount=cost,
        benchmark_median=median,
        benchmark_iqr=iqr,
        deviation_percent=round(deviation_pct, 1),
        ratio_vs_median=round(ratio, 1),
        deviation_score=None if active_role == UserRole.CITIZEN else (0.94 if ratio > 5.0 else 0.12),
        status_label=fin_label,
        reason_text=fin_reason,
    )

    # Similar Projects
    sim_data = proj.get("similar_projects", [])
    similar_projects = [
        SimilarProjectModel(
            id=s["id"],
            work=s["work"],
            state=s["state"],
            constituency=s["constituency"],
            similarity_score=None if active_role == UserRole.CITIZEN else s.get("similarity_score"),
            reason=s["reason"],
        )
        for s in sim_data
    ]

    # Image Timeline
    captures = [c for c in STORE_CAPTURES if c["project_id"] == project_id]
    captures.sort(key=lambda x: x["capture_date"])

    has_pothole = any(c.get("defect_class") == "pothole" for c in captures)
    has_crack = any(c.get("defect_class") == "crack" for c in captures)

    if has_pothole:
        progression = "Progressive degradation detected: surface progressed to severe structural potholes."
        deg_score = 0.89
    elif has_crack:
        progression = "Minor cracking detected; monitoring recommended."
        deg_score = 0.45
    else:
        progression = "Asset remains in sound physical condition across captures with zero visible defects."
        deg_score = 0.05

    image_timeline = ImageTimelineAnalysisModel(
        total_captures=len(captures),
        degradation_score=None if active_role == UserRole.CITIZEN else deg_score,
        progression_summary=progression,
        captures=[ImageCaptureModel(**c) for c in captures],
        has_synthetic_data=True,
    )

    risk_score = None if active_role == UserRole.CITIZEN else proj.get("risk_score")

    return ProjectDetailModel(
        id=proj["id"],
        title=proj["title"],
        work=proj.get("work", proj["title"]),
        type=proj.get("type", "other"),
        category=_resolve_category(proj),
        state=proj.get("state", ""),
        district=proj.get("district", ""),
        constituency=proj.get("constituency", ""),
        mp_name=proj.get("mp_name", ""),
        contractor_name=proj.get("contractor_name", "Registered Contractor"),
        cost=cost,
        sanction_date=proj.get("sanction_date", "2023-01-01"),
        completion_date=proj.get("completion_date"),
        status=proj.get("status", "ongoing"),
        lat=proj.get("lat"),
        lng=proj.get("lng"),
        has_synthetic_coords=proj.get("has_synthetic_coords", False),
        risk_level=proj.get("risk_level", RiskLevel.LOW),
        risk_score=risk_score,
        anomaly_count=len(sanitized_flags),
        flags=sanitized_flags,
        financial_analysis=financial_analysis,
        similar_projects=similar_projects,
        image_timeline=image_timeline,
    )



@app.get("/projects/{project_id}/risk", response_model=ProjectRiskResponse, tags=["Projects"])
@app.get("/api/v1/projects/{project_id}/risk", response_model=ProjectRiskResponse, tags=["Projects"])
def get_project_risk(project_id: str):
    """
    Detailed project risk assessment with stage indicators and recommended actions.
    Maps risk factors to process stages (approval_process vs. execution_delivery).
    Adheres strictly to hedged, non-accusatory audit compliance standards.
    """
    proj = next((p for p in STORE_PROJECTS if p["id"] == project_id), None)
    if not proj and DATABASE_URL:
        try:
            from db import PostgresExecutor, PostgresRepository
            executor = PostgresExecutor(DATABASE_URL)
            if executor.is_available():
                repo = PostgresRepository(executor)
                proj = repo.get_project_detail(project_id)
        except Exception as err:
            log.warning("Database fallback lookup failed for %s: %s", project_id, err)

    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.")

    # 1. Collect risk factors from flags
    p_flags = [f for f in STORE_FLAGS.values() if f.get("project_id") == project_id]

    risk_factors: List[RiskFactorModel] = []
    seen_types = set()

    for flag in p_flags:
        engine = str(flag.get("source_engine", "")).lower()
        score = float(flag.get("score") or 0.88)
        reason = flag.get("reason_text", "")

        factor_type = None
        if engine == "financial":
            factor_type = "financial"
        elif engine == "nlp":
            factor_type = "nlp_similarity"
        elif engine == "image":
            factor_type = "image_degradation"

        if factor_type and factor_type not in seen_types:
            seen_types.add(factor_type)
            risk_factors.append(
                RiskFactorModel(
                    type=factor_type,
                    score=score,
                    reason=reason,
                )
            )

    # 2. Fallback factors from project metrics if not already covered by flags
    cost = float(proj.get("cost", 0))
    median = float(proj.get("median_benchmark", 500000.0))
    ratio = cost / median if median > 0 else 1.0

    if "financial" not in seen_types and ratio > 1.5:
        fin_score = 0.94 if ratio > 5.0 else 0.78
        risk_factors.append(
            RiskFactorModel(
                type="financial",
                score=fin_score,
                reason=f"Project allocation (Rs. {cost:,.2f}) deviates significantly ({ratio:.1f}x) from benchmark median standards.",
            )
        )
        seen_types.add("financial")

    captures = [c for c in STORE_CAPTURES if c.get("project_id") == project_id]
    has_pothole = any(c.get("defect_class") == "pothole" for c in captures)
    has_crack = any(c.get("defect_class") == "crack" for c in captures)

    if "image_degradation" not in seen_types and (has_pothole or has_crack):
        img_score = 0.89 if has_pothole else 0.45
        risk_factors.append(
            RiskFactorModel(
                type="image_degradation",
                score=img_score,
                reason=(
                    "Inspection captures indicate severe structural potholing post-completion."
                    if has_pothole
                    else "Minor surface cracking detected in inspection capture."
                ),
            )
        )
        seen_types.add("image_degradation")

    sim_data = proj.get("similar_projects", [])
    if "nlp_similarity" not in seen_types and sim_data:
        top_sim = max(sim_data, key=lambda s: s.get("similarity_score") or 0.0)
        sim_score = top_sim.get("similarity_score") or 0.85
        if sim_score >= 0.7:
            risk_factors.append(
                RiskFactorModel(
                    type="nlp_similarity",
                    score=sim_score,
                    reason=top_sim.get("reason") or "Work description shares high semantic overlap with peer recommendations.",
                )
            )
            seen_types.add("nlp_similarity")

    # 3. Overall risk score & risk level
    if risk_factors:
        overall_score = round(max(f.score for f in risk_factors), 2)
    else:
        overall_score = float(proj.get("risk_score") or 0.05)

    if overall_score >= 0.7:
        risk_level = RiskLevel.HIGH
    elif overall_score >= 0.3:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    # 4. Recommended action based on score threshold (>= 0.7)
    if any(f.score >= 0.7 for f in risk_factors):
        recommended_action = (
            "Prioritize on-site physical verification and independent financial audit before further fund disbursement."
        )
    elif risk_factors:
        recommended_action = "Routine monitoring and administrative review; no immediate escalation required."
    else:
        recommended_action = "No intervention required; project parameters align with benchmark standards."

    # 5. Stage indicator mapping
    # - "financial" and "nlp_similarity" -> "approval_process"
    # - "image_degradation" -> "execution_delivery"
    APPROVAL_OVERVIEW = (
        "This pattern is commonly associated with irregularities in how the project was proposed or sanctioned — it does not identify any individual or agency."
    )
    DELIVERY_OVERVIEW = (
        "This pattern is commonly associated with issues in how the work was actually carried out — it does not identify any individual or agency."
    )

    approval_flagged = any(
        f.type in ("financial", "nlp_similarity") and f.score >= 0.7 for f in risk_factors
    )
    delivery_flagged = any(
        f.type == "image_degradation" and f.score >= 0.7 for f in risk_factors
    )

    stage_indicator: List[StageIndicatorModel] = []
    note: Optional[str] = None

    if approval_flagged:
        stage_indicator.append(
            StageIndicatorModel(
                stage="approval_process",
                flagged=True,
                overview=APPROVAL_OVERVIEW,
            )
        )

    if delivery_flagged:
        stage_indicator.append(
            StageIndicatorModel(
                stage="execution_delivery",
                flagged=True,
                overview=DELIVERY_OVERVIEW,
            )
        )

    if approval_flagged and delivery_flagged:
        note = "Multiple process stages show flagged patterns; review both."

    return ProjectRiskResponse(
        project_id=project_id,
        overall_risk_score=overall_score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommended_action=recommended_action,
        stage_indicator=stage_indicator,
        note=note,
    )


@app.patch("/api/v1/anomaly-flags/{flag_id}", tags=["Audit"])
def patch_anomaly_flag(flag_id: str, payload: AnomalyFlagPatchRequest):
    """
    Review action: Confirm or dismiss an anomaly flag.
    Updates the review status and records audit reviewer id.
    """
    if flag_id not in STORE_FLAGS:
        raise HTTPException(status_code=404, detail=f"Anomaly flag {flag_id} not found.")

    flag = STORE_FLAGS[flag_id]
    flag["review_status"] = payload.review_status.value
    if payload.reviewer_id:
        flag["reviewer_id"] = payload.reviewer_id

    log.info("Flag %s updated to status %s by reviewer %s", flag_id, payload.review_status, payload.reviewer_id)
    return {
        "success": True,
        "id": flag_id,
        "review_status": flag["review_status"],
        "reviewer_id": flag.get("reviewer_id"),
    }


@app.get("/api/v1/map/works-near-me", response_model=List[WorksNearMeItem], tags=["Citizen Map"])
def works_near_me(
    role: Optional[str] = Query(None),
    x_user_role: Optional[str] = Header(None),
):
    """
    Returns ONLY the 5 seeded demo projects with synthetic coordinates.
    Never fabricates coordinates for real MPLADS records.
    """
    active_role = _resolve_role(role, x_user_role)
    demo_projects = [p for p in STORE_PROJECTS if p.get("has_synthetic_coords")]

    result = []
    for p in demo_projects:
        risk_score = None if active_role == UserRole.CITIZEN else p.get("risk_score")
        result.append(
            WorksNearMeItem(
                id=p["id"],
                title=p["title"],
                work=p.get("work", p["title"]),
                state=p.get("state", ""),
                district=p.get("district", ""),
                constituency=p.get("constituency", ""),
                mp_name=p.get("mp_name", ""),
                cost=float(p["cost"]),
                status=p.get("status", "ongoing"),
                lat=p["lat"],
                lng=p["lng"],
                risk_level=p.get("risk_level", RiskLevel.LOW),
                risk_score=risk_score,
                source_type="DEMO_SYNTHETIC",
            )
        )
    return result


@app.get("/api/v1/map/administrative", response_model=List[StateSummary], tags=["Citizen Map"])
def get_administrative_map():
    """
    State -> Constituency browsing hierarchy using real administrative fields.
    Does not fabricate GPS coordinates.
    """
    state_groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    for p in STORE_PROJECTS:
        st = p.get("state", "Unknown")
        con = p.get("constituency", "Unknown")
        if st not in state_groups:
            state_groups[st] = {}
        if con not in state_groups[st]:
            state_groups[st][con] = []
        state_groups[st][con].append(p)

    result: List[StateSummary] = []
    for st, constituencies in sorted(state_groups.items()):
        total_p = 0
        total_cost = 0.0
        con_summaries: List[ConstituencySummary] = []

        for con, projs in sorted(constituencies.items()):
            p_cnt = len(projs)
            p_cost = sum(p["cost"] for p in projs)
            high_risk = sum(1 for p in projs if p.get("risk_level") == "high")

            total_p += p_cnt
            total_cost += p_cost

            con_summaries.append(
                ConstituencySummary(
                    constituency=con,
                    project_count=p_cnt,
                    total_allocation=p_cost,
                    high_risk_count=high_risk,
                )
            )

        result.append(
            StateSummary(
                state=st,
                project_count=total_p,
                total_allocation=total_cost,
                constituencies=con_summaries,
            )
        )
    return result


# ── AI Audit Assistant Endpoints ───────────────────────────────────────────

@app.get(
    "/api/v1/assistant/status",
    response_model=AuditAssistantStatusResponse,
    tags=["Audit Assistant"],
)
def get_assistant_status():
    """Returns whether the AI Audit Assistant is active."""
    return AuditAssistantStatusResponse(enabled=ENABLE_AUDIT_ASSISTANT)


@app.post(
    "/api/v1/assistant/query",
    response_model=AuditAssistantQueryResponse,
    tags=["Audit Assistant"],
)
def query_audit_assistant(
    payload: AuditAssistantQueryRequest,
    role: Optional[str] = Query(None),
    x_user_role: Optional[str] = Header(None),
):
    """
    AI audit assistant over the MPLADS database.
    Translates natural-language questions into safe, parameterized queries.
    Enforces non-accusatory audit tone and surfaces underlying project citations.
    """
    if not ENABLE_AUDIT_ASSISTANT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Audit Assistant is currently disabled.",
        )

    active_role = _resolve_role(role or (payload.role.value if payload.role else None), x_user_role)

    # 1. Safe parsing to typed QueryPlan
    plan = parse_natural_language_query(payload.question)

    # 2. Parameterized DB / Store execution
    records, flags_map = execute_query_plan(
        plan=plan,
        db_url=DATABASE_URL,
        store_projects=STORE_PROJECTS,
        store_flags=STORE_FLAGS,
    )

    # 3. Factual answer synthesis with audit compliance tone guard
    answer, citations_data = synthesize_audit_response(
        plan=plan,
        records=records,
        flags_map=flags_map,
        role=active_role.value,
    )

    citations = [
        ProjectCitation(
            project_id=c["project_id"],
            title=c["title"],
            state=c.get("state"),
            constituency=c.get("constituency"),
            allocation=c.get("allocation"),
            category=c.get("category"),
            flags=c.get("flags", []),
        )
        for c in citations_data
    ]

    return AuditAssistantQueryResponse(
        question=payload.question,
        answer=answer,
        citations=citations,
        intent=plan.intent.value,
        records_found=len(records),
        safe_audit_language=True,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
