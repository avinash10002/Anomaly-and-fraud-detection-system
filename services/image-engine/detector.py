"""
detector.py
===========
Swappable defect detection subsystem for civil infrastructure inspection imagery.

Supported Defect Classes:
  - pothole
  - crack
  - surface_deterioration
  - no_visible_defect

Architecture:
  - BaseDetector: Abstract interface enabling plug-and-play models
    (YOLOv8, fine-tuned RDD2022, StreetView/Mapillary inspection pipelines)
  - YOLOv8Detector: Pretrained deep learning model via Ultralytics
  - ComputerVisionDetector: Heuristic edge/texture/contour detector providing
    deterministic fallbacks, unit test stability, and edge capability
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw

_CURRENT_DIR = str(Path(__file__).resolve().parent)
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

from models import BoundingBox, DefectClass, Severity

log = logging.getLogger("image_engine.detector")

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    YOLO = None
    HAS_ULTRALYTICS = False


def draw_annotations(
    image: Image.Image,
    boxes: List[BoundingBox],
    primary_defect: DefectClass,
    severity: Severity,
) -> Image.Image:
    """Render clean bounding boxes and inspection overlays."""
    annotated = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated)
    w, h = annotated.size

    # Choose color according to severity
    color_map = {
        Severity.NONE: (34, 197, 94),     # Emerald Green
        Severity.LOW: (234, 179, 8),      # Amber
        Severity.MEDIUM: (249, 115, 22),  # Orange
        Severity.HIGH: (239, 68, 68),     # Crimson Red
    }
    box_color = color_map.get(severity, (239, 68, 68))

    for b in boxes:
        x0 = int(b.x_min * w)
        y0 = int(b.y_min * h)
        x1 = int(b.x_max * w)
        y1 = int(b.y_max * h)

        # Draw bounding rectangle with 3px border
        for offset in range(3):
            draw.rectangle([x0 - offset, y0 - offset, x1 + offset, y1 + offset], outline=box_color)

        # Label badge (placed above or below depending on top boundary)
        badge_text = f"{b.label.upper()} ({int(b.confidence * 100)}%)"
        text_bbox = draw.textbbox((x0, y0), badge_text)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        if y0 >= th + 6:
            badge_y0 = y0 - th - 6
            badge_y1 = y0
            text_y = y0 - th - 4
        else:
            badge_y0 = y1
            badge_y1 = min(h, y1 + th + 6)
            text_y = y1 + 2

        draw.rectangle([x0, badge_y0, min(w, x0 + tw + 8), badge_y1], fill=box_color)
        draw.text((x0 + 4, text_y), badge_text, fill=(255, 255, 255))

    # Overall Inspection Header Badge
    header_text = f"INSPECTION: {primary_defect.value.upper()} | SEVERITY: {severity.value.upper()}"
    draw.rectangle([10, 10, min(w - 10, 10 + len(header_text) * 8 + 16), 36], fill=(15, 23, 42))
    draw.text((18, 16), header_text, fill=(255, 255, 255))

    return annotated


class BaseDetector(ABC):
    """Abstract base class for infrastructure defect detectors."""

    @abstractmethod
    def detect(
        self, image: Image.Image
    ) -> Tuple[DefectClass, float, Severity, List[BoundingBox], Image.Image]:
        """
        Inspect an image and return:
          - primary defect class
          - confidence score (0.0 to 1.0)
          - severity level (none, low, medium, high)
          - list of detected bounding boxes
          - annotated PIL Image with bounding boxes & tags
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name or identifier of the detector model."""
        pass

    def draw_annotations(
        self,
        image: Image.Image,
        boxes: List[BoundingBox],
        primary_defect: DefectClass,
        severity: Severity,
    ) -> Image.Image:
        """Delegate to draw_annotations."""
        return draw_annotations(image, boxes, primary_defect, severity)


class ComputerVisionDetector(BaseDetector):
    """
    Computer Vision heuristic detector using edge gradients, contour geometry,
    and texture roughness.
    Provides fast, deterministic, offline-capable defect detection and bounding-box drawing.
    """

    def __init__(self, name: str = "cv-gradient-contour-v1") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def detect(
        self, image: Image.Image
    ) -> Tuple[DefectClass, float, Severity, List[BoundingBox], Image.Image]:
        import cv2

        # Convert PIL to RGB numpy
        img_rgb = np.array(image.convert("RGB"))
        h, w, _ = img_rgb.shape
        total_area = float(h * w)

        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 50, 150)
        edge_density = float(np.sum(edges > 0)) / total_area

        # Morphological operations to find clustered defect regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        defect_boxes: List[BoundingBox] = []
        primary_defect = DefectClass.NO_VISIBLE_DEFECT
        confidence = 0.90

        # Filter significant contours
        significant_contours = []
        for c in contours:
            ca = cv2.contourArea(c)
            if ca > (total_area * 0.01):  # greater than 1% of image
                significant_contours.append((ca, c))

        significant_contours.sort(key=lambda x: x[0], reverse=True)

        if not significant_contours:
            # Check edge density for subtle surface deterioration
            if edge_density > 0.08:
                primary_defect = DefectClass.SURFACE_DETERIORATION
                confidence = round(min(0.60 + edge_density * 2.0, 0.85), 2)
                severity = Severity.LOW
                defect_boxes.append(
                    BoundingBox(
                        x_min=0.1, y_min=0.1, x_max=0.9, y_max=0.9,
                        label="surface_deterioration", confidence=confidence
                    )
                )
            else:
                primary_defect = DefectClass.NO_VISIBLE_DEFECT
                confidence = 0.95
                severity = Severity.NONE
        else:
            total_defect_area = sum(ca for ca, _ in significant_contours[:4])
            area_ratio = total_defect_area / total_area

            # Analyze the largest defect contour geometry
            largest_area, largest_contour = significant_contours[0]
            x, y, cw, ch = cv2.boundingRect(largest_contour)
            aspect_ratio = float(cw) / float(ch) if ch > 0 else 1.0

            # Calculate solidity and bounding box extent
            hull = cv2.convexHull(largest_contour)
            hull_area = cv2.contourArea(hull)
            solidity = float(largest_area) / float(hull_area) if hull_area > 0 else 1.0
            extent = float(largest_area) / float(cw * ch) if (cw * ch) > 0 else 1.0

            # Characterize defect class:
            # - Thin lines / fractures (low extent < 0.30 or extreme aspect ratio or low solidity) -> Crack
            # - Compact, dark depressions (high solidity > 0.50 and extent > 0.35) -> Pothole
            # - Otherwise -> Surface Deterioration
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [largest_contour], -1, 255, -1)
            mean_val = cv2.mean(gray, mask=mask)[0]
            bg_mean = float(np.mean(gray))

            if aspect_ratio > 2.5 or aspect_ratio < 0.40 or extent < 0.30 or (solidity < 0.45 and area_ratio < 0.12):
                primary_defect = DefectClass.CRACK
                confidence = round(min(0.75 + (area_ratio * 1.5), 0.93), 2)
            elif mean_val < (bg_mean * 0.85) and solidity > 0.50 and area_ratio > 0.03:
                primary_defect = DefectClass.POTHOLE
                confidence = round(min(0.78 + (area_ratio * 2.0), 0.95), 2)
            else:
                primary_defect = DefectClass.SURFACE_DETERIORATION
                confidence = round(min(0.70 + (area_ratio * 1.2), 0.89), 2)

            # Map severity by affected area ratio
            if area_ratio < 0.05:
                severity = Severity.LOW
            elif area_ratio < 0.15:
                severity = Severity.MEDIUM
            else:
                severity = Severity.HIGH

            # Build bounding boxes
            for ca, c in significant_contours[:4]:
                bx, by, bw, bh = cv2.boundingRect(c)
                box_label = primary_defect.value
                box_conf = round(max(0.60, min(0.95, confidence - 0.05)), 2)
                defect_boxes.append(
                    BoundingBox(
                        x_min=round(float(bx) / w, 4),
                        y_min=round(float(by) / h, 4),
                        x_max=round(float(bx + bw) / w, 4),
                        y_max=round(float(by + bh) / h, 4),
                        label=box_label,
                        confidence=box_conf,
                    )
                )

        annotated_img = draw_annotations(image, defect_boxes, primary_defect, severity)
        return primary_defect, confidence, severity, defect_boxes, annotated_img


class YOLOv8Detector(BaseDetector):
    """
    Ultralytics YOLOv8 detector adapter.
    Loads generic yolov8n or domain-specific weights (e.g. fine-tuned on RDD2022).
    Falls back gracefully to ComputerVisionDetector if model weights cannot be loaded.
    """

    def __init__(
        self,
        weights_path: str = "yolov8n.pt",
        fallback: Optional[BaseDetector] = None,
    ) -> None:
        self.weights_path = weights_path
        self.fallback: BaseDetector = fallback or ComputerVisionDetector()
        self._model: Any = None
        self._load_error: Optional[str] = None

    @property
    def name(self) -> str:
        if self._model is not None:
            return f"YOLOv8 ({self.weights_path})"
        return f"YOLOv8-fallback ({self.fallback.name})"

    def _get_model(self) -> Any:
        if self._model is None and self._load_error is None:
            if not HAS_ULTRALYTICS:
                self._load_error = "ultralytics not installed"
                log.warning("Ultralytics not installed; using fallback detector.")
                return None
            try:
                log.info("Loading YOLO model from %s...", self.weights_path)
                self._model = YOLO(self.weights_path)
                log.info("YOLO model loaded successfully.")
            except Exception as exc:
                self._load_error = str(exc)
                log.warning("Could not load YOLO model (%s); using fallback.", exc)
        return self._model

    def detect(
        self, image: Image.Image
    ) -> Tuple[DefectClass, float, Severity, List[BoundingBox], Image.Image]:
        model = self._get_model()
        if model is None:
            return self.fallback.detect(image)

        try:
            # Ensure RGB mode for YOLO inference
            rgb_image = image.convert("RGB")
            results = model.predict(rgb_image, verbose=False)
            if not results or len(results) == 0:
                return self.fallback.detect(image)

            res = results[0]
            boxes = res.boxes

            if len(boxes) == 0:
                # No objects detected by model -> run CV detector for subtle road defects
                return self.fallback.detect(image)

            defect_boxes: List[BoundingBox] = []

            for b in boxes:
                coords = b.xyxyn[0].tolist()  # normalized x1, y1, x2, y2
                conf = float(b.conf[0])
                cls_id = int(b.cls[0])
                raw_name = str(res.names.get(cls_id, "")).lower()

                # Map label to defect classes if it matches civil defect terminology
                if any(k in raw_name for k in ("pothole", "hole", "cavity", "pit")):
                    mapped = DefectClass.POTHOLE
                elif any(k in raw_name for k in ("crack", "fracture", "fissure")):
                    mapped = DefectClass.CRACK
                elif any(k in raw_name for k in ("deteriorat", "damage", "wear", "erosion", "raveling")):
                    mapped = DefectClass.SURFACE_DETERIORATION
                else:
                    # Non-defect object (e.g. car, person, vehicle, sign in base COCO model)
                    # Ignore it so it doesn't create false positive defect flags
                    continue

                defect_boxes.append(
                    BoundingBox(
                        x_min=round(coords[0], 4),
                        y_min=round(coords[1], 4),
                        x_max=round(coords[2], 4),
                        y_max=round(coords[3], 4),
                        label=mapped.value,
                        confidence=round(conf, 4),
                    )
                )

            # If the model only detected non-defect objects (e.g. cars), inspect the pavement surface
            if not defect_boxes:
                return self.fallback.detect(image)

            # Determine dominant defect
            defect_boxes.sort(key=lambda x: x.confidence, reverse=True)
            primary_label = defect_boxes[0].label
            primary_defect = DefectClass(primary_label)
            confidence = defect_boxes[0].confidence

            # Calculate severity from box sizes
            total_box_area = sum(
                (b.x_max - b.x_min) * (b.y_max - b.y_min) for b in defect_boxes
            )
            if total_box_area > 0.15:
                severity = Severity.HIGH
            elif total_box_area > 0.05:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            annotated_img = draw_annotations(image, defect_boxes, primary_defect, severity)
            return primary_defect, confidence, severity, defect_boxes, annotated_img

        except Exception as exc:
            log.warning("YOLO prediction error (%s); falling back to CV detector.", exc)
            return self.fallback.detect(image)


# Detector cache keyed by (backend, weights_path)
_detector_cache: Dict[Tuple[str, str], BaseDetector] = {}


def get_detector(
    backend: str = "auto",
    weights_path: str = "yolov8n.pt",
    force_reload: bool = False,
) -> BaseDetector:
    """Factory to retrieve or initialize the configured detector."""
    cache_key = (backend, weights_path)
    if force_reload or cache_key not in _detector_cache:
        if backend == "cv_heuristic":
            _detector_cache[cache_key] = ComputerVisionDetector()
        else:
            # YOLOv8 with automatic CV fallback
            _detector_cache[cache_key] = YOLOv8Detector(weights_path=weights_path)
    return _detector_cache[cache_key]
