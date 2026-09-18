import type { AnomalyFlag, Project, ProjectImage } from "./types";
import rawRecords from "./mplads-records.json";

export const MOCK_PROJECTS: Project[] = rawRecords as unknown as Project[];


/** Mutable in-memory store — Confirm/Dismiss updates this array. */
export let MOCK_ANOMALIES: AnomalyFlag[] = [
  // ── Demo Cases Anomaly Flags (source_type = 'DEMO_SYNTHETIC') ──────────────
  {
    id: "77777777-0000-0000-0002-000000000001",
    projectId: "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
    sourceEngine: "financial",
    score: 0.94,
    reasonText:
      "[DEMO_SYNTHETIC] Project allocation (Rs. 3.89 Cr) is 173.4x the state category median (Rs. 2.24 L). Outlier score in top 99.8th percentile for Uttar Pradesh civil works.",
    reviewStatus: "pending",
    flaggedAt: "2024-01-15",
  },
  {
    id: "77777777-0000-0000-0003-000000000001",
    projectId: "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
    sourceEngine: "nlp",
    score: 0.92,
    reasonText:
      "[DEMO_SYNTHETIC] Near-identical work description (cosine similarity 0.96) found in project c1e1a7cf-26ab-5167-92a1-9790ca3f069e within the same block (JHAJHA) and sanction date.",
    reviewStatus: "pending",
    flaggedAt: "2023-11-20",
  },
  {
    id: "77777777-0000-0000-0004-000000000001",
    projectId: "b503d0a8-c311-5409-b365-5ade19ce3e2f",
    sourceEngine: "image",
    score: 0.89,
    reasonText:
      "[DEMO_SYNTHETIC] Chronological degradation analysis detected progressive breakdown from intact surface to structural potholes (confidence 0.91) within 8 months post-construction.",
    reviewStatus: "pending",
    flaggedAt: "2023-12-10",
  },
  {
    id: "77777777-0000-0000-0005-000000000001",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    sourceEngine: "financial",
    score: 0.96,
    reasonText:
      "[DEMO_SYNTHETIC] Project allocation of Rs. 1.34 Cr is 59.8x the state median (Rs. 2.24 L) for rural road works in Uttar Pradesh.",
    reviewStatus: "confirmed",
    flaggedAt: "2023-08-01",
  },
  {
    id: "77777777-0000-0000-0005-000000000002",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    sourceEngine: "nlp",
    score: 0.88,
    reasonText:
      "[DEMO_SYNTHETIC] Work scope is identical boilerplate repeated across 148 other sanctioned projects in Gorakhpur without site-specific bill of quantities.",
    reviewStatus: "pending",
    flaggedAt: "2023-09-15",
  },
  {
    id: "77777777-0000-0000-0005-000000000003",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    sourceEngine: "image",
    score: 0.91,
    reasonText:
      "[DEMO_SYNTHETIC] Chronological degradation analysis confirms rapid failure: road transitioned to heavy potholes (confidence 0.93) within 8 months of sanction.",
    reviewStatus: "pending",
    flaggedAt: "2024-01-20",
  },

  // ── Baseline Mock Anomalies ───────────────────────────────────────────────
  {
    id: "44444444-0000-0000-0000-000000000001",
    projectId: "33333333-0000-0000-0000-000000000006",
    sourceEngine: "financial",
    score: 0.93,
    reasonText:
      "Project cost (₹18.2 Cr) is 3.7× the district median for road projects of similar length (₹4.9 Cr). No extraordinary-conditions amendment found in official records.",
    reviewStatus: "confirmed",
    flaggedAt: "2023-12-05",
  },
  {
    id: "44444444-0000-0000-0000-000000000002",
    projectId: "33333333-0000-0000-0000-000000000006",
    sourceEngine: "image",
    score: 0.81,
    reasonText:
      "Satellite capture dated 2023-09-10 shows only 40% of superstructure in place, yet contractor billed for 85% completion milestone on 2023-08-25.",
    reviewStatus: "pending",
    flaggedAt: "2023-09-18",
  },
  {
    id: "44444444-0000-0000-0000-000000000003",
    projectId: "33333333-0000-0000-0000-000000000001",
    sourceEngine: "financial",
    score: 0.76,
    reasonText:
      'Invoice INV-BIL-2023-0441 for "sub-base material supply" appears to duplicate line items from INV-BIL-2023-0312. Combined overbilling estimate: ₹12.8 L.',
    reviewStatus: "confirmed",
    flaggedAt: "2023-10-12",
  },
  {
    id: "44444444-0000-0000-0000-000000000004",
    projectId: "33333333-0000-0000-0000-000000000001",
    sourceEngine: "image",
    score: 0.88,
    reasonText:
      "Street-level imagery captured 5 months post-completion shows extensive potholing (confidence 0.91) across 1.2 km, indicating sub-standard bitumen mix.",
    reviewStatus: "confirmed",
    flaggedAt: "2024-01-20",
  },
  {
    id: "44444444-0000-0000-0000-000000000005",
    projectId: "33333333-0000-0000-0000-000000000002",
    sourceEngine: "financial",
    score: 0.84,
    reasonText:
      "Project stalled since Nov 2023 with no site activity, yet 92% of sanctioned funds (₹17.02 L) have been disbursed. Work-in-progress certification appears backdated.",
    reviewStatus: "pending",
    flaggedAt: "2024-02-01",
  },
  {
    id: "44444444-0000-0000-0000-000000000006",
    projectId: "33333333-0000-0000-0000-000000000002",
    sourceEngine: "nlp",
    score: 0.67,
    reasonText:
      "Tender NIT document uses identical 14-sentence paragraph (cosine similarity 0.97) found verbatim in contractor Bharat Infrastructure's standard self-authored scope template.",
    reviewStatus: "pending",
    flaggedAt: "2024-02-08",
  },
  {
    id: "44444444-0000-0000-0000-000000000007",
    projectId: "33333333-0000-0000-0000-000000000005",
    sourceEngine: "nlp",
    score: 0.58,
    reasonText:
      "Work-order conditions match 79% of boilerplate text found in 6 other projects awarded to the same contractor in the same financial year, suggesting copy-paste without re-evaluation.",
    reviewStatus: "dismissed",
    flaggedAt: "2023-04-15",
  },
  {
    id: "44444444-0000-0000-0000-000000000008",
    projectId: "33333333-0000-0000-0000-000000000009",
    sourceEngine: "financial",
    score: 0.72,
    reasonText:
      "Per-metre concrete lining cost (₹4,839/m) is 2.1× the Maharashtra PWD schedule-of-rates benchmark (₹2,312/m) for the same specification.",
    reviewStatus: "confirmed",
    flaggedAt: "2023-07-22",
  },
  {
    id: "44444444-0000-0000-0000-000000000009",
    projectId: "33333333-0000-0000-0000-000000000014",
    sourceEngine: "financial",
    score: 0.65,
    reasonText:
      "Revised estimate submitted 3 months before completion increased project cost by 34% (₹5.1 Cr addition). Revision came 1 week before procurement closure; independent rate verification absent.",
    reviewStatus: "pending",
    flaggedAt: "2023-05-30",
  },
  {
    id: "44444444-0000-0000-0000-000000000010",
    projectId: "33333333-0000-0000-0000-000000000011",
    sourceEngine: "image",
    score: 0.79,
    reasonText:
      "Mapillary imagery from 4 months post-handover shows transverse cracking pattern (confidence 0.83) on 3.7 km stretch, characteristic of premature failure due to inadequate curing.",
    reviewStatus: "pending",
    flaggedAt: "2023-05-02",
  },
  {
    id: "44444444-0000-0000-0000-000000000011",
    projectId: "33333333-0000-0000-0000-000000000015",
    sourceEngine: "financial",
    score: 0.55,
    reasonText:
      "Mobilisation advance of 25% (₹9.625 Cr) released in a single tranche within 48 hours of work-order signing, exceeding standard 10% mobilisation cap without treasury approval.",
    reviewStatus: "pending",
    flaggedAt: "2023-10-12",
  },
  {
    id: "44444444-0000-0000-0000-000000000012",
    projectId: "33333333-0000-0000-0000-000000000012",
    sourceEngine: "nlp",
    score: 0.62,
    reasonText:
      "Technical specification document for road surface is only 280 words long — significantly below the 900-word median for similar PMGSY projects — and omits load-bearing and drainage clauses.",
    reviewStatus: "dismissed",
    flaggedAt: "2023-06-18",
  },
];

