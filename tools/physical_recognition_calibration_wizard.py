"""Guided physical calibration wizard for IndexedImageMatcher recognition.

The wizard captures physical card crops into a session directory, writes
``benchmark_cases.json``, then runs the existing offline benchmark from
``tools/benchmark_indexed_recognition.py``. The production recognition logic is
not modified by this script.

Example:
    python tools/physical_recognition_calibration_wizard.py \
      --index output/recognition_index/index_manifest.json \
      --output-dir output/calibration_runs \
      --camera-index 0 \
      --quick-count 5

Use ``--manual-confirm`` when automatic stability/crop capture is not reliable
for the current camera/table setup. In that mode the wizard still guides the
operator and waits for Enter before attempting the snapshot/crop.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))


BLOCKING_CROP_QUALITY_REASONS = {
    "empty_or_uniform_crop",
    "low_content_density",
}


@dataclass
class CalibrationCaptureResult:
    status: str
    crop_path: str | None = None
    snapshot_paths: list[str] | None = None
    error: str | None = None
    diagnostics: dict[str, Any] | None = None


def _image_shape(image: Any) -> tuple[int, int, int]:
    if hasattr(image, "shape"):
        shape = image.shape
        height = int(shape[0])
        width = int(shape[1])
        channels = int(shape[2]) if len(shape) > 2 else 1
        return width, height, channels
    height = len(image)
    width = len(image[0]) if height else 0
    first = image[0][0] if height and width else 0
    channels = len(first) if isinstance(first, (list, tuple)) else 1
    return width, height, channels


def _flatten_brightness(image: Any) -> list[float]:
    if hasattr(image, "reshape"):
        try:
            import cv2

            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            return [float(value) for value in gray.reshape(-1)]
        except Exception:
            pass

    values = []
    for row in image:
        for pixel in row:
            if isinstance(pixel, (list, tuple)):
                values.append(float(sum(pixel) / len(pixel)))
            else:
                values.append(float(pixel))
    return values


def _brightness_matrix(image: Any) -> list[list[float]]:
    if hasattr(image, "shape"):
        try:
            import cv2

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            return [[float(value) for value in row] for row in gray.tolist()]
        except Exception:
            pass

    matrix = []
    for row in image:
        out_row = []
        for pixel in row:
            if isinstance(pixel, (list, tuple)):
                out_row.append(float(sum(pixel) / len(pixel)))
            else:
                out_row.append(float(pixel))
        matrix.append(out_row)
    return matrix


def _crop_image(image: Any, x: int, y: int, width: int, height: int) -> Any:
    if hasattr(image, "__getitem__") and hasattr(image, "shape"):
        return image[y:y + height, x:x + width]
    return [row[x:x + width] for row in image[y:y + height]]


def _simple_std(values: list[float], mean: float) -> float:
    if not values:
        return 0.0
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _edge_density_from_values(values: list[float], width: int, height: int) -> float:
    if width < 2 or height < 2 or not values:
        return 0.0
    edges = 0
    total = 0
    for y in range(height):
        base = y * width
        for x in range(width - 1):
            total += 1
            if abs(values[base + x] - values[base + x + 1]) > 18:
                edges += 1
    for y in range(height - 1):
        base = y * width
        next_base = (y + 1) * width
        for x in range(width):
            total += 1
            if abs(values[base + x] - values[next_base + x]) > 18:
                edges += 1
    return round(edges / total, 4) if total else 0.0


def crop_quality_check(crop: Any) -> dict[str, Any]:
    """Return basic crop quality diagnostics without changing recognition logic."""
    if crop is None:
        return {
            "is_valid": False,
            "reasons": ["missing_crop"],
            "metrics": {},
        }

    width, height, _channels = _image_shape(crop)
    values = _flatten_brightness(crop)
    brightness_mean = sum(values) / len(values) if values else 0.0
    brightness_std = _simple_std(values, brightness_mean)
    overexposed_ratio = sum(1 for value in values if value >= 245) / len(values) if values else 0.0
    edge_density = _edge_density_from_values(values, width, height)
    content_density = min(1.0, brightness_std / 64.0)
    variance_of_laplacian = None

    if hasattr(crop, "shape"):
        try:
            import cv2

            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
            variance_of_laplacian = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:
            variance_of_laplacian = None

    blur_score = variance_of_laplacian if variance_of_laplacian is not None else brightness_std
    metrics = {
        "image_width": width,
        "image_height": height,
        "brightness_mean": round(float(brightness_mean), 4),
        "brightness_std": round(float(brightness_std), 4),
        "overexposed_ratio": round(float(overexposed_ratio), 4),
        "blur_score": round(float(blur_score), 4),
        "edge_density": edge_density,
        "content_density": round(float(content_density), 4),
        "non_background_ratio": round(float(content_density), 4),
    }
    if variance_of_laplacian is not None:
        metrics["variance_of_laplacian"] = round(variance_of_laplacian, 4)

    reasons = []
    if width != 600 or height != 1032:
        reasons.append("unexpected_dimensions")
    if brightness_std < 3.0 and edge_density < 0.005:
        reasons.append("empty_or_uniform_crop")
    if brightness_std < 8.0 or content_density < 0.12:
        reasons.append("low_content_density")
    if blur_score < 20.0:
        reasons.append("blurred_crop")
    if overexposed_ratio > 0.08:
        reasons.append("overexposed_crop")
    if edge_density < 0.015:
        reasons.append("low_edge_density")

    return {
        "is_valid": not reasons,
        "reasons": reasons,
        "metrics": metrics,
    }


def assess_empty_baseline(frame: Any) -> dict[str, Any]:
    """Check whether the baseline snapshot looks like an empty table."""
    if frame is None:
        return {"is_valid": False, "reasons": ["missing_frame"], "metrics": {}}

    width, height, _channels = _image_shape(frame)
    values = _flatten_brightness(frame)
    mean = sum(values) / len(values) if values else 0.0
    std = _simple_std(values, mean)
    total_pixels = max(1, width * height)
    largest_rect_ratio = 0.0
    largest_bright_ratio = 0.0
    candidate_count = 0

    try:
        import cv2
        import numpy as np

        image = np.asarray(frame)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        bright_mask = cv2.inRange(gray, 185, 255)
        kernel = np.ones((5, 5), dtype=np.uint8)
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area <= 0:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(1, w * h)
            fill_ratio = area / rect_area
            area_ratio = area / total_pixels
            aspect = max(w, h) / max(1, min(w, h))
            if fill_ratio >= 0.70 and 1.05 <= aspect <= 2.80:
                candidate_count += 1
                largest_bright_ratio = max(largest_bright_ratio, area_ratio)

        edges = cv2.Canny(gray, 40, 120)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area <= 0:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = max(1, w * h)
            area_ratio = rect_area / total_pixels
            aspect = max(w, h) / max(1, min(w, h))
            if 0.025 <= area_ratio <= 0.55 and 1.05 <= aspect <= 3.20:
                candidate_count += 1
                largest_rect_ratio = max(largest_rect_ratio, area_ratio)
    except Exception:
        high_delta = sum(1 for value in values if abs(value - mean) > 70)
        largest_bright_ratio = high_delta / len(values) if values else 0.0
        largest_rect_ratio = largest_bright_ratio
        candidate_count = 1 if largest_bright_ratio > 0.06 else 0

    metrics = {
        "image_width": width,
        "image_height": height,
        "brightness_mean": round(float(mean), 4),
        "brightness_std": round(float(std), 4),
        "largest_bright_rect_ratio": round(float(largest_bright_ratio), 4),
        "largest_rect_candidate_ratio": round(float(largest_rect_ratio), 4),
        "rect_candidate_count": candidate_count,
    }
    reasons = []
    try:
        target_detection = TargetPreflightRunner._extract_target_roi(frame)
    except Exception:
        target_detection = None
    if target_detection and target_detection.get("target_detected"):
        reasons.append("calibration_target_present")
        metrics["target_roi"] = target_detection.get("target_roi")
        metrics["target_detection_method"] = target_detection.get("detection_method")
    elif largest_bright_ratio >= 0.025 or largest_rect_ratio >= 0.025:
        reasons.append("large_rectangular_object")

    return {
        "is_valid": not reasons,
        "reasons": reasons,
        "metrics": metrics,
    }


class TargetPreflightRunner:
    target_type = "tarotvision_calibration_target_a4_v1"

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index

    def run(
        self,
        session_dir: Path,
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
    ) -> dict[str, Any]:
        print_func("=== PRE-FLIGHT TARGETU A4 ===")
        print_func("")
        print_func("Połóż wydruk TarotVision Calibration Target A4 na środku stołu.")
        print_func("Usuń ręce z pola widzenia.")
        input_func("Naciśnij ENTER, gdy target leży stabilnie.")

        from tarotvision.camera.capture import CameraCapture
        from tarotvision.vision.perspective import TablePerspectiveCorrector

        preflight_dir = Path(session_dir) / "target_preflight"
        preflight_dir.mkdir(parents=True, exist_ok=True)
        camera = CameraCapture(camera_index=self.camera_index, width=1920, height=1080, enable_preflight=False)
        if not camera.open():
            raise RuntimeError("nie udało się otworzyć kamery do target preflight")
        try:
            success, frame = camera.get_frame()
            if not success or frame is None:
                raise RuntimeError("nie udało się pobrać klatki target preflight")
            camera_properties = self._read_camera_properties(camera.cap)
        finally:
            camera.release()

        corrector = TablePerspectiveCorrector()
        warped, _matrix = corrector.get_warped_table(frame, crop_to_markers=True)
        working_frame = warped if warped is not None else frame
        detection = self._extract_target_roi(working_frame)

        frame_path = preflight_dir / "target_preflight_frame.png"
        roi_path = preflight_dir / "target_preflight_roi.png"
        debug_path = preflight_dir / "target_preflight_detection_debug.png"
        self._write_image(frame_path, working_frame)
        self._write_image(roi_path, detection["roi"])
        self._write_detection_debug(
            debug_path,
            working_frame,
            detection["target_roi"],
            detection["target_detection_status"],
            detection["detection_method"],
            detection.get("page_detection_candidates", []),
        )

        report = self.build_report(
            frame=working_frame,
            roi=detection["roi"],
            target_detected=detection["target_detected"],
            target_roi=detection["target_roi"],
            camera_properties=camera_properties,
            target_detection_status=detection["target_detection_status"],
            detection_method=detection["detection_method"],
            detection_debug_path=str(debug_path),
            page_detection_candidates=detection.get("page_detection_candidates", []),
        )
        report["report_path"] = str(preflight_dir / "target_preflight_report.json")
        with open(preflight_dir / "target_preflight_report.json", "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)

        self._print_report(report, print_func)
        return report

    def build_report(
        self,
        frame: Any,
        roi: Any,
        target_detected: bool,
        target_roi: list[int] | None,
        camera_properties: dict[str, Any],
        target_detection_status: str | None = None,
        detection_method: str | None = None,
        detection_debug_path: str | None = None,
        page_detection_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        frame_width, frame_height, _channels = _image_shape(frame)
        metrics = self._quality_metrics(roi)
        recommendation = self._recommendation(metrics, target_detected)
        image_quality_status = self._image_quality_status(metrics)
        resolved_detection_status = target_detection_status or ("detected" if target_detected else "fallback_center_roi")
        resolved_detection_method = detection_method or ("unknown" if target_detected else "fallback_center_roi")
        overall_status = self._overall_status(image_quality_status, bool(target_detected))
        geometry_status = "ok" if target_detected else resolved_detection_status
        operator_message = self._operator_message(image_quality_status, recommendation, bool(target_detected))
        return {
            "target_type": self.target_type,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "target_detected": bool(target_detected),
            "target_roi": target_roi,
            "target_detection_status": resolved_detection_status,
            "image_quality_status": image_quality_status,
            "overall_status": overall_status,
            "quality_status": overall_status,
            "recommendation": recommendation,
            "detection_method": resolved_detection_method,
            "detection_debug_path": detection_debug_path,
            "page_detection_candidates": page_detection_candidates or [],
            "geometry_status": geometry_status,
            "metrics": metrics,
            "camera_properties": camera_properties,
            "operator_message": operator_message,
        }

    @staticmethod
    def _quality_metrics(image: Any) -> dict[str, Any]:
        width, height, _channels = _image_shape(image)
        values = _flatten_brightness(image)
        mean = sum(values) / len(values) if values else 0.0
        std = _simple_std(values, mean)
        overexposed = sum(1 for value in values if value >= 245) / len(values) if values else 0.0
        underexposed = sum(1 for value in values if value <= 10) / len(values) if values else 0.0
        edge_density = _edge_density_from_values(values, width, height)
        blur_score = std
        if hasattr(image, "shape"):
            try:
                import cv2

                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
                blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            except Exception:
                pass
        contrast_score = std
        glare_score = overexposed
        return {
            "blur_score": round(float(blur_score), 4),
            "edge_density": edge_density,
            "brightness_mean": round(float(mean), 4),
            "brightness_std": round(float(std), 4),
            "overexposed_ratio": round(float(overexposed), 4),
            "underexposed_ratio": round(float(underexposed), 4),
            "contrast_score": round(float(contrast_score), 4),
            "glare_score": round(float(glare_score), 4),
        }

    @staticmethod
    def _recommendation(metrics: dict[str, Any], target_detected: bool) -> str:
        if not target_detected:
            return "target_not_detected"
        if metrics["overexposed_ratio"] > 0.08 or metrics["glare_score"] > 0.08:
            return "reduce_glare"
        if metrics["underexposed_ratio"] > 0.15 or metrics["brightness_mean"] < 45:
            return "increase_light"
        if metrics["blur_score"] < 20 or metrics["edge_density"] < 0.01:
            return "improve_focus"
        if metrics["contrast_score"] < 18:
            return "increase_light"
        return "ok_to_continue"

    @staticmethod
    def _image_quality_status(metrics: dict[str, Any]) -> str:
        if metrics["overexposed_ratio"] > 0.08 or metrics["glare_score"] > 0.08:
            return "poor"
        if metrics["blur_score"] < 20 or metrics["edge_density"] < 0.01:
            return "poor"
        if metrics["underexposed_ratio"] > 0.15 or metrics["brightness_mean"] < 45:
            return "warning"
        if metrics["contrast_score"] < 18:
            return "warning"
        if metrics["blur_score"] < 45 or metrics["edge_density"] < 0.02:
            return "warning"
        return "good"

    @staticmethod
    def _overall_status(image_quality_status: str, target_detected: bool) -> str:
        if image_quality_status == "poor":
            return "poor"
        if not target_detected:
            return "warning"
        return image_quality_status

    @staticmethod
    def _operator_message(image_quality_status: str, recommendation: str, target_detected: bool) -> str:
        if image_quality_status == "good" and target_detected:
            return "Jakość obrazu targetu jest dobra. Można kontynuować benchmark kart."
        if image_quality_status == "good" and not target_detected:
            return (
                "Jakość obrazu: OK. Detekcja targetu: NIEPEWNA. "
                "Target jest prawdopodobnie widoczny, ale algorytm nie znalazł poprawnej ramki A4. "
                "Sprawdź target_preflight_detection_debug.png."
            )
        messages = {
            "improve_focus": "Popraw ostrość kamery albo zmień wysokość kamery.",
            "reduce_glare": "Zmień kąt światła, żeby zmniejszyć odbicia i przepalenia.",
            "reduce_exposure": "Zmniejsz ekspozycję lub jasność oświetlenia.",
            "increase_light": "Zwiększ ilość światła bez kierowania go prosto w kartę.",
            "move_target_to_center": "Przesuń target do środka pola roboczego.",
            "target_not_detected": "Target nie został pewnie wykryty; ułóż wydruk centralnie na stole.",
        }
        return messages.get(recommendation, "Popraw warunki obrazu i powtórz preflight.")

    @staticmethod
    def _extract_target_roi(frame: Any) -> dict[str, Any]:
        white_detection = TargetPreflightRunner._detect_white_page_roi(frame)
        page_candidates = white_detection["candidates"]
        if white_detection["roi"] is not None:
            x, y, roi_w, roi_h = white_detection["roi"]
            return {
                "roi": _crop_image(frame, x, y, roi_w, roi_h),
                "target_roi": [x, y, roi_w, roi_h],
                "target_detected": True,
                "target_detection_status": "detected",
                "detection_method": "white_page_component",
                "page_detection_candidates": page_candidates,
            }

        black_detection = TargetPreflightRunner._detect_black_frame_roi(frame)
        page_candidates.extend(black_detection["candidates"])
        if black_detection["roi"] is not None:
            x, y, roi_w, roi_h = black_detection["roi"]
            return {
                "roi": _crop_image(frame, x, y, roi_w, roi_h),
                "target_roi": [x, y, roi_w, roi_h],
                "target_detected": True,
                "target_detection_status": "detected",
                "detection_method": "black_target_frame",
                "page_detection_candidates": page_candidates,
            }

        width, height, _channels = _image_shape(frame)
        roi_w = int(width * 0.72)
        roi_h = int(height * 0.72)
        x = max(0, (width - roi_w) // 2)
        y = max(0, (height - roi_h) // 2)
        return {
            "roi": _crop_image(frame, x, y, roi_w, roi_h),
            "target_roi": [x, y, roi_w, roi_h],
            "target_detected": False,
            "target_detection_status": "fallback_center_roi",
            "detection_method": "fallback_center_roi",
            "page_detection_candidates": page_candidates,
        }

    @staticmethod
    def _detect_white_page_roi(frame: Any) -> dict[str, Any]:
        matrix = _brightness_matrix(frame)
        width, height, _channels = _image_shape(frame)
        if width <= 0 or height <= 0:
            return {"roi": None, "candidates": []}
        values = [value for row in matrix for value in row]
        mean = sum(values) / len(values) if values else 0.0
        threshold = max(170.0, mean + 45.0)
        return TargetPreflightRunner._best_component_for_threshold(
            method="white_page_component",
            matrix=matrix,
            width=width,
            height=height,
            predicate=lambda value: value >= threshold,
            min_area_ratio=0.08,
            max_area_ratio=0.58,
            aspect_min=0.60,
            aspect_max=0.85,
            min_rectangularity=0.50,
            center_tolerance=0.34,
            pad=True,
        )

    @staticmethod
    def _detect_black_frame_roi(frame: Any) -> dict[str, Any]:
        matrix = _brightness_matrix(frame)
        width, height, _channels = _image_shape(frame)
        if width <= 0 or height <= 0:
            return {"roi": None, "candidates": []}
        values = [value for row in matrix for value in row]
        mean = sum(values) / len(values) if values else 0.0
        threshold = min(70.0, mean - 55.0)
        return TargetPreflightRunner._best_component_for_threshold(
            method="black_target_frame",
            matrix=matrix,
            width=width,
            height=height,
            predicate=lambda value: value <= threshold,
            min_area_ratio=0.015,
            max_area_ratio=0.70,
            aspect_min=0.35,
            aspect_max=0.90,
            min_rectangularity=0.08,
            center_tolerance=0.40,
            pad=True,
        )

    @staticmethod
    def _best_component_for_threshold(
        method: str,
        matrix: list[list[float]],
        width: int,
        height: int,
        predicate: Callable[[float], bool],
        min_area_ratio: float,
        max_area_ratio: float,
        aspect_min: float,
        aspect_max: float,
        min_rectangularity: float,
        center_tolerance: float,
        pad: bool,
    ) -> dict[str, Any]:
        margin_x = int(width * 0.06)
        margin_y = int(height * 0.06)
        x_start = margin_x
        x_end = max(margin_x, width - margin_x)
        y_start = margin_y
        y_end = max(margin_y, height - margin_y)
        mask = [[False for _ in range(width)] for _ in range(height)]
        for y in range(y_start, y_end):
            row = matrix[y]
            for x in range(x_start, x_end):
                mask[y][x] = bool(predicate(row[x]))

        candidates: list[dict[str, Any]] = []
        visited: set[tuple[int, int]] = set()
        for start_y in range(y_start, y_end):
            for start_x in range(x_start, x_end):
                if not mask[start_y][start_x] or (start_x, start_y) in visited:
                    continue
                stack = [(start_x, start_y)]
                visited.add((start_x, start_y))
                xs: list[int] = []
                ys: list[int] = []
                while stack:
                    x, y = stack.pop()
                    xs.append(x)
                    ys.append(y)
                    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                        if nx < x_start or nx >= x_end or ny < y_start or ny >= y_end:
                            continue
                        if (nx, ny) in visited or not mask[ny][nx]:
                            continue
                        visited.add((nx, ny))
                        stack.append((nx, ny))
                candidate = TargetPreflightRunner._component_candidate(
                    method=method,
                    xs=xs,
                    ys=ys,
                    width=width,
                    height=height,
                    min_area_ratio=min_area_ratio,
                    max_area_ratio=max_area_ratio,
                    aspect_min=aspect_min,
                    aspect_max=aspect_max,
                    min_rectangularity=min_rectangularity,
                    center_tolerance=center_tolerance,
                )
                candidates.append(candidate)

        accepted = [candidate for candidate in candidates if candidate["accepted"]]
        if not accepted:
            return {"roi": None, "candidates": sorted(candidates, key=lambda item: item["score"], reverse=True)}

        best = max(accepted, key=lambda item: item["score"])
        x0 = int(best["x"])
        y0 = int(best["y"])
        x1 = x0 + int(best["width"]) - 1
        y1 = y0 + int(best["height"]) - 1
        if pad:
            padding = max(2, int(min(width, height) * 0.01))
            x0 = max(0, x0 - padding)
            y0 = max(0, y0 - padding)
            x1 = min(width - 1, x1 + padding)
            y1 = min(height - 1, y1 + padding)
        return {
            "roi": [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
            "candidates": sorted(candidates, key=lambda item: item["score"], reverse=True),
        }

    @staticmethod
    def _component_candidate(
        method: str,
        xs: list[int],
        ys: list[int],
        width: int,
        height: int,
        min_area_ratio: float,
        max_area_ratio: float,
        aspect_min: float,
        aspect_max: float,
        min_rectangularity: float,
        center_tolerance: float,
    ) -> dict[str, Any]:
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        roi_w = x1 - x0 + 1
        roi_h = y1 - y0 + 1
        bbox_area = roi_w * roi_h
        frame_area = width * height
        area_ratio = bbox_area / frame_area if frame_area else 0.0
        aspect = roi_w / roi_h if roi_h else 0.0
        rectangularity = len(xs) / bbox_area if bbox_area else 0.0
        center_x = x0 + roi_w / 2
        center_y = y0 + roi_h / 2
        center_distance = (((center_x - width / 2) / width) ** 2 + ((center_y - height / 2) / height) ** 2) ** 0.5
        reject_reason = None
        if area_ratio < min_area_ratio:
            reject_reason = "too_small"
        elif area_ratio > max_area_ratio:
            reject_reason = "too_large"
        elif not (aspect_min <= aspect <= aspect_max):
            reject_reason = "bad_aspect_ratio"
        elif rectangularity < min_rectangularity:
            reject_reason = "low_rectangularity"
        elif center_distance > center_tolerance:
            reject_reason = "off_center"

        expected_aspect = (aspect_min + aspect_max) / 2
        aspect_score = max(0.0, 1.0 - abs(aspect - expected_aspect) / max(expected_aspect, 0.001))
        area_score = min(1.0, area_ratio / max(min_area_ratio * 2.5, 0.001))
        center_score = max(0.0, 1.0 - center_distance / max(center_tolerance, 0.001))
        rectangularity_score = min(1.0, rectangularity / max(min_rectangularity, 0.001))
        score = area_score + aspect_score + center_score + rectangularity_score
        return {
            "method": method,
            "x": int(x0),
            "y": int(y0),
            "width": int(roi_w),
            "height": int(roi_h),
            "area": int(len(xs)),
            "area_ratio": round(float(area_ratio), 4),
            "aspect_ratio": round(float(aspect), 4),
            "rectangularity": round(float(rectangularity), 4),
            "center_distance": round(float(center_distance), 4),
            "score": round(float(score), 4),
            "accepted": reject_reason is None,
            "reject_reason": reject_reason,
        }

    @staticmethod
    def _read_camera_properties(capture: Any) -> dict[str, Any]:
        props = {
            "frame_width": "CAP_PROP_FRAME_WIDTH",
            "frame_height": "CAP_PROP_FRAME_HEIGHT",
            "fps": "CAP_PROP_FPS",
            "autofocus": "CAP_PROP_AUTOFOCUS",
            "focus": "CAP_PROP_FOCUS",
            "exposure": "CAP_PROP_EXPOSURE",
            "auto_exposure": "CAP_PROP_AUTO_EXPOSURE",
        }
        result = {}
        try:
            import cv2
        except Exception:
            return {key: None for key in props}
        for key, prop_name in props.items():
            prop_id = getattr(cv2, prop_name, None)
            if prop_id is None or capture is None:
                result[key] = None
                continue
            try:
                value = capture.get(prop_id)
                result[key] = None if value is None or value < 0 else float(value)
            except Exception:
                result[key] = None
        return result

    @staticmethod
    def _write_image(path: Path, image: Any) -> None:
        import cv2

        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)

    @staticmethod
    def _write_detection_debug(
        path: Path,
        frame: Any,
        target_roi: list[int] | None,
        target_detection_status: str,
        detection_method: str,
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        import cv2

        path.parent.mkdir(parents=True, exist_ok=True)
        image = frame.copy() if hasattr(frame, "copy") else frame
        if not hasattr(image, "shape"):
            return
        for candidate in candidates or []:
            x = int(candidate["x"])
            y = int(candidate["y"])
            width = int(candidate["width"])
            height = int(candidate["height"])
            color = (120, 120, 120) if not candidate.get("accepted") else (255, 180, 0)
            cv2.rectangle(image, (x, y), (x + width, y + height), color, 1)
        if target_roi:
            x, y, width, height = target_roi
            color = (0, 180, 0) if target_detection_status == "detected" else (0, 180, 255)
            cv2.rectangle(image, (x, y), (x + width, y + height), color, 4)
        label = f"{target_detection_status} / {detection_method}"
        cv2.putText(image, label, (24, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(image, label, (24, 48), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(path), image)

    @staticmethod
    def _print_report(report: dict[str, Any], print_func: Callable[..., None]) -> None:
        print_func("")
        print_func("Wynik:")
        print_func(f"- jakość obrazu: {report.get('image_quality_status', report.get('quality_status'))}")
        print_func(f"- detekcja targetu: {report.get('target_detection_status', report.get('geometry_status'))}")
        print_func(f"- metoda detekcji: {report.get('detection_method', 'unknown')}")
        print_func(f"- ostrość: {'OK' if report['metrics']['blur_score'] >= 20 else 'SŁABA'}")
        print_func(f"- przepalenia: {'WYSOKIE' if report['metrics']['overexposed_ratio'] > 0.08 else 'OK'}")
        print_func(f"- kontrast: {'OK' if report['metrics']['contrast_score'] >= 18 else 'SŁABY'}")
        print_func(f"- geometria: {report['geometry_status']}")
        print_func("")
        print_func("Rekomendacje:")
        print_func(f"1. {report['operator_message']}")


def load_plan(plan_path: str) -> list[dict[str, Any]]:
    with open(plan_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("calibration plan JSON must be a list")
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"plan entry {index} must be an object")
        if not item.get("expected_reference_id"):
            raise ValueError(f"plan entry {index} is missing expected_reference_id")
        if not item.get("display_name"):
            item["display_name"] = item["expected_reference_id"]
    return data


def load_index_manifest(index_path: str) -> dict[str, Any]:
    path = Path(index_path)
    manifest_path = path / "index_manifest.json" if path.is_dir() else path
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict):
        raise ValueError("index manifest JSON must be an object")
    return manifest


def plan_from_index_manifest(index_path: str, quick_count: int | None = None) -> list[dict[str, Any]]:
    manifest = load_index_manifest(index_path)
    references = manifest.get("references") or []
    if not isinstance(references, list):
        raise ValueError("index manifest references must be a list")

    plan = []
    for item in references:
        if not isinstance(item, dict):
            continue
        reference_id = item.get("reference_id")
        if not reference_id:
            continue
        display_name = (
            item.get("display_name")
            or item.get("name")
            or item.get("card_name")
            or reference_id
        )
        plan.append({
            "display_name": display_name,
            "expected_reference_id": reference_id,
        })

    plan = sorted(plan, key=lambda entry: entry["expected_reference_id"])
    if quick_count is not None:
        if quick_count < 1:
            raise ValueError("quick_count must be >= 1")
        plan = plan[:quick_count]
    if not plan:
        raise ValueError("index manifest does not contain reference_id entries")
    return plan


def list_references(index_path: str, print_func: Callable[[str], None] = print) -> list[str]:
    plan = plan_from_index_manifest(index_path)
    reference_ids = [entry["expected_reference_id"] for entry in plan]
    for reference_id in reference_ids:
        print_func(reference_id)
    return reference_ids


def parse_rotations(value: str) -> list[int]:
    rotations = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        rotations.append(int(part))
    if not rotations:
        raise ValueError("at least one rotation must be provided")
    return rotations


def expand_plan_cases(
    plan: list[dict[str, Any]],
    rotations: list[int],
    samples_per_pose: int,
) -> list[dict[str, Any]]:
    if samples_per_pose < 1:
        raise ValueError("samples_per_pose must be >= 1")

    expanded = []
    sequence = 1
    for entry in plan:
        for rotation in rotations:
            for sample_index in range(1, samples_per_pose + 1):
                expanded.append({
                    "sequence_number": sequence,
                    "display_name": entry.get("display_name") or entry["expected_reference_id"],
                    "expected_reference_id": entry["expected_reference_id"],
                    "expected_rotation": int(rotation),
                    "sample_index": sample_index,
                })
                sequence += 1
    return expanded


def build_session_dir(output_dir: str | Path, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H%M%S")
    session_dir = Path(output_dir) / stamp
    (session_dir / "crops").mkdir(parents=True, exist_ok=True)
    (session_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    return session_dir


def write_benchmark_cases(session_dir: Path, cases: list[dict[str, Any]]) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "benchmark_cases.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cases, handle, indent=2, ensure_ascii=False)
    return path


def write_run_manifest(session_dir: Path, manifest: dict[str, Any]) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "run_manifest.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    return path


def _safe_filename(reference_id: str) -> str:
    allowed = []
    for char in reference_id:
        allowed.append(char if char.isalnum() or char in ("-", "_") else "_")
    return "".join(allowed)


def default_benchmark_runner(index_path: str, cases_path: str, output_path: str) -> dict[str, Any]:
    from tools.benchmark_indexed_recognition import (
        benchmark_cases,
        cv2_image_loader,
        load_cases,
        load_index_from_path,
        write_report,
    )
    from tarotvision.recognition.indexed_matcher import IndexedImageMatcher

    index = load_index_from_path(index_path)
    matcher = IndexedImageMatcher(index)
    cases = load_cases(cases_path)
    report = benchmark_cases(cases, matcher, cv2_image_loader)
    write_report(report, output_path)
    return report


class ExistingVisionCapturePipeline:
    """Capture/crop adapter built from existing TarotVision core modules."""

    def __init__(
        self,
        camera_index: int = 0,
        stable_frames: int = 5,
        timeout_seconds: float = 30.0,
    ):
        self.camera_index = camera_index
        self.stable_frames = stable_frames
        self.timeout_seconds = timeout_seconds
        self.camera = None
        self.empty_reference = None
        self.fresh_frame_reads = 5

        from tarotvision.camera.motion import MotionDetector
        from tarotvision.vision.cropper import CardCropper
        from tarotvision.vision.diff import DiffDetector
        from tarotvision.vision.perspective import TablePerspectiveCorrector
        from tarotvision.vision.refinery import CardRefinery

        self.motion_detector = MotionDetector(threshold=1.2, stabilization_time=0.5)
        self.corrector = TablePerspectiveCorrector()
        self.diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
        self.refinery = CardRefinery(margin=20)
        self.cropper = CardCropper()

    def open(self) -> bool:
        from tarotvision.camera.capture import CameraCapture

        self.camera = CameraCapture(
            camera_index=self.camera_index,
            width=1920,
            height=1080,
            enable_preflight=False,
        )
        return bool(self.camera.open())

    def close(self) -> None:
        if self.camera is not None:
            self.camera.release()
            self.camera = None

    def capture_case(
        self,
        case: dict[str, Any],
        session_dir: Path,
        manual_confirm: bool = False,
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
    ) -> CalibrationCaptureResult:
        if self.camera is None:
            raise RuntimeError("camera is not open")

        sequence = int(case["sequence_number"])
        attempt = int(case.get("attempt", 1))
        snapshots_dir = session_dir / "snapshots"
        crops_dir = session_dir / "crops"
        case_id = f"{sequence:03d}_{_safe_filename(case['expected_reference_id'])}_rot{case['expected_rotation']}"
        before_path = snapshots_dir / f"{case_id}_attempt{attempt}_before.png"
        after_path = snapshots_dir / f"{case_id}_attempt{attempt}_after.png"
        crop_path = crops_dir / (
            f"{case_id}_attempt{attempt}_pending.png"
        )

        self._last_baseline_guard = None
        self._last_after_guard = None
        self._last_detected_roi_rect = None
        self._last_detected_frame_ids = None
        baseline_rejection_dir = session_dir / "diagnostics" / case_id / f"attempt{attempt}" / "baseline_rejections"
        empty_frame = self._wait_for_empty_table(
            manual_confirm,
            input_func,
            print_func,
            baseline_rejection_dir=baseline_rejection_dir,
        )
        self._write_image(before_path, empty_frame)
        self.empty_reference = empty_frame

        if manual_confirm:
            card_frame = self._wait_for_card_snapshot(empty_frame, manual_confirm, input_func, print_func)
        else:
            card_frame = self._wait_for_changed_stable_frame(print_func)
        self._write_image(after_path, card_frame)

        crop_image = self._crop_from_changed_frame(card_frame, empty_frame)
        self._write_image(crop_path, crop_image)
        diff_mask_path = None
        diff_mask = getattr(self, "_last_diff_mask", None)
        if diff_mask is not None:
            diff_mask_path = session_dir / "diagnostics" / case_id / f"attempt{attempt}" / "diff_mask.png"
            self._write_image(diff_mask_path, diff_mask)

        if manual_confirm:
            input_func("Zabierz kartę ze stołu i naciśnij Enter...")
        else:
            self._wait_for_empty_table(False, input_func, print_func)

        return CalibrationCaptureResult(
            status="completed",
            crop_path=str(crop_path),
            snapshot_paths=[str(before_path), str(after_path)],
            diagnostics={
                "roi_debug": getattr(self, "_last_roi_debug", None),
                "diff_mask_path": str(diff_mask_path) if diff_mask_path else None,
                "baseline_guard": getattr(self, "_last_baseline_guard", None),
                "after_guard": getattr(self, "_last_after_guard", None),
                "crop_source": getattr(self, "_last_crop_source", "legacy_scaled_frame"),
                "fallback_reason": getattr(self, "_last_fallback_reason", None),
            },
        )

    def _read_warped_frame(self, fresh: bool = False):
        frame = None
        read_count = max(1, int(getattr(self, "fresh_frame_reads", 5))) if fresh else 1
        for index in range(read_count):
            success, frame = self.camera.get_frame()
            if not success or frame is None:
                raise RuntimeError("brak klatki z kamery")
            if fresh and index < read_count - 1:
                time.sleep(0.03)
        warped, matrix = self.corrector.get_warped_table(frame, crop_to_markers=True)
        if warped is None:
            raise RuntimeError("brak ArUco / nie udało się wyprostować stołu")
        self._last_raw_frame = frame
        self._last_table_matrix = matrix
        return warped

    def _wait_for_empty_table(
        self,
        manual_confirm: bool,
        input_func: Callable[[str], str],
        print_func: Callable[..., None],
        baseline_rejection_dir: Path | None = None,
    ):
        if manual_confirm:
            rejection_index = 1
            while True:
                input_func(
                    "KROK A: Usuń z obszaru stołu target A4 i wszystkie karty. "
                    "Zostaw pusty, stabilny stół i naciśnij Enter dopiero wtedy. "
                    "Teraz zostanie wykonany snapshot bazowy pustego stołu..."
                )
                frame = self._read_warped_frame(fresh=True)
                guard = assess_empty_baseline(frame)
                self._last_baseline_guard = guard
                if guard["is_valid"]:
                    return frame
                print_func("UWAGA: snapshot bazowy nie wygląda jak pusty stół:")
                for reason in guard["reasons"]:
                    print_func(f"- {reason}")
                if baseline_rejection_dir is not None:
                    image_path, json_path = self._write_baseline_rejection(
                        baseline_rejection_dir,
                        rejection_index,
                        frame,
                        guard,
                    )
                    rejection_index += 1
                    print_func(f"Diagnostyka odrzuconego baseline: {image_path}")
                    print_func(f"Metryki guard baseline: {json_path}")
                choice = input_func("Usuń obiekty i naciśnij Enter, aby powtórzyć KROK A, albo Q aby zakończyć: ")
                if choice.strip().lower() == "q":
                    raise RuntimeError("baseline guard rejected non-empty table")

        print_func("Czekam na pusty i stabilny stół...")
        start = time.monotonic()
        while time.monotonic() - start < self.timeout_seconds:
            frame = self._wait_for_stable_frame()
            guard = assess_empty_baseline(frame)
            self._last_baseline_guard = guard
            if guard["is_valid"]:
                return frame
            print_func("Wykryto obiekt na stole bazowym; czekam dalej na pusty stół...")
        raise TimeoutError("timeout oczekiwania na pusty stół")

    def _write_baseline_rejection(
        self,
        diagnostics_dir: Path,
        rejection_index: int,
        frame,
        guard: dict[str, Any],
    ) -> tuple[Path, Path]:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        image_path = diagnostics_dir / f"baseline_rejected_{rejection_index:03d}.png"
        json_path = diagnostics_dir / f"baseline_rejected_{rejection_index:03d}.json"
        self._write_image(image_path, frame)
        payload = {
            "image_path": str(image_path),
            "guard": guard,
        }
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        return image_path, json_path

    def _wait_for_card_snapshot(
        self,
        empty_frame,
        manual_confirm: bool,
        input_func: Callable[[str], str],
        print_func: Callable[..., None],
    ):
        if not manual_confirm:
            return self._wait_for_changed_stable_frame(print_func)

        while True:
            input_func(
                "KROK B: Połóż wskazaną kartę w obszarze markerów, ustaw wymagany obrót "
                "i naciśnij Enter dopiero, gdy karta leży stabilnie. "
                "Teraz zostanie wykonany snapshot z kartą..."
            )
            card_frame = self._read_warped_frame(fresh=True)
            guard = self._detect_card_change_guard(card_frame, empty_frame)
            if guard["is_valid"]:
                return card_frame

            print_func("UWAGA: snapshot z kartą nadal wygląda jak pusty stół albo karta jest poza obszarem markerów:")
            for reason in guard["reasons"]:
                print_func(f"- {reason}")
            choice = input_func("Połóż kartę i naciśnij Enter, aby powtórzyć KROK B, albo Q aby zakończyć: ")
            if choice.strip().lower() == "q":
                raise RuntimeError("card snapshot guard rejected empty card frame")

    def _detect_card_change_guard(self, card_frame, empty_frame) -> dict[str, Any]:
        roi_rect, diff_mask, debug = self.diff_detector.detect_change_roi_with_debug(card_frame, empty_frame)
        self._last_detected_roi_rect = roi_rect
        self._last_detected_frame_ids = (id(card_frame), id(empty_frame))
        self._last_roi_debug = debug
        self._last_diff_mask = diff_mask
        if roi_rect is None:
            guard = {
                "is_valid": False,
                "reasons": ["no_card_change_detected"],
                "metrics": debug or {},
            }
        else:
            guard = {
                "is_valid": True,
                "reasons": [],
                "metrics": {
                    "roi_rect": list(roi_rect) if isinstance(roi_rect, tuple) else roi_rect,
                },
            }
        self._last_after_guard = guard
        return guard

    def _wait_for_changed_stable_frame(self, print_func: Callable[..., None]):
        print_func("Czekam na pojawienie się karty i stabilizację obrazu...")
        start = time.monotonic()
        while time.monotonic() - start < self.timeout_seconds:
            frame = self._wait_for_stable_frame()
            if self.empty_reference is None:
                return frame
            roi_rect, _mask = self.diff_detector.detect_change_roi(frame, self.empty_reference)
            if roi_rect is not None:
                return frame
        raise TimeoutError("timeout oczekiwania na kartę")

    def _wait_for_stable_frame(self):
        stable_count = 0
        last_frame = None
        start = time.monotonic()
        self.motion_detector.reset()
        while time.monotonic() - start < self.timeout_seconds:
            frame = self._read_warped_frame()
            is_moving, is_stabilized = self.motion_detector.update(frame)
            if not is_moving:
                stable_count += 1
            else:
                stable_count = 0
            last_frame = frame
            if stable_count >= self.stable_frames or is_stabilized:
                return frame
            time.sleep(0.05)
        if last_frame is not None:
            raise TimeoutError("timeout oczekiwania na stabilny obraz")
        raise RuntimeError("brak klatek do stabilizacji")

    def _crop_from_changed_frame(self, card_frame, empty_frame):
        if getattr(self, "_last_detected_frame_ids", None) == (id(card_frame), id(empty_frame)):
            roi_rect = getattr(self, "_last_detected_roi_rect", None)
            diff_mask = getattr(self, "_last_diff_mask", None)
            _debug = getattr(self, "_last_roi_debug", None)
        else:
            self._detect_card_change_guard(card_frame, empty_frame)
            roi_rect = getattr(self, "_last_detected_roi_rect", None)
            diff_mask = getattr(self, "_last_diff_mask", None)
            _debug = getattr(self, "_last_roi_debug", None)
        if roi_rect is None:
            self._last_after_guard = {
                "is_valid": False,
                "reasons": ["no_card_change_detected"],
                "metrics": _debug or {},
            }
            raise RuntimeError("detektor różnicowy nie wykrył ROI karty")
        card_data = self.refinery.refine_card(card_frame, roi_rect, diff_mask=diff_mask)
        if card_data is None:
            raise RuntimeError("nie udało się doprecyzować geometrii karty")
        raw_frame = getattr(self, "_last_raw_frame", None)
        table_matrix = getattr(self, "_last_table_matrix", None)
        self._last_crop_source = "legacy_scaled_frame"
        self._last_fallback_reason = None

        if raw_frame is not None and table_matrix is not None:
            try:
                import cv2
                import numpy as np

                corners = card_data.get("corners")
                if corners and len(corners) == 4:
                    pts_table = np.array(corners, dtype=np.float32).reshape(-1, 1, 2)
                    inv_matrix = np.linalg.inv(table_matrix)
                    pts_raw = cv2.perspectiveTransform(pts_table, inv_matrix).reshape(-1, 2)

                    h_raw, w_raw = raw_frame.shape[:2]
                    in_bounds = True
                    for pt in pts_raw:
                        x_val, y_val = pt[0], pt[1]
                        if x_val < -2 or x_val > w_raw + 2 or y_val < -2 or y_val > h_raw + 2:
                            in_bounds = False
                            break

                    if in_bounds:
                        src_pts = self.cropper.order_points(pts_raw)
                        dst_pts = np.array([
                            [0, 0],
                            [599, 0],
                            [599, 1031],
                            [0, 1031]
                        ], dtype=np.float32)

                        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
                        crop_image = cv2.warpPerspective(raw_frame, M, (600, 1032))

                        self._last_crop_source = "native_frame"
                        return crop_image
                    else:
                        self._last_fallback_reason = "corners_out_of_bounds"
                else:
                    self._last_fallback_reason = "invalid_card_corners"
            except Exception as e:
                self._last_fallback_reason = f"exception_during_native_mapping: {e}"
        else:
            self._last_fallback_reason = "missing_raw_frame_or_matrix"

        crop_result = self.cropper.crop_card(card_frame, card_data)
        if not crop_result or not crop_result.get("success"):
            raise RuntimeError("nieudany crop karty")
        return crop_result["crop_image"]

    @staticmethod
    def _write_image(path: Path, image) -> None:
        import cv2

        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), image):
            raise RuntimeError(f"nie udało się zapisać obrazu: {path}")


class PhysicalRecognitionWizard:
    def __init__(
        self,
        index_path: str,
        plan_path: str | None,
        output_dir: str,
        camera_index: int = 0,
        rotations: list[int] | None = None,
        samples_per_pose: int = 1,
        quick_count: int | None = None,
        manual_confirm: bool = False,
        auto_accept_quality_ok: bool = False,
        calibration_target_preflight: bool = False,
        preflight_target: bool = False,
        target_preflight_runner: Any | None = None,
        pipeline: Any | None = None,
        benchmark_runner: Callable[[str, str, str], dict[str, Any]] = default_benchmark_runner,
        session_dir_factory: Callable[[str | Path], Path] = build_session_dir,
        input_func: Callable[[str], str] = input,
        print_func: Callable[..., None] = print,
    ):
        self.index_path = index_path
        self.plan_path = plan_path
        self.output_dir = output_dir
        self.camera_index = camera_index
        self.rotations = rotations or [0, 180]
        self.samples_per_pose = samples_per_pose
        self.quick_count = quick_count
        self.manual_confirm = manual_confirm
        self.auto_accept_quality_ok = auto_accept_quality_ok
        self.calibration_target_preflight = calibration_target_preflight
        self.preflight_target = preflight_target
        self.target_preflight_runner = target_preflight_runner
        self.pipeline = pipeline
        self.benchmark_runner = benchmark_runner
        self.session_dir_factory = session_dir_factory
        self.input_func = input_func
        self.print_func = print_func

    def run(self) -> dict[str, Any]:
        session_dir = self.session_dir_factory(self.output_dir)
        started_at = datetime.now().isoformat(timespec="seconds")
        if self.calibration_target_preflight:
            report = self._run_target_preflight_loop(session_dir, allow_continue=False)
            return {
                "session_dir": str(session_dir),
                "target_preflight_report": report,
                "target_preflight_report_path": self._target_preflight_report_path(session_dir, report),
            }

        preflight_report = None
        target_preflight_report_path = None
        if self.preflight_target:
            preflight_report = self._run_target_preflight_loop(session_dir, allow_continue=True)
            target_preflight_report_path = self._target_preflight_report_path(session_dir, preflight_report)
            if preflight_report.get("operator_decision") == "quit":
                return {
                    "session_dir": str(session_dir),
                    "target_preflight_report": preflight_report,
                    "target_preflight_report_path": target_preflight_report_path,
                    "stopped_early": True,
                }

        plan, plan_source, resolved_quick_count = self._resolve_plan()
        planned_cases = expand_plan_cases(plan, self.rotations, self.samples_per_pose)
        completed_cases: list[dict[str, Any]] = []
        failed_cases: list[dict[str, Any]] = []
        case_events: list[dict[str, Any]] = []

        pipeline = self.pipeline or ExistingVisionCapturePipeline(camera_index=self.camera_index)
        benchmark_error = None
        stopped_early = False

        self._print_header(len(planned_cases))
        try:
            if not pipeline.open():
                raise RuntimeError("brak kamery lub nie udało się jej otworzyć")

            for planned_case in planned_cases:
                attempt = 1
                while True:
                    try:
                        attempt_case = dict(planned_case)
                        attempt_case["attempt"] = attempt
                        case_id = self._case_id(attempt_case)
                        self._print_case(attempt_case, len(planned_cases))
                        result = pipeline.capture_case(
                            attempt_case,
                            session_dir,
                            manual_confirm=self.manual_confirm,
                            input_func=self.input_func,
                            print_func=self.print_func,
                        )
                        if result.status != "completed" or not result.crop_path:
                            raise RuntimeError(result.error or "case failed")

                        quality = crop_quality_check(self._load_crop_for_quality(result.crop_path))
                        self._write_attempt_diagnostics(session_dir, case_id, attempt, quality, result)
                        decision = self._resolve_crop_decision(result.crop_path, quality)
                        final_crop_path = self._finalize_attempt_crop(result.crop_path, decision)
                        crop_source = "legacy_scaled_frame"
                        fallback_reason = None
                        if result.diagnostics:
                            crop_source = result.diagnostics.get("crop_source", "legacy_scaled_frame")
                            fallback_reason = result.diagnostics.get("fallback_reason")

                        event = {
                            "case_id": case_id,
                            "attempt": attempt,
                            "status": decision,
                            "crop_path": final_crop_path,
                            "quality_is_valid": quality["is_valid"],
                            "quality_reasons": quality["reasons"],
                            "crop_source": crop_source,
                        }
                        if fallback_reason is not None:
                            event["fallback_reason"] = fallback_reason

                        warning_reasons = sorted(set(quality.get("reasons", [])) & {"blurred_crop", "low_edge_density"})
                        if decision == "accepted" and warning_reasons:
                            event["accepted_with_warnings"] = True
                            event["warning_reasons"] = warning_reasons
                        case_events.append(event)

                        if decision == "accepted":
                            case_data = {
                                "crop_path": final_crop_path,
                                "expected_reference_id": planned_case["expected_reference_id"],
                                "expected_rotation": planned_case["expected_rotation"],
                                "crop_source": crop_source,
                            }
                            if fallback_reason is not None:
                                case_data["fallback_reason"] = fallback_reason
                            if warning_reasons:
                                case_data["accepted_with_warnings"] = True
                                case_data["warning_reasons"] = warning_reasons
                                # Update diagnostic JSON of the attempt
                                diag_file = session_dir / "diagnostics" / case_id / f"attempt{attempt}" / "crop_quality.json"
                                if diag_file.exists():
                                    try:
                                        with open(diag_file, "r", encoding="utf-8") as handle:
                                            diag_data = json.load(handle)
                                        diag_data["accepted_with_warnings"] = True
                                        diag_data["warning_reasons"] = warning_reasons
                                        with open(diag_file, "w", encoding="utf-8") as handle:
                                            json.dump(diag_data, handle, indent=2, ensure_ascii=False)
                                    except Exception:
                                        pass
                            completed_cases.append(case_data)
                            self.print_func(f"Crop zaakceptowany: {final_crop_path}")
                            break
                        if decision == "retaken":
                            attempt += 1
                            continue
                        if decision == "skipped":
                            break
                        if decision == "quit":
                            stopped_early = True
                            break
                    except Exception as exc:
                        failed_cases.append({
                            "sequence_number": planned_case["sequence_number"],
                            "expected_reference_id": planned_case["expected_reference_id"],
                            "expected_rotation": planned_case["expected_rotation"],
                            "status": "failed",
                            "error": str(exc),
                        })
                        choice = self._handle_case_error(exc)
                        if choice == "retry":
                            failed_cases.pop()
                            attempt += 1
                            continue
                        if choice == "quit":
                            stopped_early = True
                        break
                if stopped_early:
                    break
        finally:
            pipeline.close()

        cases_path = write_benchmark_cases(session_dir, completed_cases)
        report_path = session_dir / "indexed_recognition_report.json"
        if completed_cases:
            try:
                self.benchmark_runner(self.index_path, str(cases_path), str(report_path))
            except Exception as exc:
                benchmark_error = str(exc)
                self.print_func(f"Błąd benchmarku: {benchmark_error}")
        else:
            report_path.write_text(
                json.dumps({"summary": {"total_cases": 0}, "cases": []}, indent=2),
                encoding="utf-8",
            )

        manifest = {
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "index_path": self.index_path,
            "plan_source": plan_source,
            "quick_count": resolved_quick_count,
            "plan_path": self.plan_path if plan_source == "file" else None,
            "camera_index": self.camera_index,
            "rotations": self.rotations,
            "samples_per_pose": self.samples_per_pose,
            "total_expected_cases": len(planned_cases),
            "completed_cases": len(completed_cases),
            "failed_cases": len(failed_cases),
            "accepted_cases": sum(1 for event in case_events if event["status"] == "accepted"),
            "retaken_cases": sum(1 for event in case_events if event["status"] == "retaken"),
            "skipped_cases": sum(1 for event in case_events if event["status"] == "skipped"),
            "crop_quality_warnings": sum(1 for event in case_events if not event["quality_is_valid"]),
            "output_dir": str(session_dir),
            "manual_confirm": self.manual_confirm,
            "auto_wait_stable": not self.manual_confirm,
            "auto_accept_quality_ok": self.auto_accept_quality_ok,
            "stopped_early": stopped_early,
            "benchmark_report_path": str(report_path),
            "benchmark_error": benchmark_error,
            "case_failures": failed_cases,
            "case_events": case_events,
        }
        if preflight_report is not None:
            manifest["target_preflight_report_path"] = target_preflight_report_path
        write_run_manifest(session_dir, manifest)
        result = {
            "session_dir": str(session_dir),
            "benchmark_cases_path": str(cases_path),
            "benchmark_report_path": str(report_path),
            "manifest": manifest,
        }
        if preflight_report is not None:
            result["target_preflight_report"] = preflight_report
            result["target_preflight_report_path"] = target_preflight_report_path
        return result

    def _run_target_preflight_loop(self, session_dir: Path, allow_continue: bool) -> dict[str, Any]:
        runner = self.target_preflight_runner or TargetPreflightRunner(camera_index=self.camera_index)
        while True:
            report = runner.run(
                session_dir,
                input_func=self.input_func,
                print_func=self.print_func,
            )
            if not allow_continue or report.get("quality_status") == "good":
                report["operator_decision"] = "continue"
                return report
            self.print_func("Jakość obrazu jest słaba.")
            choice = self.input_func("[A] kontynuuj mimo ostrzeżeń / [R] popraw kamerę/światło i powtórz preflight / [Q] zakończ: ")
            choice = choice.strip().lower()
            if choice == "r":
                continue
            if choice == "q":
                report["operator_decision"] = "quit"
                return report
            report["operator_decision"] = "continue"
            return report

    @staticmethod
    def _target_preflight_report_path(session_dir: Path, report: dict[str, Any]) -> str:
        return str(report.get("report_path") or Path(session_dir) / "target_preflight" / "target_preflight_report.json")

    @staticmethod
    def _case_id(case: dict[str, Any]) -> str:
        return f"{int(case['sequence_number']):03d}_{_safe_filename(case['expected_reference_id'])}_rot{case['expected_rotation']}"

    @staticmethod
    def _load_crop_for_quality(crop_path: str) -> Any:
        path = Path(crop_path)
        if not path.exists():
            return None
        try:
            import cv2

            return cv2.imread(str(path))
        except Exception:
            return None

    def _write_attempt_diagnostics(
        self,
        session_dir: Path,
        case_id: str,
        attempt: int,
        quality: dict[str, Any],
        result: CalibrationCaptureResult,
    ) -> None:
        diagnostics_dir = session_dir / "diagnostics" / case_id / f"attempt{attempt}"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        with open(diagnostics_dir / "crop_quality.json", "w", encoding="utf-8") as handle:
            json.dump(quality, handle, indent=2, ensure_ascii=False)

        # Write crop_source metadata
        crop_source = "legacy_scaled_frame"
        fallback_reason = None
        if result.diagnostics:
            crop_source = result.diagnostics.get("crop_source", "legacy_scaled_frame")
            fallback_reason = result.diagnostics.get("fallback_reason")

        crop_source_data = {"crop_source": crop_source}
        if fallback_reason is not None:
            crop_source_data["fallback_reason"] = fallback_reason
        with open(diagnostics_dir / "crop_source.json", "w", encoding="utf-8") as handle:
            json.dump(crop_source_data, handle, indent=2, ensure_ascii=False)

        roi_debug = None
        if result.diagnostics:
            roi_debug = result.diagnostics.get("roi_debug")
        if roi_debug:
            payload = {"available": True, "roi_debug": roi_debug}
        else:
            payload = {
                "available": False,
                "reason": "not exposed by current wizard/core pipeline",
            }
        with open(diagnostics_dir / "roi_debug.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        diff_mask_path = result.diagnostics.get("diff_mask_path") if result.diagnostics else None
        if not diff_mask_path:
            with open(diagnostics_dir / "diff_mask.json", "w", encoding="utf-8") as handle:
                json.dump({
                    "available": False,
                    "reason": "not exposed by current wizard/core pipeline",
                }, handle, indent=2, ensure_ascii=False)

        for guard_name in ("baseline_guard", "after_guard"):
            guard_payload = result.diagnostics.get(guard_name) if result.diagnostics else None
            if guard_payload:
                payload = {"available": True, guard_name: guard_payload}
            else:
                payload = {
                    "available": False,
                    "reason": "not exposed by current wizard/core pipeline",
                }
            with open(diagnostics_dir / f"{guard_name}.json", "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)

    def _resolve_crop_decision(self, crop_path: str, quality: dict[str, Any]) -> str:
        self.print_func(f"Crop zapisany: {crop_path}")
        blocking_reasons = sorted(set(quality.get("reasons", [])) & BLOCKING_CROP_QUALITY_REASONS)
        warning_reasons = sorted(set(quality.get("reasons", [])) & {"blurred_crop", "low_edge_density"})
        if not quality["is_valid"]:
            self.print_func("UWAGA: crop wygląda podejrzanie:")
            for reason in quality["reasons"]:
                self.print_func(f"- {reason}")
            if warning_reasons and not blocking_reasons:
                self.print_func("Jeśli crop pokazuje całą czytelną kartę, możesz zaakceptować go przez A.")
            else:
                self.print_func("Sugerowana akcja: R — powtórz próbę")
        if blocking_reasons:
            self.print_func("Akceptacja A jest zablokowana dla cropa bez czytelnej karty:")
            for reason in blocking_reasons:
                self.print_func(f"- {reason}")

        if self.auto_accept_quality_ok and quality["is_valid"]:
            return "accepted"
        if not self.manual_confirm:
            return "retaken" if blocking_reasons else "accepted"

        while True:
            self.print_func("Wybierz:")
            if blocking_reasons:
                self.print_func("[A] zaakceptuj crop — zablokowane dla tego cropa")
            else:
                self.print_func("[A] zaakceptuj crop")
            self.print_func("[R] powtórz próbę")
            self.print_func("[S] pomiń tę próbkę")
            self.print_func("[Q] zakończ test")
            choice = self.input_func("Decyzja: ").strip().lower()
            if choice in ("", "a"):
                if blocking_reasons:
                    self.print_func("Akceptacja A jest zablokowana; powtarzam próbę.")
                    return "retaken"
                return "accepted"
            if choice == "r":
                return "retaken"
            if choice == "s":
                return "skipped"
            if choice == "q":
                return "quit"
            self.print_func("Nieznana decyzja. Wybierz A, R, S albo Q.")

    @staticmethod
    def _finalize_attempt_crop(crop_path: str, decision: str) -> str:
        path = Path(crop_path)
        if not path.exists():
            return crop_path
        suffix_by_decision = {
            "accepted": "accepted",
            "retaken": "rejected",
            "skipped": "skipped",
            "quit": "quit",
        }
        suffix = suffix_by_decision.get(decision, decision)
        if path.stem.endswith(f"_{suffix}"):
            return str(path)
        if path.stem.endswith("_pending"):
            new_path = path.with_name(f"{path.stem[:-8]}_{suffix}{path.suffix}")
        else:
            new_path = path.with_name(f"{path.stem}_{suffix}{path.suffix}")
        path.rename(new_path)
        return str(new_path)

    def _resolve_plan(self) -> tuple[list[dict[str, Any]], str, int | None]:
        if self.plan_path:
            return load_plan(self.plan_path), "file", None
        if self.quick_count is not None:
            return plan_from_index_manifest(self.index_path, self.quick_count), "auto_quick_count", self.quick_count

        selected_count = self._prompt_for_plan_count()
        if selected_count is None:
            raise SystemExit(0)
        return plan_from_index_manifest(self.index_path, selected_count), "interactive", selected_count

    def _prompt_for_plan_count(self) -> int | None:
        self.print_func("Nie podano planu testu.")
        self.print_func("")
        self.print_func("Wybierz tryb:")
        self.print_func("[1] szybki test 3 kart")
        self.print_func("[2] szybki test 5 kart")
        self.print_func("[3] szybki test 10 kart")
        self.print_func("[4] pełny test wszystkich kart z indeksu")
        self.print_func("[Q] zakończ")
        choice = self.input_func("Wybór: ").strip().lower()
        if choice == "q":
            return None
        if choice == "1":
            return 3
        if choice == "2":
            return 5
        if choice == "3":
            return 10
        if choice == "4":
            return len(plan_from_index_manifest(self.index_path))
        raise ValueError("nieznany wybór trybu planu")

    def _print_header(self, total_cases: int) -> None:
        self.print_func("=== TarotVision physical recognition calibration ===")
        self.print_func(f"Zaplanowane próbki: {total_cases}")

    def _print_case(self, case: dict[str, Any], total_cases: int) -> None:
        self.print_func("")
        self.print_func(f"Krok {case['sequence_number']}/{total_cases}")
        self.print_func(f"Karta do testu: {case['display_name']}")
        self.print_func(f"Obrót: {case['expected_rotation']}°")
        self.print_func("")
        self.print_func("Sekwencja tej próbki:")
        self.print_func("1. KROK A: usuń target A4 i wszystkie karty; zostaw pusty, stabilny stół.")
        self.print_func("2. KROK B: dopiero potem połóż wskazaną kartę i ustaw wymagany obrót.")
        if case["expected_rotation"] == 180:
            self.print_func(
                "Ustawienie w kroku 2: karta odwrócona o 180°, góra karty skierowana w dół stołu."
            )
        else:
            self.print_func("Ustawienie w kroku 2: karta normalnie, góra karty skierowana do góry stołu.")

    def _handle_case_error(self, exc: Exception) -> str:
        self.print_func(f"Błąd próbki: {exc}")
        choice = self.input_func("[ENTER] ponów próbę / [S] pomiń próbę / [Q] zakończ test: ")
        choice = choice.strip().lower()
        if choice == "q":
            return "quit"
        if choice == "s":
            return "skip"
        return "retry"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guided physical recognition calibration wizard for IndexedImageMatcher.",
    )
    parser.add_argument("--index", help="Path to index_manifest.json or recognition_index directory.")
    parser.add_argument("--plan", help="Optional path to calibration plan JSON.")
    parser.add_argument("--output-dir", default="output/calibration_runs", help="Directory for calibration run sessions.")
    parser.add_argument("--camera-index", type=int, default=0, help="Camera index passed to CameraCapture.")
    parser.add_argument("--quick-count", type=int, help="Use first N reference_ids from index as calibration plan.")
    parser.add_argument("--list-references", action="store_true", help="List reference_id entries from index and exit.")
    parser.add_argument("--rotations", default="0,180", help="Comma-separated rotations, default: 0,180.")
    parser.add_argument("--samples-per-pose", type=int, default=1, help="Number of samples per card/rotation.")
    parser.add_argument(
        "--manual-confirm",
        action="store_true",
        help="Wait for Enter at capture steps instead of automatic stability waiting.",
    )
    parser.add_argument(
        "--auto-accept-quality-ok",
        action="store_true",
        help="Automatically accept crops that pass crop_quality_check. Disabled by default.",
    )
    parser.add_argument(
        "--calibration-target-preflight",
        action="store_true",
        help="Run only A4 calibration target preflight and exit.",
    )
    parser.add_argument(
        "--preflight-target",
        action="store_true",
        help="Run A4 calibration target preflight before card benchmark capture.",
    )
    parser.add_argument(
        "--auto-wait-stable",
        action="store_true",
        default=True,
        help="Default mode: wait automatically for stable empty/card frames.",
    )
    return parser.parse_args()


def print_final_result(result: dict[str, Any], print_func: Callable[[str], None] = print) -> None:
    if "benchmark_report_path" not in result and "target_preflight_report_path" in result:
        print_func("Zakończono preflight targetu A4.")
        print_func(f"Katalog sesji: {result['session_dir']}")
        print_func(f"Raport preflight: {result['target_preflight_report_path']}")
        return

    print_func(f"Zakończono wizard. Katalog sesji: {result['session_dir']}")
    if "target_preflight_report_path" in result:
        print_func(f"Raport preflight: {result['target_preflight_report_path']}")
    if "benchmark_report_path" in result:
        print_func(f"Raport benchmarku: {result['benchmark_report_path']}")


def main() -> int:
    args = parse_args()
    if not args.index and not args.calibration_target_preflight:
        raise SystemExit("--index is required unless --calibration-target-preflight is used")
    if args.list_references:
        list_references(args.index)
        return 0

    rotations = parse_rotations(args.rotations)
    wizard = PhysicalRecognitionWizard(
        index_path=args.index,
        plan_path=args.plan,
        output_dir=args.output_dir,
        camera_index=args.camera_index,
        rotations=rotations,
        samples_per_pose=args.samples_per_pose,
        quick_count=args.quick_count,
        manual_confirm=args.manual_confirm,
        auto_accept_quality_ok=args.auto_accept_quality_ok,
        calibration_target_preflight=args.calibration_target_preflight,
        preflight_target=args.preflight_target,
    )
    result = wizard.run()
    print_final_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
