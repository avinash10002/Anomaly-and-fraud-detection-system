"""
db.py
=====
Shared Postgres repository for the MPLADS Anomaly Detector.

Provides real, read-only, parameterized access to `mplads_project` (plus the
`anomaly_flag` and `image_capture` tables that soft-reference it).  Synthetic
content is supplied only by the companion DemoRepository, which is active solely
when ENABLE_DEMO_DATA=true.

Design notes
------------
* All SQL uses %s placeholders with bound parameters — no string interpolation
  of user input (SQL-injection safe).
* `source_type` is derived per-record: real rows report `MPLADS_HISTORIC`; demo
  rows report `DEMO_SYNTHETIC`.
* A connection is attempted lazily with a short timeout; if Postgres is
  unreachable, `is_available()` returns False so callers can fall back to the
  demo store or raise a 503.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from mapping import (
    SOURCE_TYPE_DEMO,
    SOURCE_TYPE_HISTORIC,
    capture_as_dict,
    flag_as_dict,
    row_as_summary,
    status_is_incomplete,
    to_float_or_none,
)

log = logging.getLogger("risk_aggregator.db")

DEFAULT_CONNECT_TIMEOUT = 3


class DataUnavailableError(Exception):
    """Raised when no data source (DB or demo) is available for a query."""


# ---------------------------------------------------------------------------
# Connection / executor wrapper
# ---------------------------------------------------------------------------

class PostgresExecutor:
    """Thin, injectable wrapper around a psycopg2 connection."""

    def __init__(self, db_url: str = "", conn=None):
        self.db_url = db_url
        self._conn = conn
        self._connected = False
        if conn is not None:
            self._connected = True

    def is_available(self) -> bool:
        if self._connected:
            return True
        if not self.db_url:
            return False
        try:
            import psycopg2
            import psycopg2.extras  # noqa: F401
            self._conn = psycopg2.connect(self.db_url, connect_timeout=DEFAULT_CONNECT_TIMEOUT)
            self._conn.set_session(readonly=True, autocommit=True)
            self._connected = True
            return True
        except Exception as exc:
            log.warning("Postgres unavailable: %s", exc)
            self._connected = False
            return False

    def _cursor(self):
        import psycopg2.extras
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def query_all(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def query_one(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        rows = self.query_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Tuple = ()) -> int:
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount


# ---------------------------------------------------------------------------
# Postgres-backed repository
# ---------------------------------------------------------------------------

class PostgresRepository:
    """Real-data repository backed by the mplads_project schema."""

    def __init__(self, db_url: str = ""):
        self.executor = PostgresExecutor(db_url)

    # -- low-level helpers ---------------------------------------------------
    def is_available(self) -> bool:
        return self.executor.is_available()

    def project_count(self) -> int:
        row = self.executor.query_one(
            "SELECT COUNT(*) AS n FROM mplads_project;", ()
        )
        return int(row["n"]) if row else 0

    def entities(self) -> Dict[str, List[str]]:
        """Distinct DB-derived values for states, categories, MPs, IDAs, statuses."""
        def distinct(col: str, where: str = "") -> List[str]:
            sql = f"SELECT DISTINCT {col} AS v FROM mplads_project WHERE {col} IS NOT NULL {where} ORDER BY v;"
            return [r["v"] for r in self.executor.query_all(sql, ())]

        return {
            "states": distinct("state"),
            "categories": distinct("category"),
            "mps": distinct("mp_name"),
            "idas": distinct("ida"),
            "statuses": distinct("status"),
        }

    def sample_project_id(self) -> Optional[str]:
        row = self.executor.query_one(
            "SELECT id FROM mplads_project WHERE allocation_amount IS NOT NULL "
            "ORDER BY allocation_amount DESC LIMIT 1;", ()
        )
        return str(row["id"]) if row else None

    def suggestions(self) -> List[str]:
        ents = self.entities()
        sample = self.sample_project_id()
        prompts: List[str] = []
        if ents["states"]:
            prompts.append(f"Show unusually expensive road projects in {ents['states'][0]}")
        prompts.append("Which constituencies have the most pending projects?")
        if sample:
            prompts.append(f"What anomaly indicators were flagged for project {sample}?")
        if ents["mps"]:
            prompts.append(f"Summarize allocations for MP {ents['mps'][0]}")
        if ents["idas"]:
            prompts.append(f"Summarize IDA {ents['idas'][0]} allocations")
        if ents["categories"]:
            prompts.append(f"List highest allocation {ents['categories'][0]} projects")
        prompts.append("Show the review queue of pending anomaly flags")
        return prompts[:8]

    # -- project list / detail ----------------------------------------------
    def list_projects(
        self,
        state: Optional[str] = None,
        constituency: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        sql = (
            "SELECT p.id, p.work, p.category, p.state, p.constituency, p.mp_name, "
            "p.allocation_amount, p.recommended_date, p.status, p.city, p.block, "
            "(SELECT COUNT(*) FROM anomaly_flag f WHERE f.project_id = p.id) AS anomaly_count "
            "FROM mplads_project p WHERE 1=1"
        )
        params: List[Any] = []
        if state:
            sql += " AND p.state ILIKE %s"; params.append(f"%{state}%")
        if constituency:
            sql += " AND p.constituency ILIKE %s"; params.append(f"%{constituency}%")
        if category:
            sql += " AND (p.category ILIKE %s OR p.work ILIKE %s)"; params += [f"%{category}%", f"%{category}%"]
        if status:
            sql += " AND p.status ILIKE %s"; params.append(f"%{status}%")
        if search:
            sql += " AND (p.work ILIKE %s OR p.mp_name ILIKE %s)"; params += [f"%{search}%", f"%{search}%"]

        count_sql = "SELECT COUNT(*) AS n FROM (" + sql + " ) c"
        total = self.executor.query_one(count_sql, tuple(params))[ "n"] if True else 0
        total = int(total) if total else 0

        sql += " ORDER BY p.allocation_amount DESC NULLS LAST LIMIT %s OFFSET %s;"
        params += [page_size, (page - 1) * page_size]
        rows = self.executor.query_all(sql, tuple(params))
        data = [row_as_summary(r) for r in rows]
        return {"data": data, "total": total, "page": page, "page_size": page_size}

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        row = self.executor.query_one(
            "SELECT p.id, p.work, p.category, p.state, p.constituency, p.mp_name, "
            "p.house, p.ida, p.allocation_amount, p.recommended_date, p.status, "
            "p.city, p.block, p.ward, p.village, p.allocation_amount "
            "FROM mplads_project p WHERE p.id = %s;",
            (project_id,),
        )
        if row is None:
            return None
        p = row_as_summary(row)
        p["source_type"] = SOURCE_TYPE_HISTORIC
        p["flags"] = self.get_project_flags(project_id)
        p["inspections"] = self.get_project_captures(project_id)
        p["financial_analysis"] = None
        p["similar_projects"] = []
        p["risk_breakdown"] = None
        return p

    def get_project_flags(self, project_id: str) -> List[Dict[str, Any]]:
        rows = self.executor.query_all(
            "SELECT id, project_id, source_engine, score, reason_text, review_status, "
            "reviewer_id, source_type, created_at FROM anomaly_flag "
            "WHERE project_id = %s ORDER BY score DESC NULLS LAST;",
            (project_id,),
        )
        return [flag_as_dict(r) for r in rows]

    def get_project_captures(self, project_id: str) -> List[Dict[str, Any]]:
        rows = self.executor.query_all(
            "SELECT id, project_id, source, capture_date, image_url, defect_class, "
            "defect_confidence, source_type, created_at FROM image_capture "
            "WHERE project_id = %s ORDER BY capture_date;",
            (project_id,),
        )
        return [capture_as_dict(r) for r in rows]

    def dashboard_stats(self) -> Dict[str, Any]:
        base = self.executor.query_one(
            "SELECT COUNT(*) AS total, COALESCE(SUM(allocation_amount),0) AS alloc "
            "FROM mplads_project;"
        )
        status_rows = self.executor.query_all(
            "SELECT status, COUNT(*) AS count FROM mplads_project GROUP BY status;"
        )
        flag_rows = self.executor.query_all(
            "SELECT review_status, COUNT(*) AS count FROM anomaly_flag GROUP BY review_status;"
        )
        # Risk distribution derived from real flag scores (not fabricated).
        flagged = self.executor.query_one(
            "SELECT COUNT(DISTINCT project_id) AS n, "
            "COUNT(*) FILTER (WHERE score >= 0.7) AS high, "
            "COUNT(*) FILTER (WHERE score >= 0.3 AND score < 0.7) AS med "
            "FROM anomaly_flag;"
        )
        statuses = {r["status"].lower(): r["count"] for r in status_rows}
        flags_by_status = {r["review_status"].lower(): r["count"] for r in flag_rows}
        return {
            "total_projects": int(base["total"]) if base else 0,
            "total_allocation": to_float_or_none(base["alloc"]) or 0.0,
            "status_distribution": statuses,
            "risk_distribution": {
                "high": int(flagged["high"]) if flagged else 0,
                "medium": int(flagged["med"]) if flagged else 0,
                "low": (int(base["total"]) if base else 0) - int(flagged["high"] if flagged else 0) - int(flagged["med"] if flagged else 0),
            },
            "total_anomalies_pending": flags_by_status.get("pending", 0),
            "total_anomalies_confirmed": flags_by_status.get("confirmed", 0),
            "total_anomalies_dismissed": flags_by_status.get("dismissed", 0),
        }

    # -- assistant intent queries --------------------------------------------
    def highest_allocation(
        self, state: Optional[str] = None, category: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT p.id, p.work, p.category, p.state, p.constituency, p.mp_name, "
            "p.allocation_amount, p.status, "
            "(SELECT COUNT(*) FROM anomaly_flag f WHERE f.project_id = p.id) AS anomaly_count "
            "FROM mplads_project p WHERE 1=1"
        )
        params: List[Any] = []
        if state:
            sql += " AND p.state ILIKE %s"; params.append(state)
        if category:
            sql += " AND (p.category ILIKE %s OR p.work ILIKE %s)"; params += [f"%{category}%", f"%{category}%"]
        sql += " ORDER BY p.allocation_amount DESC NULLS LAST LIMIT %s;"
        params.append(limit)
        return [row_as_summary(r) for r in self.executor.query_all(sql, tuple(params))]

    def project_search(
        self,
        keyword: Optional[str] = None,
        state: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT p.id, p.work, p.category, p.state, p.constituency, p.mp_name, "
            "p.allocation_amount, p.status, "
            "(SELECT COUNT(*) FROM anomaly_flag f WHERE f.project_id = p.id) AS anomaly_count "
            "FROM mplads_project p WHERE 1=1"
        )
        params: List[Any] = []
        if keyword:
            sql += " AND (p.work ILIKE %s OR p.mp_name ILIKE %s)"; params += [f"%{keyword}%", f"%{keyword}%"]
        if state:
            sql += " AND p.state ILIKE %s"; params.append(state)
        if status:
            sql += " AND p.status ILIKE %s"; params.append(status)
        sql += " ORDER BY p.allocation_amount DESC NULLS LAST LIMIT %s;"
        params.append(limit)
        return [row_as_summary(r) for r in self.executor.query_all(sql, tuple(params))]

    def constituency_pending(
        self, state: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT constituency, state, COUNT(*) AS pending_count, "
            "COALESCE(SUM(allocation_amount),0) AS total_allocation, "
            "MIN(id) AS sample_id FROM mplads_project "
            "WHERE status IN ('unsanctioned','ongoing','unknown') OR ida_approval_status='action_pending'"
        )
        params: List[Any] = []
        if state:
            sql += " AND state ILIKE %s"; params.append(state)
        sql += " GROUP BY constituency, state ORDER BY pending_count DESC LIMIT %s;"
        params.append(limit)
        return [self._pending_row(r) for r in self.executor.query_all(sql, tuple(params))]

    @staticmethod
    def _pending_row(r: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "constituency": r.get("constituency"),
            "state": r.get("state"),
            "pending_count": int(r["pending_count"]),
            "total_allocation": to_float_or_none(r.get("total_allocation")) or 0.0,
            "sample_id": str(r["sample_id"]) if r.get("sample_id") else "",
        }

    def flag_explanation(self, project_id: str) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        proj = self.get_project(project_id)
        if proj is None:
            return None
        return proj, proj.get("flags", [])

    def mp_summary(self, mp_name: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        sql = (
            "SELECT mp_name AS mp_name, COUNT(*) AS project_count, "
            "COALESCE(SUM(allocation_amount),0) AS total_allocation, "
            "COUNT(CASE WHEN (SELECT COUNT(*) FROM anomaly_flag f WHERE f.project_id=p.id)>0 THEN 1 END) AS flagged "
            "FROM mplads_project p WHERE 1=1"
        )
        params: List[Any] = []
        if mp_name:
            sql += " AND mp_name ILIKE %s"; params.append(f"%{mp_name}%")
        sql += " GROUP BY mp_name ORDER BY total_allocation DESC NULLS LAST LIMIT %s;"
        params.append(limit)
        out = []
        for r in self.executor.query_all(sql, tuple(params)):
            out.append({
                "mp_name": r["mp_name"],
                "project_count": int(r["project_count"]),
                "total_allocation": to_float_or_none(r["total_allocation"]) or 0.0,
                "flagged_count": int(r["flagged"]),
            })
        return out

    def ida_summary(self, ida: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        sql = (
            "SELECT ida AS ida, COUNT(*) AS project_count, "
            "COALESCE(SUM(allocation_amount),0) AS total_allocation "
            "FROM mplads_project p WHERE 1=1"
        )
        params: List[Any] = []
        if ida:
            sql += " AND ida ILIKE %s"; params.append(f"%{ida}%")
        sql += " GROUP BY ida ORDER BY total_allocation DESC NULLS LAST LIMIT %s;"
        params.append(limit)
        out = []
        for r in self.executor.query_all(sql, tuple(params)):
            out.append({
                "ida": r["ida"],
                "project_count": int(r["project_count"]),
                "total_allocation": to_float_or_none(r["total_allocation"]) or 0.0,
            })
        return out

    def category_summary(self, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        sql = (
            "SELECT category, COUNT(*) AS project_count, "
            "COALESCE(SUM(allocation_amount),0) AS total_allocation "
            "FROM mplads_project WHERE 1=1"
        )
        params: List[Any] = []
        if category:
            sql += " AND category ILIKE %s"; params.append(f"%{category}%")
        sql += " GROUP BY category ORDER BY total_allocation DESC NULLS LAST LIMIT %s;"
        params.append(limit)
        out = []
        for r in self.executor.query_all(sql, tuple(params)):
            out.append({
                "category": r["category"],
                "project_count": int(r["project_count"]),
                "total_allocation": to_float_or_none(r["total_allocation"]) or 0.0,
            })
        return out

    def review_queue(self, limit: int = 10) -> List[Dict[str, Any]]:
        sql = (
            "SELECT f.id, f.project_id, p.work, p.state, p.constituency, "
            "f.source_engine, f.score, f.reason_text, f.review_status, f.flagged_at, f.source_type "
            "FROM anomaly_flag f JOIN mplads_project p ON p.id = f.project_id "
            "WHERE f.review_status = 'pending' "
            "ORDER BY f.score DESC NULLS LAST LIMIT %s;"
        )
        out = []
        for r in self.executor.query_all(sql, (limit,)):
            out.append({
                "id": str(r["id"]),
                "project_id": str(r["project_id"]),
                "title": r.get("work"),
                "state": r.get("state"),
                "constituency": r.get("constituency"),
                "source_engine": r.get("source_engine"),
                "score": to_float_or_none(r.get("score")),
                "reason_text": r.get("reason_text"),
                "review_status": r.get("review_status"),
                "flagged_at": r.get("flagged_at"),
                "source_type": r.get("source_type") or SOURCE_TYPE_HISTORIC,
            })
        return out

    def works_near_me(self, role: str = "official") -> List[Dict[str, Any]]:
        # Real MPLADS records carry no GPS — never fabricate coordinates.
        return []

    def administrative(self) -> List[Dict[str, Any]]:
        rows = self.executor.query_all(
            "SELECT DISTINCT state, constituency FROM mplads_project "
            "WHERE state IS NOT NULL AND constituency IS NOT NULL ORDER BY state, constituency;"
        )
        states: Dict[str, List[str]] = {}
        for r in rows:
            states.setdefault(r["state"], []).append(r["constituency"])
        for arr in states.values():
            arr.sort()
        return [{"state": s, "constituencies": cs} for s, cs in sorted(states.items())]

    def patch_flag(self, flag_id: str, review_status: str, reviewer_id: Optional[str]) -> Optional[Dict[str, Any]]:
        row = self.executor.query_one(
            "UPDATE anomaly_flag SET review_status=%s, reviewer_id=%s, updated_at=NOW() "
            "WHERE id=%s RETURNING id, project_id, source_engine, score, reason_text, review_status, reviewer_id;",
            (review_status, reviewer_id, flag_id),
        )
        return flag_as_dict(row) if row else None

    def data_mode(self) -> str:
        return "database"


# ---------------------------------------------------------------------------
# Facade: DB first, demo fallback, 503 when neither available
# ---------------------------------------------------------------------------

class Repository:
    """
    Selects the active data source at runtime:
      1. Postgres (real data) when reachable.
      2. In-memory DemoRepository when ENABLE_DEMO_DATA=true and DB is down.
      3. Otherwise raises DataUnavailableError (→ HTTP 503 with an actionable
         data-source error; no synthetic content is ever silently served).
    """

    def __init__(self, db_url: str = "", enable_demo: bool = False, demo_repo=None):
        self.db_url = db_url
        self.enable_demo = enable_demo
        self._pg = PostgresRepository(db_url) if db_url else None
        self._demo = demo_repo
        self._active: Any = None
        self._active_is_demo = False
        self._probe()

    def _probe(self) -> None:
        if self._pg and self._pg.is_available():
            self._active = self._pg
            self._active_is_demo = False
            self.records_available = self._pg.project_count()
            self.data_mode = "database"
            return
        if self.enable_demo and self._demo is not None:
            self._active = self._demo
            self._active_is_demo = True
            self.records_available = self._demo.project_count()
            self.data_mode = "demo"
            return
        self._active = None
        self._active_is_demo = False
        self.records_available = 0
        self.data_mode = "unavailable"

    # The active backend may change if the DB flaps; re-probe on each access.
    def active(self) -> Any:
        if self._active is None or (self._pg is not None and not self._pg.is_available() and not self._active_is_demo):
            self._probe()
        if self._active is None:
            raise DataUnavailableError(
                "No data source available. Postgres is unreachable and "
                "ENABLE_DEMO_DATA is disabled. Enable a database connection "
                "(DATABASE_URL) or set ENABLE_DEMO_DATA=true for synthetic demo data."
            )
        return self._active

    def is_demo(self) -> bool:
        self.active()  # raises if unavailable
        return self._active_is_demo

    def __getattr__(self, name: str):
        # Delegate every high-level method to the active backend.
        return getattr(self.active(), name)
