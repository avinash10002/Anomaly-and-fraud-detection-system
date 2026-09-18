-- =============================================================================
-- MPLAD Anomaly Detector — Seed Data
-- seed.sql
--
-- Covers:
--   • 3 MPs  (Madhya Pradesh, Maharashtra, Rajasthan)
--   • 3 Contractors
--   • 15 Projects  (varying type, cost bracket, status, state)
--   • 12 Anomaly Flags (mix of engines, scores, review states)
--   • 10 Image Captures (mix of sources, defect classes)
--
-- Run AFTER the schema migration:
--   psql -U mplad_user -d mplad -f db/seeds/seed.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- MPs
-- ---------------------------------------------------------------------------
INSERT INTO mp (id, name, constituency) VALUES
    ('11111111-0000-0000-0000-000000000001', 'Ramesh Kumar Singh',    'Rewa'),
    ('11111111-0000-0000-0000-000000000002', 'Sunita Deshpande',      'Nagpur South'),
    ('11111111-0000-0000-0000-000000000003', 'Arjun Lal Meena',       'Dausa');

-- ---------------------------------------------------------------------------
-- Contractors
-- ---------------------------------------------------------------------------
INSERT INTO contractor (id, name, registration_number) VALUES
    ('22222222-0000-0000-0000-000000000001', 'Bharat Infrastructure Pvt Ltd',   'REG-MP-2016-00124'),
    ('22222222-0000-0000-0000-000000000002', 'Vidarbha Constructions Ltd',       'REG-MH-2018-00452'),
    ('22222222-0000-0000-0000-000000000003', 'Rajputana Builders & Engineers',   'REG-RJ-2019-00789');

-- ---------------------------------------------------------------------------
-- Projects  (5 per state)
-- ---------------------------------------------------------------------------
INSERT INTO project
    (id, title, type, sanction_date, completion_declared_date,
     cost, latitude, longitude, district, state,
     contractor_id, mp_id, status, description)
VALUES

-- ── Madhya Pradesh (MP: Ramesh Kumar Singh / Rewa) ─────────────────────────
(
    '33333333-0000-0000-0000-000000000001',
    'Four-lane road widening — NH-30 bypass Rewa',
    'road', '2022-04-01', '2023-09-30',
    45000000.00, 24.5362, 81.2983, 'Rewa', 'Madhya Pradesh',
    '22222222-0000-0000-0000-000000000001', '11111111-0000-0000-0000-000000000001',
    'completed',
    'Widening of 8.4 km stretch of NH-30 approaching Rewa city, including storm drains and footpaths.'
),
(
    '33333333-0000-0000-0000-000000000002',
    'Community health centre construction — Sirmaur block',
    'building', '2022-07-15', NULL,
    18500000.00, 24.8012, 81.3540, 'Rewa', 'Madhya Pradesh',
    '22222222-0000-0000-0000-000000000001', '11111111-0000-0000-0000-000000000001',
    'stalled',
    'Two-storey primary health centre with OPD, 20-bed ward and emergency unit.'
),
(
    '33333333-0000-0000-0000-000000000003',
    'Tribal park development — Govindgarh',
    'park', '2023-01-10', '2023-12-20',
    7200000.00, 24.6945, 81.1760, 'Satna', 'Madhya Pradesh',
    '22222222-0000-0000-0000-000000000001', '11111111-0000-0000-0000-000000000001',
    'completed',
    'Landscaping, children''s play area, jogging track and lighting for 3.5-acre tribal community park.'
),
(
    '33333333-0000-0000-0000-000000000004',
    'Rural road resurfacing — Sirmour–Churhat link road',
    'road', '2023-06-01', NULL,
    9800000.00, 24.3875, 81.6200, 'Sidhi', 'Madhya Pradesh',
    '22222222-0000-0000-0000-000000000001', '11111111-0000-0000-0000-000000000001',
    'ongoing',
    'BT resurfacing of 12 km single-lane rural road with culvert repair at 4 locations.'
),
(
    '33333333-0000-0000-0000-000000000005',
    'Panchayat office complex — Mauganj',
    'building', '2021-11-20', '2023-03-31',
    12300000.00, 24.6521, 81.8910, 'Rewa', 'Madhya Pradesh',
    '22222222-0000-0000-0000-000000000001', '11111111-0000-0000-0000-000000000001',
    'completed',
    'Gram panchayat complex with main office, meeting hall, and storage facility.'
),

