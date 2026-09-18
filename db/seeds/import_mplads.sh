#!/usr/bin/env bash
# =============================================================================
# db/seeds/import_mplads.sh
# =============================================================================
# One-shot local-dev script: installs deps, runs the migration, ingests the
# CSV, and generates the quality report.
#
# Usage
# -----
#   # From the repo root:
#   bash db/seeds/import_mplads.sh data/mplads.csv
#
#   # Or with an explicit DB URL:
#   DATABASE_URL=postgresql://user:pass@host:5432/mplad \
#     bash db/seeds/import_mplads.sh data/mplads.csv
#
# Requirements
# ------------
#   • Python 3.11+  (python3 / python on PATH)
#   • psql          (postgresql-client)
#   • Docker Compose stack running  (or a local Postgres instance)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve script location so paths work from any working directory
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIPELINE_DIR="$REPO_ROOT/pipeline"
MIGRATIONS_DIR="$REPO_ROOT/db/migrations"

# ---------------------------------------------------------------------------
# Argument / environment handling
# ---------------------------------------------------------------------------
CSV_FILE="${1:-}"
if [[ -z "$CSV_FILE" ]]; then
    echo "ERROR: CSV file path required."
    echo "Usage: bash db/seeds/import_mplads.sh <path/to/mplads.csv>"
    exit 1
fi

if [[ ! -f "$CSV_FILE" ]]; then
    echo "ERROR: File not found: $CSV_FILE"
    exit 1
fi

DB_URL="${DATABASE_URL:-postgresql://mplad_user:mplad_secret@localhost:5432/mplad}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  MPLADS Local Dev Import"
echo "  CSV  : $CSV_FILE"
echo "  DB   : $DB_URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ---------------------------------------------------------------------------
# Step 1: Install Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 1/4 — Installing Python dependencies …"
cd "$PIPELINE_DIR"
if [[ -d ".venv" ]]; then
    echo "  Existing .venv found — using it."
else
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✓ Dependencies ready."

# ---------------------------------------------------------------------------
# Step 2: Apply migrations 002 and 003 (idempotent - IF NOT EXISTS guards in SQL)
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 2/5 — Applying migrations 002 and 003 …"
psql "$DB_URL" \
     --single-transaction \
     --set ON_ERROR_STOP=1 \
     -f "$MIGRATIONS_DIR/002_mplads_ingestion.sql" \
  && echo "  ✓ Migration 002 applied (or already up to date)." \
  || echo "  ⚠ Migration 002 had errors (possibly already applied — check output above)."

if [[ -f "$MIGRATIONS_DIR/003_add_source_type.sql" ]]; then
    psql "$DB_URL" \
         --single-transaction \
         --set ON_ERROR_STOP=1 \
         -f "$MIGRATIONS_DIR/003_add_source_type.sql" \
      && echo "  ✓ Migration 003 applied (or already up to date)." \
      || echo "  ⚠ Migration 003 had errors (check output above)."
fi

# ---------------------------------------------------------------------------
# Step 3: Run the ingestion pipeline
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 3/5 — Ingesting CSV …"
python3 "$PIPELINE_DIR/ingest.py" \
    --csv   "$CSV_FILE" \
    --db-url "$DB_URL" \
    --batch-size 2000 \
    --verbose
echo "  ✓ Ingestion complete."

# ---------------------------------------------------------------------------
# Step 4: Generate data-quality report
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 4/5 — Generating quality report …"
mkdir -p "$REPO_ROOT/reports"
python3 "$PIPELINE_DIR/quality_report.py" \
    --db-url "$DB_URL" \
    --output "$REPO_ROOT/reports/quality_report.md"
echo "  ✓ Report saved to reports/quality_report.md"

# ---------------------------------------------------------------------------
# Step 5: Seed synthetic demo inspection timelines & anomaly flags
# ---------------------------------------------------------------------------
echo ""
echo "▶ Step 5/5 — Seeding synthetic demo inspection timelines & flags …"
python3 "$PIPELINE_DIR/seed_demo_timelines.py" \
    --db-url "$DB_URL" \
    --write-sql "$REPO_ROOT/db/seeds/demo_synthetic_timelines.sql"
echo "  ✓ Demo synthetic timelines and flags seeded."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All done! Quick sanity check:"
echo ""
psql "$DB_URL" -c \
  "SELECT status, COUNT(*) AS rows FROM mplads_project GROUP BY 1 ORDER BY 2 DESC;"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
