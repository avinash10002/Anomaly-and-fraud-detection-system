"""
analyzer.py
===========
Core scoring logic for the financial-engine.

Scoring model
-------------
The final anomaly_score is a weighted blend of two independently
interpretable signals:

  1. Deviation score  (weight 0.70)
     Derived from how many IQR-widths the allocation sits from the median.
     Formula:  z = |amount − median| / IQR   (if IQR > 0)
               deviation_score = sigmoid-clamp to [0, 1]

  2. Isolation Forest score  (weight 0.30)
     Normalised IF decision_function in [0, 1].
     Absent (0.0 weight) when the category has < 10 training samples.

Thresholds
----------
  anomaly_score ≥ 0.50  →  "flagged for review"
  anomaly_score ≥ 0.30  →  "financial anomaly indicator — borderline"
  anomaly_score <  0.30  →  "within expected range"

Confidence
----------
  ≥ 30 samples in comparison group  →  "high"
  ≥ 10 samples                      →  "medium"
  <  10 samples                      →  "low"

None of these thresholds use the word "fraud".
"""

from __future__ import annotations

import math
from typing import Optional

from benchmarks import BenchmarkStore, GroupStats
from models import (
    AnalyzeResponse,
    ComparisonGroup,
    CostEstimatorRange,
    HistoricalRange,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEIGHT_DEVIATION = 0.70
WEIGHT_IF        = 0.30

THRESHOLD_FLAGGED    = 0.50
THRESHOLD_BORDERLINE = 0.30

CONF_HIGH_MIN   = 30
CONF_MEDIUM_MIN = 10

DISCLAIMER = (
    "Financial anomaly indicators are one signal for human review. "
    "They do not constitute a determination of fraud or misconduct."
)


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------

def _deviation_score(amount: float, stats: GroupStats) -> float:
    """
    Maps |amount − median| / IQR to [0, 1] using a sigmoid-style curve.
    z = 0   → score ≈ 0.12   (at median)
    z = 1   → score ≈ 0.37   (1 IQR away)
    z = 2   → score ≈ 0.62   (2 IQRs away — moderate outlier)
    z = 3   → score ≈ 0.80   (3 IQRs away — strong outlier)
    z ≥ 5   → score → 1.00   (extreme)

    Falls back to relative deviation when IQR is 0 (all-same-amount group).
    """
    iqr = stats.iqr
    if iqr > 0:
        z = abs(amount - stats.median) / iqr
    else:
        # IQR = 0 means all values are equal; use relative deviation from mean
        if stats.mean > 0:
            z = abs(amount - stats.mean) / stats.mean * 3.0  # rescale so 100%=z3
        else:
            z = 0.0

    # Sigmoid: σ(z - 2) shifted so that z=2 → score≈0.5
    return float(1.0 / (1.0 + math.exp(-(z - 2.0))))


def _pct_deviation(amount: float, median: float) -> float:
    if median == 0:
        return 0.0
    return (amount - median) / median * 100.0


def _confidence(count: int) -> str:
    if count >= CONF_HIGH_MIN:
        return "high"
    if count >= CONF_MEDIUM_MIN:
        return "medium"
    return "low"


def _flag_label(score: float) -> str:
    if score >= THRESHOLD_FLAGGED:
        return "flagged for review"
    if score >= THRESHOLD_BORDERLINE:
        return "financial anomaly indicator — borderline"
    return "within expected range"


def _reason_text(
    amount:         float,
    stats:          GroupStats,
    pct_dev:        float,
    direction:      str,
    if_score:       Optional[float],
    ce_range:       Optional[CostEstimatorRange],
    flag_label:     str,
) -> str:
    """
    Builds a factual, number-citing reason string.
    Never uses the word 'fraud'.
    """
    state_label = f"in {stats.state}" if stats.state else "(all states)"
    cat_label   = stats.category

    lines = [
        f"Allocation (₹{amount:,.0f}) is {abs(pct_dev):.1f}% "
        f"{direction} the median allocation "
        f"(₹{stats.median:,.0f}) of comparable {cat_label!r} projects "
        f"{state_label} (sample: {stats.count} projects)."
    ]

    # IQR context
    lines.append(
        f"The typical allocation range (IQR) for this group is "
        f"₹{stats.q1:,.0f} – ₹{stats.q3:,.0f}; "
        f"Tukey outer fences are ₹{stats.lower_fence:,.0f} – ₹{stats.upper_fence:,.0f}."
    )

    # Fallback note
    if stats.is_fallback:
        lines.append(
            "Note: state-level data was insufficient; national category benchmark used."
        )

    # Isolation Forest
    if if_score is not None:
        if_label = "unusual" if if_score >= 0.5 else "typical"
        lines.append(
            f"Isolation Forest (trained on {cat_label!r} category, "
            f"n ≥ 10): classifies this allocation as {if_label!r} "
            f"(normalised IF score: {if_score:.2f})."
        )
    else:
        lines.append(
            "Isolation Forest: insufficient data for this category — "
            "statistical deviation is the sole signal."
        )

    # Cost-estimator comparison
    if ce_range is not None:
        lines.append(
            f"Cost-estimator prototype range: ₹{ce_range.low:,.0f} – "
            f"₹{ce_range.high:,.0f} ({ce_range.matched_category}, {ce_range.confidence} confidence)."
        )

    # Verdict
    if flag_label == "within expected range":
        lines.append("Overall: allocation is within the expected range — no anomaly indicator raised.")
    else:
        lines.append(
            f"Overall verdict: '{flag_label}'. "
            "This is a financial anomaly indicator only; human review is required before any conclusions."
        )

    return " ".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def score_project(
    *,
    project_id:        Optional[str],
    category:          str,
    state:             str,
    allocation_amount: float,
    store:             BenchmarkStore,
    if_score:          Optional[float],
    ce_range:          Optional[CostEstimatorRange],
) -> AnalyzeResponse:
    """
    Produce an AnalyzeResponse for a single project.

    Parameters
    ----------
    project_id        : UUID string or None (inline analysis)
    category          : work category (raw string)
    state             : state name
    allocation_amount : INR amount
    store             : populated BenchmarkStore
    if_score          : pre-computed Isolation Forest score [0,1] or None
    ce_range          : cost-estimator response or None
    """

    stats = store.get_stats(category, state)

    # ── No benchmark available ────────────────────────────────────────────
    if stats is None:
        # Return a low-confidence, neutral result rather than an error
        return AnalyzeResponse(
            project_id             = project_id,
            anomaly_score          = 0.0,
            is_flagged             = False,
            flag_label             = "within expected range",
            comparison_group       = ComparisonGroup(
                category     = category.lower().strip(),
                state        = state,
                sample_count = 0,
                is_fallback  = True,
            ),
            allocation_amount    = allocation_amount,
            historical_median    = 0.0,
            historical_range     = HistoricalRange(q1=0, q3=0, lower_fence=0, upper_fence=0),
            percentage_deviation = 0.0,
            deviation_direction  = "above",
            isolation_forest_score = None,
            cost_estimator_range   = ce_range,
            reason_text = (
                f"Insufficient historical data for category '{category}' in '{state}' "
                f"(or nationwide) to establish a benchmark. No anomaly indicator can be raised. "
                f"Review manually."
            ),
            confidence  = "low",
            disclaimer  = DISCLAIMER,
        )

    # ── Compute scores ────────────────────────────────────────────────────
    dev_score = _deviation_score(allocation_amount, stats)
    pct_dev   = _pct_deviation(allocation_amount, stats.median)
    direction = "above" if allocation_amount >= stats.median else "below"

    if if_score is not None:
        composite = WEIGHT_DEVIATION * dev_score + WEIGHT_IF * if_score
    else:
        composite = dev_score   # full weight on deviation when IF unavailable

    composite = round(float(min(1.0, max(0.0, composite))), 4)

    label = _flag_label(composite)
    conf  = _confidence(stats.count)

    reason = _reason_text(
        amount     = allocation_amount,
        stats      = stats,
        pct_dev    = pct_dev,
        direction  = direction,
        if_score   = if_score,
        ce_range   = ce_range,
        flag_label = label,
    )

    return AnalyzeResponse(
        project_id             = project_id,
        anomaly_score          = composite,
        is_flagged             = composite >= THRESHOLD_FLAGGED,
        flag_label             = label,
        comparison_group       = ComparisonGroup(
            category     = stats.category,
            state        = stats.state,
            sample_count = stats.count,
            is_fallback  = stats.is_fallback,
        ),
        allocation_amount      = allocation_amount,
        historical_median      = round(stats.median, 2),
        historical_range       = HistoricalRange(
            q1          = round(stats.q1, 2),
            q3          = round(stats.q3, 2),
            lower_fence = round(stats.lower_fence, 2),
            upper_fence = round(stats.upper_fence, 2),
        ),
        percentage_deviation   = round(pct_dev, 2),
        deviation_direction    = direction,
        isolation_forest_score = round(if_score, 4) if if_score is not None else None,
        cost_estimator_range   = ce_range,
        reason_text            = reason,
        confidence             = conf,
        disclaimer             = DISCLAIMER,
    )
