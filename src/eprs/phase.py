"""Non-destructive timing, polarity, and mono-sum observations for two microphones."""

from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from .system import load_song_manifest, probe, sha256, slugify, utc_now


PHASE_SCHEMA = "eprs.phase-observation/v1"
ANALYSIS_RATE = 2_000
MAX_REGION_SECONDS = 30.0
MAX_CORRELATION_POINTS = 20_000
MAX_CANDIDATES = 401


def _number(value: object, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"phase {label} must be a number")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"phase {label} must be between {low:g} and {high:g}")
    return result


def _source(song: Path, value: str | Path, label: str) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    else:
        candidate = (song / requested).resolve()
    try:
        candidate.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"phase {label} must be inside the song workspace") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _audio_properties(path: Path, label: str) -> tuple[dict, float]:
    report = probe(path)
    stream = next(
        (record for record in report.get("streams", []) if record.get("codec_type") == "audio"),
        None,
    )
    duration = float(report.get("format", {}).get("duration") or 0)
    if stream is None or duration <= 0:
        raise ValueError(f"phase {label} requires an audio stream with known duration")
    return report, duration


def _decode(
    ffmpeg: str,
    path: Path,
    start: float,
    duration: float,
) -> array:
    command = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-i", str(path),
        "-ss", f"{start:.12g}",
        "-t", f"{duration:.12g}",
        "-map", "0:a:0",
        "-vn",
        "-ac", "1",
        "-ar", str(ANALYSIS_RATE),
        "-f", "f32le",
        "pipe:1",
    ]
    try:
        completed = subprocess.run(command, capture_output=True)
    except OSError as exc:
        raise RuntimeError(f"phase decoder could not start: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-5000:])
    if len(completed.stdout) % 4:
        raise RuntimeError("phase decoder returned incomplete float samples")
    samples = array("f")
    samples.frombytes(completed.stdout)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples or not all(math.isfinite(value) for value in samples):
        raise ValueError("phase decoder returned no finite audio samples")
    return samples


def _ranges(length: int, shift: int) -> tuple[int, int, int]:
    if shift >= 0:
        return 0, shift, length - shift
    return -shift, 0, length + shift


def _correlation(a: array, b: array, shift: int, stride: int) -> tuple[float | None, int]:
    length = min(len(a), len(b))
    a_start, b_start, overlap = _ranges(length, shift)
    if overlap < 32:
        return None, 0
    count = 0
    sum_a = sum_b = sum_aa = sum_bb = sum_ab = 0.0
    for offset in range(0, overlap, stride):
        left = float(a[a_start + offset])
        right = float(b[b_start + offset])
        count += 1
        sum_a += left
        sum_b += right
        sum_aa += left * left
        sum_bb += right * right
        sum_ab += left * right
    numerator = sum_ab - (sum_a * sum_b / count)
    energy_a = sum_aa - (sum_a * sum_a / count)
    energy_b = sum_bb - (sum_b * sum_b / count)
    denominator = math.sqrt(max(0.0, energy_a) * max(0.0, energy_b))
    if denominator <= 1e-15:
        return None, count
    return max(-1.0, min(1.0, numerator / denominator)), count


def _mono_sum(a: array, b: array, shift: int, stride: int) -> dict:
    length = min(len(a), len(b))
    a_start, b_start, overlap = _ranges(length, shift)
    sum_a = sum_b = sum_normal = sum_inverted = 0.0
    count = 0
    for offset in range(0, overlap, stride):
        left = float(a[a_start + offset])
        right = float(b[b_start + offset])
        count += 1
        sum_a += left * left
        sum_b += right * right
        normal = (left + right) / 2
        inverted = (left - right) / 2
        sum_normal += normal * normal
        sum_inverted += inverted * inverted
    rms_a = math.sqrt(sum_a / count)
    rms_b = math.sqrt(sum_b / count)
    reference = (rms_a + rms_b) / 2
    if reference <= 1e-12:
        raise ValueError("phase region is effectively silent")

    def relative_db(energy: float) -> float:
        rms = math.sqrt(energy / count)
        if rms <= 1e-12:
            return -120.0
        return 20 * math.log10(rms / reference)

    return {
        "reference_separate_average_rms": reference,
        "normal_sum_db_relative": relative_db(sum_normal),
        "b_polarity_inverted_sum_db_relative": relative_db(sum_inverted),
        "interpretation": (
            "These are level comparisons for the measured alignment hypothesis, not permission "
            "to invert polarity or a verdict about which room/microphone relationship sounds better."
        ),
    }


def _player_language(offset_ms: float, correlation: float) -> str:
    if abs(offset_ms) < 0.25:
        timing = "The strongest measured relationship is effectively simultaneous at this resolution."
    elif offset_ms > 0:
        timing = f"The {offset_ms:.3g} ms measurement places microphone B behind microphone A."
    else:
        timing = f"The {abs(offset_ms):.3g} ms measurement places microphone B ahead of microphone A."
    if abs(correlation) < 0.2:
        polarity = "The selected region has no strong repeated polarity relationship."
    elif correlation >= 0:
        polarity = "At that offset the waveforms mostly move in the same direction."
    else:
        polarity = "At that offset the waveforms mostly move in opposite directions."
    return (
        f"{timing} {polarity} Audition the unchanged microphones in stereo and mono before "
        "deciding whether timing, polarity, bleed, room sound, or performance differences matter."
    )


def observe_phase_relationship(
    song: str | Path,
    source_a: str | Path,
    source_b: str | Path,
    role_a: str,
    role_b: str,
    intent: str,
    *,
    start_a: float = 0,
    start_b: float = 0,
    duration: float,
    max_shift_ms: float = 20,
    step_ms: float = 0.5,
) -> tuple[Path, dict]:
    """Measure one bounded two-microphone relationship without changing audio."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for phase observation")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    clean_role_a = role_a.strip()
    clean_role_b = role_b.strip()
    clean_intent = intent.strip()
    if not clean_role_a or not slugify(clean_role_a):
        raise ValueError("phase role_a must contain at least one letter or number")
    if not clean_role_b or not slugify(clean_role_b):
        raise ValueError("phase role_b must contain at least one letter or number")
    if not clean_intent:
        raise ValueError("phase observation requires player-facing intent")
    start_a_value = _number(start_a, "start_a", 0, 86_400)
    start_b_value = _number(start_b, "start_b", 0, 86_400)
    duration_value = _number(duration, "duration", 0.05, MAX_REGION_SECONDS)
    max_shift_value = _number(max_shift_ms, "max_shift_ms", 0, 100)
    step_value = _number(step_ms, "step_ms", 0.1, 10)
    if (2 * max_shift_value / step_value) + 1 > MAX_CANDIDATES + 1e-9:
        raise ValueError("phase shift scan exceeds 401 candidates; increase step_ms")
    max_shift_samples = round(max_shift_value * ANALYSIS_RATE / 1000)
    step_samples = max(1, round(step_value * ANALYSIS_RATE / 1000))
    effective_step_ms = step_samples * 1000 / ANALYSIS_RATE
    shifts = list(range(-max_shift_samples, max_shift_samples + 1, step_samples))
    shifts.extend([-max_shift_samples, 0, max_shift_samples])
    shifts = sorted(set(shifts))
    if len(shifts) > MAX_CANDIDATES:
        raise ValueError("phase shift scan exceeds 401 candidates; increase step_ms")
    a_path = _source(song_path, source_a, "source_a")
    b_path = _source(song_path, source_b, "source_b")
    if a_path == b_path:
        raise ValueError("phase observation requires two distinct source files")
    a_probe, a_duration = _audio_properties(a_path, "source_a")
    b_probe, b_duration = _audio_properties(b_path, "source_b")
    if start_a_value + duration_value > a_duration + 0.01:
        raise ValueError("phase source_a region exceeds its audio duration")
    if start_b_value + duration_value > b_duration + 0.01:
        raise ValueError("phase source_b region exceeds its audio duration")

    a_digest = sha256(a_path)
    b_digest = sha256(b_path)
    recipe = {
        "schema": PHASE_SCHEMA,
        "roles": {"a": clean_role_a, "b": clean_role_b},
        "intent": clean_intent,
        "sources": {
            "a": {
                "path": str(a_path.relative_to(song_path)),
                "sha256": a_digest,
                "start_seconds": start_a_value,
            },
            "b": {
                "path": str(b_path.relative_to(song_path)),
                "sha256": b_digest,
                "start_seconds": start_b_value,
            },
        },
        "duration_seconds": duration_value,
        "analysis": {
            "sample_rate": ANALYSIS_RATE,
            "max_shift_ms": max_shift_value,
            "requested_step_ms": step_value,
            "effective_step_ms": effective_step_ms,
            "maximum_correlation_points": MAX_CORRELATION_POINTS,
        },
    }
    observation_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "notes" / "phase"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (
        f"{slugify(clean_role_a)}-and-{slugify(clean_role_b)}-{observation_id[:10]}.json"
    )
    if destination.exists():
        existing = json.loads(destination.read_text())
        if existing.get("observation_id") == observation_id and existing.get("recipe") == recipe:
            return destination, existing
        raise FileExistsError(f"phase observation has different provenance: {destination}")

    a_samples = _decode(ffmpeg, a_path, start_a_value, duration_value)
    b_samples = _decode(ffmpeg, b_path, start_b_value, duration_value)
    if sha256(a_path) != a_digest or sha256(b_path) != b_digest:
        raise RuntimeError("phase source changed during observation")
    length = min(len(a_samples), len(b_samples))
    if length < 100:
        raise ValueError("phase region is too short after decoding")
    stride = max(1, length // MAX_CORRELATION_POINTS)
    scan = []
    for shift in shifts:
        correlation, points = _correlation(a_samples, b_samples, shift, stride)
        if correlation is not None:
            scan.append({
                "b_offset_relative_to_a_ms": shift * 1000 / ANALYSIS_RATE,
                "correlation": correlation,
                "points": points,
            })
    if not scan:
        raise ValueError("phase region is silent or lacks enough varying audio for correlation")
    strongest_positive = max(scan, key=lambda record: record["correlation"])
    strongest_negative = min(scan, key=lambda record: record["correlation"])
    strongest_absolute = max(scan, key=lambda record: abs(record["correlation"]))
    zero = next(record for record in scan if record["b_offset_relative_to_a_ms"] == 0)
    best_shift = round(
        strongest_absolute["b_offset_relative_to_a_ms"] * ANALYSIS_RATE / 1000
    )
    mono = _mono_sum(a_samples, b_samples, best_shift, stride)
    boundary_hit = abs(best_shift) == max_shift_samples and max_shift_samples > 0
    report = {
        "schema": PHASE_SCHEMA,
        "observation_id": observation_id,
        "created_at": utc_now(),
        "recipe": recipe,
        "sources": {
            "a": {**recipe["sources"]["a"], "probe": a_probe},
            "b": {**recipe["sources"]["b"], "probe": b_probe},
        },
        "measurement": {
            "offset_semantics": (
                "Positive b_offset_relative_to_a_ms means microphone B appears later than A; "
                "negative means B appears earlier. No shift was applied to either source."
            ),
            "correlation_at_declared_alignment": zero,
            "strongest_positive": strongest_positive,
            "strongest_negative": strongest_negative,
            "strongest_absolute": strongest_absolute,
            "scan_boundary_hit": boundary_hit,
            "scan": scan,
            "mono_sum_at_strongest_absolute": mono,
        },
        "player_language": _player_language(
            strongest_absolute["b_offset_relative_to_a_ms"],
            strongest_absolute["correlation"],
        ),
        "limits": [
            "Correlation can reflect shared performance, bleed, room reflections, periodic audio, or capture latency; it does not establish causation.",
            "Mono-sum level evidence is not a creative approval and does not authorize delay or polarity inversion.",
            "The analysis decodes temporary mono 2 kHz measurement streams in memory; source files are not changed and no corrected audio is rendered.",
        ],
        "actions_performed": {
            "source_audio_modified": False,
            "delay_applied": False,
            "polarity_inverted": False,
            "audio_rendered": False,
        },
    }
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete phase observation exists: {temporary}")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(destination)
    return destination, report
