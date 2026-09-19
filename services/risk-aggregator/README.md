# ⚖️ MPLADS Risk Aggregator Service

Central risk assessment and reporting microservice for the MPLADS Anomaly and Fraud Detection System.

The service aggregates multi-engine signals (financial variance, NLP work description duplication, and computer vision degradation timelines) to compute unified project risk levels and process-stage indicators.

---

## 📡 Endpoints Overview

- `GET /health` — Service liveness and dependency status.
- `GET /api/v1/dashboard/stats` — High-level statistics (totals, risk distribution, status counts).
- `GET /api/v1/projects` — Paginated project list with filtering by state, constituency, category, status, and risk level.
- `GET /api/v1/projects/{id}` — Detailed project view with forensic analysis, timeline captures, and flags.
- `GET /projects/{id}/risk` (or `/api/v1/projects/{id}/risk`) — **Project Risk Assessment & Process Stage Indicator**.
- `PATCH /api/v1/anomaly-flags/{id}` — Confirm or dismiss an anomaly flag with reviewer notes.

---

## 🧭 `GET /projects/{id}/risk` — Stage Indicator Specification

The `GET /projects/{id}/risk` endpoint provides an overview of which part of the project lifecycle an identified pattern points to, decoupled from individual factor reasons.

### 🛡️ Compliance & Framing Standards

1. **Naming**: The field is named `stage_indicator` (array). It is strictly distinct from `risk_factors[].reason` and `recommended_action`.
2. **No Blame or Accusation**: Never names individual contractors, agencies (IDA), MPs, or officers.
3. **Hedged Terminology**: Uses non-accusatory language (*"may indicate," "could point to," "is commonly associated with"*).
4. **Lifecycle Mapping**:
   - `financial` and `nlp_similarity` factor types $\rightarrow$ `"approval_process"` (the recommendation/sanctioning phase).
   - `image_degradation` factor type $\rightarrow$ `"execution_delivery"` (the construction/delivery phase).
5. **Score Threshold**: A stage is flagged (`flagged: true`) if any risk factor mapped to it has a score $\ge 0.70$.
6. **Multi-Stage Handling**: If both stages are flagged, both entries are included in `stage_indicator`, accompanied by the top-level note: `"Multiple process stages show flagged patterns; review both."`.
7. **Clean Fallback**: If no factor clears $0.70$, `stage_indicator` returns an empty array `[]` (never `null`).

---

## 📋 Example Full Responses for Frontend Integration

### Example 1: Single-Stage Flagged Response (`approval_process`)

Triggered when anomalies are isolated to the proposal, costing, or sanctioning phase (e.g. allocation exceeds historical state medians or duplicates an existing work order):

```json
{
  "project_id": "feaa76a4-cbf6-5482-8e84-ecb5600c3f9d",
  "overall_risk_score": 0.94,
  "risk_level": "high",
  "risk_factors": [
    {
      "type": "financial",
      "score": 0.94,
      "reason": "Project allocation (Rs. 7,33,000) is 3.26x the Uttar Pradesh state-category median (Rs. 2,24,500) for Normal/Others works (n=6,592 peer projects). Outlier percentile rank: 97.8th. No approved deviation note found in IDA records."
    }
  ],
  "recommended_action": "Prioritize on-site physical verification and independent financial audit before further fund disbursement.",
  "stage_indicator": [
    {
      "stage": "approval_process",
      "flagged": true,
      "overview": "This pattern is commonly associated with irregularities in how the project was proposed or sanctioned — it does not identify any individual or agency."
    }
  ],
  "note": null
}
```

---

### Example 2: Multi-Stage Flagged Response (`approval_process` + `execution_delivery`)

Triggered when a project exhibits concurrent irregularities across both sanctioning (e.g. overbilling or duplicate scope) and physical execution (e.g. rapid road degradation within 8 months post-completion):

```json
{
  "project_id": "e7becbea-467f-5e0d-a910-fe1e740972ba",
  "overall_risk_score": 0.96,
  "risk_level": "high",
  "risk_factors": [
    {
      "type": "financial",
      "score": 0.96,
      "reason": "Allocation Rs. 5,95,000 is 2.65x UP state-category median Rs. 2,24,500 (n=6,592). Same MP sanctioned peer project at 3.26x median in same quarter — systematic over-recommendation pattern detected."
    },
    {
      "type": "nlp_similarity",
      "score": 0.88,
      "reason": "Work description (cosine similarity 0.94) found verbatim in 6 other UP projects by same MP in FY 2023-24, without site-specific bill of quantities or locational variation in IDA records. Pattern consistent with boilerplate copy-paste."
    },
    {
      "type": "image_degradation",
      "score": 0.91,
      "reason": "Rapid failure timeline: (1) 2023-05-12 intact; (2) 2023-09-20 cracking conf 0.82; (3) 2024-01-18 structural pothole + washout conf 0.93. 8-month failure inconsistent with standard bituminous lifespan."
    }
  ],
  "recommended_action": "Prioritize on-site physical verification and independent financial audit before further fund disbursement.",
  "stage_indicator": [
    {
      "stage": "approval_process",
      "flagged": true,
      "overview": "This pattern is commonly associated with irregularities in how the project was proposed or sanctioned — it does not identify any individual or agency."
    },
    {
      "stage": "execution_delivery",
      "flagged": true,
      "overview": "This pattern is commonly associated with issues in how the work was actually carried out — it does not identify any individual or agency."
    }
  ],
  "note": "Multiple process stages show flagged patterns; review both."
}
```

---

## 🎨 Frontend Rendering Guidance

1. **Badge Display**:
   - When `stage_indicator` contains `"approval_process"`: render an **Approval / Sanction Phase** badge (amber/orange).
   - When `stage_indicator` contains `"execution_delivery"`: render an **Execution & Physical Delivery** badge (red/rose).
2. **Top-level Note**:
   - If `note` is not `null`, display the notice banner:
     > ⚠️ **Multiple Process Stages Flagged**: Review both the project approval history and physical field inspection records.
3. **Tooltip / Overview**:
   - Display `overview` text on hover or as sub-text beneath each badge.
   - Preserves neutral, non-accusatory governance framing across all views.
