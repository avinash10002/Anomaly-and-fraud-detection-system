"""
main.py
=======
FastAPI microservice for Image Inspection & Defect Analysis (image-engine).

CRITICAL PROVENANCE RULE:
The real MPLADS dataset has NO historical inspection imagery.
This service MUST NEVER claim demo images are real government records.
Every record processed or returned must carry a `source_type` field set to either:
  - "DEMO_SYNTHETIC" (fabricated for demonstration/pitch)
  - "USER_UPLOADED"  (future genuine user uploads)
Never silently omit this field.

Endpoints:
  GET  /health
  POST /analyze-image
  POST /timeline
"""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from PIL import Image
from detector import get_detector
from models import (
    AnalyzeImageRequest,
    AnalyzeImageResponse,
    HealthResponse,
    Severity,
    SourceType,
    TimelineRequest,
    TimelineResponse,
)
from timeline import compute_timeline_progression

# ---------------------------------------------------------------------------
# Logging & Directories
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("image_engine.main")

load_dotenv()

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
ANNOTATED_DIR = STATIC_DIR / "annotated"
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

SERVICE_PORT = int(os.getenv("SERVICE_PORT", "8082"))
DETECTOR_BACKEND = os.getenv("DETECTOR_BACKEND", "auto")
MODEL_WEIGHTS = os.getenv("MODEL_WEIGHTS", "yolov8n.pt")


# ---------------------------------------------------------------------------
# FastAPI Application Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MPLAD Image Inspection Engine",
    description=(
        "Visual defect inspection and infrastructure degradation timeline tracking.\n\n"
        "**CRITICAL NOTICE:** The official MPLADS dataset contains zero historical inspection imagery. "
        "All demo inspections are explicitly tagged `source_type: DEMO_SYNTHETIC`. "
        "Automated detections always carry `inspection_status: requires_human_review`."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount static folder for annotated inspection images
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Exception Handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception during request processing: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": str(exc),
            "disclaimer": "CRITICAL: Prototype inspection engine. Human auditor review required.",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_image_from_bytes(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded file is not a valid image: {exc}",
        )


async def _load_image_from_url(url: str) -> Image.Image:
    if url.startswith("data:image"):
        try:
            _, b64data = url.split(",", 1)
            raw = base64.b64decode(b64data)
            return _load_image_from_bytes(raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 data URI: {exc}")
    elif url.startswith("http://") or url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to fetch image from URL: HTTP status {resp.status_code}",
                )
            return _load_image_from_bytes(resp.content)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Error downloading image from URL: {exc}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="image_url must be an HTTP(S) link or base64 data URI.",
        )


def _process_inspection(
    image: Image.Image,
    project_id: str,
    capture_date: str,
    source_type: SourceType,
) -> AnalyzeImageResponse:
    image_id = str(uuid.uuid4())
    detector = get_detector(backend=DETECTOR_BACKEND, weights_path=MODEL_WEIGHTS)

    # Run detection
    defect_class, conf, severity, boxes, annotated_img = detector.detect(image)

    # Save annotated image
    annotated_filename = f"ann_{image_id}.jpg"
    annotated_path = ANNOTATED_DIR / annotated_filename
    annotated_img.save(annotated_path, format="JPEG", quality=85)

    annotated_url = f"/static/annotated/{annotated_filename}"

    return AnalyzeImageResponse(
        project_id=project_id,
        image_id=image_id,
        capture_date=capture_date,
        defect_class=defect_class,
        confidence=conf,
        severity=severity,
        inspection_status="requires_human_review",
        source_type=source_type,
        annotated_image_url=annotated_url,
        detected_boxes=boxes,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check & detector status",
    tags=["Ops"],
)
def health() -> HealthResponse:
    """Returns service operational state, detector model name, and backend."""
    detector = get_detector(backend=DETECTOR_BACKEND, weights_path=MODEL_WEIGHTS)
    return HealthResponse(
        status="ok",
        service="image-engine",
        model_name=detector.name,
        detector_backend=DETECTOR_BACKEND,
        source_type_mandatory=True,
        ready=True,
    )


@app.post(
    "/analyze-image",
    response_model=AnalyzeImageResponse,
    summary="Analyze an infrastructure inspection image for civil defects",
    tags=["Inspection"],
)
async def analyze_image(
    request: Request,
    image: Optional[UploadFile] = File(None),
    project_id: Optional[str] = Form(None),
    capture_date: Optional[str] = Form(None),
    source_type: Optional[SourceType] = Form(None),
) -> AnalyzeImageResponse:
    """
    Accepts an inspection image via multipart form upload OR JSON body with `image_url`.

    Required fields:
      - `project_id`: Target project UUID
      - `capture_date`: Inspection date (YYYY-MM-DD)
      - `source_type`: Must be "DEMO_SYNTHETIC" (for pitch) or "USER_UPLOADED"

    Returns:
      - `defect_class`: pothole | crack | surface_deterioration | no_visible_defect
      - `severity`: none | low | medium | high
      - `inspection_status`: always "requires_human_review"
      - `source_type`: Explicit provenance tag
      - `annotated_image_url`: Bounding box visualization
    """
    content_type = request.headers.get("content-type", "")

    # Handle JSON request
    if "application/json" in content_type:
        try:
            body = await request.json()
            json_req = AnalyzeImageRequest(**body)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON payload: {exc}")

        if not json_req.image_url:
            raise HTTPException(status_code=400, detail="Missing image_url in JSON payload.")

        pil_img = await _load_image_from_url(json_req.image_url)
        return _process_inspection(
            image=pil_img,
            project_id=json_req.project_id,
            capture_date=json_req.capture_date,
            source_type=json_req.source_type,
        )

    # Handle Multipart Form Upload
    if not project_id:
        raise HTTPException(status_code=422, detail="Missing form field: project_id")
    if not capture_date:
        raise HTTPException(status_code=422, detail="Missing form field: capture_date")
    if not image:
        raise HTTPException(status_code=422, detail="Missing form field: image file upload")

    # Default source_type to DEMO_SYNTHETIC if not provided, but ensure valid
    effective_source = source_type or SourceType.DEMO_SYNTHETIC

    raw_bytes = await image.read()
    pil_img = _load_image_from_bytes(raw_bytes)

    return _process_inspection(
        image=pil_img,
        project_id=project_id,
        capture_date=capture_date,
        source_type=effective_source,
    )


@app.post(
    "/timeline",
    response_model=TimelineResponse,
    summary="Compute chronological infrastructure degradation score and summary",
    tags=["Inspection"],
)
def timeline(payload: TimelineRequest) -> TimelineResponse:
    """
    Analyzes a sequence of historical inspection captures for an infrastructure project.

    Computes:
      - `degradation_score`: Continuous metric (0.0 to 1.0)
      - `progression_summary`: Human-readable narrative describing defect trajectory
      - `timespan_months`: Elapsed duration across captures
      - `source_types_present`: Provenance breakdown
    """
    try:
        return compute_timeline_progression(
            project_id=payload.project_id,
            captures=payload.captures,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.error("Timeline processing error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to compute timeline: {exc}")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
