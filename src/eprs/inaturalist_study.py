"""Measure an iNaturalist sound and turn the measurements into creative cues.

The study is deliberately descriptive.  It records measurable timing, energy,
rough pitch, and brightness features, then labels musical applications as
creative inferences.  It never claims to translate an animal vocalization or
to recover the animal's intent.
"""

from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from .lineage import trace_audio_lineage
from .bioacoustic_models import bioacoustic_model_catalog
from .system import load_song_manifest, probe, sha256, slugify, utc_now


STUDY_SCHEMA = "eprs.inaturalist-creative-study/v1"
ANALYSIS_RATE = 16_000
FRAME_SECONDS = 0.025
HOP_SECONDS = 0.010
MAX_ANALYSIS_SECONDS = 120.0


def _source_path(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    candidates = []
    if requested.is_absolute():
        candidates.append(requested)
    else:
        candidates.extend((song / requested, requested))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise FileNotFoundError(candidates[0] if candidates else requested)


def _decode(source: Path, duration: float) -> array:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for an iNaturalist sound study")
    command = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(source),
        "-t", f"{duration:.12g}", "-map", "0:a:0", "-vn", "-ac", "1",
        "-ar", str(ANALYSIS_RATE), "-f", "f32le", "pipe:1",
    ]
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    samples = array("f")
    samples.frombytes(completed.stdout)
    if samples and sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError("iNaturalist sound study decoded no audio samples")
    return samples


def _frames(samples: array) -> list[tuple[float, float, float]]:
    frame_size = round(FRAME_SECONDS * ANALYSIS_RATE)
    hop_size = round(HOP_SECONDS * ANALYSIS_RATE)
    if len(samples) < frame_size:
        samples = array("f", samples) + array("f", [0.0] * (frame_size - len(samples)))
    result = []
    for start in range(0, len(samples) - frame_size + 1, hop_size):
        frame = samples[start:start + frame_size]
        energy = math.sqrt(sum(value * value for value in frame) / frame_size)
        crossings = sum(
            1 for left, right in zip(frame, frame[1:])
            if (left < 0 <= right) or (left >= 0 > right)
        ) / max(1, frame_size - 1)
        # Zero-crossing rate is a cheap, dependency-free brightness proxy. It
        # is intentionally named a proxy rather than a spectral measurement.
        result.append((start / ANALYSIS_RATE, energy, crossings))
    return result


def _attacks(frames: list[tuple[float, float, float]]) -> list[float]:
    if len(frames) < 3:
        return []
    energies = [item[1] for item in frames]
    floor = max(1e-7, sorted(energies)[max(0, int(len(energies) * 0.2) - 1)])
    attacks = []
    last = -1e9
    for index in range(1, len(frames) - 1):
        previous, current, following = energies[index - 1:index + 2]
        if current <= floor * 1.6 or current < previous * 1.2 or current < following:
            continue
        if frames[index][0] - last < 0.06:
            continue
        attacks.append(frames[index][0])
        last = frames[index][0]
    return attacks


