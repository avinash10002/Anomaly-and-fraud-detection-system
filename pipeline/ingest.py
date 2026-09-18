#!/usr/bin/env python3
"""
pipeline/ingest.py
==================
MPLADS CSV → PostgreSQL ingestion pipeline.

Usage
-----
    python pipeline/ingest.py --csv data/mplads.csv --db-url postgresql://mplad_user:mplad_secret@localhost:5432/mplad

Options
-------
    --csv        PATH     Path to the MPLADS CSV file (required)
    --db-url     URL      PostgreSQL connection string (or set DATABASE_URL env var)
    --batch-size INT      Rows per INSERT batch (default: 1000)
    --dry-run            Parse & clean only; do NOT write to DB
    --verbose            Print per-batch stats

Design decisions
----------------
* Delimiter is auto-detected (comma vs semicolon) from the first 8 KB.
* Missing values (empty string, 'N/A', 'NA', '-', '.', 'NULL', 'null') → None.
* recommended_date: parsed with multiple format attempts; NaT → NULL.
* allocation_amount: strip commas/₹/whitespace, coerce to float; NaN → NULL.
* STATUS / IDA APPROVAL values are enum-normalised (case-insensitive strip).
* project_id: UUID v5 from a fingerprint of (mp_name|work|recommended_date|allocation_amount).
  This makes re-ingestion of the same source file idempotent.
* raw_row_hash: SHA-256 of the raw CSV line.  The ON CONFLICT DO NOTHING
  upsert uses this as the dedup key, so partially-loaded runs can be resumed.
* NO coordinates, completion dates, or contractor names are fabricated.
"""

import argparse
import csv
import hashlib
import io
import logging
import os
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mplads.ingest")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace

# Canonical column names after snake_case conversion
COL_MP_NAME          = "mp_name"
COL_WORK             = "work"
COL_CATEGORY         = "category"
COL_STATE            = "state"
COL_CONSTITUENCY     = "constituency"
COL_IDA              = "ida"
COL_CITY             = "city"
COL_WARD             = "ward"
COL_BLOCK            = "block"
COL_VILLAGE          = "village"
COL_RECOMMENDED_DATE = "recommended_date"
COL_ALLOCATION_AMOUNT= "allocation_amount"
COL_IDA_APPROVAL     = "ida_approval"
COL_STATUS           = "status"
COL_HOUSE            = "house"

REQUIRED_COLS = {COL_MP_NAME, COL_WORK, COL_STATUS}

# Null sentinels
NULL_SENTINELS = {"", "n/a", "na", "-", ".", "null", "none", "nan", "nil"}

# STATUS normalisation map  (lower-stripped input → DB enum value)
STATUS_MAP = {
    "unsanctioned": "unsanctioned",
    "un-sanctioned": "unsanctioned",
    "sanctioned":   "sanctioned",
    "ongoing":      "ongoing",
    "on-going":     "ongoing",
    "completed":    "completed",
    "complete":     "completed",
}

# IDA APPROVAL normalisation map
IDA_APPROVAL_MAP = {
    "action pending":    "action_pending",
    "action-pending":    "action_pending",
    "approved by ida":   "approved_by_ida",
    "approved_by_ida":   "approved_by_ida",
    "rejected by ida":   "rejected_by_ida",
    "rejected_by_ida":   "rejected_by_ida",
}

# Date formats to try in order
DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d",
    "%d-%b-%Y", "%d %b %Y", "%b %d, %Y",
    "%d.%m.%Y", "%Y/%m/%d",
]

