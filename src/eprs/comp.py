"""Intentional, reversible phrase comping across supplied performances."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from .system import analyze, load_song_manifest, probe, sha256, slugify, utc_now


COMP_SCHEMA = "eprs.comp/v1"
COMP_RENDER_SCHEMA = "eprs.comp-render/v1"
OUTPUT_CODEC = "pcm_f32le"
TRANSITIONS = {"cut", "silence", "crossfade"}
REVIEW_DECISIONS = {"keep", "change", "stop"}


def _number(record: dict, key: str, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"comp {key} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"comp {key} must be finite")
    return result


def _source(song: Path, value: object, segment_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"comp segment {segment_id} requires a path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"comp segment {segment_id} path must be relative to the song")
    path = (song / requested).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"comp segment {segment_id} path escapes the song workspace") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _segments(song: Path, values: object) -> list[dict]:
    if not isinstance(values, list) or not 1 <= len(values) <= 128:
        raise ValueError("comp requires between 1 and 128 ordered segments")
    segments = []
    identifiers: set[str] = set()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"comp segment {index} must be an object")
        declared_id = value.get("id")
        intent = value.get("intent")
        if not isinstance(declared_id, str) or not declared_id.strip():
            raise ValueError(f"comp segment {index} requires an id")
        segment_id = slugify(declared_id)
        if not segment_id or segment_id in identifiers:
            raise ValueError(f"comp segment id is empty or duplicated: {declared_id}")
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError(f"comp segment {segment_id} requires player-facing intent")
        identifiers.add(segment_id)
        source = _source(song, value.get("path"), segment_id)
        source_probe = probe(source)
        stream = next(
            (record for record in source_probe.get("streams", []) if record.get("codec_type") == "audio"),
            None,
        )
        if stream is None:
            raise ValueError(f"comp segment {segment_id} source has no audio stream")
        source_duration = float(source_probe.get("format", {}).get("duration") or 0)
        sample_rate = int(stream.get("sample_rate") or 0)
        channels = int(stream.get("channels") or 0)
        if source_duration <= 0 or not 8_000 <= sample_rate <= 192_000 or channels not in {1, 2}:
            raise ValueError(f"comp segment {segment_id} needs known mono/stereo audio properties")
        start = _number(value, "start_seconds", 0)
        duration = _number(value, "duration_seconds")
        if start < 0 or duration <= 0 or start >= source_duration or start + duration > source_duration + 0.01:
            raise ValueError(f"comp segment {segment_id} region exceeds its source")
        segments.append({
            "id": segment_id,
            "declared_id": declared_id.strip(),
            "intent": intent.strip(),
            "source": source,
            "source_path": str(source.relative_to(song.resolve())),
            "source_sha256": sha256(source),
            "source_probe": source_probe,
            "source_sample_rate": sample_rate,
            "source_channels": channels,
            "start_seconds": start,
            "duration_seconds": duration,
        })
    return segments


def _transitions(values: object, segments: list[dict]) -> list[dict]:
    expected_count = len(segments) - 1
    if not isinstance(values, list) or len(values) != expected_count:
        raise ValueError(f"comp requires exactly {expected_count} transition record(s)")
    transitions = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise ValueError(f"comp transition {index + 1} must be an object")
        kind = value.get("type")
        intent = value.get("intent")
        if kind not in TRANSITIONS:
            raise ValueError("comp transition type must be cut, silence, or crossfade")
        if not isinstance(intent, str) or not intent.strip():
            raise ValueError(f"comp transition {index + 1} requires player-facing intent")
        from_id = value.get("from")
        to_id = value.get("to")
        expected_from, expected_to = segments[index]["id"], segments[index + 1]["id"]
        if slugify(str(from_id)) != expected_from or slugify(str(to_id)) != expected_to:
            raise ValueError(
                f"comp transition {index + 1} must connect {expected_from} to {expected_to}"
            )
        duration = 0.0
        if kind in {"silence", "crossfade"}:
            duration = _number(value, "duration_seconds")
            if duration <= 0 or duration > 30:
                raise ValueError(f"comp {kind} duration must be greater than zero and at most 30 seconds")
        if kind == "crossfade" and duration >= min(
            segments[index]["duration_seconds"], segments[index + 1]["duration_seconds"]
        ):
            raise ValueError("comp crossfade must be shorter than both neighboring segments")
        transitions.append({
            "from": expected_from,
            "to": expected_to,
            "type": kind,
            "intent": intent.strip(),
            "duration_seconds": duration,
        })
    return transitions


def _output_format(score: dict, segments: list[dict]) -> tuple[int, int, dict]:
    output = score.get("output", {})
    if not isinstance(output, dict):
        raise ValueError("comp output must be an object")
    rates = {segment["source_sample_rate"] for segment in segments}
    channels_set = {segment["source_channels"] for segment in segments}
    rate_value = output.get("sample_rate")
    channels_value = output.get("channels")
    if rate_value is None:
        if len(rates) != 1:
            raise ValueError("comp with mixed source sample rates requires output.sample_rate")
        rate_value = next(iter(rates))
    if channels_value is None:
        if len(channels_set) != 1:
            raise ValueError("comp with mixed source channels requires output.channels")
        channels_value = next(iter(channels_set))
    if isinstance(rate_value, bool) or not isinstance(rate_value, int) or not 8_000 <= rate_value <= 192_000:
        raise ValueError("comp output sample_rate must be an integer from 8000 to 192000")
    if isinstance(channels_value, bool) or channels_value not in {1, 2}:
        raise ValueError("comp output channels must be 1 or 2")
    return rate_value, channels_value, {
        "sample_rate": rate_value,
        "channels": channels_value,
        "sample_rate_conversion": any(rate != rate_value for rate in rates),
        "channel_conversion": any(channels != channels_value for channels in channels_set),
    }


def _filter_graph(segments: list[dict], transitions: list[dict], sample_rate: int, channels: int) -> tuple[str, float]:
    layout = "mono" if channels == 1 else "stereo"
    filters = []
    for index, segment in enumerate(segments):
        filters.append(
            f"[{index}:a:0]atrim=start={segment['start_seconds']:.12g}:"
            f"duration={segment['duration_seconds']:.12g},asetpts=PTS-STARTPTS,"
            f"aresample={sample_rate},aformat=sample_fmts=fltp:"
            f"sample_rates={sample_rate}:channel_layouts={layout}[segment{index}]"
        )
    expected_duration = segments[0]["duration_seconds"]
    current = "segment0"
    for index, transition in enumerate(transitions, start=1):
        output = "out" if index == len(segments) - 1 else f"joined{index}"
        next_label = f"segment{index}"
        kind = transition["type"]
        duration = transition["duration_seconds"]
        if kind == "cut":
            filters.append(f"[{current}][{next_label}]concat=n=2:v=0:a=1[{output}]")
            expected_duration += segments[index]["duration_seconds"]
        elif kind == "silence":
            gap = f"gap{index}"
            filters.append(f"anullsrc=r={sample_rate}:cl={layout}:d={duration:.12g}[{gap}]")
            filters.append(f"[{current}][{gap}][{next_label}]concat=n=3:v=0:a=1[{output}]")
            expected_duration += duration + segments[index]["duration_seconds"]
        else:
            filters.append(
                f"[{current}][{next_label}]acrossfade=d={duration:.12g}:c1=tri:c2=tri[{output}]"
            )
            expected_duration += segments[index]["duration_seconds"] - duration
        current = output
    if len(segments) == 1:
        filters.append("[segment0]anull[out]")
    return ";".join(filters), expected_duration


def verify_comp(song: str | Path, stem: str | Path) -> tuple[Path, Path, dict]:
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(stem)
    path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        path.relative_to((song_path / "stems").resolve())
    except ValueError as exc:
        raise ValueError("comp stem must be inside the song stems directory") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    sidecar = path.with_suffix(path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"comp provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid comp provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != COMP_RENDER_SCHEMA:
        raise ValueError("unsupported comp provenance schema")
    output = metadata.get("output", {})
    if output.get("path") != str(path.relative_to(song_path.resolve())) or output.get("sha256") != sha256(path):
        raise ValueError("comp output path or checksum has changed")
    sources = metadata.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("comp provenance sources are invalid")
    for source in sources:
        source_path = song_path / source.get("path", "") if isinstance(source, dict) else None
        try:
            if source_path is None:
                raise ValueError
            source_path.resolve().relative_to(song_path.resolve())
        except ValueError as exc:
            raise ValueError("comp provenance has an unsafe source path") from exc
        if not source_path.is_file() or source.get("sha256") != sha256(source_path):
            raise ValueError("comp source is missing or changed")
    return path, sidecar, metadata


def review_comp(song: str | Path, stem: str | Path, note: str, decision: str) -> Path:
    listening_note = note.strip()
    if not listening_note:
        raise ValueError("comp review requires a listening note")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("comp review decision must be keep, change, or stop")
    _, sidecar, metadata = verify_comp(song, stem)
    review = metadata.setdefault("review", {})
    notes = review.setdefault("listening_notes", [])
    if not isinstance(notes, list):
        raise ValueError("comp listening_notes must be a list")
    if any(
        isinstance(item, dict) and item.get("note") == listening_note and item.get("decision") == decision
        for item in notes
    ):
        return sidecar
    notes.append({"reviewed_at": utc_now(), "note": listening_note, "decision": decision})
    review["decision"] = decision
    temporary = sidecar.with_name(f".{sidecar.name}.review.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete comp review exists: {temporary}")
    temporary.write_text(json.dumps(metadata, indent=2) + "\n")
    temporary.replace(sidecar)
    return sidecar


def render_comp(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Render an ordered performance comp without corrective processing."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for performance comping")
    song_path = Path(song)
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid comp JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != COMP_SCHEMA:
        raise ValueError(f"unsupported comp schema: {score.get('schema')}")
    title, role, intent = score.get("title"), score.get("role"), score.get("intent")
    if not all(isinstance(value, str) and value.strip() for value in (title, role, intent)):
        raise ValueError("comp requires title, role, and player-facing intent")
    title_slug, role_slug = slugify(title), slugify(role)
    if not title_slug or not role_slug:
        raise ValueError("comp title and role must contain a letter or number")
    segments = _segments(song_path, score.get("segments"))
    transitions = _transitions(score.get("transitions", []), segments)
    sample_rate, channels, format_record = _output_format(score, segments)
    filter_graph, expected_duration = _filter_graph(segments, transitions, sample_rate, channels)
    recipe = {
        "schema": COMP_SCHEMA,
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "segments": [{
            key: segment[key]
            for key in (
                "id", "declared_id", "intent", "source_path", "source_sha256",
                "source_sample_rate", "source_channels", "start_seconds", "duration_seconds",
            )
        } for segment in segments],
        "transitions": transitions,
        "output": {"codec": OUTPUT_CODEC, **format_record},
    }
    recipe_id = hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    destination_dir = song_path / "stems" / role_slug / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}-comp.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"comp exists without provenance sidecar: {destination}")
        existing = json.loads(sidecar.read_text())
        if existing.get("recipe_id") == recipe_id and existing.get("output", {}).get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"comp destination exists with different provenance: {destination}")
    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.wav"
    if temporary.exists():
        raise FileExistsError(f"incomplete comp render exists: {temporary}")
    command = [ffmpeg, "-nostdin", "-v", "error", "-n"]
    for segment in segments:
        command.extend(["-i", str(segment["source"])])
    command.extend([
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-map_metadata", "-1",
        "-c:a", OUTPUT_CODEC,
        "-ar", str(sample_rate),
        "-ac", str(channels),
        str(temporary),
    ])
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"comp renderer could not start: {exc}") from exc
    if completed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr[-5000:])
    for segment in segments:
        if sha256(segment["source"]) != segment["source_sha256"]:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("comp source changed during rendering")
    output_probe = probe(temporary)
    stream = next(
        (record for record in output_probe.get("streams", []) if record.get("codec_type") == "audio"),
        {},
    )
    actual_duration = float(output_probe.get("format", {}).get("duration") or 0)
    verification = {
        "float32_pcm": stream.get("codec_name") == OUTPUT_CODEC,
        "sample_rate_expected": stream.get("sample_rate") == str(sample_rate),
        "channels_expected": stream.get("channels") == channels,
        "duration_expected": abs(actual_duration - expected_duration) <= max(0.03, expected_duration * 0.002),
    }
    failed = [key for key, value in verification.items() if not value]
    if failed:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"comp failed verification: {', '.join(failed)}")
    output_analysis = analyze(temporary)
    output_analysis.pop("path", None)
    warnings = []
    true_peak = output_analysis.get("loudness", {}).get("true_peak_dbfs")
    if isinstance(true_peak, (int, float)) and true_peak >= 0:
        warnings.append("Float comp reaches or exceeds 0 dBFS; address explicit source or later mix gain without automatic limiting.")
    temporary.rename(destination)
    metadata = {
        "schema": COMP_RENDER_SCHEMA,
        "recipe_id": recipe_id,
        "rendered_at": utc_now(),
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "recipe": recipe,
        "sources": [{
            "segment_id": segment["id"],
            "path": segment["source_path"],
            "sha256": segment["source_sha256"],
            "probe": segment["source_probe"],
        } for segment in segments],
        "segments": recipe["segments"],
        "transitions": transitions,
        "filter_graph": filter_graph,
        "render": {
            "output_codec": OUTPUT_CODEC,
            **format_record,
            "automatic_normalization": False,
            "automatic_gain_control": False,
            "pitch_correction": False,
            "time_stretch": False,
            "denoise": False,
            "compression": False,
            "limiting": False,
        },
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "analysis": output_analysis,
        },
        "verification": verification,
        "warnings": warnings,
        "review": {"decision": "not recorded by renderer", "listening_notes": []},
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar
