"""Declarative, reversible audio processing and stem review."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from .evidence import bind_song_evidence, verify_evidence_bindings
from .system import analyze, load_song_manifest, probe, sha256, slugify, utc_now


PROCESS_SCHEMA = "eprs.process/v1"
PROCESS_RENDER_SCHEMA = "eprs.process-render/v1"
OUTPUT_CODEC = "pcm_f32le"
REVIEW_DECISIONS = {"keep", "change", "stop"}


def _number(record: dict, key: str, *, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"process operation {key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"process operation {key} must be finite")
    return number


def _range(record: dict, key: str, low: float, high: float, *, default: float | None = None) -> float:
    value = _number(record, key, default=default)
    if not low <= value <= high:
        raise ValueError(f"process operation {key} must be between {low:g} and {high:g}")
    return value


def _source(song: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("process recipe requires a source path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError("process source path must be relative to the song")
    source = (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError("process source path escapes the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def _operation(record: object, index: int, sample_rate: int, duration: float) -> tuple[dict, str, float]:
    if not isinstance(record, dict):
        raise ValueError(f"process operation {index} must be an object")
    kind = record.get("type")
    intent = record.get("intent")
    if not isinstance(kind, str):
        raise ValueError(f"process operation {index} requires a type")
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError(f"process operation {index} requires player-facing intent")
    kind = kind.strip().lower()
    resolved: dict = {"type": kind, "intent": intent.strip()}
    nyquist_limit = min(40_000.0, sample_rate * 0.49)

    if kind == "gain":
        db = _range(record, "db", -90, 24)
        resolved["db"] = db
        expression = f"volume={db:.12g}dB:precision=double"
    elif kind in {"highpass", "lowpass"}:
        frequency = _range(record, "frequency_hz", 10, nyquist_limit)
        poles_value = record.get("poles", 2)
        if isinstance(poles_value, bool) or not isinstance(poles_value, int) or poles_value not in {1, 2}:
            raise ValueError("process operation poles must be 1 or 2")
        resolved.update({"frequency_hz": frequency, "poles": poles_value})
        expression = (
            f"{kind}=f={frequency:.12g}:p={poles_value}:normalize=0:precision=f64"
        )
    elif kind == "eq":
        frequency = _range(record, "frequency_hz", 10, nyquist_limit)
        gain = _range(record, "gain_db", -24, 24)
        q = _range(record, "q", 0.1, 20, default=1)
        resolved.update({"frequency_hz": frequency, "gain_db": gain, "q": q})
        expression = (
            f"equalizer=f={frequency:.12g}:t=q:w={q:.12g}:g={gain:.12g}:"
            "normalize=0:precision=f64"
        )
    elif kind == "compressor":
        threshold_db = _range(record, "threshold_db", -60, 0, default=-18)
        ratio = _range(record, "ratio", 1, 20, default=2)
        attack_ms = _range(record, "attack_ms", 0.01, 2000, default=20)
        release_ms = _range(record, "release_ms", 0.01, 9000, default=250)
        makeup_db = _range(record, "makeup_db", 0, 36, default=0)
        knee = _range(record, "knee", 1, 8, default=2.82843)
        mix = _range(record, "mix", 0, 1, default=1)
        detection = record.get("detection", "rms")
        link = record.get("link", "average")
        if detection not in {"peak", "rms"}:
            raise ValueError("process compressor detection must be peak or rms")
        if link not in {"average", "maximum"}:
            raise ValueError("process compressor link must be average or maximum")
        threshold = 10 ** (threshold_db / 20)
        makeup = 10 ** (makeup_db / 20)
        resolved.update({
            "threshold_db": threshold_db,
            "ratio": ratio,
            "attack_ms": attack_ms,
            "release_ms": release_ms,
            "makeup_db": makeup_db,
            "knee": knee,
            "mix": mix,
            "detection": detection,
            "link": link,
        })
        expression = (
            f"acompressor=threshold={threshold:.12g}:ratio={ratio:.12g}:"
            f"attack={attack_ms:.12g}:release={release_ms:.12g}:"
            f"makeup={makeup:.12g}:knee={knee:.12g}:mix={mix:.12g}:"
            f"detection={detection}:link={link}:mode=downward"
        )
    elif kind == "echo":
        input_gain = _range(record, "input_gain", 0, 1, default=0.8)
        output_gain = _range(record, "output_gain", 0, 1, default=0.8)
        taps = record.get("taps")
        if not isinstance(taps, list) or not taps or len(taps) > 16:
            raise ValueError("process echo requires between 1 and 16 taps")
        resolved_taps = []
        for tap_index, tap in enumerate(taps, start=1):
            if not isinstance(tap, dict):
                raise ValueError(f"process echo tap {tap_index} must be an object")
            delay_ms = _range(tap, "delay_ms", 0.1, 90_000)
            decay = _range(tap, "decay", 0, 0.99)
            resolved_taps.append({"delay_ms": delay_ms, "decay": decay})
        delays = "|".join(f"{tap['delay_ms']:.12g}" for tap in resolved_taps)
        decays = "|".join(f"{tap['decay']:.12g}" for tap in resolved_taps)
        resolved.update({
            "input_gain": input_gain,
            "output_gain": output_gain,
            "taps": resolved_taps,
        })
        expression = (
            f"aecho=in_gain={input_gain:.12g}:out_gain={output_gain:.12g}:"
            f"delays={delays}:decays={decays}"
        )
        duration += max(tap["delay_ms"] for tap in resolved_taps) / 1000
    elif kind == "fade":
        direction = record.get("direction")
        if direction not in {"in", "out"}:
            raise ValueError("process fade direction must be in or out")
        start = _range(record, "start_seconds", 0, duration)
        fade_duration = _range(record, "duration_seconds", 0.001, duration)
        if start + fade_duration > duration + 1e-9:
            raise ValueError("process fade extends beyond the audio available at that chain position")
        resolved.update({
            "direction": direction,
            "start_seconds": start,
            "duration_seconds": fade_duration,
        })
        expression = f"afade=t={direction}:st={start:.12g}:d={fade_duration:.12g}"
    else:
        raise ValueError(f"unsupported process operation type: {kind}")
    return resolved, expression, duration


def verify_processed_stem(song: str | Path, stem: str | Path) -> tuple[Path, Path, dict]:
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(stem)
    stem_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        stem_path.relative_to((song_path / "stems").resolve())
    except ValueError as exc:
        raise ValueError("processed stem must be inside the song stems directory") from exc
    if not stem_path.is_file():
        raise FileNotFoundError(stem_path)
    sidecar = stem_path.with_suffix(stem_path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"Processed stem provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid processed stem provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != PROCESS_RENDER_SCHEMA:
        raise ValueError("unsupported processed stem provenance schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("processed stem provenance has an invalid recipe")
    expected_recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("recipe_id") != expected_recipe_id:
        raise ValueError("processed stem recipe id does not match its recipe")
    verify_evidence_bindings(
        song_path,
        recipe.get("evidence", []),
        "processed stem",
    )
    output = metadata.get("output", {})
    if not isinstance(output, dict) or output.get("path") != str(stem_path.relative_to(song_path.resolve())):
        raise ValueError("processed stem provenance has an invalid output path")
    if output.get("sha256") != sha256(stem_path):
        raise ValueError("processed stem checksum has changed")
    source = metadata.get("source", {})
    source_value = source.get("path") if isinstance(source, dict) else None
    source_path = song_path / source_value if isinstance(source_value, str) else None
    try:
        if source_path is None:
            raise ValueError
        source_path.resolve().relative_to(song_path.resolve())
    except ValueError as exc:
        raise ValueError("processed stem provenance has an unsafe source path") from exc
    if not source_path.is_file() or source.get("sha256") != sha256(source_path):
        raise ValueError("processed stem source is missing or changed")
    return stem_path, sidecar, metadata


def review_processed_stem(
    song: str | Path,
    stem: str | Path,
    listening_note: str,
    decision: str,
) -> Path:
    note = listening_note.strip()
    if not note:
        raise ValueError("process review requires a listening note")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("process review decision must be keep, change, or stop")
    _, sidecar, metadata = verify_processed_stem(song, stem)
    review = metadata.setdefault("review", {})
    notes = review.setdefault("listening_notes", [])
    if not isinstance(notes, list):
        raise ValueError("processed stem listening_notes must be a list")
    if any(
        isinstance(record, dict)
        and record.get("note") == note
        and record.get("decision") == decision
        for record in notes
    ):
        return sidecar
    notes.append({"reviewed_at": utc_now(), "note": note, "decision": decision})
    review["decision"] = decision
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return sidecar


def render_process(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Render a float working stem from one explicit ordered operation chain."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for audio processing")
    song_path = Path(song)
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid process JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != PROCESS_SCHEMA:
        raise ValueError(f"unsupported process schema: {score.get('schema')}")
    title = score.get("title")
    role = score.get("role")
    intent = score.get("intent")
    for name, value in (("title", title), ("role", role), ("intent", intent)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"process recipe requires {name}")
    title_slug = slugify(title)
    role_slug = slugify(role)
    if not title_slug or not role_slug:
        raise ValueError("process title and role must contain at least one letter or number")
    source_path = _source(song_path, score.get("source"))
    source_digest = sha256(source_path)
    evidence = bind_song_evidence(song_path, score.get("evidence"), "process")
    source_probe = probe(source_path)
    audio_stream = next(
        (stream for stream in source_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError("process source has no audio stream")
    sample_rate = int(audio_stream.get("sample_rate") or 0)
    channels = int(audio_stream.get("channels") or 0)
    source_duration = float(source_probe.get("format", {}).get("duration") or 0)
    if not 8_000 <= sample_rate <= 192_000 or channels not in {1, 2} or source_duration <= 0:
        raise ValueError("process v1 requires mono/stereo audio with known rate and duration")
    operations_value = score.get("operations")
    if not isinstance(operations_value, list) or not operations_value:
        raise ValueError("process recipe requires at least one explicit operation")
    operations = []
    filters = []
    expected_duration = source_duration
    for index, operation_value in enumerate(operations_value, start=1):
        resolved, expression, expected_duration = _operation(
            operation_value,
            index,
            sample_rate,
            expected_duration,
        )
        operations.append(resolved)
        filters.append(expression)

    source_relative = str(source_path.relative_to(song_path.resolve()))
    recipe = {
        "schema": PROCESS_SCHEMA,
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "source_path": source_relative,
        "source_sha256": source_digest,
        "sample_rate": sample_rate,
        "channels": channels,
        "output_codec": OUTPUT_CODEC,
        "evidence": evidence,
        "operations": operations,
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "stems" / role_slug / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"Processed stem exists without provenance sidecar: {destination}")
        try:
            existing = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise FileExistsError(f"Processed stem has invalid provenance: {sidecar}: {exc.msg}") from exc
        if existing.get("recipe_id") == recipe_id and existing.get("output", {}).get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"Processed stem destination exists with different provenance: {destination}")

    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.wav"
    if temporary.exists():
        raise FileExistsError(f"Incomplete process render already exists: {temporary}")
    command = [
        ffmpeg,
        "-nostdin", "-v", "error", "-n",
        "-i", str(source_path),
        "-map", "0:a:0",
        "-af", ",".join(filters),
        "-vn",
        "-map_metadata", "-1",
        "-c:a", OUTPUT_CODEC,
        "-ar", str(sample_rate),
        "-ac", str(channels),
        str(temporary),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Audio processing renderer could not start: {exc}") from exc
    if completed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr[-5000:])
    if sha256(source_path) != source_digest:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("process source changed during rendering")
    try:
        verify_evidence_bindings(song_path, evidence, "process render")
    except (FileNotFoundError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"process evidence changed during rendering: {exc}") from exc

    output_probe = probe(temporary)
    output_stream = next(
        (stream for stream in output_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        {},
    )
    actual_duration = float(output_probe.get("format", {}).get("duration") or 0)
    verification = {
        "float32_pcm": output_stream.get("codec_name") == OUTPUT_CODEC,
        "sample_rate_preserved": output_stream.get("sample_rate") == str(sample_rate),
        "channels_preserved": output_stream.get("channels") == channels,
        "duration_expected": abs(actual_duration - expected_duration) <= max(0.03, expected_duration * 0.002),
    }
    failed = [name for name, passed in verification.items() if not passed]
    if failed:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Processed stem failed verification: {', '.join(failed)}")
    output_analysis = analyze(temporary)
    output_analysis.pop("path", None)
    true_peak = output_analysis.get("loudness", {}).get("true_peak_dbfs")
    warnings = []
    if isinstance(true_peak, (int, float)) and true_peak >= 0:
        warnings.append(
            "Working float stem reaches or exceeds 0 dBFS; lower an explicit gain or makeup control before integer export."
        )
    if any(operation["type"] == "compressor" for operation in operations):
        warnings.append(
            "Explicit compression is present; compare level-matched against the source and record a listening decision."
        )
    temporary.rename(destination)
    metadata = {
        "schema": PROCESS_RENDER_SCHEMA,
        "recipe_id": recipe_id,
        "rendered_at": utc_now(),
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "recipe": recipe,
        "source": {
            "path": source_relative,
            "sha256": source_digest,
            "probe": source_probe,
        },
        "operations": operations,
        "filter_chain": filters,
        "render": {
            "output_codec": OUTPUT_CODEC,
            "automatic_normalization": False,
            "automatic_gain_control": False,
            "pitch_correction": False,
            "time_stretch": False,
            "denoise": False,
            "limiting": False,
            "compression": any(operation["type"] == "compressor" for operation in operations),
        },
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "analysis": output_analysis,
        },
        "verification": verification,
        "warnings": warnings,
        "review": {
            "decision": "not recorded by renderer",
            "listening_notes": [],
        },
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar
