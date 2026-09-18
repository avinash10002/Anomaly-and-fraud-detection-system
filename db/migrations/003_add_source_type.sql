-- =============================================================================
-- MPLAD Anomaly Detector — Migration 003: Add source_type for Synthetic Provenance
-- =============================================================================

BEGIN;

-- Add source_type to image_capture if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'image_capture' AND column_name = 'source_type'
    ) THEN
        ALTER TABLE image_capture
            ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';
        
        COMMENT ON COLUMN image_capture.source_type IS
            'Provenance indicator: DEMO_SYNTHETIC for hackathon/pitch demo data, USER_UPLOADED for genuine captures.';
    END IF;
END $$;

-- Add source_type to anomaly_flag if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'anomaly_flag' AND column_name = 'source_type'
    ) THEN
        ALTER TABLE anomaly_flag
            ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';

        COMMENT ON COLUMN anomaly_flag.source_type IS
            'Provenance indicator: DEMO_SYNTHETIC or SYSTEM_ANALYZED.';
    END IF;
END $$;

COMMIT;