INSERT_SQL = """
    INSERT INTO mplads_project (
        id,
        mp_name, constituency, house,
        work, category, ida,
        status, ida_approval_status,
        state, city, ward, block, village,
        recommended_date, allocation_amount,
        raw_row_hash, source_file, ingested_at
    )
    VALUES %s
    ON CONFLICT (raw_row_hash) DO NOTHING
"""

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def detect_delimiter(path: Path) -> str:
    """Sniff the CSV delimiter from the first 8 KB of the file."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        sample = fh.read(8192)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
        log.info("Detected delimiter: %r", delim)
        return delim
    except csv.Error:
        log.warning("Could not sniff delimiter; defaulting to ','")
        return ","


def clean_col_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip, lowercase, and snake_case all column names."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s/\\-]+", "_", regex=True)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
        .str.strip("_")
    )
    return df


def normalise_null(val) -> Optional[str]:
    """Return None for blank/sentinel strings; else return stripped value."""
    if val is None:
        return None
    s = str(val).strip()
    return None if s.lower() in NULL_SENTINELS else s


def parse_date(val: Optional[str]) -> Optional[date]:
    """Try multiple date formats; return None on failure — never fabricate."""
    if val is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(val, format=fmt).date()
        except (ValueError, TypeError):
            pass
    # Last resort: let pandas guess
    try:
        result = pd.to_datetime(val, dayfirst=True, errors="coerce")
        return None if pd.isna(result) else result.date()
    except Exception:
        return None


def parse_amount(val: Optional[str]) -> Optional[float]:
    """Strip currency symbols / commas and coerce to float; None on failure."""
    if val is None:
        return None
    cleaned = (
        val.replace("₹", "").replace(",", "").replace(" ", "").strip()
    )
    try:
        result = float(cleaned)
        return None if (result != result) else result  # NaN guard
    except (ValueError, TypeError):
        return None


def normalise_status(val: Optional[str]) -> str:
    if val is None:
        return "unknown"
    key = val.strip().lower()
    return STATUS_MAP.get(key, "unknown")


def normalise_ida_approval(val: Optional[str]) -> str:
    if val is None:
        return "unknown"
    key = val.strip().lower()
    return IDA_APPROVAL_MAP.get(key, "unknown")


def make_project_id(mp_name: str, work: str,
                    rec_date: Optional[date],
                    amount: Optional[float]) -> uuid.UUID:
    """Deterministic UUID v5 from the four most-unique fields."""
    fingerprint = "|".join([
        mp_name or "",
        work or "",
        str(rec_date) if rec_date else "",
        str(round(amount, 2)) if amount is not None else "",
    ])
    return uuid.uuid5(UUID_NAMESPACE, fingerprint)


def row_hash(raw_line: str) -> str:
    """SHA-256 of the raw CSV line for dedup."""
    return hashlib.sha256(raw_line.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def load_csv(path: Path, delimiter: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Load CSV keeping ALL columns as str.
    Returns (DataFrame with clean col names, list of raw lines for hashing).
    """
    log.info("Loading %s …", path)
    df = pd.read_csv(
        path,
        sep=delimiter,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",
        encoding_errors="replace",
        engine="python",          # tolerates irregular quoting
        on_bad_lines="warn",
    )
    log.info("Loaded %d rows × %d columns", len(df), len(df.columns))

    df = clean_col_names(df)
    log.info("Cleaned column names: %s", list(df.columns))

    # Validate required columns exist
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"Required columns missing after rename: {missing}\n"
            f"Available columns: {list(df.columns)}"
        )

    # Read raw lines for per-row SHA-256 hashing
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw_lines = fh.readlines()

    # raw_lines[0] is the header; data starts at index 1
    return df, raw_lines[1:]


def process_row(row: pd.Series, raw_line: str, source_file: str) -> dict:
    """Transform a single DataFrame row into a dict ready for DB insert."""

    def get(col: str) -> Optional[str]:
        val = row.get(col)
        return normalise_null(val)

    mp_name  = get(COL_MP_NAME) or ""
    work     = get(COL_WORK)    or ""

    rec_date = parse_date(get(COL_RECOMMENDED_DATE))
    amount   = parse_amount(get(COL_ALLOCATION_AMOUNT))

    return {
        "id":                   str(make_project_id(mp_name, work, rec_date, amount)),
        "mp_name":              mp_name,
        "constituency":         get(COL_CONSTITUENCY),
        "house":                get(COL_HOUSE),
        "work":                 work,
        "category":             get(COL_CATEGORY),
        "ida":                  get(COL_IDA),
        "status":               normalise_status(get(COL_STATUS)),
        "ida_approval_status":  normalise_ida_approval(get(COL_IDA_APPROVAL)),
        "state":                get(COL_STATE),
        "city":                 get(COL_CITY),
        "ward":                 get(COL_WARD),
        "block":                get(COL_BLOCK),
        "village":              get(COL_VILLAGE),
        "recommended_date":     rec_date,
        "allocation_amount":    amount,
        "raw_row_hash":         row_hash(raw_line),
        "source_file":          source_file,
        "ingested_at":          "NOW()",
    }