-- ── Maharashtra (MP: Sunita Deshpande / Nagpur South) ──────────────────────
(
    '33333333-0000-0000-0000-000000000006',
    'Flyover construction — Wardha road–Amravati junction',
    'road', '2021-03-15', '2023-11-30',
    182000000.00, 21.1458, 79.0882, 'Nagpur', 'Maharashtra',
    '22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000002',
    'completed',
    'Four-lane flyover of 780 m total length to decongest the Wardha road–Amravati road junction.'
),
(
    '33333333-0000-0000-0000-000000000007',
    'Municipal gymnasium — Butibori MIDC',
    'building', '2022-09-01', NULL,
    22400000.00, 21.0167, 79.2000, 'Nagpur', 'Maharashtra',
    '22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000002',
    'ongoing',
    'Multi-purpose indoor gymnasium with 400-seat gallery targeting industrial township residents.'
),
(
    '33333333-0000-0000-0000-000000000008',
    'Green lung park — Hingna node',
    'park', '2023-02-14', '2024-01-10',
    5600000.00, 21.0989, 78.9871, 'Nagpur', 'Maharashtra',
    '22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000002',
    'completed',
    'Urban green space with native plant species, amphitheatre and cycling track.'
),
(
    '33333333-0000-0000-0000-000000000009',
    'Drainage channel reinforcement — Kamptee',
    'other', '2022-05-20', '2023-06-15',
    31000000.00, 21.2195, 79.1972, 'Nagpur', 'Maharashtra',
    '22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000002',
    'completed',
    'Concrete lining of 6.2 km open drainage channel to prevent flooding in low-lying wards.'
),
(
    '33333333-0000-0000-0000-000000000010',
    'Police station reconstruction — Saoner',
    'building', '2023-08-01', NULL,
    16750000.00, 21.3876, 78.9245, 'Nagpur', 'Maharashtra',
    '22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000002',
    'planned',
    'New two-storey police station with 10 barracks, armoury, and public reception wing.'
),

-- ── Rajasthan (MP: Arjun Lal Meena / Dausa) ───────────────────────────────
(
    '33333333-0000-0000-0000-000000000011',
    'Desert highway resurfacing — Dausa–Lalsot SH-25',
    'road', '2021-09-10', '2022-12-31',
    28600000.00, 26.8884, 76.3352, 'Dausa', 'Rajasthan',
    '22222222-0000-0000-0000-000000000003', '11111111-0000-0000-0000-000000000003',
    'completed',
    'Full-depth reclamation and bituminous concrete overlay of 18 km state highway.'
),
(
    '33333333-0000-0000-0000-000000000012',
    'Rural road connectivity — Nangal Rajawatan gram panchayat',
    'road', '2023-04-01', NULL,
    6400000.00, 27.0123, 76.5421, 'Dausa', 'Rajasthan',
    '22222222-0000-0000-0000-000000000003', '11111111-0000-0000-0000-000000000003',
    'ongoing',
    'PMGSY-standard gravel-to-paved conversion of 4 km track connecting remote hamlet.'
),
(
    '33333333-0000-0000-0000-000000000013',
    'Jal Mahal heritage park renovation — Bandikui',
    'park', '2022-11-25', '2023-10-05',
    11200000.00, 27.0519, 76.5773, 'Dausa', 'Rajasthan',
    '22222222-0000-0000-0000-000000000003', '11111111-0000-0000-0000-000000000003',
    'completed',
    'Restoration of stepwell complex, boundary wall, landscape lighting and visitor walkway.'
),
(
    '33333333-0000-0000-0000-000000000014',
    'Government school auditorium — Sikandra',
    'building', '2022-03-01', '2023-08-20',
    19800000.00, 26.9431, 76.7823, 'Dausa', 'Rajasthan',
    '22222222-0000-0000-0000-000000000003', '11111111-0000-0000-0000-000000000003',
    'completed',
    'Fully air-conditioned 600-seat auditorium with stage, green rooms, and accessible facilities.'
),
(
    '33333333-0000-0000-0000-000000000015',
    'Solar-powered water supply scheme — Mahuwa block',
    'other', '2023-10-01', NULL,
    38500000.00, 26.7890, 76.3100, 'Dausa', 'Rajasthan',
    '22222222-0000-0000-0000-000000000003', '11111111-0000-0000-0000-000000000003',
    'ongoing',
    '1 MW solar array powering 6 overhead water tanks supplying 14 villages in drought-prone block.'
);

