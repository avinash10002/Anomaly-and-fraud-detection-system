-- =============================================================================
-- MPLAD Fraud/Anomaly Detector — Initial Schema Migration
-- Migration : 001_init_schema.sql
-- Requires  : PostgreSQL 14+ with PostGIS extension
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------------
CREATE TYPE project_type    AS ENUM ('road', 'building', 'park', 'other');
CREATE TYPE project_status  AS ENUM ('planned', 'ongoing', 'completed', 'stalled', 'cancelled');
CREATE TYPE source_engine   AS ENUM ('financial', 'image', 'nlp');
CREATE TYPE review_status   AS ENUM ('pending', 'confirmed', 'dismissed');
CREATE TYPE image_source    AS ENUM ('streetview', 'mapillary', 'upload');

-- ---------------------------------------------------------------------------
-- Table: mp  (Member of Parliament)
-- ---------------------------------------------------------------------------
CREATE TABLE mp (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT            NOT NULL,
    constituency    TEXT            NOT NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Table: contractor
-- ---------------------------------------------------------------------------
CREATE TABLE contractor (
    id                  UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT    NOT NULL,
    registration_number TEXT    NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Table: project
-- ---------------------------------------------------------------------------
CREATE TABLE project (
    id                          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    title                       TEXT            NOT NULL,
    type                        project_type    NOT NULL,
    sanction_date               DATE            NOT NULL,
    completion_declared_date    DATE,
    cost                        NUMERIC(15, 2)  NOT NULL CHECK (cost > 0),
    latitude                    DOUBLE PRECISION NOT NULL,
    longitude                   DOUBLE PRECISION NOT NULL,
    location                    GEOGRAPHY(POINT, 4326),          -- PostGIS spatial column
    district                    TEXT            NOT NULL,
    state                       TEXT            NOT NULL,
    contractor_id               UUID            NOT NULL REFERENCES contractor (id) ON DELETE RESTRICT,
    mp_id                       UUID            NOT NULL REFERENCES mp (id) ON DELETE RESTRICT,
    status                      project_status  NOT NULL DEFAULT 'planned',
    description                 TEXT,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Automatically populate the PostGIS geography column from lat/lon
CREATE OR REPLACE FUNCTION sync_project_location()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.location := ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326)::GEOGRAPHY;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_project_location
    BEFORE INSERT OR UPDATE OF latitude, longitude
    ON project
    FOR EACH ROW EXECUTE FUNCTION sync_project_location();

-- Spatial index
CREATE INDEX idx_project_location ON project USING GIST (location);

-- Lookup indexes
CREATE INDEX idx_project_mp_id          ON project (mp_id);
CREATE INDEX idx_project_contractor_id  ON project (contractor_id);
CREATE INDEX idx_project_status         ON project (status);
CREATE INDEX idx_project_type           ON project (type);
CREATE INDEX idx_project_district       ON project (district);

-- ---------------------------------------------------------------------------
-- Table: anomaly_flag
-- ---------------------------------------------------------------------------
CREATE TABLE anomaly_flag (
    id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID            NOT NULL REFERENCES project (id) ON DELETE CASCADE,
    source_engine   source_engine   NOT NULL,
    score           NUMERIC(4, 3)   NOT NULL CHECK (score >= 0 AND score <= 1),
    reason_text     TEXT            NOT NULL,
    review_status   review_status   NOT NULL DEFAULT 'pending',
    reviewer_id     UUID,           -- nullable; references an external user/auth table
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_anomaly_flag_project_id     ON anomaly_flag (project_id);
CREATE INDEX idx_anomaly_flag_review_status  ON anomaly_flag (review_status);
CREATE INDEX idx_anomaly_flag_source_engine  ON anomaly_flag (source_engine);
CREATE INDEX idx_anomaly_flag_score          ON anomaly_flag (score DESC);

-- ---------------------------------------------------------------------------
-- Table: image_capture
-- ---------------------------------------------------------------------------
CREATE TABLE image_capture (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id          UUID            NOT NULL REFERENCES project (id) ON DELETE CASCADE,
    source              image_source    NOT NULL,
    capture_date        DATE            NOT NULL,
    image_url           TEXT            NOT NULL,
    defect_class        TEXT,           -- e.g. 'pothole', 'crack', 'debris'
    defect_confidence   NUMERIC(4, 3)   CHECK (defect_confidence IS NULL OR (defect_confidence >= 0 AND defect_confidence <= 1)),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_image_capture_project_id   ON image_capture (project_id);
CREATE INDEX idx_image_capture_source       ON image_capture (source);
CREATE INDEX idx_image_capture_capture_date ON image_capture (capture_date DESC);

-- ---------------------------------------------------------------------------
-- updated_at triggers (generic helper)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_mp_updated_at
    BEFORE UPDATE ON mp
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_contractor_updated_at
    BEFORE UPDATE ON contractor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_project_updated_at
    BEFORE UPDATE ON project
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_anomaly_flag_updated_at
    BEFORE UPDATE ON anomaly_flag
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_image_capture_updated_at
    BEFORE UPDATE ON image_capture
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
