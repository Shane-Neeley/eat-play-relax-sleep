"""Performance-preserving rhythm observations from supplied audio."""

from __future__ import annotations

from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
from typing import Sequence

from .system import ingest, load_song_manifest, probe, sha256, slugify, utc_now


ANALYSIS_RATE = 16_000
FRAME_SECONDS = 0.025
HOP_SECONDS = 0.010
MAX_ANALYSIS_SECONDS = 120
ALGORITHM = "eprs-envelope-onset/v1"
OBSERVATION_SCHEMA = "eprs.rhythm-observation/v2"
LEGACY_OBSERVATION_SCHEMA = "eprs.rhythm-observation/v1"


def _observation_path(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    elif "/" in str(value):
        candidate = (song / requested).resolve()
    else:
        matches = sorted((song / "notes" / "rhythm").rglob(str(value)))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"rhythm observation name must resolve uniquely inside notes/rhythm: {value}"
            )
        candidate = matches[0].resolve()
    try:
        candidate.relative_to((song / "notes" / "rhythm").resolve())
    except ValueError as exc:
        raise ValueError("rhythm observation must be inside the song notes/rhythm directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_rhythm_observation(
    song: str | Path,
    observation: str | Path,
    *,
    verify_checksum: bool = True,
) -> tuple[Path, dict]:
    """Verify observation identity, source binding, and non-interpretive limits."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _observation_path(song_path, observation)
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid rhythm observation JSON: {path}: {exc.msg}") from exc
    schema = report.get("schema")
    if schema not in {LEGACY_OBSERVATION_SCHEMA, OBSERVATION_SCHEMA}:
        raise ValueError("unsupported rhythm observation schema")
    source = report.get("source")
    region = report.get("region")
    algorithm = report.get("algorithm")
    if not all(isinstance(value, dict) for value in (source, region, algorithm)):
        raise ValueError("rhythm observation source, region, or algorithm is invalid")
    role = report.get("role")
    note = report.get("note")
    if not isinstance(role, str) or not role.strip() or not isinstance(note, str):
        raise ValueError("rhythm observation role or note is invalid")
    recipe = {
        "algorithm": algorithm.get("name"),
        "source_sha256": source.get("sha256"),
        "role": role,
        "start_seconds": region.get("start_seconds"),
        "duration_seconds": region.get("duration_seconds"),
        "sensitivity": algorithm.get("sensitivity"),
        "min_gap_ms": algorithm.get("minimum_gap_ms"),
        "note": note,
    }
    if recipe["algorithm"] != ALGORITHM:
        raise ValueError("rhythm observation algorithm is unsupported")
    stored_recipe = report.get("recipe")
    if schema == OBSERVATION_SCHEMA and stored_recipe != recipe:
        raise ValueError("rhythm observation recipe is inconsistent")
    if schema == LEGACY_OBSERVATION_SCHEMA and stored_recipe is not None and stored_recipe != recipe:
        raise ValueError("rhythm observation recipe is inconsistent")
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if report.get("analysis_id") != expected_id:
        raise ValueError("rhythm observation analysis id does not match its recipe")
    source_value = source.get("path")
    if not isinstance(source_value, str) or not source_value or Path(source_value).is_absolute():
        raise ValueError("rhythm observation source path is invalid")
    source_path = (song_path / source_value).resolve()
    try:
        source_path.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("rhythm observation source escapes the song workspace") from exc
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if verify_checksum and source.get("sha256") != sha256(source_path):
        raise ValueError("rhythm observation source checksum has changed")
    start = region.get("start_seconds")
    duration = region.get("duration_seconds")
    if (
        isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0
        or isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0
        or duration > MAX_ANALYSIS_SECONDS
    ):
        raise ValueError("rhythm observation region is invalid")
    events = report.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("rhythm observation events are invalid")
    for index, event in enumerate(events, start=1):
        event_time = event.get("time_seconds") if isinstance(event, dict) else None
        if (
            not isinstance(event, dict)
            or event.get("id") != index
            or isinstance(event_time, bool)
            or not isinstance(event_time, (int, float))
            or not start <= event_time <= start + duration + FRAME_SECONDS
        ):
            raise ValueError(f"rhythm observation event {index} is invalid")
    limits = report.get("interpretation_limits")
    if (
        not isinstance(limits, dict)
        or limits.get("quantized") is not False
        or limits.get("drum_roles_assigned") is not False
        or limits.get("timbre_hints_are_inferences") is not True
    ):
        raise ValueError("rhythm observation interpretation limits are invalid")
    if not isinstance(report.get("player_language"), dict) or not isinstance(
        report.get("timing_observation"), dict
    ):
        raise ValueError("rhythm observation musical summaries are invalid")
    result_payload = {
        "algorithm_thresholds": algorithm.get("thresholds"),
        "player_language": report["player_language"],
        "timing_observation": report["timing_observation"],
        "events": events,
        "interpretation_limits": limits,
    }
    expected_result_id = hashlib.sha256(
        json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    stored_result_id = report.get("result_id")
    if schema == OBSERVATION_SCHEMA and stored_result_id != expected_result_id:
        raise ValueError("rhythm observation result id does not match its measured evidence")
    if schema == LEGACY_OBSERVATION_SCHEMA and stored_result_id is not None and stored_result_id != expected_result_id:
        raise ValueError("rhythm observation result id does not match its measured evidence")
    return path, report


def _is_within(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _decode_region(source: Path, start: float, duration: float) -> array:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for rhythm observation")
    command = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-i", str(source),
        "-ss", f"{start:.12g}",
        "-t", f"{duration:.12g}",
        "-map", "0:a:0",
        "-vn",
        "-ac", "1",
        "-ar", str(ANALYSIS_RATE),
        "-f", "f32le",
        "pipe:1",
    ]
    completed = subprocess.run(command, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    samples = array("f")
    samples.frombytes(completed.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _frame_features(samples: Sequence[float]) -> tuple[list[float], int, int]:
    frame_size = round(FRAME_SECONDS * ANALYSIS_RATE)
    hop_size = round(HOP_SECONDS * ANALYSIS_RATE)
    if len(samples) < frame_size:
        samples = list(samples) + [0.0] * (frame_size - len(samples))
    decibels: list[float] = []
    for start in range(0, len(samples) - frame_size + 1, hop_size):
        frame = samples[start : start + frame_size]
        rms = math.sqrt(sum(value * value for value in frame) / frame_size)
        decibels.append(20 * math.log10(max(rms, 1e-9)))
    return decibels, frame_size, hop_size


def _timbre_hint(samples: Sequence[float], onset_sample: int) -> tuple[str, float, float, float]:
    window = samples[onset_sample : onset_sample + round(0.09 * ANALYSIS_RATE)]
    if len(window) < 2:
        return "mixed/uncertain", 0.0, 0.0, 0.0
    zero_crossings = sum(
        1 for left, right in zip(window, window[1:])
        if (left < 0 <= right) or (left >= 0 > right)
    )
    zero_crossing_rate = zero_crossings / (len(window) - 1)
    alpha = 1 - math.exp(-2 * math.pi * 350 / ANALYSIS_RATE)
    low = 0.0
    low_energy = 0.0
    total_energy = 0.0
    for value in window:
        low += alpha * (value - low)
        low_energy += low * low
        total_energy += value * value
    low_ratio = low_energy / max(total_energy, 1e-12)
    if low_ratio >= 0.55 and zero_crossing_rate <= 0.12:
        hint = "lower/rounder"
        confidence = min(1.0, 0.55 + (low_ratio - 0.55) + (0.12 - zero_crossing_rate) * 2)
    elif low_ratio <= 0.28 or zero_crossing_rate >= 0.22:
        hint = "brighter/noisier"
        confidence = min(1.0, 0.55 + max(0.28 - low_ratio, (zero_crossing_rate - 0.22) * 2))
    else:
        hint = "mixed/uncertain"
        confidence = 0.35
    return hint, confidence, low_ratio, zero_crossing_rate


def _detect_events(
    samples: Sequence[float],
    region_start: float,
    sensitivity: float,
    min_gap_ms: float,
) -> tuple[list[dict], dict]:
    decibels, frame_size, hop_size = _frame_features(samples)
    floor_db = _percentile(decibels, 0.20)
    peak_db = _percentile(decibels, 0.95)
    # Digital silence can sit near -180 dB and make tiny tails appear active.
    # Cap the usable onset range at 50 dB below strong frames; the raw floor is
    # still reported, and sensitivity can be lowered for deliberately tiny hits.
    effective_floor_db = max(floor_db, peak_db - 50)
    dynamic_db = peak_db - effective_floor_db
    if dynamic_db < 8:
        raise ValueError("Audio region has too little level contrast for a useful rhythm observation")
    active_threshold = effective_floor_db + dynamic_db * (0.12 + sensitivity * 0.20)
    rise_threshold = 3 + sensitivity * 7
    baseline_frames = max(2, round(0.08 / HOP_SECONDS))
    novelty: list[float] = []
    for index, level in enumerate(decibels):
        history = decibels[max(0, index - baseline_frames) : index]
        baseline = min(history) if history else level
        novelty.append(max(0.0, level - baseline))

    local_radius = 2
    candidates: list[int] = []
    for index, rise in enumerate(novelty):
        local = novelty[max(0, index - local_radius) : index + local_radius + 1]
        if (
            decibels[index] >= active_threshold
            and rise >= rise_threshold
            and rise == max(local)
        ):
            candidates.append(index)

    min_gap_frames = max(1, round((min_gap_ms / 1000) / HOP_SECONDS))
    accepted: list[int] = []
    for candidate in candidates:
        if not accepted or candidate - accepted[-1] >= min_gap_frames:
            accepted.append(candidate)
        elif novelty[candidate] > novelty[accepted[-1]]:
            accepted[-1] = candidate

    events: list[dict] = []
    event_peaks = [max(decibels[index : index + baseline_frames], default=decibels[index]) for index in accepted]
    median_peak = statistics.median(event_peaks) if event_peaks else peak_db
    accent_threshold = _percentile(event_peaks, 0.75)
    for event_number, (index, event_peak) in enumerate(zip(accepted, event_peaks), 1):
        onset_sample = index * hop_size
        hint, hint_confidence, low_ratio, zero_crossing_rate = _timbre_hint(samples, onset_sample)
        if event_peak >= accent_threshold and event_peak >= median_peak + 1:
            dynamic = "accent"
        elif event_peak <= median_peak - 6:
            dynamic = "soft"
        else:
            dynamic = "normal"
        events.append({
            "id": event_number,
            "time_seconds": round(region_start + (onset_sample + frame_size / 2) / ANALYSIS_RATE, 6),
            "level_dbfs": round(event_peak, 2),
            "rise_db": round(novelty[index], 2),
            "dynamic_hint": dynamic,
            "timbre_hint": hint,
            "timbre_hint_confidence": round(hint_confidence, 3),
            "features": {
                "low_frequency_energy_ratio": round(low_ratio, 4),
                "zero_crossing_rate": round(zero_crossing_rate, 4),
            },
        })
    return events, {
        "noise_floor_dbfs": round(floor_db, 2),
        "effective_onset_floor_dbfs": round(effective_floor_db, 2),
        "active_threshold_dbfs": round(active_threshold, 2),
        "rise_threshold_db": round(rise_threshold, 2),
        "dynamic_range_db": round(dynamic_db, 2),
    }


def _timing_observation(events: list[dict]) -> dict:
    times = [event["time_seconds"] for event in events]
    intervals = [right - left for left, right in zip(times, times[1:])]
    if not intervals:
        return {
            "intervals_seconds": [],
            "median_interval_seconds": None,
            "spacing_character": "insufficient events",
            "tempo_hint_bpm": None,
            "tempo_alternatives_bpm": [],
            "tempo_caution": "At least two attacks are needed for a spacing-derived tempo hint.",
        }
    median_interval = statistics.median(intervals)
    deviations = [abs(value - median_interval) for value in intervals]
    variability = statistics.median(deviations) / max(median_interval, 1e-9)
    if variability <= 0.05:
        spacing = "evenly spaced"
    elif variability <= 0.15:
        spacing = "gently variable"
    else:
        spacing = "highly variable or free-time"
    tempo = 60 / median_interval
    while tempo < 60:
        tempo *= 2
    while tempo > 180:
        tempo /= 2
    alternatives = sorted({
        round(candidate, 1)
        for candidate in (tempo / 2, tempo * 2)
        if 40 <= candidate <= 240
    })
    return {
        "intervals_seconds": [round(value, 6) for value in intervals],
        "median_interval_seconds": round(median_interval, 6),
        "median_absolute_deviation_ratio": round(variability, 4),
        "spacing_character": spacing,
        "tempo_hint_bpm": round(tempo, 1),
        "tempo_alternatives_bpm": alternatives,
        "tempo_caution": "Spacing alone cannot tell whether attacks are beats, subdivisions, or a larger pulse.",
    }


def _player_language(events: list[dict], timing: dict, region_duration: float) -> dict:
    hints = [event["timbre_hint"] for event in events]
    lower = hints.count("lower/rounder")
    bright = hints.count("brighter/noisier")
    mixed = hints.count("mixed/uncertain")
    transitions = sum(
        1 for left, right in zip(hints, hints[1:])
        if {left, right} == {"lower/rounder", "brighter/noisier"}
    )
    alternating = len(hints) >= 4 and transitions / max(1, len(hints) - 1) >= 0.7
    if alternating:
        timbre = "The attacks mostly alternate lower, rounder and brighter, noisier gestures."
    else:
        parts = []
        if lower:
            parts.append(f"{lower} lower, rounder")
        if bright:
            parts.append(f"{bright} brighter, noisier")
        if mixed:
            parts.append(f"{mixed} mixed or uncertain")
        timbre = "Timbre hints include " + ", ".join(parts) + "."
    if timing["tempo_hint_bpm"] is None:
        timing_text = "There are not enough attacks to describe a recurring pulse."
    else:
        timing_text = (
            f"Median attack spacing is {timing['median_interval_seconds'] * 1000:.0f} ms "
            f"with {timing['spacing_character']} timing. That supports about "
            f"{timing['tempo_hint_bpm']:g} BPM only if these attacks mark the chosen pulse or subdivision."
        )
    return {
        "summary": f"Detected {len(events)} attacks across a {region_duration:g}-second listening region.",
        "timing": timing_text,
        "timbre": timbre,
        "unknowns": [
            "meter and phrase length",
            "downbeat location",
            "which gestures the performer means as kick, snare, clap, or another voice",
            "whether the spacing represents beats, subdivisions, or free-time phrasing",
        ],
    }


def observe_rhythm(
    source: str | Path,
    song: str | Path,
    role: str,
    start: float = 0,
    duration: float | None = None,
    sensitivity: float = 0.5,
    min_gap_ms: float = 150,
    note: str = "",
) -> tuple[Path, dict]:
    """Observe performed attacks without quantizing or assigning drum roles."""
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe is required for rhythm observation")
    song_path = Path(song)
    load_song_manifest(song_path)
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("rhythm role must contain at least one letter or number")
    if start < 0:
        raise ValueError("rhythm observation start must be zero or greater")
    if duration is not None and duration <= 0:
        raise ValueError("rhythm observation duration must be greater than zero")
    if not 0 <= sensitivity <= 1:
        raise ValueError("rhythm observation sensitivity must be between zero and one")
    if not 30 <= min_gap_ms <= 1000:
        raise ValueError("rhythm observation minimum gap must be between 30 and 1000 ms")

    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not _is_within(source_path, song_path):
        source_path, _ = ingest(
            source_path,
            song_path,
            role,
            f"Automatically ingested for rhythm observation. {note}".strip(),
        )
        source_path = source_path.resolve()

    source_probe = probe(source_path)
    audio_stream = next(
        (stream for stream in source_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError(f"Source has no audio stream: {source_path}")
    source_duration_value = source_probe.get("format", {}).get("duration")
    if source_duration_value is None and duration is None:
        raise ValueError("rhythm observation requires --duration when source duration is unavailable")
    source_duration = float(source_duration_value) if source_duration_value is not None else None
    region_duration = duration if duration is not None else source_duration - start
    if region_duration is None or region_duration <= 0:
        raise ValueError("rhythm observation region is empty")
    if source_duration is not None and (start >= source_duration or start + region_duration > source_duration + 0.01):
        raise ValueError(
            f"rhythm observation {start:g}s–{start + region_duration:g}s exceeds source duration {source_duration:g}s"
        )
    if region_duration > MAX_ANALYSIS_SECONDS:
        raise ValueError(
            f"rhythm observation is limited to {MAX_ANALYSIS_SECONDS} seconds; select a shorter listening region"
        )

    source_digest = sha256(source_path)
    recipe = {
        "algorithm": ALGORITHM,
        "source_sha256": source_digest,
        "role": role,
        "start_seconds": start,
        "duration_seconds": region_duration,
        "sensitivity": sensitivity,
        "min_gap_ms": min_gap_ms,
        "note": note,
    }
    analysis_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "notes" / "rhythm" / role_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source_digest[:10]}-{analysis_id[:8]}-rhythm.json"
    if destination.exists():
        _, existing = verify_rhythm_observation(song_path, destination)
        if existing.get("analysis_id") == analysis_id:
            return destination, existing
        raise FileExistsError(f"Rhythm observation destination already exists with different provenance: {destination}")

    samples = _decode_region(source_path, start, region_duration)
    events, thresholds = _detect_events(samples, start, sensitivity, min_gap_ms)
    if not events:
        raise ValueError("No clear attacks were detected; choose another region or lower --sensitivity")
    timing = _timing_observation(events)
    player_language = _player_language(events, timing, region_duration)
    interpretation_limits = {
        "quantized": False,
        "drum_roles_assigned": False,
        "timbre_hints_are_inferences": True,
        "instruction": "Listen and confirm musical roles before translating this observation to a grid or arrangement.",
    }
    result_payload = {
        "algorithm_thresholds": thresholds,
        "player_language": player_language,
        "timing_observation": timing,
        "events": events,
        "interpretation_limits": interpretation_limits,
    }
    result_id = hashlib.sha256(
        json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    report = {
        "schema": OBSERVATION_SCHEMA,
        "analysis_id": analysis_id,
        "result_id": result_id,
        "created_at": utc_now(),
        "recipe": recipe,
        "role": role,
        "note": note,
        "source": {
            "path": str(source_path.relative_to(song_path.resolve())),
            "sha256": source_digest,
            "probe": source_probe,
        },
        "region": {
            "start_seconds": start,
            "duration_seconds": region_duration,
        },
        "algorithm": {
            "name": ALGORITHM,
            "analysis_sample_rate": ANALYSIS_RATE,
            "frame_ms": FRAME_SECONDS * 1000,
            "hop_ms": HOP_SECONDS * 1000,
            "sensitivity": sensitivity,
            "minimum_gap_ms": min_gap_ms,
            "thresholds": thresholds,
        },
        "player_language": player_language,
        "timing_observation": timing,
        "events": events,
        "interpretation_limits": interpretation_limits,
    }
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete rhythm observation exists: {temporary}")
    try:
        with temporary.open("x") as output:
            output.write(json.dumps(report, indent=2) + "\n")
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination, report
