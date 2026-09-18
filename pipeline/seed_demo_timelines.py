#!/usr/bin/env python3
"""
pipeline/seed_demo_timelines.py
================================
Generates synthetic inspection timelines and anomaly flags for 5 specific demo
cases using real project IDs selected from the loaded MPLADS dataset.

Demo Cases:
  1. LOW RISK           - normal allocation, no image defects across 2 captures
  2. FINANCIAL FLAG     - allocation well above category+state median (173.4x), no image defects
  3. NLP FLAG           - near-duplicate work description in same state (Jamui, Bihar), no image defects
  4. IMAGE FLAG         - normal allocation, 3 progressive captures (none -> minor crack -> pothole)
  5. COMBINED HIGH RISK - 59.8x allocation + duplicate tender scope + 3 progressive defect captures

Critical Integrity Requirement:
  Every synthetic record carries `source_type = "DEMO_SYNTHETIC"`.

Usage:
  python pipeline/seed_demo_timelines.py
  python pipeline/seed_demo_timelines.py --db-url postgresql://mplad_user:mplad_secret@localhost:5432/mplad
  python pipeline/seed_demo_timelines.py --dry-run
  python pipeline/seed_demo_timelines.py --write-sql db/seeds/demo_synthetic_timelines.sql
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mplads.seed_demo")

SOURCE_TYPE_SYNTHETIC = "DEMO_SYNTHETIC"

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SyntheticCapture:
    id: str
    project_id: str
    capture_date: str
    source: str  # 'streetview' | 'mapillary' | 'upload'
    image_url: str
    defect_class: Optional[str]
    defect_confidence: Optional[float]
    label: str
    source_type: str = SOURCE_TYPE_SYNTHETIC

@dataclass
class SyntheticFlag:
    id: str
    project_id: str
    source_engine: str  # 'financial' | 'image' | 'nlp'
    score: float
    reason_text: str
    review_status: str = "pending"  # 'pending' | 'confirmed' | 'dismissed'
    reviewer_id: Optional[str] = None
    flagged_at: str = "2024-02-01"
    source_type: str = SOURCE_TYPE_SYNTHETIC

@dataclass
class DemoCase:
    case_num: int
    case_title: str
    risk_level: str  # 'low' | 'medium' | 'high'
    project_id: str
    mp_name: str
    constituency: str
    state: str
    district: str
    category: str
    work: str
    cost: float
    median_benchmark: float
    ratio: float
    status: str
    sanction_date: str
    completion_date: Optional[str]
    paired_project_id: Optional[str] = None
    captures: List[SyntheticCapture] = field(default_factory=list)
    flags: List[SyntheticFlag] = field(default_factory=list)
    narrative: str = ""


# ---------------------------------------------------------------------------
# Demo Cases Definitions (Selected Real MPLADS Projects)
# ---------------------------------------------------------------------------

DEMO_CASES: List[DemoCase] = [
    # ── CASE 1: LOW RISK ───────────────────────────────────────────────────
    DemoCase(
        case_num=1,
        case_title="LOW RISK",
        risk_level="low",
        project_id="ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
        mp_name="Rahul Kaswan",
        constituency="CHURU",
        state="Rajasthan",
        district="Churu",
        category="Normal/Others",
        work="NA - Development of playfields and sports grounds",
        cost=500000.0,
        median_benchmark=500000.0,
        ratio=1.0,
        status="completed",
        sanction_date="2023-08-15",
        completion_date="2024-03-05",
        narrative="Normal allocation matching category median exactly. Ground inspection across two captures confirmed sound infrastructure with no defects.",
        captures=[
            SyntheticCapture(
                id="66666666-0000-0000-0001-000000000001",
                project_id="ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
                capture_date="2024-01-10",
                source="streetview",
                image_url="https://storage.mplad-demo.in/captures/demo-case1-sv-20240110.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Baseline capture - sound sports ground perimeter and turf",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0001-000000000002",
                project_id="ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
                capture_date="2024-03-05",
                source="upload",
                image_url="https://storage.mplad-demo.in/captures/demo-case1-upload-20240305.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Post-completion handover inspection - no visible civil defects",
            ),
        ],
        flags=[],
    ),

    # ── CASE 2: FINANCIAL FLAG ─────────────────────────────────────────────
    DemoCase(
        case_num=2,
        case_title="FINANCIAL FLAG",
        risk_level="high",
        project_id="feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
        mp_name="Shri Harish Dwivedi",
        constituency="BASTI",
        state="Uttar Pradesh",
        district="Basti",
        category="Normal/Others",
        work="NA - Construction of stadiums",
        cost=38923000.0,
        median_benchmark=224500.0,
        ratio=173.4,
        status="ongoing",
        sanction_date="2023-10-01",
        completion_date=None,
        narrative="Severe financial outlier with allocation Rs. 3.89 Cr (173.4x the UP category median of Rs. 2.24 L). Physical imagery shows normal progress without defect flags.",
        captures=[
            SyntheticCapture(
                id="66666666-0000-0000-0002-000000000001",
                project_id="feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
                capture_date="2023-11-12",
                source="streetview",
                image_url="https://storage.mplad-demo.in/captures/demo-case2-sv-20231112.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Site entrance capture - foundation works ongoing, no surface defect",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0002-000000000002",
                project_id="feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
                capture_date="2024-02-20",
                source="upload",
                image_url="https://storage.mplad-demo.in/captures/demo-case2-upload-20240220.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Civil pavilion frame inspection - clean concrete structure",
            ),
        ],
        flags=[
            SyntheticFlag(
                id="77777777-0000-0000-0002-000000000001",
                project_id="feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
                source_engine="financial",
                score=0.94,
                reason_text="Project allocation (Rs. 3.89 Cr) is 173.4x the state category median (Rs. 2.24 L). Outlier score in top 99.8th percentile for Uttar Pradesh civil works.",
                review_status="pending",
                flagged_at="2024-01-15",
            ),
        ],
    ),

    # ── CASE 3: NLP FLAG ───────────────────────────────────────────────────
    DemoCase(
        case_num=3,
        case_title="NLP FLAG",
        risk_level="medium",
        project_id="fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
        paired_project_id="c1e1a7cf-26ab-5167-92a1-9790ca3f069e",
        mp_name="Chirag Paswan",
        constituency="JAMUI(SC)",
        state="Bihar",
        district="Jamui",
        category="Normal/Others",
        work="NA - Construction of Covered Common Sitting Place for Village People on Government Land",
        cost=350000.0,
        median_benchmark=500000.0,
        ratio=0.7,
        status="completed",
        sanction_date="2023-10-18",
        completion_date="2024-02-15",
        narrative="Near-duplicate tender/work scope in same block (Jhajha) matching c1e1a7cf-26ab-5167-92a1-9790ca3f069e. Flags potential repetitive billing/boilerplate duplicate sanctions.",
        captures=[
            SyntheticCapture(
                id="66666666-0000-0000-0003-000000000001",
                project_id="fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
                capture_date="2023-12-01",
                source="streetview",
                image_url="https://storage.mplad-demo.in/captures/demo-case3-sv-20231201.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Village sitting shed site verification - roof structure sound",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0003-000000000002",
                project_id="fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
                capture_date="2024-02-15",
                source="upload",
                image_url="https://storage.mplad-demo.in/captures/demo-case3-upload-20240215.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Handover photo - sitting platform intact, no physical defects",
            ),
        ],
        flags=[
            SyntheticFlag(
                id="77777777-0000-0000-0003-000000000001",
                project_id="fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
                source_engine="nlp",
                score=0.92,
                reason_text="Near-identical work description (cosine similarity 0.96) found in project c1e1a7cf-26ab-5167-92a1-9790ca3f069e within the same block (JHAJHA) and sanction date.",
                review_status="pending",
                flagged_at="2023-11-20",
            ),
        ],
    ),

    # ── CASE 4: IMAGE FLAG ─────────────────────────────────────────────────
    DemoCase(
        case_num=4,
        case_title="IMAGE FLAG",
        risk_level="high",
        project_id="b503d0a8-c311-5409-b365-5ade19ce3e2f",
        mp_name="Mahendra Singh Solanky",
        constituency="DEWAS(SC)",
        state="Madhya Pradesh",
        district="Dewas",
        category="Normal/Others",
        work="WS/MP653/2023-2024/82102 - Construction of roads, link roads, pathways or any other road with or without drainage system",
        cost=300000.0,
        median_benchmark=299000.0,
        ratio=1.0,
        status="completed",
        sanction_date="2023-03-15",
        completion_date="2023-12-10",
        narrative="Normal allocation road project displaying rapid progressive degradation across 3 captures over 8 months (sound -> minor crack -> pothole).",
        captures=[
            SyntheticCapture(
                id="66666666-0000-0000-0004-000000000001",
                project_id="b503d0a8-c311-5409-b365-5ade19ce3e2f",
                capture_date="2023-04-10",
                source="streetview",
                image_url="https://storage.mplad-demo.in/captures/demo-case4-sv-20230410.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Baseline capture (Month 1) - newly laid asphalt, sound road surface",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0004-000000000002",
                project_id="b503d0a8-c311-5409-b365-5ade19ce3e2f",
                capture_date="2023-08-15",
                source="mapillary",
                image_url="https://storage.mplad-demo.in/captures/demo-case4-mapillary-20230815.jpg",
                defect_class="crack",
                defect_confidence=0.78,
                label="Monsoon capture (Month 5) - longitudinal cracking & surface deterioration",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0004-000000000003",
                project_id="b503d0a8-c311-5409-b365-5ade19ce3e2f",
                capture_date="2023-12-05",
                source="upload",
                image_url="https://storage.mplad-demo.in/captures/demo-case4-upload-20231205.jpg",
                defect_class="pothole",
                defect_confidence=0.91,
                label="Audit inspection (Month 9) - severe pothole formation & bitumen stripping",
            ),
        ],
        flags=[
            SyntheticFlag(
                id="77777777-0000-0000-0004-000000000001",
                project_id="b503d0a8-c311-5409-b365-5ade19ce3e2f",
                source_engine="image",
                score=0.89,
                reason_text="Chronological degradation analysis detected progressive breakdown from intact surface to structural potholes (confidence 0.91) within 8 months post-construction.",
                review_status="pending",
                flagged_at="2023-12-10",
            ),
        ],
    ),

    # ── CASE 5: COMBINED HIGH RISK ─────────────────────────────────────────
    DemoCase(
        case_num=5,
        case_title="COMBINED HIGH RISK",
        risk_level="high",
        project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
        mp_name="Ravindra Shyamnarayan Alias Ravi Kishan Shukla",
        constituency="GORAKHPUR",
        state="Uttar Pradesh",
        district="Gorakhpur",
        category="Normal/Others",
        work="NA - Construction of roads, link roads, pathways or any other road with or without drainage system",
        cost=13429000.0,
        median_benchmark=224500.0,
        ratio=59.8,
        status="stalled",
        sanction_date="2023-05-01",
        completion_date=None,
        narrative="Extreme multi-engine anomaly: 59.8x cost outlier + repetitive tender scope across 148 works in Gorakhpur + 3-stage progressive road degradation.",
        captures=[
            SyntheticCapture(
                id="66666666-0000-0000-0005-000000000001",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                capture_date="2023-05-12",
                source="streetview",
                image_url="https://storage.mplad-demo.in/captures/demo-case5-sv-20230512.jpg",
                defect_class=None,
                defect_confidence=None,
                label="Baseline capture - cleared corridor before paving",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0005-000000000002",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                capture_date="2023-09-20",
                source="mapillary",
                image_url="https://storage.mplad-demo.in/captures/demo-case5-mapillary-20230920.jpg",
                defect_class="crack",
                defect_confidence=0.82,
                label="Interim capture - extensive longitudinal cracking on substandard sub-base",
            ),
            SyntheticCapture(
                id="66666666-0000-0000-0005-000000000003",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                capture_date="2024-01-18",
                source="upload",
                image_url="https://storage.mplad-demo.in/captures/demo-case5-upload-20240118.jpg",
                defect_class="pothole",
                defect_confidence=0.93,
                label="Site inspection upload - severe potholing, washouts & total structural failure",
            ),
        ],
        flags=[
            SyntheticFlag(
                id="77777777-0000-0000-0005-000000000001",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                source_engine="financial",
                score=0.96,
                reason_text="Project allocation of Rs. 1.34 Cr is 59.8x the state median (Rs. 2.24 L) for rural road works in Uttar Pradesh.",
                review_status="confirmed",
                reviewer_id="aaaaaaaa-0000-0000-0000-000000000001",
                flagged_at="2023-08-01",
            ),
            SyntheticFlag(
                id="77777777-0000-0000-0005-000000000002",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                source_engine="nlp",
                score=0.88,
                reason_text="Work scope is identical boilerplate repeated across 148 other sanctioned projects in Gorakhpur without site-specific bill of quantities.",
                review_status="pending",
                flagged_at="2023-09-15",
            ),
            SyntheticFlag(
                id="77777777-0000-0000-0005-000000000003",
                project_id="e7becbea-467f-5e0d-a910-fe1e740972ba",
                source_engine="image",
                score=0.91,
                reason_text="Chronological degradation analysis confirms rapid failure: road transitioned to heavy potholes (confidence 0.93) within 8 months of sanction.",
                review_status="pending",
                flagged_at="2024-01-20",
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# SQL Generation
# ---------------------------------------------------------------------------

def generate_sql() -> str:
    """Generate SQL statements to insert/upsert the synthetic demo data."""
    lines: List[str] = [
        "-- =============================================================================",
        "-- MPLAD Demo Synthetic Inspection Timelines & Anomaly Flags",
        "-- Generated automatically by pipeline/seed_demo_timelines.py",
        "-- Provenance: All records tagged with source_type = 'DEMO_SYNTHETIC'",
        "-- =============================================================================",
        "BEGIN;",
        "",
        "-- Ensure columns exist if migration 003 hasn't run yet",
        "DO $$",
        "BEGIN",
        "    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'image_capture' AND column_name = 'source_type') THEN",
        "        ALTER TABLE image_capture ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';",
        "    END IF;",
        "    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'anomaly_flag' AND column_name = 'source_type') THEN",
        "        ALTER TABLE anomaly_flag ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';",
        "    END IF;",
        "END $$;",
        "",
        "-- ---------------------------------------------------------------------------",
        "-- Synthetic Image Captures",
        "-- ---------------------------------------------------------------------------",
    ]

    for case in DEMO_CASES:
        lines.append(f"-- Demo Case {case.case_num}: {case.case_title} (Project {case.project_id})")
        for cap in case.captures:
            defect_class_sql = f"'{cap.defect_class}'" if cap.defect_class else "NULL"
            defect_conf_sql = f"{cap.defect_confidence:.3f}" if cap.defect_confidence is not None else "NULL"
            lines.append(
                f"INSERT INTO image_capture (id, project_id, source, capture_date, image_url, defect_class, defect_confidence, source_type) "
                f"VALUES ('{cap.id}', '{cap.project_id}', '{cap.source}', '{cap.capture_date}', '{cap.image_url}', {defect_class_sql}, {defect_conf_sql}, '{cap.source_type}') "
                f"ON CONFLICT (id) DO UPDATE SET "
                f"source = EXCLUDED.source, capture_date = EXCLUDED.capture_date, image_url = EXCLUDED.image_url, "
                f"defect_class = EXCLUDED.defect_class, defect_confidence = EXCLUDED.defect_confidence, source_type = EXCLUDED.source_type;"
            )
        lines.append("")

    lines.append("-- ---------------------------------------------------------------------------")
    lines.append("-- Synthetic Anomaly Flags")
    lines.append("-- ---------------------------------------------------------------------------")
    for case in DEMO_CASES:
        if not case.flags:
            continue
        lines.append(f"-- Demo Case {case.case_num}: {case.case_title} (Project {case.project_id})")
        for flg in case.flags:
            reviewer_sql = f"'{flg.reviewer_id}'" if flg.reviewer_id else "NULL"
            escaped_reason = flg.reason_text.replace("'", "''")
            lines.append(
                f"INSERT INTO anomaly_flag (id, project_id, source_engine, score, reason_text, review_status, reviewer_id, source_type) "
                f"VALUES ('{flg.id}', '{flg.project_id}', '{flg.source_engine}', {flg.score:.3f}, '{escaped_reason}', '{flg.review_status}', {reviewer_sql}, '{flg.source_type}') "
                f"ON CONFLICT (id) DO UPDATE SET "
                f"source_engine = EXCLUDED.source_engine, score = EXCLUDED.score, reason_text = EXCLUDED.reason_text, "
                f"review_status = EXCLUDED.review_status, reviewer_id = EXCLUDED.reviewer_id, source_type = EXCLUDED.source_type;"
            )
        lines.append("")

    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Database Ingestion
# ---------------------------------------------------------------------------

def seed_to_database(db_url: str) -> None:
    """Insert synthetic records directly into the PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        log.error("psycopg2 is required for database insertion. Run: pip install psycopg2-binary")
        return

    log.info("Connecting to PostgreSQL at %s ...", db_url.split("@")[-1])
    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        log.warning("Could not connect to database (%s). Writing SQL file instead.", exc)
        return

    with conn.cursor() as cur:
        # Check and add source_type columns if necessary
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'image_capture' AND column_name = 'source_type') THEN
                    ALTER TABLE image_capture ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'anomaly_flag' AND column_name = 'source_type') THEN
                    ALTER TABLE anomaly_flag ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';
                END IF;
            END $$;
        """)

        total_captures = 0
        total_flags = 0

        # Insert captures
        for case in DEMO_CASES:
            for cap in case.captures:
                cur.execute("""
                    INSERT INTO image_capture (
                        id, project_id, source, capture_date, image_url,
                        defect_class, defect_confidence, source_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        capture_date = EXCLUDED.capture_date,
                        image_url = EXCLUDED.image_url,
                        defect_class = EXCLUDED.defect_class,
                        defect_confidence = EXCLUDED.defect_confidence,
                        source_type = EXCLUDED.source_type
                """, (
                    cap.id, cap.project_id, cap.source, cap.capture_date, cap.image_url,
                    cap.defect_class, cap.defect_confidence, cap.source_type
                ))
                total_captures += 1

            for flg in case.flags:
                cur.execute("""
                    INSERT INTO anomaly_flag (
                        id, project_id, source_engine, score, reason_text,
                        review_status, reviewer_id, source_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        source_engine = EXCLUDED.source_engine,
                        score = EXCLUDED.score,
                        reason_text = EXCLUDED.reason_text,
                        review_status = EXCLUDED.review_status,
                        reviewer_id = EXCLUDED.reviewer_id,
                        source_type = EXCLUDED.source_type
                """, (
                    flg.id, flg.project_id, flg.source_engine, flg.score, flg.reason_text,
                    flg.review_status, flg.reviewer_id, flg.source_type
                ))
                total_flags += 1

        conn.commit()
        conn.close()

    log.info("✓ Inserted/Updated %d synthetic captures and %d anomaly flags into database.", total_captures, total_flags)


# ---------------------------------------------------------------------------
# Printed Manifest
# ---------------------------------------------------------------------------

def print_manifest() -> None:
    """Print a clean, clear terminal manifest for the demo team."""
    divider = "=" * 80
    subdivider = "-" * 80

    print("\n" + divider)
    print("  MPLADS FRAUD & ANOMALY DETECTOR - DEMO PROJECT MANIFEST")
    print("  5 Interactive Demo Cases (Tagged: source_type = 'DEMO_SYNTHETIC')")
    print(divider)

    for case in DEMO_CASES:
        print(f"\n[CASE {case.case_num}] {case.case_title}  (Risk Level: {case.risk_level.upper()})")
        print(subdivider)
        print(f"  * Project ID      : {case.project_id}")
        if case.paired_project_id:
            print(f"  * Paired Duplicate: {case.paired_project_id}")
        print(f"  * MP Name         : {case.mp_name}")
        print(f"  * State / Dist    : {case.state} ({case.constituency} constituency)")
        print(f"  * Work Scope      : {case.work}")
        print(f"  * Allocation      : Rs. {case.cost:,.2f}  (Category+State Median: Rs. {case.median_benchmark:,.2f} | Ratio: {case.ratio:.1f}x)")
        print(f"  * Status          : {case.status.upper()}")
        print(f"  * Summary         : {case.narrative}")

        print(f"  * Inspection Captures ({len(case.captures)} total, source_type='{SOURCE_TYPE_SYNTHETIC}'):")
        for i, cap in enumerate(case.captures, 1):
            defect_str = f"{cap.defect_class} (conf: {cap.defect_confidence})" if cap.defect_class else "sound / no defect"
            print(f"      {i}. [{cap.capture_date}] ({cap.source.upper()}): {defect_str} - {cap.label}")

        if case.flags:
            print(f"  * Anomaly Flags ({len(case.flags)} total, source_type='{SOURCE_TYPE_SYNTHETIC}'):")
            for flg in case.flags:
                print(f"      - [{flg.source_engine.upper()}] Score: {flg.score:.2f} ({flg.review_status}) - {flg.reason_text}")
        else:
            print(f"  * Anomaly Flags   : None (Sound project)")

    print("\n" + divider)
    print("  DEMO CLICK LIST (COPY-PASTE READY FOR BROWSER / API TESTING):")
    for case in DEMO_CASES:
        print(f"  Case {case.case_num} ({case.case_title:18s}): {case.project_id}")
    print(divider + "\n")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Seed synthetic inspection timelines for 5 real demo MPLADS projects."
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://mplad_user:mplad_secret@localhost:5432/mplad"),
        help="PostgreSQL connection string (defaults to DATABASE_URL or standard local dev)",
    )
    parser.add_argument(
        "--write-sql",
        type=Path,
        default=Path("db/seeds/demo_synthetic_timelines.sql"),
        help="Path to output SQL file (default: db/seeds/demo_synthetic_timelines.sql)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print manifest and SQL preview only; skip database writes",
    )
    args = parser.parse_args()

    # Always generate and write the SQL script so it can be committed and applied via psql / import_mplads.sh
    sql_content = generate_sql()
    if args.write_sql:
        args.write_sql.parent.mkdir(parents=True, exist_ok=True)
        args.write_sql.write_text(sql_content, encoding="utf-8")
        log.info("Wrote SQL seed script to %s", args.write_sql)

    # Insert into database if not dry-run and db-url is provided
    if not args.dry_run and args.db_url:
        seed_to_database(args.db_url)

    # Print the manifest for the team
    print_manifest()


if __name__ == "__main__":
    main()
