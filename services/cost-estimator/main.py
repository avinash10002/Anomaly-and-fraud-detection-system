"""
main.py
=======
FastAPI application for the MPLAD Cost Estimator service.

Endpoints
---------
  GET  /health    → {"status": "ok"}
  GET  /rates     → Entire rate catalogue (for UI display / debugging)
  POST /estimate  → Cost range estimate with disclaimer
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

import estimator as est_module
from estimator import estimate, load_catalogue

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "PROTOTYPE DEMONSTRATION RATES ONLY — not official Schedule of Rates "
    "figures. Do not use for procurement or audit purposes."
)

app = FastAPI(
    title="MPLAD Cost Estimator",
    description=(
        "Prototype cost-estimation service for MPLAD infrastructure projects. "
        f"**{DISCLAIMER}**"
    ),
    version="0.1.0-prototype",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class EstimateRequest(BaseModel):
    category: str = Field(
        ...,
        min_length=2,
        examples=["road"],
        description=(
            "Work category from the MPLADS dataset (e.g. 'road', 'drainage', "
            "'community hall', 'street lighting', 'borewell'). "
            "Free-text is matched via keyword lookup — partial matches work."
        ),
    )
    state: str = Field(
        ...,
        min_length=2,
        examples=["Rajasthan"],
        description="Indian state name for cost-index adjustment.",
    )
    description: Optional[str] = Field(
        default=None,
        examples=["Construction of CC road from village Rampur to school gate 1.2 km"],
        description=(
            "Optional WORK description text from the MPLADS row. "
            "Improves category matching when category alone is ambiguous."
        ),
    )
    declared_allocation: float = Field(
        ...,
        gt=0,
        examples=[2500000.0],
        description="Declared project allocation amount in INR (from the dataset).",
    )

    @field_validator("declared_allocation")
    @classmethod
    def must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("declared_allocation must be > 0")
        return v


class CostRange(BaseModel):
    low:      float = Field(..., description="Lower bound of estimated cost (INR)")
    high:     float = Field(..., description="Upper bound of estimated cost (INR)")
    currency: str   = Field(default="INR")


class DeviationInfo(BaseModel):
    vs_midpoint_pct: float = Field(
        ...,
        description=(
            "How far the declared allocation sits from the estimated midpoint as a "
            "percentage. Positive = declared is higher than estimated. "
            "Negative = declared is lower."
        ),
    )
    verdict: Literal["within_range", "above_range", "below_range"] = Field(
        ...,
        description="Whether declared_allocation falls inside the estimated range.",
    )
    note: str


class EstimateResponse(BaseModel):
    estimated_cost_range:       CostRange
    declared_allocation:        float
    deviation_from_declared:    DeviationInfo
    matched_category:           str
    matched_category_label:     str
    catalogue_unit:             str
    state_cost_index_applied:   float
    assumptions:                List[str]
    data_source:                Literal["PROTOTYPE_DEMO_RATES"]
    confidence:                 Literal["low", "medium"]
    disclaimer:                 str = Field(
        ...,
        description="Always present. Frontend MUST display this string visibly.",
    )
    catalogue_version:          str


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error":   "internal_error",
            "message": str(exc),
            "disclaimer": DISCLAIMER,
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Health check",
    tags=["Ops"],
)
def health() -> Dict[str, str]:
    """Returns `{"status": "ok"}` — used by Docker Compose healthcheck."""
    return {"status": "ok"}


@app.get(
    "/rates",
    summary="View rate catalogue",
    tags=["Catalogue"],
    response_model=Dict[str, Any],
)
def get_rates() -> Dict[str, Any]:
    """
    Returns the full rate catalogue JSON.
    Useful for the frontend to display available categories and disclaimer metadata.
    """
    catalogue = load_catalogue()
    # Prepend a top-level disclaimer for any consumer of this endpoint
    return {
        "disclaimer": DISCLAIMER,
        "catalogue":  catalogue,
    }


@app.post(
    "/estimate",
    summary="Estimate project cost range",
    tags=["Estimation"],
    response_model=EstimateResponse,
    responses={
        200: {
            "description": "Cost range estimate with full disclaimer",
        },
        422: {
            "description": "Validation error — check request body",
        },
    },
)
def post_estimate(req: EstimateRequest) -> EstimateResponse:
    """
    Given a project's **category**, **state**, optional **description**, and
    **declared allocation**, returns:

    - `estimated_cost_range`: low/high bounds based on prototype rate catalogue
    - `deviation_from_declared`: how far the declared amount is from the estimate
    - `assumptions`: transparent list of all inputs and defaults applied
    - `disclaimer`: **always present** — must be shown in the UI

    ⚠️ **All rates are prototype/demonstration figures — not official SoR data.**
    """
    try:
        result = estimate(
            category=req.category,
            state=req.state,
            description=req.description,
            declared_allocation=req.declared_allocation,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EstimateResponse(**result)


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8084, reload=True)