export const MOCK_IMAGES: ProjectImage[] = [
  // ── Demo Cases Image Captures (source_type = 'DEMO_SYNTHETIC') ─────────────
  // Case 1: Low Risk (2 sound captures)
  {
    id: "66666666-0000-0000-0001-000000000001",
    projectId: "ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
    captureDate: "2024-01-10",
    label: "Street View — sound perimeter and sports ground turf [DEMO_SYNTHETIC]",
    source: "streetview",
  },
  {
    id: "66666666-0000-0000-0001-000000000002",
    projectId: "ce266c84-add9-59bb-b4ac-9fe61e2bf98d",
    captureDate: "2024-03-05",
    label: "Handover inspection upload — sound condition, no defects [DEMO_SYNTHETIC]",
    source: "upload",
  },
  // Case 2: Financial Flag (2 sound captures)
  {
    id: "66666666-0000-0000-0002-000000000001",
    projectId: "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
    captureDate: "2023-11-12",
    label: "Street View — foundation site entrance, no surface defect [DEMO_SYNTHETIC]",
    source: "streetview",
  },
  {
    id: "66666666-0000-0000-0002-000000000002",
    projectId: "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
    captureDate: "2024-02-20",
    label: "Civil structure upload — pavilion frame sound [DEMO_SYNTHETIC]",
    source: "upload",
  },
  // Case 3: NLP Flag (2 sound captures)
  {
    id: "66666666-0000-0000-0003-000000000001",
    projectId: "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
    captureDate: "2023-12-01",
    label: "Street View — village sitting shed frame intact [DEMO_SYNTHETIC]",
    source: "streetview",
  },
  {
    id: "66666666-0000-0000-0003-000000000002",
    projectId: "fa527ded-f8b7-518e-9ba0-72556cf0f7c9",
    captureDate: "2024-02-15",
    label: "Handover photo upload — seating platform sound [DEMO_SYNTHETIC]",
    source: "upload",
  },
  // Case 4: Image Flag (3 progressive captures: none -> minor crack -> pothole)
  {
    id: "66666666-0000-0000-0004-000000000001",
    projectId: "b503d0a8-c311-5409-b365-5ade19ce3e2f",
    captureDate: "2023-04-10",
    label: "Month 1 Street View — newly paved sound asphalt [DEMO_SYNTHETIC]",
    source: "streetview",
  },
  {
    id: "66666666-0000-0000-0004-000000000002",
    projectId: "b503d0a8-c311-5409-b365-5ade19ce3e2f",
    captureDate: "2023-08-15",
    label: "Month 5 Mapillary — minor crack detected (conf: 0.78) [DEMO_SYNTHETIC]",
    source: "mapillary",
  },
  {
    id: "66666666-0000-0000-0004-000000000003",
    projectId: "b503d0a8-c311-5409-b365-5ade19ce3e2f",
    captureDate: "2023-12-05",
    label: "Month 9 Upload — severe pothole detected (conf: 0.91) [DEMO_SYNTHETIC]",
    source: "upload",
  },
  // Case 5: Combined High Risk (3 progressive captures: none -> crack -> pothole)
  {
    id: "66666666-0000-0000-0005-000000000001",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    captureDate: "2023-05-12",
    label: "Baseline Street View — cleared road corridor [DEMO_SYNTHETIC]",
    source: "streetview",
  },
  {
    id: "66666666-0000-0000-0005-000000000002",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    captureDate: "2023-09-20",
    label: "Interim Mapillary — surface cracking & wear (conf: 0.82) [DEMO_SYNTHETIC]",
    source: "mapillary",
  },
  {
    id: "66666666-0000-0000-0005-000000000003",
    projectId: "e7becbea-467f-5e0d-a910-fe1e740972ba",
    captureDate: "2024-01-18",
    label: "Audit Upload — severe pothole & structural washout (conf: 0.93) [DEMO_SYNTHETIC]",
    source: "upload",
  },

  // ── Baseline Mock Images ──────────────────────────────────────────────────
  {
    id: "img-1",
    projectId: "33333333-0000-0000-0000-000000000001",
    captureDate: "2024-01-15",
    label: "Street View — north stretch",
    source: "streetview",
  },
  {
    id: "img-2",
    projectId: "33333333-0000-0000-0000-000000000001",
    captureDate: "2024-01-15",
    label: "Street View — junction cracks",
    source: "streetview",
  },
  {
    id: "img-3",
    projectId: "33333333-0000-0000-0000-000000000006",
    captureDate: "2023-09-10",
    label: "Mapillary — mid-span progress",
    source: "mapillary",
  },
  {
    id: "img-4",
    projectId: "33333333-0000-0000-0000-000000000006",
    captureDate: "2023-11-05",
    label: "Site upload — debris near pier",
    source: "upload",
  },
  {
    id: "img-5",
    projectId: "33333333-0000-0000-0000-000000000002",
    captureDate: "2024-02-20",
    label: "Inspection upload — incomplete shell",
    source: "upload",
  },
  {
    id: "img-6",
    projectId: "33333333-0000-0000-0000-000000000011",
    captureDate: "2023-04-18",
    label: "Mapillary — transverse cracking",
    source: "mapillary",
  },
  {
    id: "img-7",
    projectId: "33333333-0000-0000-0000-000000000011",
    captureDate: "2023-04-18",
    label: "Mapillary — surface wear",
    source: "mapillary",
  },
  {
    id: "img-8",
    projectId: "33333333-0000-0000-0000-000000000008",
    captureDate: "2024-02-01",
    label: "Street View — park baseline",
    source: "streetview",
  },
  {
    id: "img-9",
    projectId: "33333333-0000-0000-0000-000000000009",
    captureDate: "2023-07-12",
    label: "Engineer upload — channel lining",
    source: "upload",
  },
  {
    id: "img-10",
    projectId: "33333333-0000-0000-0000-000000000013",
    captureDate: "2023-10-20",
    label: "Post-renovation upload",
    source: "upload",
  },
];

export function replaceAnomalies(next: AnomalyFlag[]) {
  MOCK_ANOMALIES = next;
}
