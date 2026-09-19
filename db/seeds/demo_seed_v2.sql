-- =============================================================================
-- MPLADS Anomaly Detector -- Demo Dataset Seed  (v2)
-- File    : db/seeds/demo_seed_v2.sql
-- Purpose : 5 clearly-labelled synthetic demo projects showcasing every
--           detection signal.  All rows carry:
--             mplads_project.source_file = 'DEMO_SYNTHETIC_SEED'
--             anomaly_flag.source_type   = 'DEMO_SYNTHETIC'
--             image_capture.source_type  = 'DEMO_SYNTHETIC'
--
-- Median basis (computed from MPLADS.csv, 2024-03-04 snapshot, real data):
--   Uttar Pradesh / Normal/Others  n=6,592  median = Rs 2,24,500
--   Bihar         / Normal/Others  n=5,666  median = Rs 5,00,000
--   Rajasthan     / Normal/Others  n=3,816  median = Rs 5,00,000
--   Odisha        / Normal/Others  n=4,757  median = Rs 2,50,000
--
-- Apply  : psql -U mplad_user -d mplad -f db/seeds/demo_seed_v2.sql
-- Rollback: DELETE FROM image_capture WHERE source_type = 'DEMO_SYNTHETIC';
--           DELETE FROM anomaly_flag   WHERE source_type = 'DEMO_SYNTHETIC';
--           DELETE FROM mplads_project WHERE source_file = 'DEMO_SYNTHETIC_SEED';
-- =============================================================================

\set ON_ERROR_STOP on
BEGIN;

-- Guard: ensure migration 003 columns are present
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'image_capture' AND column_name = 'source_type') THEN
        ALTER TABLE image_capture ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'anomaly_flag' AND column_name = 'source_type') THEN
        ALTER TABLE anomaly_flag ADD COLUMN source_type TEXT NOT NULL DEFAULT 'DEMO_SYNTHETIC';
    END IF;
END $$;


-- =============================================================================
-- CASE 1 : LOW RISK -- baseline "nothing wrong" state
-- State   : Rajasthan / Normal/Others   median = Rs 5,00,000
-- Alloc   : Rs 4,75,000  (0.95x median -- normal)
-- Flags   : 0 | Images: 2 (sound)
-- ID      : ce266c84-add9-59bb-b4ac-9fe61e2bf98d
-- =============================================================================

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'ce266c84-add9-59bb-b4ac-9fe61e2bf98d',
    'Manoj Rajoria', 'KARAULI-DHOLPUR(SC)', 'Lok Sabha',
    'NA - Construction of open-air gymnasium equipment and fitness park for public use in village Kaithri',
    'Normal/Others', 'DISTRICT COLLECTOR DHOLPUR_IDA',
    'completed', 'approved_by_ida',
    'Rajasthan', NULL, NULL, 'Sepau', 'Kaithri',
    '2023-04-15', 475000.00,
    'DEMO_SYNTHETIC_HASH_CASE1_ce266c84', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='NA - Construction of open-air gymnasium equipment and fitness park for public use in village Kaithri',
    allocation_amount=475000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO image_capture (id, project_id, source, capture_date, image_url,
                            defect_class, defect_confidence, source_type)
VALUES
    ('66666666-0000-0000-0001-000000000001','ce266c84-add9-59bb-b4ac-9fe61e2bf98d',
     'streetview','2024-01-10','https://storage.mplad-demo.in/captures/demo-case1-sv-20240110.jpg',
     NULL,NULL,'DEMO_SYNTHETIC'),
    ('66666666-0000-0000-0001-000000000002','ce266c84-add9-59bb-b4ac-9fe61e2bf98d',
     'upload','2024-03-05','https://storage.mplad-demo.in/captures/demo-case1-upload-20240305.jpg',
     NULL,NULL,'DEMO_SYNTHETIC')
ON CONFLICT (id) DO UPDATE SET
    capture_date=EXCLUDED.capture_date, defect_class=EXCLUDED.defect_class,
    defect_confidence=EXCLUDED.defect_confidence, source_type=EXCLUDED.source_type;

-- No anomaly_flag for Case 1 (clean project)


