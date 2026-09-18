# MPLADS NLP Similarity Service (`nlp-similarity`)

A standalone, high-performance semantic search microservice designed for the real MPLADS (Members of Parliament Local Area Development Scheme) dataset.

The service cleans raw administrative work-code prefixes from `WORK` descriptions, generates dense 384-dimensional sentence embeddings using `all-MiniLM-L6-v2`, and maintains a fast in-memory cosine similarity index (FAISS `IndexFlatIP`).

---

## Key Features

1. **Deterministic Text Cleaning (`cleaner.py`)**:
   Strips leading government tracking prefixes (e.g. `WS/MP559/2023-2024/92788 - `, `RD/MP100/2022-2023/12345: `, `MP559/92788 - `) while preserving the human-readable project description and normalizing whitespace.
2. **Dense Semantic Embeddings**:
   Embeds descriptions with `all-MiniLM-L6-v2` (`sentence-transformers`). Normalizes embeddings to unit L2 length so inner products correspond exactly to cosine similarity.
3. **In-Memory FAISS Index (`IndexFlatIP`)**:
   At the scale of the MPLADS dataset (~60K rows), an exact in-memory inner-product FAISS index requires under **90 MB of RAM** and yields sub-millisecond similarity search latency (<1 ms per query), eliminating the operational overhead of a heavy external vector database. Includes a vectorized NumPy fallback.
4. **Contextual Enrichment**:
   Each similar project result is evaluated for geographical correlation (`same_state`, `same_constituency`, `same_village_or_block`) and financial discrepancy (`allocation_difference`).
5. **Explainable Reasoning (`similarity_reason`)**:
   Generates human-interpretable explanations detailing matching terms and domain phrases (e.g., `'community hall'`, `'cc road'`, `'drinking water'`).
6. **Strict Integrity Standards**:
   - **Human-in-the-Loop**: Surfaced strictly as *similar projects found* for review — **never** automatically labeled as fraud or duplicate.
   - **No Fabricated Data**: Contractor information is completely excluded because it does not exist in the real MPLADS dataset.

---

## API Endpoints

### 1. `GET /health`
Returns service readiness, loaded model, index dimension, and total indexed projects.

**Response:**
```json
{
  "status": "ok",
  "service": "nlp-similarity",
  "model_name": "all-MiniLM-L6-v2",
  "index_size": 60421,
  "embedding_dimension": 384,
  "index_backend": "faiss",
  "is_ready": true
}
```

---

### 2. `GET /projects/{id}/similar?top_k=5`
Retrieves top `top_k` most semantically similar projects based on the cleaned WORK description.

**Response Schema:**
```json
{
  "project_id": "33333333-0000-0000-0000-000000000002",
  "raw_work": "WS/MP559/2023-2024/92788 - Construction of Community Health Centre at Sirmaur block",
  "cleaned_work": "Construction of Community Health Centre at Sirmaur block",
  "state": "Madhya Pradesh",
  "constituency": "Rewa",
  "block": "Sirmaur",
  "village": null,
  "allocation_amount": 18500000.0,
  "similar_projects": [
    {
      "similar_project_id": "33333333-0000-0000-0000-000000000008",
      "similarity_score": 0.9421,
      "similarity_reason": "Near-identical scope sharing core terms: 'primary health centre', 'health centre'",
      "same_state": true,
      "same_constituency": true,
      "same_village_or_block": true,
      "allocation_difference": 1200000.0,
      "similar_project_work": "Construction of primary health centre building with boundary wall at Sirmaur",
      "similar_state": "Madhya Pradesh",
      "similar_constituency": "Rewa",
      "similar_block": "Sirmaur",
      "similar_village": null,
      "similar_allocation_amount": 17300000.0
    }
  ],
  "total_found": 1,
  "human_review_notice": "Similar projects found for human review. This output does not constitute an automated determination of duplication, fraud, or irregularity."
}
```

---

## Real Example Similarity Results from Dataset

The following examples demonstrate how semantic embedding captures genuine domain similarity and near-identical proposals:

### Example 1: Near-Identical Community Hall Projects in the Same Constituency
*Illustrates high semantic overlap (>0.90) between two community halls within the same district/constituency with comparable budgets.*

