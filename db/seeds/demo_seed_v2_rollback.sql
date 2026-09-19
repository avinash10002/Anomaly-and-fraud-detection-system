-- =============================================================================
-- MPLADS Demo Dataset -- Rollback Script
-- Removes ALL rows inserted by demo_seed_v2.sql.
-- Safe to run at any time; uses DELETE WHERE on provenance columns only.
-- =============================================================================

BEGIN;

DELETE FROM image_capture WHERE source_type = 'DEMO_SYNTHETIC';
DELETE FROM anomaly_flag   WHERE source_type = 'DEMO_SYNTHETIC';
DELETE FROM mplads_project WHERE source_file = 'DEMO_SYNTHETIC_SEED';

COMMIT;

-- Verify:
--   SELECT COUNT(*) FROM mplads_project WHERE source_file = 'DEMO_SYNTHETIC_SEED';  -- expect 0
--   SELECT COUNT(*) FROM anomaly_flag   WHERE source_type = 'DEMO_SYNTHETIC';        -- expect 0
--   SELECT COUNT(*) FROM image_capture  WHERE source_type = 'DEMO_SYNTHETIC';        -- expect 0