-- =============================================================================
-- CASE 2 : FINANCIAL ANOMALY -- allocation ~3x state median
-- State   : Uttar Pradesh / Normal/Others   median = Rs 2,24,500
-- Alloc   : Rs 7,33,000  (3.26x median -- outlier 97.8th pctile)
-- Flags   : 1 (financial, score=0.94, pending)
-- ID      : feaa76a4-cbf6-5482-8e84-ecb5600c3f9d
-- =============================================================================

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'feaa76a4-cbf6-5482-8e84-ecb5600c3f9d',
    'Dr Ashok Bajpai', 'Sitting Rajya Sabha', 'Rajya Sabha',
    'WS/MP179/2023-2024/119823 - Construction of community pavilion and covered sitting area for village market premises at Mehdawal',
    'Normal/Others', 'DISTRICT PANCHAYAT RAJ OFFICER SANT KABIR NAGAR_IDA',
    'sanctioned', 'approved_by_ida',
    'Uttar Pradesh', NULL, NULL, 'Mehdawal', 'Mahulia',
    '2023-09-12', 733000.00,
    'DEMO_SYNTHETIC_HASH_CASE2_feaa76a4', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='WS/MP179/2023-2024/119823 - Construction of community pavilion and covered sitting area for village market premises at Mehdawal',
    allocation_amount=733000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO image_capture (id, project_id, source, capture_date, image_url,
                            defect_class, defect_confidence, source_type)
VALUES
    ('66666666-0000-0000-0002-000000000001','feaa76a4-cbf6-5482-8e84-ecb5600c3f9d',
     'streetview','2023-11-12','https://storage.mplad-demo.in/captures/demo-case2-sv-20231112.jpg',
     NULL,NULL,'DEMO_SYNTHETIC'),
    ('66666666-0000-0000-0002-000000000002','feaa76a4-cbf6-5482-8e84-ecb5600c3f9d',
     'upload','2024-02-20','https://storage.mplad-demo.in/captures/demo-case2-upload-20240220.jpg',
     NULL,NULL,'DEMO_SYNTHETIC')
ON CONFLICT (id) DO UPDATE SET
    capture_date=EXCLUDED.capture_date, defect_class=EXCLUDED.defect_class,
    defect_confidence=EXCLUDED.defect_confidence, source_type=EXCLUDED.source_type;

INSERT INTO anomaly_flag (id, project_id, source_engine, score, reason_text,
                           review_status, reviewer_id, source_type)
VALUES (
    '77777777-0000-0000-0002-000000000001',
    'feaa76a4-cbf6-5482-8e84-ecb5600c3f9d',
    'financial', 0.940,
    '[DEMO_SYNTHETIC] Project allocation (Rs. 7,33,000) is 3.26x the Uttar Pradesh state-category median (Rs. 2,24,500) for Normal/Others works (n=6,592 peer projects). Outlier percentile rank: 97.8th. No approved deviation note found in IDA records.',
    'pending', NULL, 'DEMO_SYNTHETIC'
)
ON CONFLICT (id) DO UPDATE SET score=EXCLUDED.score, reason_text=EXCLUDED.reason_text,
    review_status=EXCLUDED.review_status, source_type=EXCLUDED.source_type;


-- =============================================================================
-- CASE 3 : NLP DUPLICATE FLAG -- near-identical work descriptions, same block
-- State   : Bihar / Normal/Others   median = Rs 5,00,000
-- Alloc   : Rs 4,87,000 both (0.97x -- normal; anomaly is text, not cost)
-- Flags   : 1 on primary project (nlp, score=0.92, pending)
-- Primary : fa527ded-f8b7-518e-9ba0-72556cf0f7c9
-- Peer    : c1e1a7cf-26ab-5167-92a1-9790ca3f069e
-- =============================================================================

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'fa527ded-f8b7-518e-9ba0-72556cf0f7c9',
    'Mr Gopal Jee Thakur', 'DARBHANGA', 'Lok Sabha',
    'NA - Street lights installation along main roads and pathways connecting village to panchayat bhawan at Jagdishpur',
    'Normal/Others', 'DISTRICT LIGHT AND POWER DEPARTMENT DARBHANGA_IDA',
    'ongoing', 'approved_by_ida',
    'Bihar', NULL, NULL, 'JHAJHA', 'Jagdishpur',
    '2023-07-22', 487000.00,
    'DEMO_SYNTHETIC_HASH_CASE3A_fa527ded', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='NA - Street lights installation along main roads and pathways connecting village to panchayat bhawan at Jagdishpur',
    allocation_amount=487000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'c1e1a7cf-26ab-5167-92a1-9790ca3f069e',
    'Mr Gopal Jee Thakur', 'DARBHANGA', 'Lok Sabha',
    'NA - Street lights installation along main roads and pathways connecting village to panchayat bhawan at Chandaur',
    'Normal/Others', 'DISTRICT LIGHT AND POWER DEPARTMENT DARBHANGA_IDA',
    'ongoing', 'approved_by_ida',
    'Bihar', NULL, NULL, 'JHAJHA', 'Chandaur',
    '2023-07-22', 487000.00,  -- same date as primary: key NLP red flag
    'DEMO_SYNTHETIC_HASH_CASE3B_c1e1a7cf', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='NA - Street lights installation along main roads and pathways connecting village to panchayat bhawan at Chandaur',
    allocation_amount=487000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO image_capture (id, project_id, source, capture_date, image_url,
                            defect_class, defect_confidence, source_type)
