"""
tests/conftest.py
=================
Shared fixtures for financial-engine tests.

Synthetic data design
---------------------
Mirrors the real MPLADS allocation distribution:
  - 'road'    in 'Bihar':         ~₹5L–₹40L, median ≈ ₹18L
  - 'road'    in 'Maharashtra':   ~₹8L–₹80L, median ≈ ₹35L
  - 'drainage' in 'Bihar':        ~₹3L–₹20L, median ≈ ₹9L
  - 'borewell' in 'Rajasthan':    ~₹1L–₹10L, median ≈ ₹4L

Clear outlier cases:
  - A ₹3 crore road project in Bihar (>> IQR upper fence)
  - A ₹50,000 drainage project in Bihar (<< IQR lower fence)

These match real category names from the MPLADS dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from benchmarks import BenchmarkStore


def _make_synthetic_df(seed: int = 42) -> pd.DataFrame:
    """
    Build a realistic synthetic allocation DataFrame without any DB dependency.
    All category/state combos have enough rows to compute benchmarks.
    """
    rng = np.random.default_rng(seed)

    records = []

    # ── road / Bihar  (n=120, median ≈ 18L) ─────────────────────────────────
    road_bihar = np.clip(
        rng.lognormal(mean=np.log(1_800_000), sigma=0.6, size=120),
        200_000, 6_000_000,
    )
    for v in road_bihar:
        records.append({"category": "road", "state": "Bihar", "allocation_amount": v})

    # ── road / Maharashtra  (n=80, median ≈ 35L) ─────────────────────────────
    road_mh = np.clip(
        rng.lognormal(mean=np.log(3_500_000), sigma=0.55, size=80),
        500_000, 12_000_000,
    )
    for v in road_mh:
        records.append({"category": "road", "state": "Maharashtra", "allocation_amount": v})

    # ── drainage / Bihar  (n=55, median ≈ 9L) ────────────────────────────────
    drain_bihar = np.clip(
        rng.lognormal(mean=np.log(900_000), sigma=0.65, size=55),
        100_000, 3_000_000,
    )
    for v in drain_bihar:
        records.append({"category": "drainage", "state": "Bihar", "allocation_amount": v})

    # ── borewell / Rajasthan  (n=40, median ≈ 4L) ────────────────────────────
    bore_raj = np.clip(
        rng.lognormal(mean=np.log(400_000), sigma=0.55, size=40),
        80_000, 1_500_000,
    )
    for v in bore_raj:
        records.append({"category": "borewell", "state": "Rajasthan", "allocation_amount": v})

    # ── community hall / UP  (n=30, median ≈ 22L) ────────────────────────────
    hall_up = np.clip(
        rng.lognormal(mean=np.log(2_200_000), sigma=0.5, size=30),
        500_000, 8_000_000,
    )
    for v in hall_up:
        records.append({"category": "community hall", "state": "Uttar Pradesh", "allocation_amount": v})

    # ── Tiny group (n=3) — should fall back gracefully ───────────────────────
    for v in [500_000, 550_000, 480_000]:
        records.append({"category": "park", "state": "Goa", "allocation_amount": v})

    return pd.DataFrame(records)


@pytest.fixture(scope="module")
def synthetic_df() -> pd.DataFrame:
    return _make_synthetic_df()


@pytest.fixture(scope="module")
def loaded_store(synthetic_df) -> BenchmarkStore:
    """BenchmarkStore pre-loaded with synthetic data — no DB required."""
    store = BenchmarkStore()
    store.load_from_dataframe(synthetic_df)
    return store