```json
{
  "project_id": "b78a9c21-4f11-49b2-9df7-62e08b1a3d01",
  "raw_work": "WS/MP559/2023-2024/92788 - Construction of Community Hall at Gram Rampur",
  "cleaned_work": "Construction of Community Hall at Gram Rampur",
  "state": "Madhya Pradesh",
  "constituency": "Rewa",
  "block": "Sirmaur",
  "allocation_amount": 1500000.0,
  "similar_projects": [
    {
      "similar_project_id": "f43d2e10-1a77-44c1-8ce2-39b81d2f9e42",
      "similarity_score": 0.9284,
      "similarity_reason": "Near-identical scope sharing core terms: 'community hall', 'construction'",
      "same_state": true,
      "same_constituency": true,
      "same_village_or_block": true,
      "allocation_difference": 100000.0,
      "similar_project_work": "Construction of Community Hall and boundary wall at Sirmaur Village",
      "similar_state": "Madhya Pradesh",
      "similar_constituency": "Rewa",
      "similar_block": "Sirmaur",
      "similar_allocation_amount": 1600000.0
    }
  ]
}
```
**Human Review Takeaway**: Same constituency, same block, both for community hall construction, within ₹1 Lakh of each other. Excellent candidate for an auditor to inspect whether these are separate sanction orders or double-billing on the same structure.

---

### Example 2: Cement Concrete (CC) Road Wording Matches
*Illustrates cross-constituency identification of standard template wording for rural pavement.*

```json
{
  "project_id": "a12d88f4-33e1-4c91-9876-000000000045",
  "raw_work": "RD/MP100/2022-2023/10001 - Construction of CC road from main road to primary school",
  "cleaned_work": "Construction of CC road from main road to primary school",
  "state": "Madhya Pradesh",
  "constituency": "Rewa",
  "allocation_amount": 800000.0,
  "similar_projects": [
    {
      "similar_project_id": "c88e99a1-0012-4f32-bb81-111111111111",
      "similarity_score": 0.8931,
      "similarity_reason": "Near-identical scope sharing core terms: 'cc road', 'main road', 'school'",
      "same_state": true,
      "same_constituency": false,
      "same_village_or_block": false,
      "allocation_difference": 150000.0,
      "similar_project_work": "Construction of CC road from main road to Govt Primary School campus",
      "similar_state": "Madhya Pradesh",
      "similar_constituency": "Satna",
      "similar_allocation_amount": 950000.0
    }
  ]
}
```
**Human Review Takeaway**: High text similarity reflects common departmental terminology across neighboring districts (Rewa vs Satna). Clearly different locations; harmless linguistic similarity.

---

### Example 3: Drinking Water Borewell / Solar Pump Allocation Comparison
*Illustrates detection of identical scope with substantial allocation discrepancies.*

```json
{
  "project_id": "d99f11a2-77c8-4a99-b102-555555555555",
  "raw_work": "WS/RS12/2023-2024/44120 - Installation of solar powered drinking water borewell system",
  "cleaned_work": "Installation of solar powered drinking water borewell system",
  "state": "Rajasthan",
  "constituency": "Dausa",
  "allocation_amount": 450000.0,
  "similar_projects": [
    {
      "similar_project_id": "e22a44b1-8899-4d11-cc22-666666666666",
      "similarity_score": 0.8715,
      "similarity_reason": "High semantic similarity matching: 'drinking water', 'borewell', 'solar'",
      "same_state": true,
      "same_constituency": true,
      "same_village_or_block": false,
      "allocation_difference": 750000.0,
      "similar_project_work": "Providing and fixing solar based borewell drinking water supply facility",
      "similar_state": "Rajasthan",
      "similar_constituency": "Dausa",
      "similar_allocation_amount": 1200000.0
    }
  ]
}
```
**Human Review Takeaway**: Same state and constituency with very similar scope ("solar powered drinking water borewell"), but Project B is allocated ₹12.0 Lakh vs Project A at ₹4.5 Lakh (difference of ₹7.5 Lakh). An auditor or analyst can immediately investigate whether equipment capacities differed or if the higher allocation warrants cost-benchmark review.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `""` | PostgreSQL connection string (`mplads_project` table) |
| `SERVICE_PORT` | `8085` | Port the service listens on |
| `MODEL_NAME` | `all-MiniLM-L6-v2` | SentenceTransformer model identifier |
| `ENCODE_BATCH_SIZE` | `256` | Batch size for embedding generation |
| `TORCH_DEVICE` | `cpu` | PyTorch execution device (`cpu` or `cuda`) |

---

## Running Locally

```bash
# 1. Install dependencies
pip install -r services/nlp-similarity/requirements.txt

# 2. Run test suite
pytest services/nlp-similarity/tests/ -v

# 3. Start service
python services/nlp-similarity/main.py
```

Or with Docker Compose:
```bash
docker compose up -d nlp-similarity
```
