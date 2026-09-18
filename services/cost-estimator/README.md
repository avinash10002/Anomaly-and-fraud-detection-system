# MPLAD Cost Estimator — `cost-estimator` service

> ⚠️ **PROTOTYPE DEMONSTRATION RATES ONLY — not official Schedule of Rates figures. Do not use for procurement or audit purposes.**

A standalone FastAPI microservice that estimates a plausible cost range for MPLAD infrastructure works and flags how far the declared allocation deviates from that range.

---

## Quick start

```bash
# Run in isolation
cd services/cost-estimator
pip install -r requirements.txt
uvicorn main:app --reload --port 8084

# Or via Docker Compose (from repo root)
docker compose up cost-estimator
```

Service listens on **port 8084**.
Interactive docs: http://localhost:8084/docs

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Healthcheck — returns `{"status": "ok"}` |
| GET | `/rates` | Full rate catalogue JSON (categories + state indices) |
| POST | `/estimate` | Cost range estimate |

---

## POST /estimate — request schema

```json
{
  "category":             "string  (required) — work category or keyword",
  "state":                "string  (required) — Indian state name",
  "description":          "string  (optional) — WORK field from MPLADS row",
  "declared_allocation":  "number  (required) — INR amount from dataset"
}
```

---

## Example 1 — Road project, within range

**Request**
```bash
curl -X POST http://localhost:8084/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "category": "road",
    "state": "Rajasthan",
    "description": "Construction of link road from village Toda to panchayat bhawan 2 km",
    "declared_allocation": 2200000
  }'
```

**Response (200)**
```json
{
  "estimated_cost_range": {
    "low":      329000,
    "high":     25400000,
    "currency": "INR"
  },
  "declared_allocation": 2200000,
  "deviation_from_declared": {
    "vs_midpoint_pct": -17.3,
    "verdict": "within_range",
    "note": "Positive % = declared is higher than estimated midpoint. Negative % = declared is lower. Use this signal as one input to the anomaly engine — not as a standalone verdict."
  },
  "matched_category":       "road",
  "matched_category_label": "Road / Link Road / Pathway Construction",
  "catalogue_unit":         "km",
  "state_cost_index_applied": 0.94,
  "assumptions": [
    "Matched input category 'road' → 'Road / Link Road / Pathway Construction'",
    "Unit of estimation: kilometre",
    "Typical quantity assumed: 0.5–6.0 km",
    "Base rate range (national): ₹700,000 – ₹4,500,000 per km",
    "State cost index for 'Rajasthan': 0.94× (applied to base rates)",
    "Adjusted rate range: ₹658,000 – ₹4,230,000 per km",
    "Single or double-lane rural road with WBM/BT/CC surface",
    "Excludes land acquisition, utility relocation, and retaining walls",
    "Hilly or waterlogged terrain may increase cost by 50–150%",
    "Rate includes formation, sub-base, base, and wearing course"
  ],
  "data_source":   "PROTOTYPE_DEMO_RATES",
  "confidence":    "medium",
  "disclaimer":    "PROTOTYPE DEMONSTRATION RATES ONLY — not official Schedule of Rates figures. Do not use for procurement or audit purposes.",
  "catalogue_version": "0.1.0-prototype"
}
```

---

## Example 2 — Suspicious cost inflation (above range)

**Request**
```bash
curl -X POST http://localhost:8084/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "category": "street lighting",
    "state": "Uttar Pradesh",
    "description": "Installation of solar street lights in ward 4",
    "declared_allocation": 9500000
  }'
```