def _activity_window(frames: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    """Return the prominent activity envelope, not a claimed event boundary.

    Wildlife recordings often contain long quiet beds before a call.  A fixed
    peak-relative threshold gives the study a reproducible listening window
    without treating every low-level noise floor sample as musical material.
    The threshold is intentionally conservative and is reported with the
    result so downstream authors can judge it.
    """
    if not frames:
        return None
    energies = [energy for _, energy, _ in frames]
    peak = max(energies, default=0.0)
    if peak <= 1e-7:
        return None
    threshold = max(1e-7, peak * 0.08)
    active_indices = [index for index, energy in enumerate(energies) if energy >= threshold]
    if not active_indices:
        return None
    first = active_indices[0]
    last = active_indices[-1]
    return (
        frames[first][0],
        frames[last][0] + FRAME_SECONDS,
        threshold,
    )


def _autocorrelation_pitch(
    samples: array,
    *,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
) -> float | None:
    """Return a rough F0 for tonal material, or None for noise/ambiguous audio."""
    start = max(0, round(start_seconds * ANALYSIS_RATE))
    end = len(samples) if end_seconds is None else min(len(samples), round(end_seconds * ANALYSIS_RATE))
    window = list(samples[start:end][:round(0.12 * ANALYSIS_RATE)])
    if len(window) < round(0.04 * ANALYSIS_RATE):
        return None
    mean = sum(window) / len(window)
    window = [value - mean for value in window]
    energy = sum(value * value for value in window)
    if energy < 1e-8:
        return None
    low_lag = round(ANALYSIS_RATE / 1200)
    high_lag = round(ANALYSIS_RATE / 80)
    scores: list[tuple[float, int]] = []
    for lag in range(low_lag, min(high_lag, len(window) - 1) + 1):
        score = sum(window[index] * window[index - lag] for index in range(lag, len(window)))
        scores.append((score / energy, lag))
    score, lag = max(scores, default=(0.0, 0))
    if score < 0.25 or not lag:
        return None
    return ANALYSIS_RATE / lag


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _tempo_candidates(interval: float | None) -> list[float]:
    if interval is None or interval <= 0:
        return []
    candidates = []
    for multiplier in (1, 2, 4):
        bpm = 60.0 / interval * multiplier
        if 60 <= bpm <= 180:
            candidates.append(round(bpm, 2))
    return candidates


def _midi(frequency: float | None) -> float | None:
    if frequency is None or frequency <= 0:
        return None
    return round(69 + 12 * math.log2(frequency / 440), 2)


def _creative_map(metrics: dict, common_name: str, key: str, scale: str) -> dict:
    density = metrics["attack_count"] / max(metrics["duration_seconds"], 0.01)
    if metrics["spacing_cv"] is None or metrics["spacing_cv"] > 0.35:
        time_shape = "free-time or highly varied spacing"
    elif density >= 4:
        time_shape = "repeated pulse candidate"
    else:
        time_shape = "spaced call-and-response candidate"
    brightness = metrics["median_zero_crossing_rate"]
    texture = "bright/noisy proxy" if brightness is not None and brightness >= 0.18 else "round/tonal proxy"
    return {
        "beats": {
            "time_shape": time_shape,
            "attack_density_per_second": round(density, 3),
            "tempo_candidates_bpm": _tempo_candidates(metrics["median_attack_spacing_seconds"]),
            "translation_prompt": "Use the observed spacing as a starting grid; keep the animal recording unquantized.",
        },
        "noises": {
            "texture_proxy": texture,
            "processing_starts": ["band-pass or spectral tilt", "short granular cuts", "reverse a tail only if the musical edit is intentional"],
            "translation_prompt": "Make a new texture from the measured contrast; do not overwrite or disguise the source reference.",
        },
        "lyrics": {
            "subject": common_name or "wild voice",
            "line_seeds": ["call into the green", "answer in the open", "small signal, wide world"],
            "translation_prompt": "Write human metaphor inspired by the ecology and contour, never a claimed animal translation.",
        },
        "vocals": {
            "phrase_shape": "short-short-long" if metrics["attack_count"] >= 3 else "single sustained gesture",
            "vowel_starts": ["o", "a", "u"] if texture == "round/tonal proxy" else ["i", "e", "a"],
            "translation_prompt": "Use the contour as a syllable rhythm for an original voice; preserve intelligibility and authorship.",
        },
        "tones": {
            "key": key,
            "scale": scale,
            "source_f0_hz": metrics["f0_hz"],
            "source_midi": metrics["f0_midi"],
            "translation_prompt": "Map the measured pitch only to an authored scale; do not imply that the source encodes this key.",
        },
    }


def study_inaturalist_sound(
    source: str | Path,
    song: str | Path,
    role: str,
    *,
    key: str = "C",
    scale: str = "minor-pentatonic",
    note: str = "",
    tempo_bpm: float | None = None,
) -> tuple[Path, dict]:
    """Create an idempotent, provenance-bound creative study for a frozen sound."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    source_path = _source_path(song_path, source)
    lineage = trace_audio_lineage(song_path, source_path)
    external = lineage.get("external_audio", [])
    if not external:
        raise ValueError("source does not trace to an iNaturalist sound")
    if not isinstance(role, str) or not role.strip():
        raise ValueError("study role is required")
    if not isinstance(key, str) or not key.strip() or not isinstance(scale, str) or not scale.strip():
        raise ValueError("study key and scale are required")
    source_probe = probe(source_path)
    duration_value = source_probe.get("format", {}).get("duration")
    if duration_value is None:
        raise ValueError("source duration is unavailable")
    duration = float(duration_value)
    if duration <= 0 or duration > MAX_ANALYSIS_SECONDS:
        raise ValueError(f"iNaturalist sound study is limited to {MAX_ANALYSIS_SECONDS:g} seconds")
    samples = _decode(source_path, duration)
    frames = _frames(samples)
    attacks = _attacks(frames)
    activity = _activity_window(frames)
    spacing = [right - left for left, right in zip(attacks, attacks[1:])]
    median_spacing = _median(spacing)
    spacing_cv = None
    if spacing and median_spacing:
        mean = sum(spacing) / len(spacing)
        deviation = math.sqrt(sum((value - mean) ** 2 for value in spacing) / len(spacing))
        spacing_cv = round(deviation / max(mean, 1e-9), 4)
    energy_values = [energy for _, energy, _ in frames]
    active = [energy for energy in energy_values if energy > 1e-7]
    f0 = _autocorrelation_pitch(
        samples,
        start_seconds=activity[0] if activity else 0.0,
        end_seconds=activity[1] if activity else None,
    )
    activity_threshold_db = (
        round(20 * math.log10(max(activity[2], 1e-7)), 3) if activity else None
    )
    metrics = {
        "duration_seconds": round(duration, 4),
        "analysis_sample_rate": ANALYSIS_RATE,
        "attack_count": len(attacks),
        "attack_times_seconds": [round(value, 4) for value in attacks],
        "median_attack_spacing_seconds": round(median_spacing, 4) if median_spacing is not None else None,
        "spacing_cv": spacing_cv,
        "event_density_per_second": round(len(attacks) / max(duration, 0.01), 4),
        "median_zero_crossing_rate": round(_median([item[2] for item in frames]) or 0.0, 4),
        "peak_energy": round(max(energy_values, default=0.0), 6),
        "active_energy_db": round(20 * math.log10(max(_median(active) or 1e-7, 1e-7)), 3),
        "activity_window_seconds": (
            [round(activity[0], 4), round(activity[1], 4)] if activity else None
        ),
        "activity_duration_seconds": (
            round(activity[1] - activity[0], 4) if activity else 0.0
        ),
        "activity_threshold_db": activity_threshold_db,
        "f0_hz": round(f0, 3) if f0 is not None else None,
        "f0_midi": _midi(f0),
    }
    source_digest = sha256(source_path)
    external_reference = external[0]
    recipe = {
        "schema": STUDY_SCHEMA,
        "source_sha256": source_digest,
        "observation_id": external_reference.get("observation_id"),
        "sound_id": external_reference.get("sound_id"),
        "role": role.strip(),
        "key": key.strip(),
        "scale": scale.strip(),
        "note": note,
        "tempo_bpm": tempo_bpm,
    }
    study_id = hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("study role must contain a letter or number")
    destination = song_path / "notes" / "inaturalist-studies" / role_slug / f"{source_digest[:10]}-{study_id[:10]}"
    manifest_path = destination / "study.json"
    if manifest_path.is_file():
        return manifest_path, json.loads(manifest_path.read_text())
    taxon = external_reference.get("taxon") if isinstance(external_reference.get("taxon"), dict) else {}
    common_name = taxon.get("common_name") or taxon.get("scientific_name") or "wild voice"
    record = {
        "schema": STUDY_SCHEMA,
        "study_id": study_id,
        "created_at": utc_now(),
        "recipe": recipe,
        "source": {
            "path": str(source_path.relative_to(song_path)),
            "sha256": source_digest,
            "probe": source_probe,
            "iNaturalist": external_reference,
        },
        "metrics": metrics,
        "theory": {
            "frameworks": ["repetition-and-variation", "temporal-spacing", "spectral-contrast", "call-and-response-as-a-musical-analogy"],
            "evidence_boundary": "Metrics are measured from this recording; musical applications are creative inferences, not animal communication decoding.",
        },
        "bioacoustic_ai": bioacoustic_model_catalog(),
        "creative_map": _creative_map(metrics, common_name, key.strip(), scale.strip()),
        "interpretation_limits": {
            "animal_language_translation": False,
            "species_intent_inferred": False,
            "musical_roles_are_authored": True,
            "model_prediction_is_not_ethological_evidence": True,
        },
        "note": note,
        "tempo_bpm": tempo_bpm,
    }
    destination.mkdir(parents=True, exist_ok=False)
    try:
        manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return manifest_path, record
