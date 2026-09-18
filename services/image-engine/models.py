"""
models.py
=========
Data schemas and enums for the image-engine inspection service.

CRITICAL INTEGRITY PRINCIPLE:
The real MPLADS dataset has NO historical inspection imagery.
Every record processed or returned MUST carry a source_type field:
  - "DEMO_SYNTHETIC" (fabricated for pitch / demonstration)
  - "USER_UPLOADED"  (future genuine user uploads)
Never silently omit this field.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    DEMO_SYNTHETIC = "DEMO_SYNTHETIC"
    USER_UPLOADED = "USER_UPLOADED"


class DefectClass(str, Enum):
    POTHOLE = "pothole"
    CRACK = "crack"
    SURFACE_DETERIORATION = "surface_deterioration"
    NO_VISIBLE_DEFECT = "no_visible_defect"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BoundingBox(BaseModel):
    x_min: float = Field(..., description="Normalized x-min coordinate (0.0 to 1.0)")
    y_min: float = Field(..., description="Normalized y-min coordinate (0.0 to 1.0)")
    x_max: float = Field(..., description="Normalized x-max coordinate (0.0 to 1.0)")
    y_max: float = Field(..., description="Normalized y-max coordinate (0.0 to 1.0)")
    label: str
    confidence: float


class AnalyzeImageRequest(BaseModel):
    """Payload when sending image as URL via JSON."""
    project_id: str = Field(..., description="Target project UUID or identifier")
    capture_date: str = Field(..., description="Inspection date (YYYY-MM-DD)")
    image_url: Optional[str] = Field(None, description="Public HTTP URL or data URI of the image")
    source_type: SourceType = Field(
        default=SourceType.DEMO_SYNTHETIC,
        description="Must be DEMO_SYNTHETIC or USER_UPLOADED",
    )


class AnalyzeImageResponse(BaseModel):
    """
    Standard analysis response for POST /analyze-image.
    Never omits source_type. Inspection status is always 'requires_human_review'.
    """
    project_id: str
    image_id: str
    capture_date: str
    defect_class: DefectClass
    confidence: float = Field(..., description="Detection confidence score between 0.0 and 1.0")
    severity: Severity = Field(..., description="Severity category: none, low, medium, high")
    inspection_status: str = Field(
        default="requires_human_review",
        description="Always requires_human_review — human-in-the-loop audit protocol",
    )
    source_type: SourceType = Field(
        ...,
        description="Crucial provenance tag: DEMO_SYNTHETIC or USER_UPLOADED",
    )
    annotated_image_url: Optional[str] = Field(
        None,
        description="Relative URL to bounding-box annotated inspection image",
    )
    detected_boxes: List[BoundingBox] = Field(
        default_factory=list,
        description="Detected bounding boxes with labels and confidence",
    )
    disclaimer: str = Field(
        default="CRITICAL NOTICE: Prototype detection intended for human auditor review only. Real MPLADS dataset does not contain historical inspection imagery.",
        description="Mandatory integrity disclaimer",
    )


class CaptureRecord(BaseModel):
    """An individual inspection capture record for timeline progression analysis."""
    image_id: Optional[str] = None
    capture_date: str = Field(..., description="YYYY-MM-DD format")
    defect_class: DefectClass
    severity: Severity
    confidence: Optional[float] = 1.0
    source_type: SourceType = Field(
        default=SourceType.DEMO_SYNTHETIC,
        description="Provenance of this individual capture",
    )


class TimelineRequest(BaseModel):
    """Input payload for POST /timeline."""
    project_id: str
    captures: List[CaptureRecord] = Field(
        ...,
        min_length=1,
        description="List of prior capture records to analyze for degradation progression",
    )


class TimelineResponse(BaseModel):
    """Output for POST /timeline."""
    project_id: str
    degradation_score: float = Field(
        ...,
        description="Overall infrastructure degradation score (0.0 = intact, 1.0 = critical degradation)",
    )
    progression_summary: str = Field(
        ...,
        description="Plain-language summary of progression over time",
    )
    total_captures: int
    timespan_months: float = Field(
        ...,
        description="Number of months elapsed between earliest and latest capture",
    )
    current_severity: Severity
    dominant_defect: DefectClass
    source_types_present: List[SourceType] = Field(
        ...,
        description="All source types present in this timeline",
    )
    disclaimer: str = Field(
        default="CRITICAL NOTICE: Prototype degradation timeline. Real MPLADS dataset does not contain historical imagery.",
    )


class HealthResponse(BaseModel):
    status: str
    service: str = "image-engine"
    model_name: str
    detector_backend: str
    source_type_mandatory: bool = True
    ready: bool
