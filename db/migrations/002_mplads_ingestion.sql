-- =============================================================================
-- MPLAD Anomaly Detector — MPLADS Real Dataset Ingestion
-- Migration : 002_mplads_ingestion.sql
-- Run after : 001_init_schema.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Drop hard foreign-key constraints on anomaly_flag and image_capture
--    so project_id can reference EITHER project(id) OR mplads_project(id).
--    Referential integrity is enforced at the application layer.
-- ---------------------------------------------------------------------------
ALTER TABLE anomaly_flag
    DROP CONSTRAINT IF EXISTS anomaly_flag_project_id_fkey;

ALTER TABLE image_capture
    DROP CONSTRAINT IF EXISTS image_capture_project_id_fkey;

-- Add a comment so the intent is not lost during future schema reviews
COMMENT ON COLUMN anomaly_flag.project_id IS
    'Soft reference — may point to project(id) OR mplads_project(id). No DB-level FK enforced; app layer validates.';

COMMENT ON COLUMN image_capture.project_id IS
    'Soft reference — may point to project(id) OR mplads_project(id). No DB-level FK enforced; app layer validates.';

-- ---------------------------------------------------------------------------
-- 2. New enum: mplads_status
--    Maps CSV STATUS column values to stable identifiers.
--    'unknown' covers any values not in the canonical set.
-- ---------------------------------------------------------------------------
CREATE TYPE mplads_status AS ENUM (
    'unsanctioned',
    'sanctioned',
    'ongoing',
    'completed',
    'unknown'
);

-- ---------------------------------------------------------------------------
-- 3. New enum: ida_approval
--    Maps CSV "IDA APPROVAL" column values.
-- ---------------------------------------------------------------------------
CREATE TYPE ida_approval AS ENUM (
    'action_pending',
    'approved_by_ida',
    'rejected_by_ida',
    'unknown'
);

-- ---------------------------------------------------------------------------
-- 4. Main table: mplads_project
--    One row per CSV row.  Columns map 1:1 to the CSV schema.
--    Nothing is fabricated: coordinates, completion_date, contractor UUIDs
--    are NOT present and are NOT added.
-- ---------------------------------------------------------------------------
CREATE TABLE mplads_project (
    -- Primary key: stable UUID v5 derived from row fingerprint (see pipeline/ingest.py)
    id                  UUID            PRIMARY KEY,

    -- ── MP & constituency ──────────────────────────────────────────────────
    mp_name             TEXT            NOT NULL,
    constituency        TEXT,
    house               TEXT,           -- 'Lok Sabha' | 'Rajya Sabha' | other

    -- ── Project description ────────────────────────────────────────────────
    -- Preserved EXACTLY as in the source CSV — will be used for embeddings.
    work                TEXT            NOT NULL,

    -- Category as raw string (road / building / bridge / water supply / etc.)
    -- Not forced into the project_type enum; kept open for the ML layer.
    category            TEXT,

    -- ── Implementing authority ────────────────────────────────────────────
    -- "IDA" column: Implementing Department/Agency name, free text.
    ida                 TEXT,

    -- ── Status (enum-normalised) ──────────────────────────────────────────
    status              mplads_status   NOT NULL DEFAULT 'unknown',
    ida_approval_status ida_approval    NOT NULL DEFAULT 'unknown',

    -- ── Administrative location — stored at whatever granularity is present
    state               TEXT,
    city                TEXT,           -- NULL is common and expected
    ward                TEXT,           -- NULL is common and expected
    block               TEXT,
    village             TEXT,

    -- ── Financials ────────────────────────────────────────────────────────
    recommended_date    DATE,           -- NULL when unparseable in source
    allocation_amount   NUMERIC(15, 2), -- NULL when blank/non-numeric in source

    -- ── Ingestion metadata ────────────────────────────────────────────────
    -- SHA-256 of the raw CSV line; used as dedup key for idempotent re-runs.
    raw_row_hash        TEXT            NOT NULL UNIQUE,
    source_file         TEXT            NOT NULL,   -- basename of the CSV file
    ingested_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- ── Audit ─────────────────────────────────────────────────────────────
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE mplads_project IS
    'Real MPLADS project records ingested from the government CSV dataset (~60 k rows). '
    'No coordinates, contractor UUIDs, or completion dates are fabricated. '
    'The "work" column is preserved verbatim for downstream embedding models.';

-- ---------------------------------------------------------------------------
-- 5. Indexes
-- ---------------------------------------------------------------------------

-- Most common API filter: state + constituency drill-down
CREATE INDEX idx_mplads_state_constituency ON mplads_project (state, constituency);

-- Anomaly / audit engine filters
CREATE INDEX idx_mplads_status             ON mplads_project (status);
CREATE INDEX idx_mplads_ida_approval       ON mplads_project (ida_approval_status);

-- Time-range scans
CREATE INDEX idx_mplads_recommended_date   ON mplads_project (recommended_date DESC NULLS LAST);

-- MP-level aggregations
CREATE INDEX idx_mplads_mp_name            ON mplads_project (mp_name);

-- Category queries (used by financial engine for peer-group comparisons)
CREATE INDEX idx_mplads_category           ON mplads_project (category);

-- Amount range queries
CREATE INDEX idx_mplads_allocation_amount  ON mplads_project (allocation_amount DESC NULLS LAST);

-- IDA / implementing agency grouping
CREATE INDEX idx_mplads_ida                ON mplads_project (ida);

-- Dedup — also enforced by UNIQUE constraint above, but explicit index for visibility
CREATE UNIQUE INDEX idx_mplads_raw_row_hash ON mplads_project (raw_row_hash);

-- ---------------------------------------------------------------------------
-- 6. updated_at trigger (reuses the function from migration 001)
-- ---------------------------------------------------------------------------
CREATE TRIGGER trg_mplads_project_updated_at
    BEFORE UPDATE ON mplads_project
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