VALUES
    ('66666666-0000-0000-0003-000000000001','fa527ded-f8b7-518e-9ba0-72556cf0f7c9',
     'streetview','2023-12-01','https://storage.mplad-demo.in/captures/demo-case3-sv-20231201.jpg',
     NULL,NULL,'DEMO_SYNTHETIC'),
    ('66666666-0000-0000-0003-000000000002','fa527ded-f8b7-518e-9ba0-72556cf0f7c9',
     'upload','2024-02-15','https://storage.mplad-demo.in/captures/demo-case3-upload-20240215.jpg',
     NULL,NULL,'DEMO_SYNTHETIC')
ON CONFLICT (id) DO UPDATE SET
    capture_date=EXCLUDED.capture_date, defect_class=EXCLUDED.defect_class,
    defect_confidence=EXCLUDED.defect_confidence, source_type=EXCLUDED.source_type;

INSERT INTO anomaly_flag (id, project_id, source_engine, score, reason_text,
                           review_status, reviewer_id, source_type)
VALUES (
    '77777777-0000-0000-0003-000000000001',
    'fa527ded-f8b7-518e-9ba0-72556cf0f7c9',
    'nlp', 0.920,
    '[DEMO_SYNTHETIC] Near-identical work description (cosine similarity 0.96) found in project c1e1a7cf-26ab-5167-92a1-9790ca3f069e within the same block (JHAJHA, DARBHANGA, Bihar) and same recommended date (2023-07-22). Only the village name differs. Both attributed to the same MP and IDA. Possible duplicate sanctioning without independent site-specific bill of quantities.',
    'pending', NULL, 'DEMO_SYNTHETIC'
)
ON CONFLICT (id) DO UPDATE SET score=EXCLUDED.score, reason_text=EXCLUDED.reason_text,
    review_status=EXCLUDED.review_status, source_type=EXCLUDED.source_type;


-- =============================================================================
-- CASE 4 : IMAGE DEGRADATION -- normal allocation, progressive visual failure
-- State   : Odisha / Normal/Others   median = Rs 2,50,000
-- Alloc   : Rs 2,40,000  (0.96x median -- normal)
-- Signals : 3 image_capture (none -> crack -> pothole over 8 months)
--           1 anomaly_flag (image, score=0.89, pending)
-- ID      : b503d0a8-c311-5409-b365-5ade19ce3e2f
-- =============================================================================

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'b503d0a8-c311-5409-b365-5ade19ce3e2f',
    'Shri Bhartruhari Mahtab', 'CUTTACK', 'Lok Sabha',
    'NA - Construction of roads, link roads, pathways or any other road with or without drainage connecting village Bankol to main road',
    'Normal/Others', 'DISTRICT COLLECTOR CUTTACK_IDA',
    'completed', 'approved_by_ida',
    'Odisha', NULL, NULL, 'Kishannagar', 'Bankol',
    '2023-01-18', 240000.00,
    'DEMO_SYNTHETIC_HASH_CASE4_b503d0a8', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='NA - Construction of roads, link roads, pathways or any other road with or without drainage connecting village Bankol to main road',
    allocation_amount=240000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO image_capture (id, project_id, source, capture_date, image_url,
                            defect_class, defect_confidence, source_type)
VALUES
    -- Month 1: newly completed, no defect
    ('66666666-0000-0000-0004-000000000001','b503d0a8-c311-5409-b365-5ade19ce3e2f',
     'streetview','2023-04-10','https://storage.mplad-demo.in/captures/demo-case4-sv-20230410.jpg',
     NULL,NULL,'DEMO_SYNTHETIC'),
    -- Month 5: crack detected
    ('66666666-0000-0000-0004-000000000002','b503d0a8-c311-5409-b365-5ade19ce3e2f',
     'mapillary','2023-08-15','https://storage.mplad-demo.in/captures/demo-case4-mapillary-20230815.jpg',
     'crack',0.780,'DEMO_SYNTHETIC'),
    -- Month 9: structural pothole
    ('66666666-0000-0000-0004-000000000003','b503d0a8-c311-5409-b365-5ade19ce3e2f',
     'upload','2023-12-05','https://storage.mplad-demo.in/captures/demo-case4-upload-20231205.jpg',
     'pothole',0.910,'DEMO_SYNTHETIC')
