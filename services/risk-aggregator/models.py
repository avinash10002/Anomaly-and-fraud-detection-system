"""
models.py
=========
Pydantic models and schemas for the risk-aggregator service.
Matches api/openapi.yaml contract and supports role-based views.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectType(str, Enum):
    ROAD = "road"
    BUILDING = "building"
    PARK = "park"
    OTHER = "other"


class ProjectStatus(str, Enum):
    PLANNED = "planned"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    STALLED = "stalled"
    CANCELLED = "cancelled"
    SANCTIONED = "sanctioned"
    UNSANCTIONED = "unsanctioned"


class SourceEngine(str, Enum):
    FINANCIAL = "financial"
    IMAGE = "image"
    NLP = "nlp"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ImageSource(str, Enum):
    STREETVIEW = "streetview"
    MAPILLARY = "mapillary"
    UPLOAD = "upload"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class UserRole(str, Enum):
    CITIZEN = "citizen"
    OFFICIAL = "official"


# ── Inspection Captures ──────────────────────────────────────────────────────

class ImageCaptureModel(BaseModel):
    id: str
    project_id: str
    source: ImageSource
    capture_date: str
    image_url: str
    defect_class: Optional[str] = None
    defect_confidence: Optional[float] = None
    label: Optional[str] = None
    source_type: str = "MPLADS_HISTORIC"


# ── Anomaly Flags ────────────────────────────────────────────────────────────

class AnomalyFlagModel(BaseModel):
    id: str
    project_id: str
    source_engine: SourceEngine
    score: Optional[float] = None  # None when redacted for citizens
    reason_text: str
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewer_id: Optional[str] = None  # None when redacted for citizens
    flagged_at: str
    source_type: str = "MPLADS_HISTORIC"


class AnomalyFlagPatchRequest(BaseModel):
    review_status: ReviewStatus
    reviewer_id: Optional[str] = None


# ── Analysis Sub-Sections ────────────────────────────────────────────────────

class FinancialAnalysisModel(BaseModel):
    allocation_amount: float
    benchmark_median: float
    benchmark_iqr: float
    deviation_percent: float
    ratio_vs_median: float
    deviation_score: Optional[float] = None
    status_label: str
    reason_text: str


class SimilarProjectModel(BaseModel):
    id: str
    work: str
    state: str
    constituency: str
    similarity_score: Optional[float] = None
    reason: str


class ImageTimelineAnalysisModel(BaseModel):
    total_captures: int
    degradation_score: Optional[float] = None
    progression_summary: str
    captures: List[ImageCaptureModel]
    has_synthetic_data: bool = False
    disclaimer: str = (
        "CRITICAL NOTICE: Prototype inspection data. Real MPLADS records do not contain historical imagery."
    )


# ── Project Model ────────────────────────────────────────────────────────────

class ProjectDetailModel(BaseModel):
    id: str
    title: str
    work: str
    type: str
    category: str
    state: str
    district: str
    constituency: str
    mp_name: str
    contractor_name: str
    cost: float
    sanction_date: str
    completion_date: Optional[str] = None
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    has_synthetic_coords: bool = False
    risk_level: RiskLevel
    risk_score: Optional[float] = None  # Redacted for citizens
    anomaly_count: int = 0
    flags: List[AnomalyFlagModel] = Field(default_factory=list)
    financial_analysis: Optional[FinancialAnalysisModel] = None
    similar_projects: List[SimilarProjectModel] = Field(default_factory=list)
    image_timeline: Optional[ImageTimelineAnalysisModel] = None


class ProjectListItemModel(BaseModel):
    id: str
    title: str
    work: str
    type: str
    category: str
    state: str
    district: str
    constituency: str
    mp_name: str
    contractor_name: str
    cost: float
    sanction_date: str
    completion_date: Optional[str] = None
    status: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    has_synthetic_coords: bool = False
    risk_level: RiskLevel
    risk_score: Optional[float] = None
    anomaly_count: int = 0


class ProjectListResponse(BaseModel):
    data: List[ProjectListItemModel]
    total: int
    page: int
    page_size: int


# ── Dashboard Statistics ─────────────────────────────────────────────────────

class StatusCount(BaseModel):
    status: str
    count: int


class RiskCount(BaseModel):
    level: str
    count: int


class DashboardStatsResponse(BaseModel):
    total_projects: int
    total_allocation: float
    status_distribution: List[StatusCount]
    risk_distribution: List[RiskCount]
    total_anomalies_pending: int
    total_anomalies_confirmed: int
    total_anomalies_dismissed: int


# ── Citizen Map Models ───────────────────────────────────────────────────────

class ConstituencySummary(BaseModel):
    constituency: str
    project_count: int
    total_allocation: float
    high_risk_count: int


class StateSummary(BaseModel):
    state: str
    project_count: int
    total_allocation: float
    constituencies: List[ConstituencySummary]


class WorksNearMeItem(BaseModel):
    id: str
    title: str
    work: str
    state: str
    district: str
    constituency: str
    mp_name: str
    cost: float
    status: str
    lat: float
    lng: float
    risk_level: RiskLevel
    risk_score: Optional[float] = None
    source_type: str = "DEMO_SYNTHETIC"
    disclaimer: str = (
        "DEMO DATA: Synthetic coordinates applied strictly for demonstration. Real MPLADS records have no GPS pins."
    )


# ── Audit Assistant Models ──────────────────────────────────────────────────

class ProjectCitation(BaseModel):
    project_id: str
    title: str
    state: Optional[str] = None
    constituency: Optional[str] = None
    allocation: Optional[float] = None
    category: Optional[str] = None
    flags: List[str] = []


class AuditAssistantQueryRequest(BaseModel):
    question: str
    role: Optional[UserRole] = None


class AuditAssistantQueryResponse(BaseModel):
    question: str
    answer: str
    citations: List[ProjectCitation] = []
    intent: str
    records_found: int
    safe_audit_language: bool = True
    disclaimer: str = (
        "This assistant surfaces anomaly indicators and statistical outliers for audit review. It does not determine fraud."
    )


class AuditAssistantStatusResponse(BaseModel):
    enabled: bool
    service: str = "MPLADS AI Audit Assistant"
    version: str = "1.0.0"
    data_mode: str = "database"
    records_available: Optional[int] = None


class AuditAssistantSuggestionsResponse(BaseModel):
    suggestions: List[str] = Field(default_factory=list)
    data_mode: str = "database"
