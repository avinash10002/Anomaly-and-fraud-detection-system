#!/usr/bin/env python3
"""
pipeline/quality_report.py
===========================
Post-ingestion data-quality report for the mplads_project table.

Outputs
-------
  • Printed summary to stdout
  • Markdown file at reports/quality_report.md

Usage
-----
    python pipeline/quality_report.py --db-url postgresql://mplad_user:mplad_secret@localhost:5432/mplad
    python pipeline/quality_report.py          # uses DATABASE_URL env var
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from tabulate import tabulate


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def q(conn, sql: str, params=None) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def scalar(conn, sql: str, params=None):
    rows = q(conn, sql, params)
    if not rows:
        return None
    return list(rows[0].values())[0]


# ---------------------------------------------------------------------------
# Individual report sections
# ---------------------------------------------------------------------------

def section_overview(conn) -> str:
    total = scalar(conn, "SELECT COUNT(*) FROM mplads_project")
    src   = q(conn, "SELECT source_file, COUNT(*) AS rows FROM mplads_project GROUP BY 1 ORDER BY 2 DESC")
    ing   = scalar(conn, "SELECT MIN(ingested_at) FROM mplads_project")

    lines = [
        "## Overview\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total rows | **{total:,}** |",
        f"| Source file(s) | {', '.join(r['source_file'] for r in src)} |",
        f"| Earliest ingest | {ing} |",
        f"| Report generated | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        "",
    ]
    return "\n".join(lines)


def section_status_distribution(conn) -> str:
    rows = q(conn, """
        SELECT status, COUNT(*) AS cnt,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM mplads_project
        GROUP BY status
        ORDER BY cnt DESC
    """)
    table = tabulate(
        [(r["status"], f"{r['cnt']:,}", f"{r['pct']}%") for r in rows],
        headers=["Status", "Count", "% of total"],
        tablefmt="github",
    )
    return f"## Status Distribution\n\n{table}\n"


def section_ida_approval_distribution(conn) -> str:
    rows = q(conn, """
        SELECT ida_approval_status, COUNT(*) AS cnt,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM mplads_project
        GROUP BY ida_approval_status
        ORDER BY cnt DESC
    """)
    table = tabulate(
        [(r["ida_approval_status"], f"{r['cnt']:,}", f"{r['pct']}%") for r in rows],
        headers=["IDA Approval", "Count", "% of total"],
        tablefmt="github",
    )
    return f"## IDA Approval Distribution\n\n{table}\n"


def section_null_rates(conn) -> str:
    total = scalar(conn, "SELECT COUNT(*) FROM mplads_project")

    columns = [
        "mp_name", "constituency", "house", "work", "category", "ida",
        "state", "city", "ward", "block", "village",
        "recommended_date", "allocation_amount",
    ]

    rows_out = []
    for col in columns:
        null_count = scalar(conn, f"SELECT COUNT(*) FROM mplads_project WHERE {col} IS NULL")
        pct = round(100.0 * null_count / total, 1) if total else 0
        rows_out.append((col, f"{null_count:,}", f"{pct}%"))

    table = tabulate(rows_out, headers=["Column", "Null Count", "Null %"], tablefmt="github")
    return f"## Null-Field Rates\n\n{table}\n"


def section_date_range(conn) -> str:
    row = q(conn, """
        SELECT
            MIN(recommended_date)  AS earliest,
            MAX(recommended_date)  AS latest,
            COUNT(recommended_date) AS parsed_count,
            COUNT(*) - COUNT(recommended_date) AS unparsed_count
        FROM mplads_project
    """)[0]
    lines = [
        "## Recommended Date Range\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Earliest | {row['earliest']} |",
        f"| Latest | {row['latest']} |",
        f"| Parsed (non-null) | {row['parsed_count']:,} |",
        f"| Unparsed (null) | {row['unparsed_count']:,} |",
        "",
    ]
    return "\n".join(lines)


def section_amount_stats(conn) -> str:
    row = q(conn, """
        SELECT
            COUNT(allocation_amount)                        AS count_non_null,
            COUNT(*) - COUNT(allocation_amount)             AS count_null,
            MIN(allocation_amount)                          AS min_amt,
            PERCENTILE_CONT(0.25) WITHIN GROUP
                (ORDER BY allocation_amount)                AS p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP
                (ORDER BY allocation_amount)                AS median,
            PERCENTILE_CONT(0.75) WITHIN GROUP
                (ORDER BY allocation_amount)                AS p75,
            MAX(allocation_amount)                          AS max_amt,
            SUM(allocation_amount)                          AS total_amt
        FROM mplads_project
    """)[0]

    def fmt(v):
        if v is None:
            return "N/A"
        try:
            return f"₹{float(v):,.2f}"
        except Exception:
            return str(v)

    lines = [
        "## Allocation Amount Statistics\n",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Non-null rows | {row['count_non_null']:,} |",
        f"| Null rows | {row['count_null']:,} |",
        f"| Minimum | {fmt(row['min_amt'])} |",
        f"| 25th percentile | {fmt(row['p25'])} |",
        f"| Median | {fmt(row['median'])} |",
        f"| 75th percentile | {fmt(row['p75'])} |",
        f"| Maximum | {fmt(row['max_amt'])} |",
        f"| Total (sum) | {fmt(row['total_amt'])} |",
        "",
    ]
    return "\n".join(lines)


def section_top_states(conn) -> str:
    rows = q(conn, """
        SELECT state, COUNT(*) AS cnt
        FROM mplads_project
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY cnt DESC
        LIMIT 15
    """)
    table = tabulate(
        [(r["state"], f"{r['cnt']:,}") for r in rows],
        headers=["State", "Count"],
        tablefmt="github",
    )
    return f"## Top 15 States by Row Count\n\n{table}\n"


def section_top_categories(conn) -> str:
    rows = q(conn, """
        SELECT COALESCE(category, '(null)') AS category, COUNT(*) AS cnt
        FROM mplads_project
        GROUP BY category
        ORDER BY cnt DESC
        LIMIT 20
    """)
    table = tabulate(
        [(r["category"], f"{r['cnt']:,}") for r in rows],
        headers=["Category", "Count"],
        tablefmt="github",
    )
    return f"## Top 20 Categories\n\n{table}\n"


def section_top_ida(conn) -> str:
    rows = q(conn, """
        SELECT COALESCE(ida, '(null)') AS ida, COUNT(*) AS cnt
        FROM mplads_project
        GROUP BY ida
        ORDER BY cnt DESC
        LIMIT 15
    """)
    table = tabulate(
        [(r["ida"], f"{r['cnt']:,}") for r in rows],
        headers=["IDA (Implementing Agency)", "Count"],
        tablefmt="github",
    )
    return f"## Top 15 Implementing Agencies (IDA)\n\n{table}\n"


def section_yearly_trend(conn) -> str:
    rows = q(conn, """
        SELECT
            EXTRACT(YEAR FROM recommended_date)::INT AS year,
            COUNT(*)                                  AS projects,
            SUM(allocation_amount)                    AS total_amount
        FROM mplads_project
        WHERE recommended_date IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """)
    table = tabulate(
        [
            (r["year"], f"{r['projects']:,}",
             f"₹{float(r['total_amount']):,.0f}" if r["total_amount"] else "N/A")
            for r in rows
        ],
        headers=["Year", "Projects", "Total Allocated"],
        tablefmt="github",
    )
    return f"## Yearly Trend (by Recommended Date)\n\n{table}\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_report(conn) -> str:
    sections = [
        "# MPLADS Data Quality Report\n",
        "_Auto-generated by `pipeline/quality_report.py`_\n",
        "---\n",
        section_overview(conn),
        section_status_distribution(conn),
        section_ida_approval_distribution(conn),
        section_null_rates(conn),
        section_date_range(conn),
        section_amount_stats(conn),
        section_top_states(conn),
        section_top_categories(conn),
        section_top_ida(conn),
        section_yearly_trend(conn),
    ]
    return "\n".join(sections)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate a data-quality report for mplads_project."
    )
    parser.add_argument(
        "--db-url", default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL (or set DATABASE_URL)"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/quality_report.md"),
        help="Output path for Markdown report (default: reports/quality_report.md)"
    )
    args = parser.parse_args()

    if not args.db_url:
        print("ERROR: No database URL. Use --db-url or set DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    print("Connecting to database …")
    conn = psycopg2.connect(args.db_url)

    print("Running quality checks …")
    report_md = build_report(conn)
    conn.close()

    # Write to file
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_md, encoding="utf-8")
    print(f"\nReport written to: {args.output}\n")

    # Also print to stdout
    print(report_md)


if __name__ == "__main__":
    main()