def batch_insert(conn, rows: list[dict], dry_run: bool) -> tuple[int, int]:
    """
    Insert a batch of processed rows.
    Returns (inserted, skipped_duplicates).
    """
    if dry_run or not rows:
        return 0, 0

    values = [
        (
            r["id"],
            r["mp_name"],         r["constituency"],  r["house"],
            r["work"],            r["category"],      r["ida"],
            r["status"],          r["ida_approval_status"],
            r["state"],           r["city"],           r["ward"],
            r["block"],           r["village"],
            r["recommended_date"],r["allocation_amount"],
            r["raw_row_hash"],    r["source_file"],
        )
        for r in rows
    ]

    with conn.cursor() as cur:
        before = cur.rowcount
        psycopg2.extras.execute_values(
            cur,
            INSERT_SQL,
            values,
            template=None,
            page_size=len(values),
        )
        inserted = cur.rowcount if cur.rowcount >= 0 else len(values)

    conn.commit()
    skipped = len(rows) - inserted
    return inserted, skipped


def run(csv_path: Path, db_url: str, batch_size: int,
        dry_run: bool, verbose: bool) -> None:

    delimiter = detect_delimiter(csv_path)
    df, raw_lines = load_csv(csv_path, delimiter)
    source_file = csv_path.name

    conn = None
    if not dry_run:
        log.info("Connecting to database …")
        conn = psycopg2.connect(db_url)

    total_rows    = len(df)
    total_inserted = 0
    total_skipped  = 0
    total_errors   = 0

    log.info("Processing %d rows in batches of %d …", total_rows, batch_size)

    with tqdm(total=total_rows, unit="rows", desc="Ingesting") as pbar:
        batch: list[dict] = []

        for idx, (_, row) in enumerate(df.iterrows()):
            raw_line = raw_lines[idx] if idx < len(raw_lines) else ""
            try:
                record = process_row(row, raw_line, source_file)
                batch.append(record)
            except Exception as exc:
                total_errors += 1
                log.debug("Row %d skipped due to error: %s", idx, exc)

            if len(batch) >= batch_size:
                inserted, skipped = batch_insert(conn, batch, dry_run)
                total_inserted += inserted
                total_skipped  += skipped
                if verbose:
                    log.info(
                        "Batch %d–%d: +%d inserted, %d skipped",
                        idx - batch_size + 1, idx, inserted, skipped,
                    )
                batch.clear()

            pbar.update(1)

        # flush remainder
        if batch:
            inserted, skipped = batch_insert(conn, batch, dry_run)
            total_inserted += inserted
            total_skipped  += skipped

    if conn:
        conn.close()

    log.info("━" * 60)
    log.info("Done.")
    log.info("  Total rows processed : %d", total_rows)
    log.info("  Inserted             : %d", total_inserted)
    log.info("  Skipped (duplicates) : %d", total_skipped)
    log.info("  Errors (parse)       : %d", total_errors)
    if dry_run:
        log.info("  [DRY RUN — no data written to DB]")
    log.info("━" * 60)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Ingest MPLADS CSV into PostgreSQL mplads_project table."
    )
    parser.add_argument("--csv", default=None, type=Path,
                        help="Path to MPLADS CSV file (default: auto-detects MPLADS.csv or data/mplads.csv)")
    parser.add_argument("--db-url",     default=os.getenv("DATABASE_URL"),
                        help="PostgreSQL connection URL (or set DATABASE_URL)")
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="Rows per INSERT batch (default: 1000)")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Parse & clean only; skip DB writes")
    parser.add_argument("--verbose",    action="store_true",
                        help="Print per-batch statistics")
    args = parser.parse_args()

    csv_path = args.csv
    if not csv_path:
        for candidate in [Path("data/mplads.csv"), Path("MPLADS.csv"), Path("../MPLADS.csv")]:
            if candidate.exists():
                csv_path = candidate
                break

    if not csv_path or not csv_path.exists():
        log.error("CSV file not found. Provide --csv <path> or ensure MPLADS.csv is in the workspace.")
        sys.exit(1)

    args.csv = csv_path

    if not args.dry_run and not args.db_url:
        log.error("No database URL provided. Use --db-url or set DATABASE_URL.")
        sys.exit(1)

    run(
        csv_path   = args.csv,
        db_url     = args.db_url or "",
        batch_size = args.batch_size,
        dry_run    = args.dry_run,
        verbose    = args.verbose,
    )


if __name__ == "__main__":
    main()
