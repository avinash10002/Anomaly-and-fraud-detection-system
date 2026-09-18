"""
benchmarks.py
=============
Loads raw allocation data from mplads_project, computes per-(category, state)
and per-category statistical benchmarks, and trains one Isolation Forest model
per category as a supplementary anomaly signal.

Design decisions
----------------
* Minimum group size for a reliable (category, state) benchmark: MIN_GROUP_SIZE (5).
  Below that threshold the service falls back to category-level stats.
* Isolation Forest is trained per category (not per state), using log1p(amount)
  as the single feature to handle heavy right-skew in MPLAD allocations.
* IF contamination is set conservatively at 0.05 (5%) — only the most extreme
  allocations are treated as intrinsically anomalous by the model.
* IF is a supplementary signal only; the main score is driven by deviation
  from the median, which is independently interpretable (see analyzer.py).
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from sklearn.ensemble import IsolationForest

log = logging.getLogger("financial_engine.benchmarks")

# Minimum samples required for a (category, state) or (category) group
MIN_GROUP_SIZE_STATE = 5
MIN_GROUP_SIZE_CAT = 10

# Isolation Forest is only fitted when the category has at least this many rows
MIN_IF_SAMPLES = 10

IF_CONTAMINATION = 0.05
IF_RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Data class for per-group statistics
# ---------------------------------------------------------------------------

@dataclass
class GroupStats:
    group_key:   str                # "category|state" or "category"
    category:    str
    state:       Optional[str]      # None for category-level fallback groups
    count:       int
    median:      float
    q1:          float
    q3:          float
    iqr:         float
    lower_fence: float              # Tukey: Q1 − 1.5·IQR  (floored at 0)
    upper_fence: float              # Tukey: Q3 + 1.5·IQR
    mean:        float
    std:         float
    is_fallback: bool = False       # True for category-level (state omitted)


# ---------------------------------------------------------------------------
# BenchmarkStore
# ---------------------------------------------------------------------------

class BenchmarkStore:
    """
    In-memory store of GroupStats dicts and per-category Isolation Forest models.
    Populate via load_from_db() at startup, or load_from_dataframe() in tests.
    All read operations are thread-safe (no mutation after load).
    """

    def __init__(self) -> None:
        self._by_cat_state: Dict[Tuple[str, str], GroupStats] = {}
        self._by_cat:       Dict[str, GroupStats] = {}
        self._if_models:    Dict[str, IsolationForest] = {}
        self._if_ranges:    Dict[str, Tuple[float, float]] = {}  # (score_min, score_max) for normalization
        self._loaded:       bool = False

    # ── Loading ─────────────────────────────────────────────────────────────

    def load_from_db(self, db_url: str) -> None:
        log.info("Connecting to DB to load benchmark data …")
        conn = psycopg2.connect(db_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        LOWER(TRIM(category))   AS category,
                        TRIM(state)             AS state,
                        allocation_amount
                    FROM mplads_project
                    WHERE allocation_amount IS NOT NULL
                      AND allocation_amount > 0
                      AND category         IS NOT NULL
                      AND state            IS NOT NULL
                """)
                rows = cur.fetchall()
        finally:
            conn.close()

        df = pd.DataFrame(rows)
        log.info("Fetched %d allocation rows for benchmark computation", len(df))
        self._fit(df)

    def load_from_dataframe(self, df: pd.DataFrame) -> None:
        """For unit tests: skip DB, load from an in-memory DataFrame."""
        self._fit(df.copy())

    # ── Internals ────────────────────────────────────────────────────────────

    def _normalise_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["category"] = df["category"].astype(str).str.lower().str.strip()
        df["state"]    = df["state"].astype(str).str.strip()
        df["allocation_amount"] = pd.to_numeric(df["allocation_amount"], errors="coerce")
        return df.dropna(subset=["allocation_amount"]).query("allocation_amount > 0")

    @staticmethod
    def _compute_stats_for_group(
        amounts: np.ndarray,
        category: str,
        state: Optional[str],
        is_fallback: bool,
    ) -> Optional[GroupStats]:
        n = len(amounts)
        min_n = MIN_GROUP_SIZE_CAT if is_fallback else MIN_GROUP_SIZE_STATE
        if n < min_n:
            return None

        q1, median, q3 = np.percentile(amounts, [25, 50, 75])
        iqr = q3 - q1

        return GroupStats(
            group_key   = f"{category}|{state}" if state else category,
            category    = category,
            state       = state,
            count       = n,
            median      = float(median),
            q1          = float(q1),
            q3          = float(q3),
            iqr         = float(iqr),
            lower_fence = float(max(0.0, q1 - 1.5 * iqr)),
            upper_fence = float(q3 + 1.5 * iqr),
            mean        = float(amounts.mean()),
            std         = float(amounts.std(ddof=1)) if n > 1 else 0.0,
            is_fallback = is_fallback,
        )

    def _fit_if_model(self, category: str, amounts: np.ndarray) -> None:
        """Fit an Isolation Forest on log1p(amounts) for a single category."""
        if len(amounts) < MIN_IF_SAMPLES:
            return

        X = np.log1p(amounts).reshape(-1, 1)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf = IsolationForest(
                contamination  = IF_CONTAMINATION,
                random_state   = IF_RANDOM_STATE,
                n_estimators   = 100,
                max_samples    = min(256, len(amounts)),
            )
            clf.fit(X)

        # Compute min/max of decision_function on training data for normalisation
        scores = clf.decision_function(X)
        self._if_models[category] = clf
        self._if_ranges[category] = (float(scores.min()), float(scores.max()))
        log.debug("IF model fitted for category='%s' on %d samples", category, len(amounts))

    def _fit(self, df: pd.DataFrame) -> None:
        df = self._normalise_df(df)

        # ── (category, state) level ─────────────────────────────────────────
        for (cat, state), grp in df.groupby(["category", "state"]):
            stats = self._compute_stats_for_group(
                grp["allocation_amount"].to_numpy(), cat, state, is_fallback=False
            )
            if stats:
                self._by_cat_state[(cat, state)] = stats

        # ── category level (fallback) ───────────────────────────────────────
        for cat, grp in df.groupby("category"):
            amounts = grp["allocation_amount"].to_numpy()
            stats = self._compute_stats_for_group(amounts, cat, None, is_fallback=True)
            if stats:
                self._by_cat[cat] = stats
            self._fit_if_model(cat, amounts)

        self._loaded = True
        log.info(
            "Benchmarks loaded: %d (cat,state) groups | %d cat groups | %d IF models",
            len(self._by_cat_state), len(self._by_cat), len(self._if_models),
        )

    # ── Public read API ──────────────────────────────────────────────────────

    def get_stats(self, category: str, state: str) -> Optional[GroupStats]:
        """Return the most specific GroupStats for (category, state), or None."""
        cat_n   = category.lower().strip()
        state_n = state.strip()

        stats = self._by_cat_state.get((cat_n, state_n))
        if stats:
            return stats

        # Fall back to category-level
        return self._by_cat.get(cat_n)

    def isolation_forest_score(
        self, category: str, allocation_amount: float
    ) -> Optional[float]:
        """
        Return a normalised Isolation Forest anomaly score in [0, 1].
        0 = very normal, 1 = extreme outlier.
        Returns None if no model is available for the category.
        """
        cat_n = category.lower().strip()
        clf   = self._if_models.get(cat_n)
        if clf is None:
            return None

        X     = np.log1p([[allocation_amount]])
        raw   = float(clf.decision_function(X)[0])

        score_min, score_max = self._if_ranges[cat_n]
        if score_max == score_min:
            return 0.5

        # decision_function: positive = normal, negative = anomaly
        # Invert and normalise so that large positive → score≈1 (outlier)
        normalised = (raw - score_max) / (score_min - score_max)
        return float(np.clip(normalised, 0.0, 1.0))

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def summary(self) -> dict:
        return {
            "cat_state_groups":  len(self._by_cat_state),
            "category_groups":   len(self._by_cat),
            "if_models_trained": len(self._if_models),
            "loaded":            self._loaded,
        }


# ---------------------------------------------------------------------------
# Module-level singleton (populated at app startup)
# ---------------------------------------------------------------------------

_store = BenchmarkStore()


def get_store() -> BenchmarkStore:
    return _store
