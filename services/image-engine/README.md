# MPLAD Image Inspection Engine (`image-engine`)

A standalone computer-vision microservice providing automated defect detection and time-series degradation tracking for civil infrastructure funded under MPLADS.

---

## ⚠️ Critical Provenance & Disclosure Notice for Pitches

> **CRITICAL FACT**: The official government MPLADS dataset contains **no historical inspection imagery**.
> 
> To protect project integrity and transparency during evaluation and pitching:
> 1. **This service NEVER claims its demo inspection imagery originates from government records.**
> 2. **Every record processed or returned MUST carry a mandatory `source_type` field**:
>    - `"DEMO_SYNTHETIC"`: Clearly labeled as synthetic/demo data fabricated for the hackathon pitch.
>    - `"USER_UPLOADED"`: Reserved for genuine user uploads or future live field auditor inspections.
> 3. **Inspection Status**: All automated analyses are designated `inspection_status: "requires_human_review"`. The tool acts as a triage assistant for human auditors, never as an unverified decision-maker.

---

## Model Architecture, Weights, and Limitations

### 1. Model & Weights Used
- **Primary Deep Learning Model**: **YOLOv8 Nano (`yolov8n.pt`)** via Ultralytics (3.2M parameters, fast inference on CPU).
- **Computer Vision Gradient Engine**: Multi-scale Canny edge detection, morphological dilation, and contour topology analysis (`ComputerVisionDetector`).
- **Swappable Interface (`BaseDetector`)**: Built with a plug-and-play abstract base class. Production deployments can swap weights with **RDD2022** (Road Damage Detection 2022) or connect to **Google Street View**, **Mapillary**, or **NIC eSAKSHI mobile inspection APIs** without altering the API contract.

### 2. Defect Classes
- `pothole`: Depressions, localized cavity breaks, asphalt voids.
- `crack`: Longitudinal, transverse, alligator, or boundary wall fractures.
- `surface_deterioration`: General surface raveling, erosion, gravel stripping.
- `no_visible_defect`: Structurally intact and well-maintained surfaces.

### 3. Limitations (Pitch Talking Points)
When presenting to judges and technical evaluators, be completely transparent about:
- **Perspective & Angle Sensitivity**: Overhead aerial drone photos vs. ground-level mobile phone photos exhibit different visual scales; perspective calibration will be needed for exact physical metric estimation (e.g. area in $m^2$).
- **Lighting & Weather Artifacts**: Shadows, puddles, and high sun reflection can introduce visual noise; the system mitigates this by generating bounding box confidence scores and flagging all outputs for human audit.
- **Generic Base Weights vs Domain Road Weights**: Off-the-shelf YOLO weights detect general object geometries; for production, fine-tuning on the 47,000-image RDD2022 dataset is recommended to separate minor asphalt hairline cracks from major structural faults.

---

## API Endpoints

### 1. `GET /health`
Returns service operational state, detector model name, and backend.

```json
{
  "status": "ok",
  "service": "image-engine",
  "model_name": "YOLOv8 (yolov8n.pt)",
  "detector_backend": "auto",
  "source_type_mandatory": true,
  "ready": true
}
```

---

### 2. `POST /analyze-image`
Analyzes a single inspection image. Accepts either a multipart form upload or a JSON body with `image_url`.

**Form Parameters:**
- `image`: Image file upload (JPEG/PNG)
- `project_id`: Project UUID
- `capture_date`: Inspection date (`YYYY-MM-DD`)
- `source_type`: `"DEMO_SYNTHETIC"` or `"USER_UPLOADED"` (default: `"DEMO_SYNTHETIC"`)

**JSON Body (Alternative):**
```json
{
  "project_id": "33333333-0000-0000-0000-000000000001",
  "capture_date": "2023-09-15",
  "image_url": "https://images.unsplash.com/photo-1515162816999-a0c47dc192f7",
  "source_type": "DEMO_SYNTHETIC"
}
```

**Response:**
```json
{
  "project_id": "33333333-0000-0000-0000-000000000001",
  "image_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "capture_date": "2023-09-15",
  "defect_class": "pothole",
  "confidence": 0.88,
  "severity": "high",
  "inspection_status": "requires_human_review",
  "source_type": "DEMO_SYNTHETIC",
  "annotated_image_url": "/static/annotated/ann_9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d.jpg",
  "detected_boxes": [
    {
      "x_min": 0.245,
      "y_min": 0.381,
      "x_max": 0.612,
      "y_max": 0.745,
      "label": "pothole",
      "confidence": 0.88
    }
  ],
  "disclaimer": "CRITICAL NOTICE: Prototype detection intended for human auditor review only. Real MPLADS dataset does not contain historical inspection imagery."
}
```

---

### 3. `POST /timeline`
Evaluates chronological progression across sequential captures for an asset.

**Request:**
```json
{
  "project_id": "33333333-0000-0000-0000-000000000001",
  "captures": [
    {
      "capture_date": "2022-09-01",
      "defect_class": "no_visible_defect",
      "severity": "none",
      "confidence": 0.95,
      "source_type": "DEMO_SYNTHETIC"
    },
    {
      "capture_date": "2023-03-15",
      "defect_class": "crack",
      "severity": "medium",
      "confidence": 0.82,
      "source_type": "DEMO_SYNTHETIC"
    },
    {
      "capture_date": "2023-09-01",
      "defect_class": "pothole",
      "severity": "high",
      "confidence": 0.89,
      "source_type": "DEMO_SYNTHETIC"
    }
  ]
}
```

**Response:**
```json
{
  "project_id": "33333333-0000-0000-0000-000000000001",
  "degradation_score": 0.885,
  "progression_summary": "Defect severity increased from none to high over 3 captures spanning 12.0 months.",
  "total_captures": 3,
  "timespan_months": 12.0,
  "current_severity": "high",
  "dominant_defect": "pothole",
  "source_types_present": [
    "DEMO_SYNTHETIC"
  ],
  "disclaimer": "CRITICAL NOTICE: Prototype degradation timeline. Real MPLADS dataset does not contain historical imagery."
}
```

---

## Running Locally

```bash
# 1. Install dependencies
pip install -r services/image-engine/requirements.txt

# 2. Run test suite
pytest services/image-engine/tests -v

# 3. Start service
python services/image-engine/main.py
```
Or via Docker:
```bash
docker compose up -d image-engine
```
