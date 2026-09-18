"""
main.py
=======
FastAPI application for the MPLAD Financial Engine.

Startup sequence
----------------
1. Load benchmarks from mplads_project table in PostgreSQL.
2. Fit per-category Isolation Forest models (all in-process).
3. Begin serving requests.

Endpoints
---------
  GET  /health   → {"status": "ok", "benchmarks": {...}}
  GET  /benchmarks/{category}/{state}  → raw GroupStats for debugging
  POST /analyze  → AnalyzeResponse

Environment variables
---------------------
  DATABASE_URL               PostgreSQL connection string (required for real data)
  COST_ESTIMATOR_URL         http://cost-estimator:8084 (optional, enables CE calls)
  BENCHMARK_MIN_ROWS         Override MIN_GROUP_SIZE_STATE (default 5)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

import httpx
import psycopg2
import psycopg2.extras
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import analyzer as anlz
from benchmarks import get_store
from models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CostEstimatorRange,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("financial_engine.main")

load_dotenv()

DB_URL             = os.getenv("DATABASE_URL", "")
COST_ESTIMATOR_URL = os.getenv("COST_ESTIMATOR_URL", "http://cost-estimator:8084")
CE_TIMEOUT         = float(os.getenv("COST_ESTIMATOR_TIMEOUT_S", "5"))

DISCLAIMER = anlz.DISCLAIMER


# ---------------------------------------------------------------------------
# Lifespan — load benchmarks at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_store()
    if DB_URL:
        try:
            store.load_from_db(DB_URL)
        except Exception as exc:
            log.warning(
                "Could not load benchmarks from DB (%s). "
                "POST /analyze will return low-confidence responses. "
                "Set DATABASE_URL and restart to load real data.",
                exc,
            )
    else:
        log.warning(
            "DATABASE_URL not set — benchmarks not loaded. "
            "POST /analyze will return low-confidence responses."
        )
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title       = "MPLAD Financial Engine",
    description = (
        "Statistical and ML-based financial anomaly detection for MPLAD projects.\n\n"
        f"**{DISCLAIMER}**"
    ),
    version     = "0.1.0",
    lifespan    = lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],
    allow_methods  = ["GET", "POST"],
    allow_headers  = ["*"],
)


# ---------------------------------------------------------------------------
# Cost-estimator client
# ---------------------------------------------------------------------------

async def call_cost_estimator(
    category: str,
    state: str,
    description: Optional[str],
    allocation_amount: float,
) -> Optional[CostEstimatorRange]:
    """
    Call the cost-estimator service and return a CostEstimatorRange, or None
    on any failure (network error, timeout, service unavailable).
    """
    payload = {
        "category":            category,
        "state":               state,
        "description":         description,
        "declared_allocation": allocation_amount,
    }
    try:
        async with httpx.AsyncClient(timeout=CE_TIMEOUT) as client:
            resp = await client.post(f"{COST_ESTIMATOR_URL}/estimate", json=payload)
        if resp.status_code != 200:
            log.debug("cost-estimator returned %d", resp.status_code)
            return None
        data = resp.json()
        rng  = data.get("estimated_cost_range", {})
        return CostEstimatorRange(
            low              = rng.get("low", 0),
            high             = rng.get("high", 0),
            currency         = rng.get("currency", "INR"),
            matched_category = data.get("matched_category", category),
            confidence       = data.get("confidence", "low"),
            disclaimer       = data.get("disclaimer", ""),
        )
    except Exception as exc:
        log.debug("cost-estimator unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# DB project lookup
# ---------------------------------------------------------------------------

def fetch_project_from_db(project_id: UUID) -> dict:
    """
    Fetch (category, state, allocation_amount, constituency, ida, description)
    from mplads_project.  Raises HTTPException 404 if not found.
    """
    if not DB_URL:
        raise HTTPException(
            status_code = 503,
            detail      = "DATABASE_URL not configured; project_id lookup unavailable.",
        )
    conn = psycopg2.connect(DB_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, category, state, allocation_amount,
                       constituency, ida, work, status
                FROM mplads_project
                WHERE id = %s
                """,
                (str(project_id),),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code = 404,
            detail      = f"Project {project_id} not found in mplads_project.",
        )
    return dict(row)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception")
    return JSONResponse(
        status_code = 500,
        content     = {
            "error":      "internal_error",
            "message":    str(exc),
            "disclaimer": DISCLAIMER,
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary = "Health check",
    tags    = ["Ops"],
)
def health() -> dict:
    """Returns service status and benchmark summary."""
    store = get_store()
    return {
        "status":     "ok",
        "benchmarks": store.summary(),
        "disclaimer": DISCLAIMER,
    }


@app.get(
    "/benchmarks/{category}/{state}",
    summary = "Inspect raw benchmark stats for a (category, state) group",
    tags    = ["Debug"],
)
def get_benchmark(category: str, state: str) -> dict:
    """
    Returns the raw GroupStats for the given (category, state) pair.
    Useful for debugging and for the frontend to display context.
    """
    store = get_store()
    stats = store.get_stats(category, state)
    if stats is None:
        raise HTTPException(
            status_code = 404,
            detail      = f"No benchmark data for category='{category}' state='{state}'.",
        )
    return {
        "group_key":   stats.group_key,
        "category":    stats.category,
        "state":       stats.state,
        "count":       stats.count,
        "median":      stats.median,
        "q1":          stats.q1,
        "q3":          stats.q3,
        "iqr":         stats.iqr,
        "lower_fence": stats.lower_fence,
        "upper_fence": stats.upper_fence,
        "mean":        stats.mean,
        "std":         stats.std,
        "is_fallback": stats.is_fallback,
        "disclaimer":  DISCLAIMER,
    }


@app.post(
    "/analyze",
    summary         = "Analyze a project for financial anomaly indicators",
    tags            = ["Analysis"],
    response_model  = AnalyzeResponse,
    responses={
        200: {"description": "Anomaly analysis complete"},
        404: {"description": "project_id not found in mplads_project"},
        422: {"description": "Validation error — check request body"},
        503: {"description": "DB unavailable when project_id lookup was requested"},
    },
)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyse a project for financial anomaly indicators using:
    - Statistical deviation from historical (category, state) median
    - Isolation Forest trained on category allocation data
    - Optional: cost-estimator service as a second reference point

    ⚠️ Results are anomaly **indicators** for human review.
    They do not constitute a determination of fraud or misconduct.
    """
    store = get_store()

    # ── Resolve project fields ──────────────────────────────────────────────
    if req.project_id is not None:
        row           = fetch_project_from_db(req.project_id)
        category      = req.category      or row.get("category")      or ""
        state         = req.state         or row.get("state")         or ""
        amount        = req.allocation_amount or row.get("allocation_amount")
        description   = req.description   or row.get("work")
        project_id_str = str(req.project_id)

        if not category or not state or amount is None:
            raise HTTPException(
                status_code = 422,
                detail      = f"Project {req.project_id} has missing category/state/allocation_amount.",
            )
    else:
        category       = req.category      # type: ignore[assignment]
        state          = req.state          # type: ignore[assignment]
        amount         = req.allocation_amount  # type: ignore[assignment]
        description    = req.description
        project_id_str = None

    # ── Isolation Forest score ──────────────────────────────────────────────
    if_score = store.isolation_forest_score(category, amount)

    # ── Cost-estimator (optional, async, best-effort) ───────────────────────
    ce_range: Optional[CostEstimatorRange] = None
    if req.include_cost_estimate:
        ce_range = await call_cost_estimator(category, state, description, amount)

    # ── Score and build response ────────────────────────────────────────────
    return anlz.score_project(
        project_id        = project_id_str,
        category          = category,
        state             = state,
        allocation_amount = float(amount),
        store             = store,
        if_score          = if_score,
        ce_range          = ce_range,
    )


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