-- ---------------------------------------------------------------------------
-- Anomaly Flags  (12 flags across various projects)
-- ---------------------------------------------------------------------------
INSERT INTO anomaly_flag
    (id, project_id, source_engine, score, reason_text, review_status, reviewer_id)
VALUES

-- Flyover cost outlier (financial) — HIGH score, confirmed
(
    '44444444-0000-0000-0000-000000000001',
    '33333333-0000-0000-0000-000000000006',
    'financial', 0.93,
    'Project cost (₹18.2 Cr) is 3.7× the district median for road projects of similar length (₹4.9 Cr). No extraordinary-conditions amendment found in official records.',
    'confirmed', 'aaaaaaaa-0000-0000-0000-000000000001'
),
-- Flyover satellite imagery vs declared progress (image) — HIGH, pending
(
    '44444444-0000-0000-0000-000000000002',
    '33333333-0000-0000-0000-000000000006',
    'image', 0.81,
    'Satellite capture dated 2023-09-10 shows only 40% of superstructure in place, yet contractor billed for 85% completion milestone on 2023-08-25.',
    'pending', NULL
),
-- NH-30 road — financial duplicate billing flag
(
    '44444444-0000-0000-0000-000000000003',
    '33333333-0000-0000-0000-000000000001',
    'financial', 0.76,
    'Invoice INV-BIL-2023-0441 for "sub-base material supply" appears to duplicate line items from INV-BIL-2023-0312. Combined overbilling estimate: ₹12.8 L.',
    'confirmed', 'aaaaaaaa-0000-0000-0000-000000000001'
),
-- NH-30 road — image quality (pothole detected on completed road)
(
    '44444444-0000-0000-0000-000000000004',
    '33333333-0000-0000-0000-000000000001',
    'image', 0.88,
    'Street-level imagery captured 5 months post-completion shows extensive potholing (confidence 0.91) across 1.2 km, indicating sub-standard bitumen mix.',
    'confirmed', 'aaaaaaaa-0000-0000-0000-000000000001'
),
-- Health centre — stalled with full milestone payments (financial)
(
    '44444444-0000-0000-0000-000000000005',
    '33333333-0000-0000-0000-000000000002',
    'financial', 0.84,
    'Project stalled since Nov 2023 with no site activity, yet 92% of sanctioned funds (₹17.02 L) have been disbursed. Work-in-progress certification appears backdated.',
    'pending', NULL
),
-- Health centre — NLP contract language anomaly
(
    '44444444-0000-0000-0000-000000000006',
    '33333333-0000-0000-0000-000000000002',
    'nlp', 0.67,
    'Tender NIT document uses identical 14-sentence paragraph (cosine similarity 0.97) found verbatim in contractor Bharat Infrastructure''s standard self-authored scope template.',
    'pending', NULL
),
-- Panchayat office — NLP clause similarity
(
    '44444444-0000-0000-0000-000000000007',
    '33333333-0000-0000-0000-000000000005',
    'nlp', 0.58,
    'Work-order conditions match 79% of boilerplate text found in 6 other projects awarded to the same contractor in the same financial year, suggesting copy-paste without re-evaluation.',
    'dismissed', 'aaaaaaaa-0000-0000-0000-000000000002'
),
-- Drainage channel — cost inflation (financial)
(
    '44444444-0000-0000-0000-000000000008',
    '33333333-0000-0000-0000-000000000009',
    'financial', 0.72,
    'Per-metre concrete lining cost (₹4,839/m) is 2.1× the Maharashtra PWD schedule-of-rates benchmark (₹2,312/m) for the same specification.',
    'confirmed', 'aaaaaaaa-0000-0000-0000-000000000001'
),
-- School auditorium — financial timeline vs cost spike
(
    '44444444-0000-0000-0000-000000000009',
    '33333333-0000-0000-0000-000000000014',
    'financial', 0.65,
    'Revised estimate submitted 3 months before completion increased project cost by 34% (₹5.1 Cr addition). Revision came 1 week before procurement closure; independent rate verification absent.',
    'pending', NULL
),
-- Desert highway — image surface defect shortly after completion
(
    '44444444-0000-0000-0000-000000000010',
    '33333333-0000-0000-0000-000000000011',
    'image', 0.79,
    'Mapillary imagery from 4 months post-handover shows transverse cracking pattern (confidence 0.83) on 3.7 km stretch, characteristic of premature failure due to inadequate curing.',
    'pending', NULL
),
-- Solar water scheme — financial advance disbursement anomaly
(
    '44444444-0000-0000-0000-000000000011',
    '33333333-0000-0000-0000-000000000015',
    'financial', 0.55,
    'Mobilisation advance of 25% (₹9.625 Cr) released in a single tranche within 48 hours of work-order signing, exceeding standard 10% mobilisation cap without treasury approval.',
    'pending', NULL
),
-- Rural road connectivity — NLP low-quality spec
(
    '44444444-0000-0000-0000-000000000012',
    '33333333-0000-0000-0000-000000000012',
    'nlp', 0.62,
    'Technical specification document for road surface is only 280 words long — significantly below the 900-word median for similar PMGSY projects — and omits load-bearing and drainage clauses.',
    'dismissed', 'aaaaaaaa-0000-0000-0000-000000000002'
);