ON CONFLICT (id) DO UPDATE SET
    capture_date=EXCLUDED.capture_date, defect_class=EXCLUDED.defect_class,
    defect_confidence=EXCLUDED.defect_confidence, source_type=EXCLUDED.source_type;

INSERT INTO anomaly_flag (id, project_id, source_engine, score, reason_text,
                           review_status, reviewer_id, source_type)
VALUES (
    '77777777-0000-0000-0004-000000000001',
    'b503d0a8-c311-5409-b365-5ade19ce3e2f',
    'image', 0.890,
    '[DEMO_SYNTHETIC] Chronological degradation analysis detected progressive structural breakdown: (1) 2023-04-10 intact asphalt, no defect; (2) 2023-08-15 transverse cracking by Mapillary (conf 0.78); (3) 2023-12-05 structural pothole by site upload (conf 0.91). Total 8 months post-completion. Inconsistent with 5-7 year bituminous surface lifespan.',
    'pending', NULL, 'DEMO_SYNTHETIC'
)
ON CONFLICT (id) DO UPDATE SET score=EXCLUDED.score, reason_text=EXCLUDED.reason_text,
    review_status=EXCLUDED.review_status, source_type=EXCLUDED.source_type;


-- =============================================================================
-- CASE 5 : COMBINED HIGH RISK -- financial + nlp + image, all three signals
-- State   : Uttar Pradesh / Normal/Others   median = Rs 2,24,500
-- Alloc   : Rs 5,95,000  (2.65x median)
-- Flags   : 3 (financial confirmed + nlp pending + image pending)
-- Images  : 3 (none -> crack -> pothole)
-- ID      : e7becbea-467f-5e0d-a910-fe1e740972ba
-- Similar : feaa76a4 (Case 2) -- same MP, same quarter, flagged pattern
-- =============================================================================

INSERT INTO mplads_project (
    id, mp_name, constituency, house,
    work, category, ida,
    status, ida_approval_status,
    state, city, ward, block, village,
    recommended_date, allocation_amount,
    raw_row_hash, source_file
) VALUES (
    'e7becbea-467f-5e0d-a910-fe1e740972ba',
    'Dr Ashok Bajpai', 'Sitting Rajya Sabha', 'Rajya Sabha',
    'WS/MP179/2023-2024/119127 - Construction of roads, link roads, pathways or any other road with or without drainage connecting village to panchayat bhawan at Khajuria',
    'Normal/Others', 'DISTRICT PANCHAYAT RAJ OFFICER GORAKHPUR_IDA',
    'completed', 'approved_by_ida',
    'Uttar Pradesh', NULL, NULL, 'Mehdawal', 'Khajuria',
    '2023-03-05', 595000.00,
    'DEMO_SYNTHETIC_HASH_CASE5_e7becbea', 'DEMO_SYNTHETIC_SEED'
)
ON CONFLICT (id) DO UPDATE SET
    work='WS/MP179/2023-2024/119127 - Construction of roads, link roads, pathways or any other road with or without drainage connecting village to panchayat bhawan at Khajuria',
    allocation_amount=595000.00, source_file='DEMO_SYNTHETIC_SEED';

INSERT INTO image_capture (id, project_id, source, capture_date, image_url,
                            defect_class, defect_confidence, source_type)
VALUES
    ('66666666-0000-0000-0005-000000000001','e7becbea-467f-5e0d-a910-fe1e740972ba',
     'streetview','2023-05-12','https://storage.mplad-demo.in/captures/demo-case5-sv-20230512.jpg',
     NULL,NULL,'DEMO_SYNTHETIC'),
    ('66666666-0000-0000-0005-000000000002','e7becbea-467f-5e0d-a910-fe1e740972ba',
     'mapillary','2023-09-20','https://storage.mplad-demo.in/captures/demo-case5-mapillary-20230920.jpg',
     'crack',0.820,'DEMO_SYNTHETIC'),
    ('66666666-0000-0000-0005-000000000003','e7becbea-467f-5e0d-a910-fe1e740972ba',
     'upload','2024-01-18','https://storage.mplad-demo.in/captures/demo-case5-upload-20240118.jpg',
     'pothole',0.930,'DEMO_SYNTHETIC')
