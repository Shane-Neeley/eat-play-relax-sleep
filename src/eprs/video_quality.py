"""Optional OpenCV-backed video quality evidence for EPRS picture candidates.

This is intentionally an evidence lane, not an aesthetic oracle.  It samples a
bounded number of frames and reports focus, contrast, edge density, sampled
motion, decode health, thumbnail readiness, and center-crop geometry.  It never
rewrites a source or claims that a picture is creatively approved.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib
import json
import math
from pathlib import Path
from typing import Any

from .system import sha256


VIDEO_QUALITY_SCHEMA = "eprs.video-quality/v1"
DEFAULT_MAX_FRAMES = 18
# Procedural EPRS visuals often contain deliberately broad gradients and still
# have crisp edges.  This low default catches obvious decode/blur regressions;
# concrete delivery lanes can raise it with --min-sharpness.
DEFAULT_MIN_SHARPNESS = 2.0
DEFAULT_MIN_CONTRAST = 18.0
DEFAULT_MAX_CROP_FRACTION = 0.40
MAX_SOURCE_BYTES = 4 * 1024 * 1024 * 1024
MAX_FRAME_DIMENSION = 4096
MAX_FRAME_PIXELS = 16_777_216
MAX_DECODE_PIXELS = 250_000_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_opencv() -> tuple[Any, Any]:
    try:
        cv2 = importlib.import_module("cv2")
        numpy = importlib.import_module("numpy")
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV video quality is optional; install it with `make opencv-install` "
            "or run `uv run --extra opencv eprs video-quality ...`."
        ) from exc
    return cv2, numpy


def sample_indices(frame_count: int, max_frames: int = DEFAULT_MAX_FRAMES) -> list[int]:
    """Return evenly spaced, deterministic frame indices."""
    if frame_count < 1:
        return []
    if not 1 <= max_frames <= 240:
        raise ValueError("video quality max_frames must be between 1 and 240")
    count = min(frame_count, max_frames)
    if count == 1:
        return [0]
    return sorted({round(index * (frame_count - 1) / (count - 1)) for index in range(count)})


def crop_geometry(
    width: int,
    height: int,
    target_aspect: float | None,
    max_crop_fraction: float = DEFAULT_MAX_CROP_FRACTION,
) -> dict[str, Any]:
    """Report center-crop loss; this is geometry, not subject-aware safety."""
    if width <= 0 or height <= 0:
        raise ValueError("video dimensions must be positive")
    if target_aspect is None:
        return {
            "evaluated": False,
            "source_aspect": round(width / height, 6),
            "target_aspect": None,
            "crop_fraction": 0.0,
            "within_budget": True,
            "method": "not_requested",
        }
    if not math.isfinite(target_aspect) or target_aspect <= 0:
        raise ValueError("target aspect must be a positive finite number")
    if not 0 <= max_crop_fraction < 1:
        raise ValueError("max_crop_fraction must be between 0 inclusive and 1 exclusive")
    source_aspect = width / height
    if source_aspect >= target_aspect:
        retained_fraction = target_aspect / source_aspect
        method = "center_crop_width"
    else:
        retained_fraction = source_aspect / target_aspect
        method = "center_crop_height"
    crop_fraction = max(0.0, 1.0 - retained_fraction)
    return {
        "evaluated": True,
        "source_aspect": round(source_aspect, 6),
        "target_aspect": round(target_aspect, 6),
        "crop_fraction": round(crop_fraction, 6),
        "within_budget": crop_fraction <= max_crop_fraction,
        "method": method,
        "max_crop_fraction": max_crop_fraction,
    }


def _frame_metrics(cv2: Any, numpy: Any, frame: Any, previous_gray: Any | None) -> tuple[dict[str, float], Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    edges = cv2.Canny(gray, 100, 200)
    metrics = {
        "sharpness_laplacian_variance": float(numpy.var(laplacian)),
        "edge_density": float(cv2.countNonZero(edges) / edges.size),
        "contrast_stddev": float(numpy.std(gray)),
    }
    if previous_gray is not None:
        metrics["sampled_motion_mean_abs_difference"] = float(numpy.mean(cv2.absdiff(gray, previous_gray)))
    return metrics, gray


def _thumbnail_score(metrics: dict[str, float]) -> float:
    contrast_factor = max(0.5, min(1.5, metrics["contrast_stddev"] / 32.0))
    edge_factor = 0.75 + min(0.25, metrics["edge_density"])
    return math.log1p(max(0.0, metrics["sharpness_laplacian_variance"])) * contrast_factor * edge_factor


def analyze_video(
    video: str | Path,
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    min_sharpness: float = DEFAULT_MIN_SHARPNESS,
    min_contrast: float = DEFAULT_MIN_CONTRAST,
    target_aspect: float | None = None,
    max_crop_fraction: float = DEFAULT_MAX_CROP_FRACTION,
) -> dict[str, Any]:
    """Sample one video and return deterministic, review-oriented evidence."""
    source = Path(video).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("video quality source exceeds the 4 GiB safety limit")
    if not math.isfinite(min_sharpness) or min_sharpness < 0:
        raise ValueError("min_sharpness must be a finite non-negative number")
    if not math.isfinite(min_contrast) or min_contrast < 0:
        raise ValueError("min_contrast must be a finite non-negative number")
    cv2, numpy = _load_opencv()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"OpenCV could not open video: {source}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if (
            width <= 0
            or height <= 0
            or width > MAX_FRAME_DIMENSION
            or height > MAX_FRAME_DIMENSION
            or width * height > MAX_FRAME_PIXELS
        ):
            raise ValueError(
                "video dimensions exceed the 4096px/16-megapixel video quality safety limit"
            )
        indices = sample_indices(frame_count, max_frames)
        if len(indices) * width * height > MAX_DECODE_PIXELS:
            raise ValueError(
                "video quality sampling exceeds the 250-megapixel decode budget; "
                "request fewer frames"
            )
        samples: list[dict[str, Any]] = []
        previous_gray = None
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(frame_index))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            metrics, previous_gray = _frame_metrics(cv2, numpy, frame, previous_gray)
            samples.append({
                "frame_index": frame_index,
                "timestamp_seconds": round(frame_index / fps, 6) if fps > 0 else None,
                **{key: round(value, 6) for key, value in metrics.items()},
            })
    finally:
        capture.release()

    if not samples:
        raise ValueError(f"OpenCV decoded no sample frames from video: {source}")
    sharpness = [item["sharpness_laplacian_variance"] for item in samples]
    contrast = [item["contrast_stddev"] for item in samples]
    motion = [item["sampled_motion_mean_abs_difference"] for item in samples if "sampled_motion_mean_abs_difference" in item]
    thumbnail = max(samples, key=_thumbnail_score)
    crop = crop_geometry(width, height, target_aspect, max_crop_fraction)
    thumbnail_ready = (
        min(width, height) >= 360
        and thumbnail["sharpness_laplacian_variance"] >= min_sharpness
        and thumbnail["contrast_stddev"] >= min_contrast
    )
    checks = {
        "sample_decode": len(samples) == len(indices),
        "sharpness_floor": float(numpy.percentile(sharpness, 25)) >= min_sharpness,
        "contrast_floor": float(numpy.percentile(contrast, 25)) >= min_contrast,
        "thumbnail_candidate": thumbnail_ready,
        "crop_geometry": bool(crop["within_budget"]),
    }
    decision = "pass" if all(checks.values()) else "hold"
    return {
        "schema": VIDEO_QUALITY_SCHEMA,
        "source": {
            "path": source.name,
            "path_kind": "basename_redacted",
            "sha256": sha256(source),
        },
        "video": {
            "width": width,
            "height": height,
            "fps": round(fps, 6),
            "frame_count": frame_count,
            "duration_seconds": round(frame_count / fps, 6) if fps > 0 else None,
        },
        "sampling": {
            "requested_frames": max_frames,
            "sampled_frames": len(samples),
            "sample_indices": [item["frame_index"] for item in samples],
        },
        "metrics": {
            "sharpness_laplacian_variance": {
                "min": round(min(sharpness), 6),
                "p25": round(float(numpy.percentile(sharpness, 25)), 6),
                "mean": round(float(numpy.mean(sharpness)), 6),
                "max": round(max(sharpness), 6),
            },
            "contrast_stddev": {
                "min": round(min(contrast), 6),
                "p25": round(float(numpy.percentile(contrast, 25)), 6),
                "mean": round(float(numpy.mean(contrast)), 6),
                "max": round(max(contrast), 6),
            },
            "edge_density_mean": round(float(numpy.mean([item["edge_density"] for item in samples])), 6),
            "sampled_motion_mean_abs_difference": round(float(numpy.mean(motion)), 6) if motion else 0.0,
        },
        "thresholds": {
            "min_sharpness": min_sharpness,
            "min_contrast": min_contrast,
            "max_crop_fraction": max_crop_fraction,
        },
        "crop_geometry": crop,
        "thumbnail_candidate": {
            "frame_index": thumbnail["frame_index"],
            "timestamp_seconds": thumbnail["timestamp_seconds"],
            "sharpness_laplacian_variance": thumbnail["sharpness_laplacian_variance"],
            "contrast_stddev": thumbnail["contrast_stddev"],
            "edge_density": thumbnail["edge_density"],
            "ready_for_review": thumbnail_ready,
        },
        "checks": checks,
        "decision": decision,
        "creative_approval": "not_evaluated",
        "samples": samples,
        "generated_at": _utc_now(),
    }


def write_video_quality_report(video: str | Path, out: str | Path, **kwargs: Any) -> Path:
    """Write one JSON report, replacing only a prior report at the same path."""
    source = Path(video).expanduser().resolve()
    destination = Path(out).expanduser().resolve()
    if source == destination:
        raise ValueError("video quality report output must differ from the source video")
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = analyze_video(source, **kwargs)
    temporary = destination.with_name(f".{destination.name}.partial")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination
