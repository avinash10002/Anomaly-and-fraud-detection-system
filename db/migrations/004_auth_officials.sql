-- =============================================================================
-- Migration 004: Auth Service — Officials & OTP Tables
-- =============================================================================
-- Run this migration on the shared Postgres instance when deploying auth-service
-- alongside the other services. The auth-service uses SQLite locally (via db.js)
-- but this schema is compatible with Postgres for production deployments.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Enum: official role
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE official_role AS ENUM ('reviewer', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- Table: officials  (pre-registered MPLADS reviewers — no public signup)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS officials (
    id          UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       TEXT            NOT NULL UNIQUE,
    name        TEXT            NOT NULL,
    role        official_role   NOT NULL DEFAULT 'reviewer',
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    locked_until TIMESTAMPTZ,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_officials_email ON officials(LOWER(email));

-- ---------------------------------------------------------------------------
-- Table: otp_tokens  (single-use, expiring OTP tokens tied to an official)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS otp_tokens (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    official_id     UUID        NOT NULL REFERENCES officials(id) ON DELETE CASCADE,
    email           TEXT        NOT NULL,
    hash            TEXT        NOT NULL,           -- bcrypt hash of 6-digit code
    expires_at      TIMESTAMPTZ NOT NULL,
    used            BOOLEAN     NOT NULL DEFAULT FALSE,
    failed_attempts SMALLINT    NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,                    -- NULL = not locked
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_otp_email    ON otp_tokens(LOWER(email));
CREATE INDEX IF NOT EXISTS idx_otp_official ON otp_tokens(official_id);

-- ---------------------------------------------------------------------------
-- Seed: Demo officials for local testing
-- (Emails use .test TLD — safe to commit; swap for real emails in production)
-- ---------------------------------------------------------------------------
INSERT INTO officials (email, name, role) VALUES
    ('avinahgoel12@gmail.com',         'Avinash Goel (Admin)', 'admin'),
    ('avinashgoel6654@gmail.com',      'Avinash Goel',       'reviewer'),
ON CONFLICT (email) DO NOTHING;
