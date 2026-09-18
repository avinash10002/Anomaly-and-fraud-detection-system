"""
estimator.py
============
Core estimation logic — fully decoupled from FastAPI.
Reads the rate catalogue from JSON; the catalogue can be swapped without
touching this file or the API layer.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Catalogue loading
# ---------------------------------------------------------------------------

CATALOGUE_PATH = Path(__file__).parent / "rates" / "catalogue.json"


@lru_cache(maxsize=1)
def load_catalogue() -> dict:
    """Load and cache the rate catalogue. Restart service to pick up changes."""
    with open(CATALOGUE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Category matching
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for matching."""
    text = text.lower().strip()
    text = re.sub(r"[_\-/\\]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _kw_hit(keyword: str, text: str) -> bool:
    """
    True if `keyword` appears as a whole-word match inside `text`.
    Uses \\b word boundaries to prevent 'lane' matching 'miscellaneous'.
    Multi-word keywords (e.g. 'link road') are matched as a phrase.
    """
    pattern = r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])"
    return bool(re.search(pattern, text))


def match_category(category: str, description: Optional[str]) -> str:
    """
    Match the user-supplied category (and optional description) to a catalogue
    key using keyword overlap.  Falls back to 'other' if no match is found.

    Matching priority:
      1. Exact catalogue key match
      2. Category string keyword scan (whole-word, weight 3)
      3. Description keyword scan (whole-word, weight 1)
    """
    cat = load_catalogue()["categories"]
    norm_category = _normalise(category)
    norm_desc = _normalise(description or "")

    # 1. Exact key match
    if norm_category in cat:
        return norm_category

    # 2. Score each catalogue entry by keyword hits
    scores: dict[str, int] = {}
    for key, entry in cat.items():
        if key == "other":
            continue
        score = 0
        for kw in entry["keywords"]:
            kw_norm = _normalise(kw)
            if _kw_hit(kw_norm, norm_category):
                score += 3          # category field hit = high weight
            if _kw_hit(kw_norm, norm_desc):
                score += 1          # description hit = lower weight
        scores[key] = score

    best_key = max(scores, key=lambda k: scores[k]) if scores else "other"
    best_score = scores.get(best_key, 0)

    return best_key if best_score > 0 else "other"


# ---------------------------------------------------------------------------
# State cost index
# ---------------------------------------------------------------------------

def get_state_index(state: str) -> float:
    index_map: dict = load_catalogue()["state_cost_index"]
    # Try exact match first, then case-insensitive
    if state in index_map:
        return float(index_map[state])
    for k, v in index_map.items():
        if k.lower() == state.lower():
            return float(v)
    return float(index_map.get("default", 1.0))


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------

def _round_inr(value: float, sig_figs: int = 3) -> float:
    """Round to sig_figs significant figures for cleaner output."""
    if value == 0:
        return 0.0
    magnitude = math.floor(math.log10(abs(value)))
    factor = 10 ** (magnitude - sig_figs + 1)
    return round(value / factor) * factor


def estimate(
    category: str,
    state: str,
    description: Optional[str],
    declared_allocation: float,
) -> dict:
    """
    Estimate a cost range for a project and compare with the declared allocation.

    Returns a dict matching the EstimateResponse schema.
    """
    catalogue = load_catalogue()
    meta = catalogue["_meta"]
    categories = catalogue["categories"]

    matched_key = match_category(category, description)
    entry = categories[matched_key]

    state_index = get_state_index(state)

    # Base rates × state index
    rate_low  = entry["rate_inr"]["low"]  * state_index
    rate_high = entry["rate_inr"]["high"] * state_index

    qty_low  = entry["typical_quantity"]["low"]
    qty_high = entry["typical_quantity"]["high"]

    raw_low  = rate_low  * qty_low
    raw_high = rate_high * qty_high

    est_low  = _round_inr(raw_low)
    est_high = _round_inr(raw_high)
    est_mid  = (est_low + est_high) / 2

    # Deviation of declared_allocation from estimated mid-point
    if est_mid > 0:
        deviation_pct = round((declared_allocation - est_mid) / est_mid * 100, 1)
    else:
        deviation_pct = 0.0

    # Determine whether declared falls inside, above, or below the range
    if est_low <= declared_allocation <= est_high:
        range_verdict = "within_range"
    elif declared_allocation < est_low:
        range_verdict = "below_range"
    else:
        range_verdict = "above_range"

    # Build assumption list: catalogue assumptions + runtime context
    runtime_assumptions = [
        f"Matched input category '{category}' → '{entry['label']}'",
        f"Unit of estimation: {entry['unit_label']}",
        f"Typical quantity assumed: {qty_low}–{qty_high} {entry['unit']}",
        f"Base rate range (national): ₹{entry['rate_inr']['low']:,.0f} – ₹{entry['rate_inr']['high']:,.0f} per {entry['unit']}",
        f"State cost index for '{state}': {state_index:.2f}× (applied to base rates)",
        f"Adjusted rate range: ₹{rate_low:,.0f} – ₹{rate_high:,.0f} per {entry['unit']}",
    ]

    all_assumptions = runtime_assumptions + entry["assumptions"]

    return {
        "estimated_cost_range": {
            "low":      est_low,
            "high":     est_high,
            "currency": "INR",
        },
        "declared_allocation":  declared_allocation,
        "deviation_from_declared": {
            "vs_midpoint_pct":  deviation_pct,
            "verdict":          range_verdict,
            "note": (
                "Positive % = declared is higher than estimated midpoint. "
                "Negative % = declared is lower. "
                "Use this signal as one input to the anomaly engine — not as a standalone verdict."
            ),
        },
        "matched_category":       matched_key,
        "matched_category_label": entry["label"],
        "catalogue_unit":         entry["unit"],
        "state_cost_index_applied": state_index,
        "assumptions":            all_assumptions,
        "data_source":            "PROTOTYPE_DEMO_RATES",
        "confidence":             entry["confidence"],
        "disclaimer":             meta["disclaimer"],
        "catalogue_version":      meta["catalogue_version"],
    }
