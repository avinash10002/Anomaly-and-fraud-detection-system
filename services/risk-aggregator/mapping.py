"""
mapping.py
==========
Shared field/type inference helpers used by both the Postgres-backed
repository (real data) and the in-memory demo repository. Keeping these
in one place guarantees identical field mapping regardless of which
data source is active.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

SOURCE_TYPE_HISTORIC = "MPLADS_HISTORIC"
SOURCE_TYPE_DEMO = "DEMO_SYNTHETIC"

# Category (free text from mplads_project.category) → coarse project type.
_TYPE_KEYWORDS: Dict[str, str] = [
    ("road", "road"),
    ("bridge", "road"),
    ("highway", "road"),
    ("pathway", "road"),
    ("flyover", "road"),
    ("street", "road"),
]
_TYPE_KEYWORDS = {
    "road": ["road", "bridge", "highway", "pathway", "flyover", "street", "drainage"],
    "building": ["building", "office", "centre", "center", "school", "auditorium",
                  "sitting place", "hall", "hospital", "dispensary", "health", "stadium",
                  "gymnasium", "community hall", "police"],
    "park": ["park", "stadium", "sports", "ground", "playground", "playfield", "recreation",
              "green", "garden", "jug", "cultural"],
    "other": ["water", "supply", "irrigation", "well", "ponds", "solar", "scheme",
               "channel", "drain", "sanitation", "electric"],
}

# mplads_project.status enum values that represent work that is not yet complete.
_PENDING_STATUS_VALUES = {"unsanctioned", "sanctioned", "ongoing", "unknown"}


def infer_project_type(category: Optional[str], work: Optional[str]) -> str:
    """
    Derive a coarse project type from the category/work text.
    Real MPLADS records only carry a free-text category, so this is a
    keyword classification (not a hardcoded whitelist of states).
    """
    haystack = " ".join([category or "", work or ""]).lower()
    for ptype, keywords in _TYPE_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return ptype
    return "other"


def resolve_category(category: Optional[str], ptype: str) -> str:
    """
    Prefer the stored category. Fall back to a type-derived label when the
    stored value is empty or the CSV sentinel 'Normal/Others'.
    """
    cat = (category or "").strip()
    if not cat or cat.lower() == "normal/others":
        return {
            "road": "Roads and Bridges",
            "building": "Community Infrastructure",
            "park": "Sports / Recreation",
            "other": "Other Works",
        }.get(ptype, "Other Works")
    return cat


def status_is_incomplete(status: Optional[str]) -> bool:
    """A project counts as 'pending/incomplete' if its status is not 'completed'."""
    s = (status or "").strip().lower()
    return s in _PENDING_STATUS_VALUES or s == ""


def cost_to_float(value: Any) -> Optional[float]:
    """Coerce a DB NUMERIC/None to a clean float (or None)."""
    if value is None:
        return None
    try:
        f = float(value)
        return f if f == f else None  # NaN guard
    except (TypeError, ValueError):
        return None


def to_float_or_none(value: Any) -> Optional[float]:
    return cost_to_float(value)


def row_as_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a raw mplads_project row into a summary dict for the API."""
    work = (row.get("work") or "").strip()
    ptype = infer_project_type(row.get("category"), work)
    return {
        "id": str(row["id"]),
        "title": work or row.get("title") or "Untitled Work",
        "work": work,
        "type": ptype,
        "category": resolve_category(row.get("category"), ptype),
        "state": (row.get("state") or "").strip() or None,
        "district": row.get("district"),  # NULL on real mplads_project
        "constituency": row.get("constituency"),
        "mp_name": row.get("mp_name"),
        "contractor_name": row.get("contractor_name"),
        "cost": cost_to_float(row.get("allocation_amount") or row.get("cost")),
        "sanction_date": row.get("recommended_date") or row.get("sanction_date"),
        "completion_date": row.get("completion_date"),
        "status": (row.get("status") or "unknown").lower(),
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "has_synthetic_coords": bool(row.get("has_synthetic_coords")),
        "source_type": row.get("source_type") or SOURCE_TYPE_HISTORIC,
        "anomaly_count": row.get("anomaly_count", 0),
        "risk_level": (row.get("risk_level") or "low").lower(),
        "risk_score": row.get("risk_score"),
    }


def flag_as_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "project_id": str(row["project_id"]),
        "source_engine": row.get("source_engine"),
        "score": to_float_or_none(row.get("score")),
        "reason_text": row.get("reason_text") or "",
        "review_status": (row.get("review_status") or "pending").lower(),
        "reviewer_id": row.get("reviewer_id"),
        "flagged_at": row.get("flagged_at") or row.get("created_at"),
        "source_type": row.get("source_type") or SOURCE_TYPE_HISTORIC,
    }


def capture_as_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "project_id": str(row["project_id"]),
        "source": row.get("source"),
        "capture_date": row.get("capture_date"),
        "image_url": row.get("image_url"),
        "defect_class": row.get("defect_class"),
        "defect_confidence": to_float_or_none(row.get("defect_confidence")),
        "source_type": row.get("source_type") or SOURCE_TYPE_HISTORIC,
    }
