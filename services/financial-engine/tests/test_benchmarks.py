"""
tests/test_benchmarks.py
========================
Unit tests for BenchmarkStore:
  - GroupStats correctness (median, IQR, Tukey fences)
  - (category, state) vs category-level fallback
  - Isolation Forest score direction (outlier > normal)
  - Edge cases: tiny group, missing category
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from benchmarks import BenchmarkStore, GroupStats, MIN_GROUP_SIZE_STATE


class TestGroupStats:
    """Test that BenchmarkStore computes correct statistics."""

    def test_median_road_bihar(self, loaded_store: BenchmarkStore):
        stats = loaded_store.get_stats("road", "Bihar")
        assert stats is not None
        assert stats.category == "road"
        assert stats.state == "Bihar"
        # Synthetic median ≈ 1.8M — check it's in a sensible range
        assert 1_000_000 < stats.median < 3_000_000, f"Unexpected median: {stats.median}"

    def test_q1_less_than_median_less_than_q3(self, loaded_store: BenchmarkStore):
        for cat, state in [("road", "Bihar"), ("drainage", "Bihar"), ("borewell", "Rajasthan")]:
            stats = loaded_store.get_stats(cat, state)
            assert stats is not None, f"No stats for ({cat}, {state})"
            assert stats.q1 <= stats.median <= stats.q3, (
                f"({cat},{state}): Q1={stats.q1} median={stats.median} Q3={stats.q3}"
            )

    def test_tukey_fences(self, loaded_store: BenchmarkStore):
        stats = loaded_store.get_stats("road", "Bihar")
        assert stats.lower_fence >= 0
        assert stats.upper_fence > stats.q3
        # Tukey check: upper_fence = Q3 + 1.5 * IQR
        expected_upper = stats.q3 + 1.5 * stats.iqr
        assert abs(stats.upper_fence - expected_upper) < 1.0, (
            f"upper_fence mismatch: got {stats.upper_fence}, expected {expected_upper}"
        )

    def test_sample_count_matches_input(self, loaded_store: BenchmarkStore):
        # road/Bihar was seeded with 120 rows
        stats = loaded_store.get_stats("road", "Bihar")
        assert stats.count == 120

    def test_is_not_fallback_for_specific_state(self, loaded_store: BenchmarkStore):
        stats = loaded_store.get_stats("road", "Bihar")
        assert not stats.is_fallback

    def test_fallback_for_unknown_state(self, loaded_store: BenchmarkStore):
        """road/UnknownState should fall back to category-level benchmark."""
        stats = loaded_store.get_stats("road", "SomeNonExistentState")
        assert stats is not None, "Should fall back to category-level stats"
        assert stats.is_fallback is True
        # Category-level should include both Bihar + Maharashtra road rows
        assert stats.count >= 120 + 80

    def test_none_for_completely_unknown_category(self, loaded_store: BenchmarkStore):
        stats = loaded_store.get_stats("flying saucer repair", "Bihar")
        assert stats is None

    def test_tiny_group_not_returned_for_state_level(self, loaded_store: BenchmarkStore):
        """park/Goa has only 3 rows — below MIN_GROUP_SIZE_STATE; state-level should be absent."""
        # The store won't have a (park, Goa) entry
        stats_direct = loaded_store._by_cat_state.get(("park", "goa"))
        assert stats_direct is None, "Group with 3 rows should not produce (cat,state) stats"

    def test_case_insensitive_lookup(self, loaded_store: BenchmarkStore):
        s1 = loaded_store.get_stats("Road",  "Bihar")
        s2 = loaded_store.get_stats("ROAD",  "Bihar")
        s3 = loaded_store.get_stats("road",  "Bihar")
        assert s1 is not None and s2 is not None and s3 is not None
        assert s1.median == s2.median == s3.median


class TestIsolationForestScore:
    """Test that IF scores differentiate outliers from normal values."""

    def test_if_model_exists_for_large_category(self, loaded_store: BenchmarkStore):
        # road has 200 rows total → IF model must be fitted
        score = loaded_store.isolation_forest_score("road", 1_800_000)
        assert score is not None, "IF model should exist for road (200 rows)"

    def test_normal_value_lower_score_than_outlier(self, loaded_store: BenchmarkStore):
        # road/Bihar median ≈ 1.8M
        normal_score  = loaded_store.isolation_forest_score("road", 1_800_000)
        outlier_score = loaded_store.isolation_forest_score("road", 30_000_000)

        assert normal_score  is not None
        assert outlier_score is not None
        assert normal_score < outlier_score, (
            f"Normal ({normal_score:.3f}) should score lower than outlier ({outlier_score:.3f})"
        )

    def test_if_score_in_unit_range(self, loaded_store: BenchmarkStore):
        for amount in [100_000, 1_000_000, 5_000_000, 50_000_000]:
            score = loaded_store.isolation_forest_score("road", amount)
            if score is not None:
                assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] for amount={amount}"

    def test_no_if_for_unknown_category(self, loaded_store: BenchmarkStore):
        score = loaded_store.isolation_forest_score("flying saucer", 1_000_000)
        assert score is None


class TestBenchmarkStoreEdgeCases:
    """Edge cases for BenchmarkStore.load_from_dataframe."""

    def test_empty_dataframe_does_not_crash(self):
        store = BenchmarkStore()
        empty = pd.DataFrame(columns=["category", "state", "allocation_amount"])
        store.load_from_dataframe(empty)
        assert store.is_loaded
        assert store.get_stats("road", "Bihar") is None

    def test_all_same_amount_group(self):
        """IQR = 0 case — store should still load without division-by-zero."""
        store = BenchmarkStore()
        df = pd.DataFrame({
            "category":         ["road"] * 20,
            "state":            ["Bihar"] * 20,
            "allocation_amount": [1_000_000.0] * 20,
        })
        store.load_from_dataframe(df)
        stats = store.get_stats("road", "Bihar")
        assert stats is not None
        assert stats.iqr == 0.0
        assert stats.median == 1_000_000.0
