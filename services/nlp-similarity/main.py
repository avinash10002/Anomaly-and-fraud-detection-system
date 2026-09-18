"""
main.py
=======
FastAPI microservice for NLP Similarity on MPLADS WORK descriptions.

Features:
- Cleans WORK description by stripping administrative prefixes (e.g. 'WS/MP559/2023-2024/92788 - ').
- Generates 384-dimensional dense semantic embeddings using all-MiniLM-L6-v2.
- In-memory FAISS IndexFlatIP (or vectorized cosine fallback) for fast nearest-neighbor retrieval.
- Exposes:
    GET /health
    GET /projects/{id}/similar?top_k=5
- Does NOT classify results as duplicates or fraud — surfaces them as "similar projects found"
  for human review.
- Never invents or relies upon contractor data.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from indexer import NLPSimilarityIndex
from models import HealthResponse, SimilarProjectsResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nlp_similarity.main")

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
MODEL_NAME = os.getenv("MODEL_NAME", "all-MiniLM-L6-v2")
BATCH_SIZE = int(os.getenv("ENCODE_BATCH_SIZE", "256"))
DEVICE = os.getenv("TORCH_DEVICE", "cpu")
SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8085"))

# Global similarity index instance
_index: Optional[NLPSimilarityIndex] = None


def get_index() -> NLPSimilarityIndex:
    global _index
    if _index is None:
        _index = NLPSimilarityIndex(model_name=MODEL_NAME, device=DEVICE)
    return _index


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    index = get_index()
    if DATABASE_URL:
        try:
            log.info("Populating similarity index from DATABASE_URL...")
            count = index.load_from_db(DATABASE_URL, batch_size=BATCH_SIZE)
            log.info("Successfully indexed %d projects from database.", count)
        except Exception as exc:
            log.warning(
                "Could not load projects from DB (%s). "
                "The service will start in degraded mode. Provide records via API or reload.",
                exc,
            )
            # Mark loaded as True with 0 records so healthcheck doesn't crash
            index._is_loaded = True
    else:
        log.warning(
            "DATABASE_URL not set. Service starting with empty similarity index. "
            "Set DATABASE_URL to populate from mplads_project."
        )
        index._is_loaded = True
    yield


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MPLAD NLP Similarity Service",
    description=(
        "Semantic similarity search service for MPLADS WORK descriptions.\n\n"
        "**Important Note:** Surfaced results indicate text similarity to aid human review. "
        "They do NOT constitute an automated determination of duplication, corruption, or fraud."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error processing request: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "notice": "Surfaced for human review only.",
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check & index status",
    tags=["Ops"],
)
def health() -> HealthResponse:
    """
    Returns service health, loaded model details, index backend (faiss/numpy),
    and count of indexed project descriptions.
    """
    index = get_index()
    summary = index.summary()
    return HealthResponse(**summary)


@app.get(
    "/projects/{id}/similar",
    response_model=SimilarProjectsResponse,
    summary="Find semantically similar projects by description",
    tags=["Similarity"],
    responses={
        200: {"description": "Similar projects found"},
        404: {"description": "Project ID not found in similarity index"},
        503: {"description": "Similarity index not yet loaded"},
    },
)
def get_similar_projects(
    id: str,
    top_k: int = Query(
        default=5,
        ge=1,
        le=50,
        description="Number of top similar projects to return (default: 5)",
    ),
) -> SimilarProjectsResponse:
    """
    Retrieve the top similar projects for a given MPLADS project ID based on cosine similarity
    of their cleaned WORK descriptions.

    Returned fields per similar project:
    - **similar_project_id**: Project UUID
    - **similarity_score**: Cosine similarity (0.0 to 1.0)
    - **similarity_reason**: Human-readable explanation of matching terms/scope
    - **same_state**: Boolean flag
    - **same_constituency**: Boolean flag
    - **same_village_or_block**: Boolean flag
    - **allocation_difference**: Numerical difference in allocation amount (|A - B| in INR)

    ⚠️ **Notice**: These results are provided as similarity indicators for human review.
    No contractor information is used or fabricated.
    """
    index = get_index()
    if not index._is_loaded or index.embeddings is None or len(index.project_ids) == 0:
        raise HTTPException(
            status_code=503,
            detail="Similarity index has no projects loaded or is still initializing.",
        )

    try:
        return index.get_similar(project_id=id, top_k=top_k)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{id}' not found in similarity index.",
        )
    except Exception as exc:
        log.error("Error finding similar projects for '%s': %s", id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Error querying similarity index: {exc}",
        )


# ---------------------------------------------------------------------------
# CLI Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
