# MPLAD Financial Engine — `financial-engine` service

> ⚠️ **Financial anomaly indicators are one signal for human review. They do not constitute a determination of fraud or misconduct.**

A FastAPI microservice that analyses MPLAD project allocations for financial anomaly indicators using:
1. **Statistical benchmark** — deviation from the (category, state) median in the real MPLADS dataset, expressed as percentage and IQR-units
2. **Isolation Forest** — trained per-category on log-scaled allocation amounts
3. **Cost-estimator** — optional second reference point via the `cost-estimator` service

---

## Quick start

```bash
cd services/financial-engine
pip install -r requirements.txt

# With real data (benchmarks loaded from DB)
DATABASE_URL=postgresql://mplad_user:mplad_secret@localhost:5432/mplad \
COST_ESTIMATOR_URL=http://localhost:8084 \
uvicorn main:app --reload --port 8081

# Via Docker Compose (from repo root)
docker compose up financial-engine
```

Service listens on **port 8081**.
Interactive docs: http://localhost:8081/docs

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Status + benchmark summary |
| GET | `/benchmarks/{category}/{state}` | Raw GroupStats for debugging |
| POST | `/analyze` | Anomaly analysis |

---

## POST /analyze — request schema

```json
{
  "project_id":           "uuid (optional) — looks up mplads_project row",
  "category":             "string — required if project_id absent",
  "state":                "string — required if project_id absent",
  "allocation_amount":    "number (INR) — required if project_id absent",
  "description":          "string (optional) — WORK field, forwarded to cost-estimator",
  "include_cost_estimate": "bool (default true)"
}
```

---

## Example 1 — Normal road project in Bihar

**Request**
```bash
curl -X POST http://localhost:8081/analyze \
  -H "Content-Type: application/json" \
  -d '{"category":"road","state":"Bihar","allocation_amount":1800000,"include_cost_estimate":false}'
```

**Response**
```json
{
  "project_id": null,
  "anomaly_score": 0.1192,
  "is_flagged": false,
  "flag_label": "within expected range",
  "comparison_group": {
    "category": "road",
    "state": "Bihar",
    "sample_count": 1842,
    "is_fallback": false
  },
  "allocation_amount": 1800000,
  "historical_median": 1756000,
  "historical_range": {
    "q1": 980000, "q3": 2840000,
    "lower_fence": 340000, "upper_fence": 4480000
  },
  "percentage_deviation": 2.51,
  "deviation_direction": "above",
  "isolation_forest_score": 0.18,
  "cost_estimator_range": null,
  "reason_text": "Allocation (₹1,800,000) is 2.5% above the median allocation (₹1,756,000) of comparable 'road' projects in Bihar (sample: 1842 projects). The typical allocation range (IQR) for this group is ₹980,000 – ₹2,840,000; Tukey outer fences are ₹340,000 – ₹4,480,000. Overall: allocation is within the expected range — no anomaly indicator raised.",
  "confidence": "high",
  "disclaimer": "Financial anomaly indicators are one signal for human review. They do not constitute a determination of fraud or misconduct."
}
```

---

## Example 2 — Suspicious high allocation (real outlier pattern)

**Request**
```bash
curl -X POST http://localhost:8081/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "category": "drainage",
    "state": "Bihar",
    "allocation_amount": 4500000,
    "description": "Construction of concrete nali in ward no. 5",
    "include_cost_estimate": true
  }'
```

**Response (abridged)**
```json
{
  "anomaly_score": 0.7241,
  "is_flagged": true,
  "flag_label": "flagged for review",
  "comparison_group": {
    "category": "drainage",
    "state": "Bihar",
    "sample_count": 312
  },
  "allocation_amount": 4500000,
  "historical_median": 875000,
  "historical_range": {
    "q1": 500000, "q3": 1400000,
    "lower_fence": 0, "upper_fence": 2750000
  },
  "percentage_deviation": 414.3,
  "deviation_direction": "above",
  "isolation_forest_score": 0.81,
  "cost_estimator_range": {
    "low": 150000, "high": 16250000,
    "matched_category": "drainage", "confidence": "medium",
    "disclaimer": "PROTOTYPE DEMONSTRATION RATES ONLY..."
  },
  "reason_text": "Allocation (₹4,500,000) is 414.3% above the median allocation (₹875,000) of comparable 'drainage' projects in Bihar (sample: 312 projects). The typical allocation range (IQR) for this group is ₹500,000 – ₹1,400,000; Tukey outer fences are ₹0 – ₹2,750,000. Isolation Forest (trained on 'drainage' category, n ≥ 10): classifies this allocation as 'unusual' (normalised IF score: 0.81). Cost-estimator prototype range: ₹150,000 – ₹16,250,000 (drainage, medium confidence). Overall verdict: 'flagged for review'. This is a financial anomaly indicator only; human review is required before any conclusions.",
  "confidence": "high",
  "disclaimer": "Financial anomaly indicators are one signal for human review. They do not constitute a determination of fraud or misconduct."
}
```

---

## Example 3 — Project by UUID (project_id lookup from DB)

```bash
curl -X POST http://localhost:8081/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "33333333-0000-0000-0000-000000000006",
    "include_cost_estimate": true
  }'
```

The service looks up the row from `mplads_project`, extracts `category`, `state`, `allocation_amount`, and `work`, then runs the same analysis.

---

## Scoring model

```
deviation_score = sigmoid_clamp(|amount − median| / IQR)
                  ↓
composite = 0.70 × deviation_score
          + 0.30 × isolation_forest_score   (0 if IF unavailable)

anomaly_score ≥ 0.50 → "flagged for review"
anomaly_score ≥ 0.30 → "financial anomaly indicator — borderline"
anomaly_score <  0.30 → "within expected range"
```

The deviation calculation is **always independently verifiable** from the response fields (`allocation_amount`, `historical_median`, `percentage_deviation`).

---

## Running tests

```bash
cd services/financial-engine
pip install -r requirements.txt
pytest tests/ -v
```

All tests run fully offline — no DB, no cost-estimator required.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(empty)* | PostgreSQL connection string. If absent, only inline mode works. |
| `COST_ESTIMATOR_URL` | `http://cost-estimator:8084` | Base URL of the cost-estimator service. |
| `COST_ESTIMATOR_TIMEOUT_S` | `5` | Seconds before giving up on cost-estimator call. |

---

## File structure

```
services/financial-engine/
  main.py        FastAPI app (lifespan, endpoints, DB/CE clients)
  benchmarks.py  BenchmarkStore + Isolation Forest fitting
  analyzer.py    Scoring logic + reason_text builder
  models.py      Pydantic request/response models
  Dockerfile
  requirements.txt
  tests/
    conftest.py        Synthetic fixtures (no DB)
    test_benchmarks.py GroupStats + IF score tests
    test_analyzer.py   Scoring logic + language policy tests
    test_api.py        FastAPI endpoint tests
  README.md
```
