"""Bounded phrase, pitch, and pulse evidence from an unchanged performance."""

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


ANALYSIS_RATE = 8_000
LEVEL_FRAME_SECONDS = 0.025
LEVEL_HOP_SECONDS = 0.010
PITCH_FRAME_SECONDS = 0.040
PITCH_HOP_SECONDS = 0.020
MAX_PITCH_FRAMES = 256
MAX_ANALYSIS_SECONDS = 120
ALGORITHM = "eprs-phrase-pitch-pulse/v1"
OBSERVATION_SCHEMA = "eprs.musical-observation/v1"


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


def _percentile(values: Sequence[float], fraction: float) -> float:
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
        raise RuntimeError("FFmpeg is required for musical observation")
    completed = subprocess.run(
        [
            ffmpeg,
            "-nostdin", "-v", "error", "-i", str(source),
            "-ss", f"{start:.12g}", "-t", f"{duration:.12g}",
            "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(ANALYSIS_RATE),
            "-f", "f32le", "pipe:1",
        ],
        check=False,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    samples = array("f")
    samples.frombytes(completed.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    return samples


def _frame_levels(
    samples: Sequence[float], frame_seconds: float, hop_seconds: float
) -> tuple[list[float], int, int]:
    frame_size = round(frame_seconds * ANALYSIS_RATE)
    hop_size = round(hop_seconds * ANALYSIS_RATE)
    padded = samples
    if len(padded) < frame_size:
        padded = list(padded) + [0.0] * (frame_size - len(padded))
    levels: list[float] = []
    for offset in range(0, len(padded) - frame_size + 1, hop_size):
        frame = padded[offset : offset + frame_size]
        rms = math.sqrt(sum(value * value for value in frame) / frame_size)
        levels.append(20 * math.log10(max(rms, 1e-9)))
    return levels, frame_size, hop_size


def _phrase_shape(levels: Sequence[float]) -> tuple[list[float], str]:
    if not levels:
        return [], "unknown"
    profile: list[float] = []
    for part in range(4):
        start = round(part * len(levels) / 4)
        end = max(start + 1, round((part + 1) * len(levels) / 4))
        profile.append(round(statistics.median(levels[start:end]), 2))
    span = max(profile) - min(profile)
    if span < 3:
        hint = "mostly steady"
    elif profile[-1] >= profile[0] + 3:
        hint = "growing"
    elif profile[0] >= profile[-1] + 3:
        hint = "releasing"
    elif max(profile[1:3]) >= max(profile[0], profile[-1]) + 3:
        hint = "arching"
    else:
        hint = "changing"
    return profile, hint


def _phrase_observation(
    levels: list[float], region_start: float, region_duration: float
) -> dict:
    floor_db = _percentile(levels, 0.10)
    peak_db = _percentile(levels, 0.95)
    effective_floor = max(floor_db, peak_db - 50)
    dynamic_db = peak_db - effective_floor
    if peak_db <= -90:
        active = [False] * len(levels)
        threshold = -90.0
    elif dynamic_db < 6:
        # A sustained performance may legitimately fill the complete region.
        active = [True] * len(levels)
        threshold = peak_db - 3
    else:
        threshold = effective_floor + max(6, min(18, dynamic_db * 0.28))
        active = [level >= threshold for level in levels]

    bridge_frames = round(0.18 / LEVEL_HOP_SECONDS)
    index = 0
    while index < len(active):
        if active[index]:
            index += 1
            continue
        gap_start = index
        while index < len(active) and not active[index]:
            index += 1
        if gap_start > 0 and index < len(active) and index - gap_start <= bridge_frames:
            active[gap_start:index] = [True] * (index - gap_start)

    minimum_frames = max(1, round(0.10 / LEVEL_HOP_SECONDS))
    regions: list[dict] = []
    index = 0
    while index < len(active):
        if not active[index]:
            index += 1
            continue
        first = index
        while index < len(active) and active[index]:
            index += 1
        last = index
        if last - first < minimum_frames:
            continue
        start_seconds = max(region_start, region_start + first * LEVEL_HOP_SECONDS)
        end_seconds = min(
            region_start + region_duration,
            region_start + last * LEVEL_HOP_SECONDS + LEVEL_FRAME_SECONDS,
        )
        profile, shape = _phrase_shape(levels[first:last])
        regions.append({
            "id": len(regions) + 1,
            "start_seconds": round(start_seconds, 6),
            "end_seconds": round(end_seconds, 6),
            "duration_seconds": round(max(0.0, end_seconds - start_seconds), 6),
            "peak_level_dbfs": round(max(levels[first:last]), 2),
            "four_part_level_profile_dbfs": profile,
            "shape_hint": shape,
        })

    gaps: list[dict] = []
    cursor = region_start
    for phrase in regions:
        if phrase["start_seconds"] - cursor >= 0.08:
            gaps.append({
                "start_seconds": round(cursor, 6),
                "end_seconds": phrase["start_seconds"],
                "duration_seconds": round(phrase["start_seconds"] - cursor, 6),
            })
        cursor = phrase["end_seconds"]
    region_end = region_start + region_duration
    if region_end - cursor >= 0.08:
        gaps.append({
            "start_seconds": round(cursor, 6),
            "end_seconds": round(region_end, 6),
            "duration_seconds": round(region_end - cursor, 6),
        })
    return {
        "regions": regions,
        "quiet_gaps": gaps,
        "first_activity_seconds": regions[0]["start_seconds"] if regions else None,
        "last_activity_seconds": regions[-1]["end_seconds"] if regions else None,
        "thresholds": {
            "measured_floor_dbfs": round(floor_db, 2),
            "effective_floor_dbfs": round(effective_floor, 2),
            "activity_threshold_dbfs": round(threshold, 2),
            "dynamic_range_db": round(dynamic_db, 2),
        },
        "caution": "Regions and shape labels come from level contrast; breath, room tone, legato boundaries, and musical sentence meaning still require listening.",
    }


def _pitch_name(midi: int) -> str:
    return ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")[midi % 12]


def _pitch_frame(frame: Sequence[float]) -> tuple[float, float] | None:
    mean = sum(frame) / len(frame)
    centered = [(value - mean) for value in frame]
    energy = sum(value * value for value in centered)
    if energy <= 1e-9:
        return None
    minimum_lag = max(2, math.floor(ANALYSIS_RATE / 1000))
    maximum_lag = min(len(centered) // 2, math.ceil(ANALYSIS_RATE / 65))
    correlations: dict[int, float] = {}
    for lag in range(minimum_lag, maximum_lag + 1):
        left = centered[:-lag]
        right = centered[lag:]
        numerator = sum(a * b for a, b in zip(left, right))
        denominator = math.sqrt(
            max(1e-18, sum(a * a for a in left) * sum(b * b for b in right))
        )
        correlations[lag] = numerator / denominator
    peaks = [
        lag for lag in range(minimum_lag + 1, maximum_lag)
        if correlations[lag] >= correlations[lag - 1]
        and correlations[lag] > correlations[lag + 1]
    ]
    if not peaks:
        return None
    strongest = max(correlations[lag] for lag in peaks)
    if strongest < 0.55:
        return None
    lag = min(
        (item for item in peaks if correlations[item] >= max(0.55, strongest * 0.92)),
        default=max(peaks, key=lambda item: correlations[item]),
    )
    left = correlations.get(lag - 1, correlations[lag])
    center = correlations[lag]
    right = correlations.get(lag + 1, correlations[lag])
    curvature = left - 2 * center + right
    offset = 0.5 * (left - right) / curvature if abs(curvature) > 1e-9 else 0.0
    refined_lag = lag + max(-0.5, min(0.5, offset))
    return ANALYSIS_RATE / refined_lag, center


def _pitch_observation(samples: Sequence[float], activity_threshold: float) -> dict:
    levels, frame_size, hop_size = _frame_levels(
        samples, PITCH_FRAME_SECONDS, PITCH_HOP_SECONDS
    )
    eligible = [index for index, level in enumerate(levels) if level >= activity_threshold]
    if len(eligible) > MAX_PITCH_FRAMES:
        eligible = [
            eligible[round(index * (len(eligible) - 1) / (MAX_PITCH_FRAMES - 1))]
            for index in range(MAX_PITCH_FRAMES)
        ]
    measurements: list[tuple[float, float, int]] = []
    for index in eligible:
        offset = index * hop_size
        result = _pitch_frame(samples[offset : offset + frame_size])
        if result is None:
            continue
        frequency, confidence = result
        midi = round(69 + 12 * math.log2(frequency / 440))
        measurements.append((frequency, confidence, midi))

    clusters: list[dict] = []
    for midi in sorted({item[2] for item in measurements}):
        members = [item for item in measurements if item[2] == midi]
        clusters.append({
            "pitch_class": _pitch_name(midi),
            "nearest_midi_note": midi,
            "nearest_note_name": f"{_pitch_name(midi)}{midi // 12 - 1}",
            "median_frequency_hz": round(statistics.median(item[0] for item in members), 2),
            "share_of_voiced_frames": round(len(members) / max(1, len(measurements)), 4),
            "median_periodicity_confidence": round(statistics.median(item[1] for item in members), 4),
        })
    clusters.sort(key=lambda item: (-item["share_of_voiced_frames"], item["nearest_midi_note"]))
    return {
        "method": "bounded monophonic periodicity sampling",
        "eligible_frames": len(eligible),
        "analyzed_frame_cap": MAX_PITCH_FRAMES,
        "periodic_frames": len(measurements),
        "periodic_fraction": round(len(measurements) / max(1, len(eligible)), 4),
        "candidates": clusters[:12],
        "key_or_chord": None,
        "caution": "Pitch candidates are evidence, not tuning targets. Chords, polyphony, noisy attacks, room sound, and octave ambiguity can mislead this monophonic estimator; listen before naming harmony.",
    }


def _pulse_observation(levels: Sequence[float], region_start: float) -> dict:
    baseline_frames = max(2, round(0.08 / LEVEL_HOP_SECONDS))
    novelty: list[float] = []
    for index, level in enumerate(levels):
        history = levels[max(0, index - baseline_frames) : index]
        baseline = min(history) if history else level
        novelty.append(max(0.0, level - baseline))
    threshold = max(3.0, _percentile(novelty, 0.85))
    candidates = [
        index for index in range(1, max(1, len(novelty) - 1))
        if novelty[index] >= threshold
        and novelty[index] >= novelty[index - 1]
        and novelty[index] > novelty[index + 1]
    ]
    minimum_gap = round(0.08 / LEVEL_HOP_SECONDS)
    attacks: list[int] = []
    for candidate in candidates:
        if not attacks or candidate - attacks[-1] >= minimum_gap:
            attacks.append(candidate)
        elif novelty[candidate] > novelty[attacks[-1]]:
            attacks[-1] = candidate
    times = [region_start + index * LEVEL_HOP_SECONDS for index in attacks]
    intervals = [right - left for left, right in zip(times, times[1:])]
    tempo_candidates: list[dict] = []
    spacing = "insufficient attacks"
    if intervals:
        median_interval = statistics.median(intervals)
        variability = statistics.median(
            abs(value - median_interval) for value in intervals
        ) / max(median_interval, 1e-9)
        spacing = (
            "evenly spaced" if variability <= 0.05
            else "gently variable" if variability <= 0.15
            else "highly variable or free-time"
        )
        base = 60 / median_interval
        while base < 60:
            base *= 2
        while base > 180:
            base /= 2
        for relation, bpm in (("half-time", base / 2), ("event-spacing", base), ("double-time", base * 2)):
            if 40 <= bpm <= 240:
                tempo_candidates.append({
                    "bpm": round(bpm, 1),
                    "relation_to_median_spacing": relation,
                    "spacing_consistency": round(max(0.0, 1 - variability), 4),
                })
    return {
        "attack_landmarks_seconds": [round(value, 6) for value in times],
        "intervals_seconds": [round(value, 6) for value in intervals],
        "spacing_character": spacing,
        "tempo_candidates": tempo_candidates,
        "selected_bpm": None,
        "selected_meter": None,
        "grid_created": False,
        "caution": "Attack spacing cannot decide whether a landmark is a beat, subdivision, pickup, larger pulse, or free-time gesture; every BPM candidate remains optional.",
    }


def _player_language(phrases: dict, pitch: dict, pulse: dict) -> dict:
    phrase_count = len(phrases["regions"])
    periodic = pitch["periodic_frames"]
    pitch_text = (
        f"Periodicity appeared in {periodic} sampled frame(s); the strongest note-name candidates are "
        + ", ".join(item["nearest_note_name"] for item in pitch["candidates"][:4])
        + "."
        if periodic and pitch["candidates"]
        else "No stable monophonic pitch evidence was found in the bounded sample."
    )
    pulse_text = (
        "Possible pulse readings are "
        + ", ".join(f"{item['bpm']:g} BPM ({item['relation_to_median_spacing']})" for item in pulse["tempo_candidates"])
        + "; none is selected."
        if pulse["tempo_candidates"]
        else "There are not enough recurring attacks to offer a pulse reading."
    )
    return {
        "phrasing": f"Level contrast suggests {phrase_count} phrase region(s) and {len(phrases['quiet_gaps'])} substantial quiet gap(s).",
        "pitch": pitch_text,
        "pulse": pulse_text,
        "arranger_questions": [
            "Which detected region is a complete musical sentence rather than a level-defined fragment?",
            "Should accompaniment follow the performance's entrances and releases, or leave them unanswered?",
            "Do the pitch candidates describe a tonal center, passing tones, chord members, another voice, or estimator error?",
            "Is any pulse candidate actually felt, and where are the pickup and downbeat?",
        ],
    }


def _observation_path(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        path = requested.resolve()
    elif requested.exists():
        path = requested.resolve()
    elif "/" in str(value):
        path = (song / requested).resolve()
    else:
        matches = sorted((song / "notes" / "musical-observations").rglob(str(value)))
        if len(matches) != 1:
            raise FileNotFoundError(
                f"musical observation name must resolve uniquely inside notes/musical-observations: {value}"
            )
        path = matches[0].resolve()
    try:
        path.relative_to((song / "notes" / "musical-observations").resolve())
    except ValueError as exc:
        raise ValueError("musical observation must stay inside notes/musical-observations") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_musical_observation(
    song: str | Path,
    observation: str | Path,
    *,
    verify_checksum: bool = True,
) -> tuple[Path, dict]:
    """Verify a musical observation and its unchanged source binding."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _observation_path(song_path, observation)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid musical observation JSON: {path}: {exc.msg}") from exc
    if report.get("schema") != OBSERVATION_SCHEMA:
        raise ValueError("unsupported musical observation schema")
    recipe = report.get("recipe")
    source = report.get("source")
    region = report.get("region")
    if not all(isinstance(item, dict) for item in (recipe, source, region)):
        raise ValueError("musical observation recipe, source, or region is invalid")
    if recipe.get("algorithm") != ALGORITHM:
        raise ValueError("musical observation algorithm is unsupported")
    expected_analysis_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if report.get("analysis_id") != expected_analysis_id:
        raise ValueError("musical observation analysis id does not match its recipe")
    if report.get("role") != recipe.get("role") or report.get("note") != recipe.get("note"):
        raise ValueError("musical observation role or note does not match its recipe")
    source_value = source.get("path")
    if not isinstance(source_value, str) or not source_value or Path(source_value).is_absolute():
        raise ValueError("musical observation source path is invalid")
    source_path = (song_path / source_value).resolve()
    if not _inside(source_path, song_path) or not source_path.is_file():
        raise FileNotFoundError(source_path)
    if source.get("sha256") != recipe.get("source_sha256"):
        raise ValueError("musical observation source binding is inconsistent")
    if verify_checksum and sha256(source_path) != source.get("sha256"):
        raise ValueError("musical observation source checksum has changed")
    start = region.get("start_seconds")
    duration = region.get("duration_seconds")
    if (
        isinstance(start, bool) or not isinstance(start, (int, float)) or start < 0
        or isinstance(duration, bool) or not isinstance(duration, (int, float))
        or duration <= 0 or duration > MAX_ANALYSIS_SECONDS
    ):
        raise ValueError("musical observation region is invalid")
    if recipe.get("start_seconds") != start or recipe.get("duration_seconds") != duration:
        raise ValueError("musical observation region does not match its recipe")
    for key in ("phrase_observation", "pitch_observation", "pulse_observation", "player_language"):
        if not isinstance(report.get(key), dict):
            raise ValueError(f"musical observation {key} is invalid")
    algorithm = report.get("algorithm")
    decoded_samples = algorithm.get("decoded_samples") if isinstance(algorithm, dict) else None
    if (
        not isinstance(algorithm, dict)
        or algorithm.get("name") != ALGORITHM
        or algorithm.get("analysis_sample_rate") != ANALYSIS_RATE
        or algorithm.get("maximum_pitch_frames") != MAX_PITCH_FRAMES
        or algorithm.get("maximum_region_seconds") != MAX_ANALYSIS_SECONDS
        or isinstance(decoded_samples, bool)
        or not isinstance(decoded_samples, int)
        or decoded_samples <= 0
        or decoded_samples > math.ceil(duration * ANALYSIS_RATE) + round(PITCH_FRAME_SECONDS * ANALYSIS_RATE)
    ):
        raise ValueError("musical observation bounded algorithm evidence is invalid")
    phrases = report["phrase_observation"].get("regions")
    if not isinstance(phrases, list):
        raise ValueError("musical observation phrase regions are invalid")
    for index, phrase in enumerate(phrases, start=1):
        phrase_start = phrase.get("start_seconds") if isinstance(phrase, dict) else None
        phrase_end = phrase.get("end_seconds") if isinstance(phrase, dict) else None
        if (
            not isinstance(phrase, dict) or phrase.get("id") != index
            or isinstance(phrase_start, bool) or not isinstance(phrase_start, (int, float))
            or isinstance(phrase_end, bool) or not isinstance(phrase_end, (int, float))
            or not start <= phrase_start < phrase_end <= start + duration + LEVEL_FRAME_SECONDS
        ):
            raise ValueError(f"musical observation phrase region {index} is invalid")
    pitch = report["pitch_observation"]
    pulse = report["pulse_observation"]
    if pitch.get("key_or_chord") is not None:
        raise ValueError("musical observation must not infer a key or chord")
    if (
        pulse.get("selected_bpm") is not None
        or pulse.get("selected_meter") is not None
        or pulse.get("grid_created") is not False
    ):
        raise ValueError("musical observation must keep pulse interpretation open")
    limits = report.get("interpretation_limits")
    if not isinstance(limits, dict) or any(limits.get(key) is not False for key in (
        "source_modified", "pitch_corrected", "quantized", "key_inferred",
        "chord_inferred", "tempo_selected", "meter_selected",
    )):
        raise ValueError("musical observation interpretation limits are invalid")
    result_payload = {
        "phrase_observation": report["phrase_observation"],
        "pitch_observation": report["pitch_observation"],
        "pulse_observation": report["pulse_observation"],
        "player_language": report["player_language"],
        "interpretation_limits": limits,
    }
    expected_result_id = hashlib.sha256(
        json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if report.get("result_id") != expected_result_id:
        raise ValueError("musical observation result id does not match its evidence")
    return path, report


def observe_musical_performance(
    source: str | Path,
    song: str | Path,
    role: str,
    start: float = 0,
    duration: float | None = None,
    note: str = "",
) -> tuple[Path, dict]:
    """Write bounded arrangement-facing evidence without altering the source."""
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe is required for musical observation")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("musical observation role must contain at least one letter or number")
    if start < 0:
        raise ValueError("musical observation start must be zero or greater")
    if duration is not None and duration <= 0:
        raise ValueError("musical observation duration must be greater than zero")
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not _inside(source_path, song_path):
        source_path, _ = ingest(
            source_path,
            song_path,
            role,
            f"Automatically ingested for bounded musical observation. {note}".strip(),
        )
        source_path = source_path.resolve()
    source_probe = probe(source_path)
    if not any(item.get("codec_type") == "audio" for item in source_probe.get("streams", [])):
        raise ValueError(f"Source has no audio stream: {source_path}")
    duration_value = source_probe.get("format", {}).get("duration")
    if duration_value is None and duration is None:
        raise ValueError("musical observation requires --duration when source duration is unavailable")
    source_duration = float(duration_value) if duration_value is not None else None
    region_duration = duration if duration is not None else source_duration - start
    if region_duration is None or region_duration <= 0:
        raise ValueError("musical observation region is empty")
    if source_duration is not None and (
        start >= source_duration or start + region_duration > source_duration + 0.01
    ):
        raise ValueError(
            f"musical observation {start:g}s–{start + region_duration:g}s exceeds source duration {source_duration:g}s"
        )
    if region_duration > MAX_ANALYSIS_SECONDS:
        raise ValueError(
            f"musical observation is limited to {MAX_ANALYSIS_SECONDS} seconds; select a shorter listening region"
        )

    source_digest = sha256(source_path)
    recipe = {
        "algorithm": ALGORITHM,
        "source_sha256": source_digest,
        "role": role,
        "start_seconds": start,
        "duration_seconds": region_duration,
        "note": note,
    }
    analysis_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "notes" / "musical-observations" / role_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{source_digest[:10]}-{analysis_id[:8]}-musical.json"
    if destination.exists():
        _, existing = verify_musical_observation(song_path, destination)
        if existing.get("analysis_id") == analysis_id:
            return destination, existing
        raise FileExistsError(
            f"musical observation destination has different provenance: {destination}"
        )

    samples = _decode_region(source_path, start, region_duration)
    levels, _, _ = _frame_levels(samples, LEVEL_FRAME_SECONDS, LEVEL_HOP_SECONDS)
    phrases = _phrase_observation(levels, start, region_duration)
    pitch = _pitch_observation(
        samples, phrases["thresholds"]["activity_threshold_dbfs"]
    )
    pulse = _pulse_observation(levels, start)
    player_language = _player_language(phrases, pitch, pulse)
    limits = {
        "source_modified": False,
        "pitch_corrected": False,
        "quantized": False,
        "key_inferred": False,
        "chord_inferred": False,
        "tempo_selected": False,
        "meter_selected": False,
        "instruction": "Listen to the unchanged source before using any landmark or candidate in an arrangement.",
    }
    result_payload = {
        "phrase_observation": phrases,
        "pitch_observation": pitch,
        "pulse_observation": pulse,
        "player_language": player_language,
        "interpretation_limits": limits,
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
            "path": str(source_path.relative_to(song_path)),
            "sha256": source_digest,
            "probe": source_probe,
        },
        "region": {"start_seconds": start, "duration_seconds": region_duration},
        "algorithm": {
            "name": ALGORITHM,
            "analysis_sample_rate": ANALYSIS_RATE,
            "level_frame_ms": LEVEL_FRAME_SECONDS * 1000,
            "level_hop_ms": LEVEL_HOP_SECONDS * 1000,
            "pitch_frame_ms": PITCH_FRAME_SECONDS * 1000,
            "pitch_hop_ms": PITCH_HOP_SECONDS * 1000,
            "maximum_pitch_frames": MAX_PITCH_FRAMES,
            "maximum_region_seconds": MAX_ANALYSIS_SECONDS,
            "decoded_samples": len(samples),
        },
        **result_payload,
    }
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete musical observation exists: {temporary}")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2) + "\n")
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination, report
