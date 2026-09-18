"""
models.py
=========
Pydantic schemas for the nlp-similarity service.
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SimilarProject(BaseModel):
    """
    Metadata and similarity metrics for a matching project.
    Contractor information is strictly omitted as it does not exist in this dataset.
    """
    similar_project_id: str = Field(
        ...,
        description="ID of the matching project",
    )
    similarity_score: float = Field(
        ...,
        description="Cosine similarity score between 0.0 and 1.0",
    )
    similarity_reason: str = Field(
        ...,
        description="Human-interpretable explanation of why the descriptions match",
    )
    same_state: bool = Field(
        ...,
        description="True if both projects are located in the same state",
    )
    same_constituency: bool = Field(
        ...,
        description="True if both projects are located in the same constituency",
    )
    same_village_or_block: bool = Field(
        ...,
        description="True if village or block matches between projects (where administrative data is present)",
    )
    allocation_difference: Optional[float] = Field(
        None,
        description="Absolute difference in allocation amount in INR (|A - B|), or null if either project has no allocation",
    )
    # Optional metadata fields to help the human reviewer verify context
    similar_project_work: Optional[str] = Field(
        None,
        description="Cleaned work description of the matched project",
    )
    similar_state: Optional[str] = Field(
        None,
        description="State of the matched project",
    )
    similar_constituency: Optional[str] = Field(
        None,
        description="Constituency of the matched project",
    )
    similar_block: Optional[str] = Field(
        None,
        description="Block of the matched project",
    )
    similar_village: Optional[str] = Field(
        None,
        description="Village of the matched project",
    )
    similar_allocation_amount: Optional[float] = Field(
        None,
        description="Allocation amount of the matched project in INR",
    )


class SimilarProjectsResponse(BaseModel):
    """
    Response returned by GET /projects/{id}/similar.
    Results are surfaced as 'similar projects found' for human review,
    not classified as fraud or duplicates.
    """
    project_id: str = Field(..., description="Query project ID")
    raw_work: Optional[str] = Field(None, description="Original uncleaned WORK field")
    cleaned_work: str = Field(..., description="Cleaned WORK description used for semantic embedding")
    state: Optional[str] = Field(None, description="State of the query project")
    constituency: Optional[str] = Field(None, description="Constituency of the query project")
    block: Optional[str] = Field(None, description="Block of the query project")
    village: Optional[str] = Field(None, description="Village of the query project")
    allocation_amount: Optional[float] = Field(None, description="Allocation amount in INR")
    similar_projects: List[SimilarProject] = Field(
        default_factory=list,
        description="Top similar projects found (default up to 5)",
    )
    total_found: int = Field(..., description="Number of similar projects returned")
    human_review_notice: str = Field(
        default="Similar projects found for human review. This output does not constitute an automated determination of duplication, fraud, or irregularity.",
        description="Human-in-the-loop review disclaimer",
    )


class HealthResponse(BaseModel):
    """
    Response returned by GET /health.
    """
    status: str = Field(..., description="Service status ('ok' or 'degraded')")
    service: str = "nlp-similarity"
    model_name: str = Field(..., description="Embedding model name (e.g. all-MiniLM-L6-v2)")
    index_size: int = Field(..., description="Number of indexed projects in memory")
    embedding_dimension: int = Field(..., description="Vector embedding dimension (384 for MiniLM-L6)")
    index_backend: str = Field(..., description="faiss or numpy_fallback")
    is_ready: bool = Field(..., description="Whether the similarity index is loaded and ready for queries")
