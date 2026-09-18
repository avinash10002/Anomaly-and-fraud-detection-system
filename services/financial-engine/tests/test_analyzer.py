"""
tests/test_analyzer.py
======================
Unit tests for analyzer.score_project():
  - Normal projects (within IQR) → low score, not flagged
  - Clear outliers (>> upper fence) → high score, flagged
  - Below-median projects → correct direction label
  - reason_text cites actual numbers
  - No "fraud" language anywhere
  - Language policy: "flagged for review" / "financial anomaly indicator" only
  - Mandatory disclaimer always present
  - No-benchmark case → graceful low-confidence response
"""

from __future__ import annotations

import re

import pytest

import analyzer as anlz
from analyzer import score_project
from models import CostEstimatorRange


DISCLAIMER_FRAGMENT = "Financial anomaly indicators are one signal"
FORBIDDEN_WORDS = ["fraud", "criminal", "illegal", "corrupt"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(
    category,
    state,
    amount,
    store,
    if_score=None,
    ce_range=None,
):
    return score_project(
        project_id        = None,
        category          = category,
        state             = state,
        allocation_amount = amount,
        store             = store,
        if_score          = if_score,
        ce_range          = ce_range,
    )


# ---------------------------------------------------------------------------
# Normal project (within expected range)
# ---------------------------------------------------------------------------

class TestNormalProject:
    """A project at the median should have a low anomaly score."""

    def test_at_median_low_score(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median, loaded_store)
        assert result.anomaly_score < 0.30, (
            f"At-median project should score < 0.30, got {result.anomaly_score}"
        )

    def test_at_median_not_flagged(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median, loaded_store)
        assert not result.is_flagged

    def test_at_median_flag_label(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median, loaded_store)
        assert result.flag_label == "within expected range"

    def test_normal_project_pct_deviation_near_zero(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median, loaded_store)
        assert abs(result.percentage_deviation) < 1.0  # exactly at median

    def test_within_iqr_not_flagged(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        mid_iqr = (stats.q1 + stats.q3) / 2
        result = _score("road", "Bihar", mid_iqr, loaded_store)
        assert not result.is_flagged


# ---------------------------------------------------------------------------
# Outlier project (>> upper fence)
# ---------------------------------------------------------------------------

class TestOutlierProject:
    """A project at 10× the median should be flagged."""

    def test_extreme_high_flagged(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        extreme_amount = stats.median * 10
        result = _score("road", "Bihar", extreme_amount, loaded_store)
        assert result.is_flagged, f"10× median should be flagged. Score={result.anomaly_score}"

    def test_extreme_high_score_above_half(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 10, loaded_store)
        assert result.anomaly_score >= 0.50

    def test_extreme_high_direction_above(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 10, loaded_store)
        assert result.deviation_direction == "above"

    def test_extreme_high_positive_pct_deviation(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 10, loaded_store)
        assert result.percentage_deviation > 100

    def test_extreme_high_reason_cites_numbers(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 10, loaded_store)
        # reason_text must contain actual INR amounts
        assert "₹" in result.reason_text
        # Must contain the pct deviation
        assert re.search(r"\d+\.\d+%", result.reason_text)
        # Must cite the median
        assert "median" in result.reason_text.lower()


# ---------------------------------------------------------------------------
# Below-median project
# ---------------------------------------------------------------------------

class TestBelowMedianProject:
    """A project at 10% of median is suspiciously low."""

    def test_very_low_direction_below(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 0.10, loaded_store)
        assert result.deviation_direction == "below"

    def test_very_low_negative_pct_deviation(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 0.10, loaded_store)
        assert result.percentage_deviation < 0

    def test_very_low_flagged_with_if_signal(self, loaded_store):
        # With synthetic data the IQR is wide, so pure deviation at 2% of median
        # yields ~0.38 (borderline).  Adding a high IF score (0.95) pushes it over 0.50.
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 0.02, loaded_store, if_score=0.95)
        assert result.is_flagged, (
            f"Expected flagged at 2% of median with high IF score. Score={result.anomaly_score}"
        )

    def test_very_low_is_at_least_borderline(self, loaded_store):
        """Even without an IF signal, a 98%-below-median project must be at least borderline."""
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * 0.02, loaded_store)
        assert result.anomaly_score >= 0.30, (
            f"98%-below-median project should score ≥ 0.30. Got {result.anomaly_score}"
        )
        assert result.flag_label in (
            "flagged for review",
            "financial anomaly indicator — borderline",
        )


# ---------------------------------------------------------------------------
# Isolation Forest integration
# ---------------------------------------------------------------------------

class TestIsolationForestSignal:
    """IF score must contribute to the composite when available."""

    def test_high_if_score_raises_composite(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        # Same near-median amount, but inject an artificially high IF score
        r_no_if = _score("road", "Bihar", stats.median, loaded_store, if_score=None)
        r_hi_if = _score("road", "Bihar", stats.median, loaded_store, if_score=0.95)
        assert r_hi_if.anomaly_score > r_no_if.anomaly_score

    def test_if_score_zero_does_not_exceed_deviation_alone(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        r_no_if    = _score("road", "Bihar", stats.median, loaded_store, if_score=None)
        r_zero_if  = _score("road", "Bihar", stats.median, loaded_store, if_score=0.0)
        # With IF=0, composite = 0.70 * dev_score + 0.30 * 0.0 < deviation_alone
        assert r_zero_if.anomaly_score <= r_no_if.anomaly_score + 0.01

    def test_if_score_none_when_store_has_no_model(self):
        """With an empty store, IF score should be None and not crash."""
        from benchmarks import BenchmarkStore
        store = BenchmarkStore()
        score = store.isolation_forest_score("road", 1_800_000)
        assert score is None


# ---------------------------------------------------------------------------
# Cost-estimator range in response
# ---------------------------------------------------------------------------

class TestCostEstimatorRange:

    def test_ce_range_included_when_provided(self, loaded_store):
        ce = CostEstimatorRange(
            low=500_000, high=5_000_000, currency="INR",
            matched_category="road", confidence="medium",
            disclaimer="PROTOTYPE",
        )
        result = _score("road", "Bihar", 1_800_000, loaded_store, ce_range=ce)
        assert result.cost_estimator_range is not None
        assert result.cost_estimator_range.low == 500_000

    def test_ce_range_in_reason_text(self, loaded_store):
        ce = CostEstimatorRange(
            low=500_000, high=5_000_000, currency="INR",
            matched_category="road", confidence="medium",
            disclaimer="PROTOTYPE",
        )
        result = _score("road", "Bihar", 1_800_000, loaded_store, ce_range=ce)
        assert "cost-estimator" in result.reason_text.lower()

    def test_none_ce_range_not_in_response(self, loaded_store):
        result = _score("road", "Bihar", 1_800_000, loaded_store, ce_range=None)
        assert result.cost_estimator_range is None


# ---------------------------------------------------------------------------
# No-benchmark case
# ---------------------------------------------------------------------------

class TestNoBenchmarkCase:

    def test_unknown_category_returns_response(self, loaded_store):
        result = _score("rocket propulsion", "Bihar", 1_000_000, loaded_store)
        assert result is not None

    def test_unknown_category_score_zero(self, loaded_store):
        result = _score("rocket propulsion", "Bihar", 1_000_000, loaded_store)
        assert result.anomaly_score == 0.0

    def test_unknown_category_not_flagged(self, loaded_store):
        result = _score("rocket propulsion", "Bihar", 1_000_000, loaded_store)
        assert not result.is_flagged

    def test_unknown_category_confidence_low(self, loaded_store):
        result = _score("rocket propulsion", "Bihar", 1_000_000, loaded_store)
        assert result.confidence == "low"


# ---------------------------------------------------------------------------
# Language policy: no forbidden words, disclaimer always present
# ---------------------------------------------------------------------------

class TestLanguagePolicy:

    @pytest.mark.parametrize("amount_mult", [0.05, 1.0, 10.0])
    def test_no_fraud_language(self, amount_mult, loaded_store):
        # The disclaimer intentionally says "determination of fraud or misconduct"
        # (to explain what it is NOT). We only scan reason_text and flag_label.
        stats = loaded_store.get_stats("road", "Bihar")
        amount = stats.median * amount_mult
        result = _score("road", "Bihar", amount, loaded_store)
        full_text = (
            result.reason_text + " " +
            result.flag_label
        ).lower()
        for word in FORBIDDEN_WORDS:
            assert word not in full_text, (
                f"Forbidden word '{word}' found in reason_text/flag_label for amount_mult={amount_mult}"
            )

    @pytest.mark.parametrize("amount_mult", [0.05, 1.0, 10.0])
    def test_disclaimer_always_present(self, amount_mult, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        result = _score("road", "Bihar", stats.median * amount_mult, loaded_store)
        assert DISCLAIMER_FRAGMENT in result.disclaimer

    def test_flag_label_uses_approved_vocabulary(self, loaded_store):
        approved = {
            "flagged for review",
            "financial anomaly indicator — borderline",
            "within expected range",
        }
        stats = loaded_store.get_stats("road", "Bihar")
        for amount in [stats.median * 0.1, stats.median, stats.median * 5, stats.median * 15]:
            result = _score("road", "Bihar", amount, loaded_store)
            assert result.flag_label in approved, (
                f"Unexpected flag_label: {result.flag_label!r}"
            )


# ---------------------------------------------------------------------------
# Score monotonicity
# ---------------------------------------------------------------------------

class TestScoreMonotonicity:
    """Higher deviations from median should generally produce higher scores."""

    def test_scores_increase_with_deviation(self, loaded_store):
        stats = loaded_store.get_stats("road", "Bihar")
        amounts = [
            stats.median * m for m in [0.5, 1.0, 2.0, 5.0, 10.0, 20.0]
        ]
        scores = [
            _score("road", "Bihar", a, loaded_store).anomaly_score
            for a in amounts
        ]
        # Not strictly monotonic (sigmoid is symmetric around median),
        # but amounts 2×, 5×, 10×, 20× median should be > 1× median score
        for i in range(2, len(scores)):
            assert scores[i] >= scores[1], (
                f"Score at {amounts[i]:,.0f} ({scores[i]:.3f}) should be ≥ "
                f"score at median ({scores[1]:.3f})"
            )