**Response — `verdict: above_range` flags this for the anomaly engine**
```json
{
  "estimated_cost_range": {
    "low":      202000,
    "high":     2010000,
    "currency": "INR"
  },
  "declared_allocation": 9500000,
  "deviation_from_declared": {
    "vs_midpoint_pct": 746.0,
    "verdict": "above_range",
    "note": "..."
  },
  "matched_category":       "street_lighting",
  "matched_category_label": "Street Lighting / Solar Lighting Installation",
  "catalogue_unit":         "light point",
  "state_cost_index_applied": 0.90,
  "assumptions": [
    "Matched input category 'street lighting' → 'Street Lighting / Solar Lighting Installation'",
    "Unit of estimation: light point (pole + fitting + wiring)",
    "Typical quantity assumed: 15–250 points",
    "Base rate range (national): ₹15,000 – ₹90,000 per light point",
    "State cost index for 'Uttar Pradesh': 0.90× (applied to base rates)",
    "Adjusted rate range: ₹13,500 – ₹81,000 per light point",
    "Includes pole, LED fitting, wiring/cable trenching, and metering",
    "Solar standalone units at lower end; grid-connected at upper end",
    "Excludes transformer upgrade or HT line extension",
    "Battery and controller included for solar variants"
  ],
  "data_source":   "PROTOTYPE_DEMO_RATES",
  "confidence":    "medium",
  "disclaimer":    "PROTOTYPE DEMONSTRATION RATES ONLY — not official Schedule of Rates figures. Do not use for procurement or audit purposes.",
  "catalogue_version": "0.1.0-prototype"
}
```

---

## Example 3 — Unmatched category (low confidence fallback)

**Request**
```bash
curl -X POST http://localhost:8084/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "category": "miscellaneous civic works",
    "state": "Maharashtra",
    "declared_allocation": 750000
  }'
```

**Response — `confidence: low`, wide range, explicit fallback notice**
```json
{
  "estimated_cost_range": {
    "low":      50000,
    "high":     10000000,
    "currency": "INR"
  },
  "declared_allocation": 750000,
  "deviation_from_declared": {
    "vs_midpoint_pct": -85.8,
    "verdict": "within_range",
    "note": "..."
  },
  "matched_category":       "other",
  "matched_category_label": "Other / Unclassified Work",
  "catalogue_unit":         "lump sum",
  "state_cost_index_applied": 1.16,
  "assumptions": [
    "Matched input category 'miscellaneous civic works' → 'Other / Unclassified Work'",
    "Unit of estimation: lump sum (unclassified)",
    "Work category could not be matched to a known MPLAD work type",
    "Very wide range reflects uncertainty — manual review of description is essential",
    "Confidence is LOW; do not use this estimate for any scoring without human review"
  ],
  "data_source":   "PROTOTYPE_DEMO_RATES",
  "confidence":    "low",
  "disclaimer":    "PROTOTYPE DEMONSTRATION RATES ONLY — not official Schedule of Rates figures. Do not use for procurement or audit purposes.",
  "catalogue_version": "0.1.0-prototype"
}
```

---

## Swapping in real Schedule of Rates data

The rate catalogue lives entirely in [`rates/catalogue.json`](rates/catalogue.json).
To replace prototype figures with real PWD/SoR data:

1. Keep the same JSON schema (`unit`, `rate_inr.low/high`, `typical_quantity.low/high`, `confidence`, `assumptions`)
2. Update `catalogue_version` and `last_updated` in `_meta`
3. Change `data_source` from `"PROTOTYPE_DEMO_RATES"` to your authoritative source string
4. Restart the service — no code changes required

---

## Pitch prep — what to say about the rates

> *"The cost estimator uses clearly labeled prototype rates for demonstration. In production, the `rates/catalogue.json` file would be replaced with the official state-PWD Schedule of Rates, which is published annually and freely available. The API contract and the anomaly-scoring pipeline do not change — only the data file changes."*

**What the service does NOT do:**
- It does not fabricate coordinates, quantities, contractor names, or completion dates
- It does not claim these are official government rates
- Every single API response carries the disclaimer string that the frontend must render visibly

---

## File structure

```
services/cost-estimator/
  main.py           FastAPI app (endpoints, Pydantic models)
  estimator.py      Core logic (category matching, range computation)
  rates/
    catalogue.json  ← swap this file to upgrade to real SoR data
  Dockerfile
  requirements.txt
  README.md         (this file)
```
