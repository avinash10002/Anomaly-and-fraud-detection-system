"""
models.py
=========
Pydantic v2 request / response models for the financial-engine service.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """
    Accepts EITHER a project_id (looked up from mplads_project in the DB)
    OR inline fields.  Both paths produce identical response shapes.
    """

    project_id: Optional[UUID] = Field(
        default=None,
        description="UUID from mplads_project. When supplied, other fields are optional overrides.",
    )

    # Inline / override fields  ─────────────────────────────────────────────
    category: Optional[str] = Field(
        default=None,
        examples=["road"],
        description="Work category (e.g. 'road', 'drainage'). Required if project_id is absent.",
    )
    state: Optional[str] = Field(
        default=None,
        examples=["Bihar"],
        description="State name. Required if project_id is absent.",
    )
    allocation_amount: Optional[float] = Field(
        default=None,
        gt=0,
        examples=[4500000.0],
        description="Declared allocation in INR. Required if project_id is absent.",
    )

    # Optional context ───────────────────────────────────────────────────────
    constituency: Optional[str] = None
    ida:          Optional[str] = None
    description:  Optional[str] = Field(
        default=None,
        description="WORK description text — forwarded to cost-estimator for better category matching.",
    )
    status:       Optional[str] = None

    # Service behaviour ──────────────────────────────────────────────────────
    include_cost_estimate: bool = Field(
        default=True,
        description="If True, call the cost-estimator service for a second reference point.",
    )

    @model_validator(mode="after")
    def require_core_fields(self) -> "AnalyzeRequest":
        if self.project_id is None:
            missing = [
                f for f in ("category", "state", "allocation_amount")
                if getattr(self, f) is None
            ]
            if missing:
                raise ValueError(
                    f"Either project_id or inline fields are required. "
                    f"Missing: {missing}"
                )
        return self


# ---------------------------------------------------------------------------
# Response sub-models
# ---------------------------------------------------------------------------

class ComparisonGroup(BaseModel):
    category:     str
    state:        Optional[str]
    sample_count: int
    is_fallback:  bool = Field(
        description="True when state-level data was insufficient and the category-level benchmark was used.",
    )


class HistoricalRange(BaseModel):
    q1:          float = Field(description="25th percentile (INR)")
    q3:          float = Field(description="75th percentile (INR)")
    lower_fence: float = Field(description="Q1 − 1.5 × IQR (Tukey lower fence)")
    upper_fence: float = Field(description="Q3 + 1.5 × IQR (Tukey upper fence)")


class CostEstimatorRange(BaseModel):
    low:                float
    high:               float
    currency:           str = "INR"
    matched_category:   str
    confidence:         str
    disclaimer:         str


# ---------------------------------------------------------------------------
# Main response
# ---------------------------------------------------------------------------

class AnalyzeResponse(BaseModel):

    # Identity ───────────────────────────────────────────────────────────────
    project_id: Optional[str] = Field(
        description="UUID of the mplads_project row, if looked up.",
    )

    # Verdict ────────────────────────────────────────────────────────────────
    anomaly_score: float = Field(
        ge=0.0, le=1.0,
        description="Composite financial anomaly score 0–1. Higher = more unusual.",
    )
    is_flagged: bool = Field(
        description="True when anomaly_score ≥ 0.5.",
    )
    flag_label: Literal[
        "flagged for review",
        "financial anomaly indicator — borderline",
        "within expected range",
    ] = Field(
        description="Human-readable verdict. Never uses the word 'fraud'.",
    )

    # Benchmark context ──────────────────────────────────────────────────────
    comparison_group: ComparisonGroup
    allocation_amount:    float
    historical_median:    float
    historical_range:     HistoricalRange
    percentage_deviation: float = Field(
        description="(allocation_amount − median) / median × 100. Positive = above median.",
    )
    deviation_direction: Literal["above", "below"] = Field(
        description="Whether the allocation is above or below the group median.",
    )

    # Signals ────────────────────────────────────────────────────────────────
    isolation_forest_score: Optional[float] = Field(
        default=None,
        description="Isolation Forest anomaly score (0–1). Absent when group has < 10 samples.",
    )
    cost_estimator_range: Optional[CostEstimatorRange] = Field(
        default=None,
        description="Range from the cost-estimator service. Absent if service unavailable or disabled.",
    )

    # Narrative ──────────────────────────────────────────────────────────────
    reason_text: str = Field(
        description="Plain-language explanation citing actual numbers.",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="high ≥ 30 samples in group; medium ≥ 10; low < 10.",
    )

    # Mandatory disclaimer ───────────────────────────────────────────────────
    disclaimer: str = Field(
        default=(
            "Financial anomaly indicators are one signal for human review. "
            "They do not constitute a determination of fraud or misconduct."
        ),
        description="Must be rendered visibly in any UI that displays this result.",
    )