-- ---------------------------------------------------------------------------
-- Image Captures  (10 captures, mix of sources and defect types)
-- ---------------------------------------------------------------------------
INSERT INTO image_capture
    (id, project_id, source, capture_date, image_url, defect_class, defect_confidence)
VALUES

-- NH-30 road widening — post-completion streetview showing potholes
(
    '55555555-0000-0000-0000-000000000001',
    '33333333-0000-0000-0000-000000000001',
    'streetview', '2024-01-15',
    'https://storage.mplad-demo.in/captures/nh30-rewa-sv-20240115-001.jpg',
    'pothole', 0.91
),
(
    '55555555-0000-0000-0000-000000000002',
    '33333333-0000-0000-0000-000000000001',
    'streetview', '2024-01-15',
    'https://storage.mplad-demo.in/captures/nh30-rewa-sv-20240115-002.jpg',
    'crack', 0.74
),

-- Flyover — Mapillary coverage during construction
(
    '55555555-0000-0000-0000-000000000003',
    '33333333-0000-0000-0000-000000000006',
    'mapillary', '2023-09-10',
    'https://storage.mplad-demo.in/captures/flyover-ngp-mapillary-20230910.jpg',
    NULL, NULL
),
(
    '55555555-0000-0000-0000-000000000004',
    '33333333-0000-0000-0000-000000000006',
    'upload', '2023-11-05',
    'https://storage.mplad-demo.in/captures/flyover-ngp-uploaded-20231105.jpg',
    'debris', 0.61
),

-- Health centre — uploaded site inspection photo
(
    '55555555-0000-0000-0000-000000000005',
    '33333333-0000-0000-0000-000000000002',
    'upload', '2024-02-20',
    'https://storage.mplad-demo.in/captures/chc-sirmaur-upload-20240220.jpg',
    'crack', 0.69
),

-- Desert highway — Mapillary post-completion
(
    '55555555-0000-0000-0000-000000000006',
    '33333333-0000-0000-0000-000000000011',
    'mapillary', '2023-04-18',
    'https://storage.mplad-demo.in/captures/sh25-dausa-mapillary-20230418-001.jpg',
    'crack', 0.83
),
(
    '55555555-0000-0000-0000-000000000007',
    '33333333-0000-0000-0000-000000000011',
    'mapillary', '2023-04-18',
    'https://storage.mplad-demo.in/captures/sh25-dausa-mapillary-20230418-002.jpg',
    'pothole', 0.55
),

-- Green lung park — streetview baseline capture
(
    '55555555-0000-0000-0000-000000000008',
    '33333333-0000-0000-0000-000000000008',
    'streetview', '2024-02-01',
    'https://storage.mplad-demo.in/captures/park-hingna-sv-20240201.jpg',
    NULL, NULL
),

-- Drainage channel — uploaded engineer inspection
(
    '55555555-0000-0000-0000-000000000009',
    '33333333-0000-0000-0000-000000000009',
    'upload', '2023-07-12',
    'https://storage.mplad-demo.in/captures/drainage-kamptee-upload-20230712.jpg',
    'crack', 0.48
),

-- Jal Mahal park renovation — upload post-renovation
(
    '55555555-0000-0000-0000-000000000010',
    '33333333-0000-0000-0000-000000000013',
    'upload', '2023-10-20',
    'https://storage.mplad-demo.in/captures/jalmahal-bandikui-upload-20231020.jpg',
    NULL, NULL
);

COMMIT;
