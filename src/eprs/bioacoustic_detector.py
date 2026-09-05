"""Rank short bioacoustic events without pretending to translate them.

This module is the small, dependency-light fusion layer around optional
bioacoustic models. A frame classifier can constrain a target interval, but it
is usually too temporally broad to decide which waveform is the event of
interest. We therefore combine it with transient, pulse-train, or sustained-call
morphology and, when available, a reference recording from the same taxon.

The detector emits reviewable JSON.  It deliberately does not write clips or
approve a source for publication.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any
from uuid import uuid4


DETECTION_SCHEMA = "eprs.bioacoustic-detection/v1"
DEFAULT_SPECIES = "Dryocopus pileatus"
BEHAVIORS = ("transient", "pulse-train", "sustained-call")
DEFAULT_PULSE_MIN_GAP_SECONDS = 0.025
DEFAULT_PULSE_MAX_GAP_SECONDS = 0.220
DEFAULT_PULSE_MIN_COUNT = 4
DEFAULT_PULSE_MIN_FLUX_Z = 4.0
DEFAULT_SUSTAINED_MIN_SNR_DB = 6.0
DEFAULT_MAX_DURATION_SECONDS = 120.0
MAX_ANALYSIS_SAMPLES = 1_500_000
MIN_SAMPLE_RATE_HZ = 1_000
MAX_SAMPLE_RATE_HZ = 192_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        pass
    try:
        return str(Path("$HOME") / resolved.relative_to(Path.home().resolve()))
    except ValueError:
        return str(Path("<external>") / resolved.name)


def _audio_dependencies() -> tuple[Any, Any, Any]:
    """Import optional numerical/audio dependencies with an actionable error."""
    try:
        import numpy as np
        import soundfile as sf
        from scipy import signal
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "bioacoustic detection needs the optional audio lane; run "
            "'uv sync --extra bioacoustic'"
        ) from exc
    return np, sf, signal


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sigmoid(value: float) -> float:
    if value >= 0:
        scaled = 2.718281828459045 ** (-value)
        return 1.0 / (1.0 + scaled)
    scaled = 2.718281828459045**value
    return scaled / (1.0 + scaled)


def _robust_z(values: Any, np: Any) -> Any:
    median = float(np.median(values))
    mad_scale = float(np.median(np.abs(values - median))) * 1.4826
    percentile_scale = float(np.percentile(values, 75) - median)
    scale = max(mad_scale, percentile_scale, 1e-6)
    return np.clip((values - median) / scale, -6.0, 6.0)


def _decode_audio_with_ffmpeg(
    source: str | Path,
    np: Any,
    max_duration_seconds: float,
) -> tuple[Any, int]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            "compressed audio needs ffmpeg and ffprobe on PATH; the source was not modified"
        )
    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels:format=duration",
            "-of",
            "json",
            str(source),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise ValueError(f"could not inspect audio source: {source}")
    try:
        probe_record = json.loads(probe.stdout)
        streams = probe_record["streams"]
        sample_rate = int(streams[0]["sample_rate"])
        channels = int(streams[0]["channels"])
        duration = float(probe_record.get("format", {}).get("duration", 0.0))
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"audio source has no readable audio stream: {source}"
        ) from exc
    _validate_audio_shape(sample_rate, channels, duration, max_duration_seconds)
    if duration and duration * sample_rate > MAX_ANALYSIS_SAMPLES:
        raise ValueError(
            f"audio source has about {duration * sample_rate:.0f} samples per channel; "
            f"analysis is bounded to {MAX_ANALYSIS_SAMPLES} (trim a lossless review region first)"
        )
    decoded = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-ac",
            "1",
            "-c:a",
            "pcm_f32le",
            "-f",
            "f32le",
            "-t",
            str(max_duration_seconds),
            "-",
        ],
        check=False,
        capture_output=True,
    )
    if decoded.returncode != 0 or not decoded.stdout:
        raise ValueError(f"could not decode audio source: {source}")
    samples = np.frombuffer(decoded.stdout, dtype="<f4").copy()
    if samples.size / sample_rate >= max_duration_seconds and not duration:
        raise ValueError(
            "audio source duration could not be probed and reached the analysis limit; "
            "trim a bounded lossless review region first"
        )
    return samples, sample_rate


def _read_audio(source: str | Path, max_duration_seconds: float) -> tuple[Any, int]:
    np, sf, _ = _audio_dependencies()
    try:
        info = sf.info(str(source))
        duration = info.frames / info.samplerate if info.samplerate else 0.0
        _validate_audio_shape(
            info.samplerate, info.channels, duration, max_duration_seconds
        )
        if info.frames > MAX_ANALYSIS_SAMPLES:
            raise ValueError(
                f"audio source has {info.frames} samples per channel; analysis is bounded "
                f"to {MAX_ANALYSIS_SAMPLES} (trim a lossless review region first)"
            )
        samples, sample_rate = sf.read(str(source), dtype="float32", always_2d=True)
        mono = samples.mean(axis=1, dtype=np.float32)
    except RuntimeError:
        mono, sample_rate = _decode_audio_with_ffmpeg(source, np, max_duration_seconds)
    if mono.size == 0:
        raise ValueError(f"audio source is empty: {source}")
    if mono.size > MAX_ANALYSIS_SAMPLES:
        raise ValueError(
            f"decoded audio has {mono.size} samples; analysis is bounded to "
            f"{MAX_ANALYSIS_SAMPLES} (trim a lossless review region first)"
        )
    if not np.isfinite(mono).all():
        raise ValueError(f"audio source contains NaN or infinite samples: {source}")
    return mono, int(sample_rate)


def _validate_audio_shape(
    sample_rate: int,
    channels: int,
    duration: float,
    max_duration_seconds: float,
) -> None:
    if not MIN_SAMPLE_RATE_HZ <= int(sample_rate) <= MAX_SAMPLE_RATE_HZ:
        raise ValueError(
            f"audio sample rate must be between {MIN_SAMPLE_RATE_HZ} and "
            f"{MAX_SAMPLE_RATE_HZ} Hz; found {sample_rate}"
        )
    if not 1 <= int(channels) <= 64:
        raise ValueError(
            f"audio channel count must be between 1 and 64; found {channels}"
        )
    if not math.isfinite(float(duration)) or duration < 0:
        raise ValueError("audio duration must be finite and non-negative")
    if duration > max_duration_seconds:
        raise ValueError(
            f"audio source is {duration:.1f}s; bioacoustic detection is bounded to "
            f"{max_duration_seconds:.1f}s (trim a lossless review region first)"
        )


def _frame_analysis(samples: Any, sample_rate: int) -> dict[str, Any]:
    """Measure transient and spectral features at roughly 6 ms resolution."""
    np, _, signal = _audio_dependencies()
    if samples.size < 32:
        samples = np.pad(samples, (0, 32 - samples.size))
    nperseg = min(2048, max(256, int(round(sample_rate * 0.025))))
    nperseg = min(nperseg, int(samples.size))
    hop = max(1, int(round(nperseg * 0.125)))
    frequencies, times, spectrum = signal.stft(
        samples,
        fs=sample_rate,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg - hop,
        boundary="zeros",
        padded=True,
    )
    magnitude = np.abs(spectrum).astype(np.float64)
    power = np.maximum(magnitude * magnitude, 1e-12)
    normalized = magnitude / np.maximum(magnitude.sum(axis=0, keepdims=True), 1e-12)
    flux = np.zeros(normalized.shape[1], dtype=np.float64)
    if normalized.shape[1] > 1:
        positive_delta = np.maximum(np.diff(normalized, axis=1), 0.0)
        flux[1:] = np.sqrt(np.mean(positive_delta * positive_delta, axis=0))
    flux_z = _robust_z(flux, np)

    nyquist = sample_rate / 2.0
    broad_band = (frequencies >= min(1_000.0, nyquist * 0.1)) & (
        frequencies <= min(18_000.0, nyquist * 0.95)
    )
    broad_power = power[broad_band].sum(axis=0)
    total_power = power.sum(axis=0)
    high_ratio = broad_power / np.maximum(total_power, 1e-12)
    flatness = np.exp(np.mean(np.log(power), axis=0)) / np.maximum(
        np.mean(power, axis=0), 1e-12
    )
    centroid = (frequencies[:, None] * power).sum(axis=0) / np.maximum(
        total_power, 1e-12
    )
    bandwidth = np.sqrt(
        (((frequencies[:, None] - centroid[None, :]) ** 2) * power).sum(axis=0)
        / np.maximum(total_power, 1e-12)
    )
    rms_kernel = np.ones(nperseg, dtype=np.float64) / nperseg
    rms = np.sqrt(
        np.maximum(
            signal.fftconvolve(
                samples.astype(np.float64) ** 2,
                rms_kernel,
                mode="same",
            ),
            1e-12,
        )
    )
    frame_rms = np.interp(times, np.arange(samples.size) / sample_rate, rms)
    rms_z = _robust_z(frame_rms, np)

    # A persistent whistle or hum has little positive spectral flux.  The
    # flatness/high-band terms help prefer broadband impacts without requiring
    # a fixed frequency range that would exclude other real recordings.
    flatness_component = np.clip(
        (flatness - np.percentile(flatness, 10))
        / max(float(np.percentile(flatness, 90) - np.percentile(flatness, 10)), 1e-9),
        0.0,
        1.0,
    )
    broad_component = np.clip(
        (high_ratio - np.percentile(high_ratio, 10))
        / max(
            float(np.percentile(high_ratio, 90) - np.percentile(high_ratio, 10)), 1e-9
        ),
        0.0,
        1.0,
    )
    flux_component = np.clip((flux_z - 0.5) / 6.0, 0.0, 1.0)
    rms_component = np.clip((rms_z - 0.5) / 6.0, 0.0, 1.0)
    event_score = (
        0.55 * flux_component
        + 0.25 * rms_component
        + 0.15 * flatness_component
        + 0.05 * broad_component
    )

    return {
        "times": times,
        "flux_z": flux_z,
        "flatness": flatness,
        "high_ratio": high_ratio,
        "centroid": centroid,
        "bandwidth": bandwidth,
        "event_score": event_score,
        "frame_rms": frame_rms,
        "rms_z": rms_z,
        "hop_seconds": hop / sample_rate,
    }


def _event_vector(event: dict[str, Any], sample_rate: int) -> list[float]:
    features = event["features"]
    nyquist = max(sample_rate / 2.0, 1.0)
    return [
        _clip01(features["spectral_centroid_hz"] / nyquist),
        _clip01(features["spectral_bandwidth_hz"] / nyquist),
        _clip01(features["spectral_flatness"]),
        _clip01(features["broadband_ratio"]),
        _clip01((features["crest_factor"] - 1.0) / 12.0),
    ]


def _segment_events(
    samples: Any,
    sample_rate: int,
) -> tuple[list[dict[str, Any]], float, float]:
    np, _, signal = _audio_dependencies()
    analysis = _frame_analysis(samples, sample_rate)
    score = analysis["event_score"]
    min_distance = max(1, int(round(0.075 / analysis["hop_seconds"])))
    edge_frames = max(1, int(round(0.08 / analysis["hop_seconds"])))
    score[:edge_frames] = 0.0
    score[-edge_frames:] = 0.0
    height = max(0.25, float(np.median(score) + 0.08))
    peaks, properties = signal.find_peaks(
        score,
        distance=min_distance,
        height=height,
        prominence=0.035,
    )
    duration = float(samples.size / sample_rate)
    events: list[dict[str, Any]] = []
    for index in peaks:
        peak_seconds = float(analysis["times"][index])
        left = max(0, int(round((peak_seconds - 0.105) * sample_rate)))
        right = min(samples.size, int(round((peak_seconds + 0.165) * sample_rate)))
        segment = samples[left:right]
        if segment.size == 0:
            continue
        rms = float(np.sqrt(np.mean(segment.astype(np.float64) ** 2)))
        peak_amplitude = float(np.max(np.abs(segment)))
        crest_factor = peak_amplitude / max(rms, 1e-9)
        flux_z = float(analysis["flux_z"][index])
        morphology_score = _clip01(
            0.65 * _clip01((flux_z - 0.5) / 6.0)
            + 0.25 * _clip01((float(analysis["rms_z"][index]) - 0.5) / 6.0)
            + 0.10 * float(analysis["flatness"][index])
        )
        start_seconds = max(0.0, peak_seconds - 0.105)
        end_seconds = min(duration, peak_seconds + 0.165)
        events.append(
            {
                "start_seconds": round(start_seconds, 6),
                "end_seconds": round(end_seconds, 6),
                "peak_seconds": round(peak_seconds, 6),
                "morphology_score": round(morphology_score, 6),
                "features": {
                    "spectral_flux_z": round(flux_z, 6),
                    "spectral_flatness": round(float(analysis["flatness"][index]), 6),
                    "broadband_ratio": round(float(analysis["high_ratio"][index]), 6),
                    "spectral_centroid_hz": round(
                        float(analysis["centroid"][index]), 3
                    ),
                    "spectral_bandwidth_hz": round(
                        float(analysis["bandwidth"][index]), 3
                    ),
                    "crest_factor": round(crest_factor, 6),
                    "rms": round(rms, 9),
                },
            }
        )
    return events, duration, float(analysis["hop_seconds"])


def _segment_sustained_events(
    samples: Any,
    sample_rate: int,
    *,
    minimum_snr_db: float,
) -> tuple[list[dict[str, Any]], float, float]:
    """Find call-like energy regions without assuming a bird frequency range."""
    np, _, _ = _audio_dependencies()
    analysis = _frame_analysis(samples, sample_rate)
    times = analysis["times"]
    frame_rms = np.maximum(analysis["frame_rms"], 1e-12)
    frame_db = 20.0 * np.log10(frame_rms)
    baseline_db = float(np.percentile(frame_db, 20))
    active = frame_db >= baseline_db + minimum_snr_db

    active_indices = np.flatnonzero(active)
    max_gap_frames = max(1, int(round(0.080 / analysis["hop_seconds"])))
    minimum_frames = max(2, int(round(0.150 / analysis["hop_seconds"])))
    groups: list[list[int]] = []
    group: list[int] = []
    for raw_index in active_indices:
        index = int(raw_index)
        if group and index - group[-1] > max_gap_frames + 1:
            groups.append(group)
            group = []
        group.append(index)
    if group:
        groups.append(group)

    duration = float(samples.size / sample_rate)
    events: list[dict[str, Any]] = []
    for indices in groups:
        span_frames = indices[-1] - indices[0] + 1
        if span_frames < minimum_frames:
            continue
        peak_index = max(indices, key=lambda index: float(frame_db[index]))
        start_seconds = max(0.0, float(times[indices[0]]) - 0.100)
        end_seconds = min(duration, float(times[indices[-1]]) + 0.100)
        left = max(0, int(round(start_seconds * sample_rate)))
        right = min(samples.size, int(round(end_seconds * sample_rate)))
        segment = samples[left:right]
        if segment.size == 0:
            continue
        rms = float(np.sqrt(np.mean(segment.astype(np.float64) ** 2)))
        peak_amplitude = float(np.max(np.abs(segment)))
        crest_factor = peak_amplitude / max(rms, 1e-9)
        snr_db = float(frame_db[peak_index] - baseline_db)
        morphology_score = _clip01((snr_db - minimum_snr_db) / 18.0)
        events.append(
            {
                "start_seconds": round(start_seconds, 6),
                "end_seconds": round(end_seconds, 6),
                "peak_seconds": round(float(times[peak_index]), 6),
                "morphology_score": round(morphology_score, 6),
                "features": {
                    "spectral_flux_z": round(float(analysis["flux_z"][peak_index]), 6),
                    "spectral_flatness": round(
                        float(analysis["flatness"][peak_index]), 6
                    ),
                    "broadband_ratio": round(
                        float(analysis["high_ratio"][peak_index]), 6
                    ),
                    "spectral_centroid_hz": round(
                        float(analysis["centroid"][peak_index]), 3
                    ),
                    "spectral_bandwidth_hz": round(
                        float(analysis["bandwidth"][peak_index]), 3
                    ),
                    "crest_factor": round(crest_factor, 6),
                    "rms": round(rms, 9),
                    "peak_snr_db": round(snr_db, 6),
                    "baseline_rms_db": round(baseline_db, 6),
                },
            }
        )
    return events, duration, float(analysis["hop_seconds"])


def _segment_for_behavior(
    samples: Any,
    sample_rate: int,
    behavior: str,
    *,
    sustained_minimum_snr_db: float,
) -> tuple[list[dict[str, Any]], float, float]:
    if behavior == "sustained-call":
        return _segment_sustained_events(
            samples,
            sample_rate,
            minimum_snr_db=sustained_minimum_snr_db,
        )
    return _segment_events(samples, sample_rate)


def load_species_selection_table(
    path: str | Path,
    *,
    species: str = DEFAULT_SPECIES,
) -> list[dict[str, float | str]]:
    """Read a time-aligned classifier/annotation table as soft evidence.

    BirdCODE/Raven headings and common generic aliases are accepted, but every
    row still has the same small contract: start, end, taxon label, and score.
    A row is not treated as a confirmed identification.
    """
    table_path = Path(path)
    with table_path.open(newline="", encoding="utf-8") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        delimiter = "\t" if "\t" in sample else ","
        rows = csv.DictReader(handle, delimiter=delimiter)
        if not rows.fieldnames:
            raise ValueError(f"species selection table has no header: {path}")
        normalized_fields = {
            field.strip().casefold().replace(" (s)", ""): field
            for field in rows.fieldnames
            if field
        }
        aliases = {
            "begin time": ("begin time", "start time", "start", "begin"),
            "end time": ("end time", "stop time", "end", "stop"),
            "species": ("species", "taxon", "label", "class"),
            "score": ("score", "confidence", "probability"),
        }
        fields = {
            canonical: next(
                (
                    normalized_fields[alias]
                    for alias in candidates
                    if alias in normalized_fields
                ),
                None,
            )
            for canonical, candidates in aliases.items()
        }
        missing = sorted(key for key, value in fields.items() if value is None)
        if missing:
            raise ValueError(
                f"species selection table missing columns: {', '.join(missing)}"
            )
        wanted = species.casefold()
        parsed: list[dict[str, float | str]] = []
        for row in rows:
            cells = {
                name: row.get(field) if isinstance(field, str) else None
                for name, field in fields.items()
            }
            validated: dict[str, str] = {}
            for name, value in cells.items():
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"invalid species selection row in {path}")
                validated[name] = value.strip()
            label = validated["species"]
            if label.casefold() != wanted:
                continue
            try:
                begin = float(validated["begin time"])
                end = float(validated["end time"])
                score = float(validated["score"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid species selection row in {path}") from exc
            if not all(math.isfinite(value) for value in (begin, end, score)):
                raise ValueError(f"non-finite species selection value in {path}")
            if begin < 0 or end <= begin:
                raise ValueError(f"invalid species selection interval in {path}")
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"species selection score must be between 0 and 1 in {path}"
                )
            parsed.append(
                {
                    "begin_seconds": begin,
                    "end_seconds": end,
                    "score": score,
                    "species": label,
                }
            )
    return parsed


def _attach_species_scores(
    events: list[dict[str, Any]],
    rows: list[dict[str, float | str]],
) -> None:
    for event in events:
        matches = []
        for row in rows:
            # Use the detected peak, not a one-sample overlap between broad
            # windows. The latter can grant full species evidence to an event
            # whose actual transient sits outside the model interval.
            if row["begin_seconds"] <= event["peak_seconds"] <= row["end_seconds"]:
                matches.append(row)
        if matches:
            match = max(matches, key=lambda row: float(row["score"]))
            score = float(match["score"])
            event["species_score"] = round(_clip01(score), 6)
            event["species_interval"] = {
                "begin_seconds": float(match["begin_seconds"]),
                "end_seconds": float(match["end_seconds"]),
            }
            event["species_gate_passed"] = True
        else:
            event["species_score"] = None
            event["species_interval"] = None
            event["species_gate_passed"] = False


def _attach_behavior_scores(
    events: list[dict[str, Any]],
    behavior: str,
    *,
    pulse_minimum_count: int,
    pulse_minimum_gap_seconds: float,
    pulse_maximum_gap_seconds: float,
    pulse_minimum_flux_z: float,
) -> None:
    """Attach an explainable behavior gate without claiming species identity."""
    if behavior != "pulse-train":
        for event in events:
            event["behavior_score"] = float(event["morphology_score"])
            event["behavior_gate_passed"] = True
            event["pulse_train"] = None
        return

    ordered = sorted(events, key=lambda event: event["peak_seconds"])
    strong = [
        event
        for event in ordered
        if event["features"]["spectral_flux_z"] >= pulse_minimum_flux_z
    ]
    runs: list[list[dict[str, Any]]] = []
    run: list[dict[str, Any]] = []
    for event in strong:
        if run:
            gap = event["peak_seconds"] - run[-1]["peak_seconds"]
            if not pulse_minimum_gap_seconds <= gap <= pulse_maximum_gap_seconds:
                runs.append(run)
                run = []
        run.append(event)
    if run:
        runs.append(run)

    run_by_identity: dict[int, list[dict[str, Any]]] = {}
    for pulse_run in runs:
        for event in pulse_run:
            run_by_identity[id(event)] = pulse_run

    for event in events:
        pulse_run = run_by_identity.get(id(event), [])
        count = len(pulse_run)
        gaps = [
            pulse_run[index]["peak_seconds"] - pulse_run[index - 1]["peak_seconds"]
            for index in range(1, count)
        ]
        mean_gap = sum(gaps) / len(gaps) if gaps else None
        regularity = 0.0
        if mean_gap and len(gaps) > 1:
            mean_deviation = sum(abs(gap - mean_gap) for gap in gaps) / len(gaps)
            regularity = _clip01(1.0 - mean_deviation / mean_gap)
        elif mean_gap:
            regularity = 0.5
        count_score = _clip01((count - 1) / max(pulse_minimum_count + 3, 1))
        event["behavior_score"] = round(0.75 * count_score + 0.25 * regularity, 6)
        event["behavior_gate_passed"] = count >= pulse_minimum_count
        event["pulse_train"] = {
            "count": count,
            "start_seconds": pulse_run[0]["peak_seconds"] if pulse_run else None,
            "end_seconds": pulse_run[-1]["peak_seconds"] if pulse_run else None,
            "mean_gap_seconds": round(mean_gap, 6) if mean_gap is not None else None,
            "minimum_count": pulse_minimum_count,
            "minimum_gap_seconds": pulse_minimum_gap_seconds,
            "maximum_gap_seconds": pulse_maximum_gap_seconds,
            "minimum_flux_z": pulse_minimum_flux_z,
        }


def _attach_reference_similarity(
    events: list[dict[str, Any]],
    reference_events: list[dict[str, Any]],
    sample_rate: int,
    reference_rate: int,
) -> None:
    np, _, _ = _audio_dependencies()
    reference_vectors = np.asarray(
        [_event_vector(event, reference_rate) for event in reference_events]
    )
    if reference_vectors.size == 0:
        for event in events:
            event["reference_similarity"] = None
        return
    for event in events:
        vector = np.asarray(_event_vector(event, sample_rate))
        norm = float(np.linalg.norm(vector))
        if norm == 0:
            event["reference_similarity"] = 0.0
            continue
        distances = np.linalg.norm(reference_vectors - vector, axis=1)
        best = int(np.argmin(distances))
        event["reference_similarity"] = round(
            _clip01(float(np.exp(-distances[best] / 0.35))),
            6,
        )
        event["reference_match_seconds"] = reference_events[best]["peak_seconds"]


def _combine_scores(
    events: list[dict[str, Any]],
    *,
    behavior: str,
    species_required: bool,
    reference_configured: bool,
) -> None:
    for event in events:
        components = {"morphology": float(event["morphology_score"])}
        weights = {"morphology": 0.60}
        if behavior == "pulse-train":
            components["behavior"] = float(event["behavior_score"])
            weights = {"morphology": 0.35, "behavior": 0.30}
        if reference_configured:
            components["reference"] = float(event.get("reference_similarity") or 0.0)
            weights["reference"] = 0.20 if behavior == "pulse-train" else 0.25
        if species_required:
            # Missing evidence is zero evidence. Renormalizing it away was the
            # ranking bug that let species-negative background win.
            components["species"] = float(event.get("species_score") or 0.0)
            weights["species"] = 0.15
        total_weight = sum(weights.values())
        event["combined_score"] = round(
            sum(components[key] * weights[key] for key in components) / total_weight, 6
        )
        event["score_components"] = {
            key: round(value, 6) for key, value in components.items()
        }
        rejection_reasons = []
        if species_required and not event["species_gate_passed"]:
            rejection_reasons.append("outside-target-species-interval")
        if not event["behavior_gate_passed"]:
            rejection_reasons.append(f"does-not-match-{behavior}")
        event["target_gate_passed"] = not rejection_reasons
        event["rejection_reasons"] = rejection_reasons
        event["review_status"] = (
            "candidate-only" if not rejection_reasons else "rejected-by-target-gate"
        )


def _target_segments(
    events: list[dict[str, Any]],
    behavior: str,
) -> list[dict[str, Any]]:
    accepted = [event for event in events if event["target_gate_passed"]]
    if behavior != "pulse-train":
        return [
            {
                "segment_id": f"segment-{index:03d}",
                "rank": index,
                "start_seconds": event["start_seconds"],
                "end_seconds": event["end_seconds"],
                "peak_seconds": event["peak_seconds"],
                "combined_score": event["combined_score"],
                "event_count": 1,
                "review_status": "candidate-only",
            }
            for index, event in enumerate(accepted, start=1)
        ]

    grouped: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for event in accepted:
        pulse_train = event["pulse_train"]
        key = (pulse_train["start_seconds"], pulse_train["end_seconds"])
        grouped.setdefault(key, []).append(event)

    segments = []
    for grouped_events in grouped.values():
        best = max(grouped_events, key=lambda event: event["combined_score"])
        segments.append(
            {
                "start_seconds": min(
                    event["start_seconds"] for event in grouped_events
                ),
                "end_seconds": max(event["end_seconds"] for event in grouped_events),
                "peak_seconds": best["peak_seconds"],
                "combined_score": best["combined_score"],
                "event_count": len(grouped_events),
                "pulse_train": best["pulse_train"],
                "review_status": "candidate-only",
            }
        )
    segments.sort(key=lambda segment: segment["combined_score"], reverse=True)
    for index, segment in enumerate(segments, start=1):
        segment["rank"] = index
        segment["segment_id"] = f"segment-{index:03d}"
    return segments


def detect_audio(
    source: str | Path,
    *,
    species_selection_table: str | Path | None = None,
    reference: str | Path | None = None,
    species: str = DEFAULT_SPECIES,
    species_model: str = "selection-table",
    behavior: str = "transient",
    pulse_minimum_count: int = DEFAULT_PULSE_MIN_COUNT,
    pulse_minimum_gap_seconds: float = DEFAULT_PULSE_MIN_GAP_SECONDS,
    pulse_maximum_gap_seconds: float = DEFAULT_PULSE_MAX_GAP_SECONDS,
    pulse_minimum_flux_z: float = DEFAULT_PULSE_MIN_FLUX_Z,
    sustained_minimum_snr_db: float = DEFAULT_SUSTAINED_MIN_SNR_DB,
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
    max_events: int = 100,
) -> dict[str, Any]:
    """Rank candidate events in ``source`` and return an auditable report."""
    if max_events < 1:
        raise ValueError("max_events must be positive")
    if behavior not in BEHAVIORS:
        raise ValueError(f"behavior must be one of: {', '.join(BEHAVIORS)}")
    if pulse_minimum_count < 2:
        raise ValueError("pulse_minimum_count must be at least 2")
    if pulse_minimum_gap_seconds <= 0:
        raise ValueError("pulse_minimum_gap_seconds must be positive")
    if pulse_maximum_gap_seconds <= pulse_minimum_gap_seconds:
        raise ValueError("pulse_maximum_gap_seconds must exceed the minimum gap")
    if pulse_minimum_flux_z < 0:
        raise ValueError("pulse_minimum_flux_z must not be negative")
    if sustained_minimum_snr_db <= 0:
        raise ValueError("sustained_minimum_snr_db must be positive")
    if max_duration_seconds <= 0 or max_duration_seconds > DEFAULT_MAX_DURATION_SECONDS:
        raise ValueError(
            "max_duration_seconds must be greater than zero and no more than "
            f"{DEFAULT_MAX_DURATION_SECONDS:g}"
        )
    source_path = Path(source).expanduser().resolve()
    samples, sample_rate = _read_audio(source_path, max_duration_seconds)
    events, duration, frame_hop_seconds = _segment_for_behavior(
        samples,
        sample_rate,
        behavior,
        sustained_minimum_snr_db=sustained_minimum_snr_db,
    )
    _attach_behavior_scores(
        events,
        behavior,
        pulse_minimum_count=pulse_minimum_count,
        pulse_minimum_gap_seconds=pulse_minimum_gap_seconds,
        pulse_maximum_gap_seconds=pulse_maximum_gap_seconds,
        pulse_minimum_flux_z=pulse_minimum_flux_z,
    )

    table_rows: list[dict[str, float | str]] = []
    if species_selection_table:
        table_rows = load_species_selection_table(
            species_selection_table, species=species
        )
        if not table_rows:
            raise ValueError(
                f"species selection table contains no rows for target species: {species}"
            )
        _attach_species_scores(events, table_rows)
    else:
        for event in events:
            event["species_score"] = None
            event["species_interval"] = None
            event["species_gate_passed"] = None

    reference_path: Path | None = None
    reference_events: list[dict[str, Any]] = []
    if reference:
        reference_path = Path(reference).expanduser().resolve()
        reference_samples, reference_rate = _read_audio(
            reference_path, max_duration_seconds
        )
        reference_events, _, _ = _segment_for_behavior(
            reference_samples,
            reference_rate,
            behavior,
            sustained_minimum_snr_db=sustained_minimum_snr_db,
        )
        # Feature vectors are normalized by Nyquist, so matching remains
        # meaningful when the two files have different sample rates.
        _attach_reference_similarity(
            events, reference_events, sample_rate, reference_rate
        )
    else:
        for event in events:
            event["reference_similarity"] = None

    _combine_scores(
        events,
        behavior=behavior,
        species_required=bool(species_selection_table),
        reference_configured=bool(reference),
    )
    events.sort(
        key=lambda event: (event["target_gate_passed"], event["combined_score"]),
        reverse=True,
    )
    target_segments = _target_segments(events, behavior)
    events = events[:max_events]
    for rank, event in enumerate(events, start=1):
        event["rank"] = rank
        event["event_id"] = f"event-{rank:03d}"

    return {
        "schema": DETECTION_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": _display_path(source_path),
            "location": "working-directory-relative-or-redacted-external",
            "sha256": _sha256(source_path),
            "sample_rate_hz": sample_rate,
            "duration_seconds": round(duration, 6),
        },
        "method": {
            "event_detector": (
                "sustained-energy-envelope/v1"
                if behavior == "sustained-call"
                else "spectral-flux-plus-broadband-morphology/v1"
            ),
            "frame_hop_seconds": round(frame_hop_seconds, 6),
            "target_behavior": behavior,
            "max_duration_seconds": max_duration_seconds,
            "pulse_train_parameters": (
                {
                    "minimum_count": pulse_minimum_count,
                    "minimum_gap_seconds": pulse_minimum_gap_seconds,
                    "maximum_gap_seconds": pulse_maximum_gap_seconds,
                    "minimum_flux_z": pulse_minimum_flux_z,
                }
                if behavior == "pulse-train"
                else None
            ),
            "sustained_call_parameters": (
                {
                    "minimum_snr_db": sustained_minimum_snr_db,
                }
                if behavior == "sustained-call"
                else None
            ),
            "species_evidence": "required-target-interval"
            if species_selection_table
            else None,
            "reference_evidence": (
                "nearest-handcrafted-event-morphology" if reference else None
            ),
        },
        "species_evidence": {
            "species": species,
            "model": species_model if species_selection_table else None,
            "selection_table": (
                {
                    "path": _display_path(Path(species_selection_table)),
                    "sha256": _sha256(
                        Path(species_selection_table).expanduser().resolve()
                    ),
                }
                if species_selection_table
                else None
            ),
            "rows_used": len(table_rows),
        },
        "reference": {
            "path": _display_path(reference_path) if reference_path else None,
            "sha256": _sha256(reference_path) if reference_path else None,
            "candidate_events": len(reference_events),
        },
        "target_segments": target_segments[:max_events],
        "events": events,
        "review": {
            "status": (
                "review-required" if target_segments else "no-target-candidates"
            ),
            "target_candidates": len(target_segments),
            "automatic_clipping": False,
            "note": (
                "Scores rank waveform candidates; they are not proof of species identity, "
                "animal intent, or a publication-ready selection. Listen to the source "
                "before making any derivative."
            ),
        },
    }


def write_detection_report(
    report: dict[str, Any],
    destination: str | Path,
    *,
    protected_paths: list[str | Path] | None = None,
) -> Path:
    """Write a JSON report without modifying the source audio."""
    path = Path(destination).expanduser().resolve()
    declared_protected_paths = {
        value
        for value in (
            report.get("source", {}).get("path"),
            report.get("reference", {}).get("path"),
            (
                report.get("species_evidence", {})
                .get("selection_table", {})
                .get("path")
                if isinstance(
                    report.get("species_evidence", {}).get("selection_table"), dict
                )
                else report.get("species_evidence", {}).get("selection_table")
            ),
        )
        if value
    }
    declared_protected_paths.update(
        str(value) for value in (protected_paths or []) if value
    )
    normalized_protected = set()
    for value in declared_protected_paths:
        expanded = str(value).replace("$HOME", str(Path.home()), 1)
        normalized_protected.add(str(Path(expanded).expanduser().resolve()))
    if str(path) in normalized_protected:
        raise ValueError(
            "report destination must not overwrite source or evidence files"
        )
    if path.exists():
        raise FileExistsError(f"bioacoustic report already exists: {path}")
    for parent in (path.parent, *path.parent.parents):
        if not (parent / "song.json").is_file():
            continue
        relative = path.relative_to(parent)
        if relative.parts[:2] == ("recordings", "raw") or relative.parts[:1] == (
            "FINAL",
        ):
            raise ValueError(
                "bioacoustic report must not be written under recordings/raw or FINAL"
            )
        break
    report["report_path"] = _display_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path