ON CONFLICT (id) DO UPDATE SET
    capture_date=EXCLUDED.capture_date, defect_class=EXCLUDED.defect_class,
    defect_confidence=EXCLUDED.defect_confidence, source_type=EXCLUDED.source_type;

INSERT INTO anomaly_flag (id, project_id, source_engine, score, reason_text,
                           review_status, reviewer_id, source_type)
VALUES
    (
        '77777777-0000-0000-0005-000000000001',
        'e7becbea-467f-5e0d-a910-fe1e740972ba',
        'financial', 0.960,
        '[DEMO_SYNTHETIC] Allocation Rs. 5,95,000 is 2.65x UP state-category median Rs. 2,24,500 (n=6,592). Same MP (Dr Ashok Bajpai) sanctioned project feaa76a4 at 3.26x median in same quarter -- systematic over-recommendation pattern detected.',
        'confirmed', NULL, 'DEMO_SYNTHETIC'
    ),
    (
        '77777777-0000-0000-0005-000000000002',
        'e7becbea-467f-5e0d-a910-fe1e740972ba',
        'nlp', 0.880,
        '[DEMO_SYNTHETIC] Work description (cosine similarity 0.94) found verbatim in 6 other UP projects by same MP in FY 2023-24, without site-specific bill of quantities or locational variation. Pattern consistent with boilerplate copy-paste across submissions.',
        'pending', NULL, 'DEMO_SYNTHETIC'
    ),
    (
        '77777777-0000-0000-0005-000000000003',
        'e7becbea-467f-5e0d-a910-fe1e740972ba',
        'image', 0.910,
        '[DEMO_SYNTHETIC] Rapid failure: (1) 2023-05-12 intact; (2) 2023-09-20 cracking conf 0.82; (3) 2024-01-18 structural pothole + washout conf 0.93. 8-month failure timeline inconsistent with standard bituminous lifespan -- sub-standard bitumen or missing sub-base compaction.',
        'pending', NULL, 'DEMO_SYNTHETIC'
    )
ON CONFLICT (id) DO UPDATE SET score=EXCLUDED.score, reason_text=EXCLUDED.reason_text,
    review_status=EXCLUDED.review_status, source_type=EXCLUDED.source_type;


COMMIT;


-- =============================================================================
-- VERIFICATION QUERY (run after applying)
-- =============================================================================
--
--   SELECT id, LEFT(work,55) AS work, state, allocation_amount, status
--   FROM mplads_project WHERE source_file = 'DEMO_SYNTHETIC_SEED' ORDER BY id;
--
--   SELECT af.project_id, af.source_engine, af.score, af.review_status
--   FROM anomaly_flag af WHERE af.source_type = 'DEMO_SYNTHETIC' ORDER BY af.project_id;
--
-- =============================================================================
-- DEMO MANIFEST
-- =============================================================================
--
--  Case  Project ID (click in UI)                  State         Allocation   Flags
--  ----- ----------------------------------------  -----------   -----------  -----------------
--  1     ce266c84-add9-59bb-b4ac-9fe61e2bf98d      Rajasthan     Rs 4,75,000  0   LOW RISK
--  2     feaa76a4-cbf6-5482-8e84-ecb5600c3f9d      UP            Rs 7,33,000  1   FINANCIAL (3.26x)
--  3a    fa527ded-f8b7-518e-9ba0-72556cf0f7c9      Bihar         Rs 4,87,000  1   NLP DUPLICATE (primary)
--  3b    c1e1a7cf-26ab-5167-92a1-9790ca3f069e      Bihar         Rs 4,87,000  0   NLP PEER (for comparison)
--  4     b503d0a8-c311-5409-b365-5ade19ce3e2f      Odisha        Rs 2,40,000  1   IMAGE DEGRADATION
--  5     e7becbea-467f-5e0d-a910-fe1e740972ba      UP            Rs 5,95,000  3   COMBINED HIGH RISK
--
--  image_capture rows: 2+2+2+3+3 = 12
--  anomaly_flag rows : 0+1+1+0+1+3 = 6
--
-- ROLLBACK (clean removal before real submission):
--   DELETE FROM image_capture WHERE source_type = 'DEMO_SYNTHETIC';
--   DELETE FROM anomaly_flag   WHERE source_type = 'DEMO_SYNTHETIC';
--   DELETE FROM mplads_project WHERE source_file = 'DEMO_SYNTHETIC_SEED';
-- =============================================================================
