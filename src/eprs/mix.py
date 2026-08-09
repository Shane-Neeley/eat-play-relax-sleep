"""Declarative, reversible arrangement and working-mix rendering."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from .evidence import bind_song_evidence, verify_evidence_bindings
from .system import analyze, load_song_manifest, probe, sha256, slugify, utc_now


MIX_SCHEMA = "eprs.mix/v1"
MIX_RENDER_SCHEMA = "eprs.mix-render/v1"
OUTPUT_CODEC = "pcm_f32le"
REVIEW_DECISIONS = {"keep", "change", "stop"}
MIX_TRACK_RECIPE_KEYS = (
    "id", "role", "intent", "source_path", "source_sha256",
    "start_seconds", "source_start_seconds", "duration_seconds",
    "gain_db", "pan", "pan_law", "fade_in_ms", "fade_out_ms",
)


def _number(record: dict, key: str, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"mix track {key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"mix track {key} must be finite")
    return number


def _song_source(song: Path, value: object, track_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"mix track {track_id} requires a path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"mix track {track_id} path must be relative to the song")
    source = (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"mix track {track_id} path escapes the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def _pan_filter(channels: int, pan: float) -> tuple[str, str]:
    # A conservative balance law: the near side stays at unity while the far
    # side attenuates. It never adds compensating gain.
    left = 1.0 if pan <= 0 else 1.0 - pan
    right = 1.0 if pan >= 0 else 1.0 + pan
    if channels == 1:
        expression = f"pan=stereo|c0={left:.8g}*c0|c1={right:.8g}*c0"
    elif channels == 2:
        expression = f"pan=stereo|c0={left:.8g}*c0|c1={right:.8g}*c1"
    else:
        raise ValueError("mix v1 accepts mono or stereo sources; prepare a derived stereo stem first")
    return expression, "conservative-balance-no-boost"


def _validated_track(song: Path, record: object, identifiers: set[str], sample_rate: int) -> dict:
    if not isinstance(record, dict):
        raise ValueError("each mix track must be an object")
    raw_id = record.get("id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError("each mix track requires an id")
    track_id = slugify(raw_id)
    if not track_id:
        raise ValueError("mix track id must contain at least one letter or number")
    if track_id in identifiers:
        raise ValueError(f"duplicate mix track id: {raw_id}")
    identifiers.add(track_id)
    role = record.get("role", raw_id)
    intent = record.get("intent", "")
    if not isinstance(role, str) or not role.strip():
        raise ValueError(f"mix track {track_id} role must be text")
    if not isinstance(intent, str):
        raise ValueError(f"mix track {track_id} intent must be text")
    source = _song_source(song, record.get("path"), track_id)
    media_probe = probe(source)
    audio_stream = next(
        (stream for stream in media_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError(f"mix track {track_id} has no audio stream")
    channels = int(audio_stream.get("channels") or 0)
    start = _number(record, "start_seconds", 0)
    source_start = _number(record, "source_start_seconds", 0)
    gain_db = _number(record, "gain_db", 0)
    pan = _number(record, "pan", 0)
    fade_in_ms = _number(record, "fade_in_ms", 0)
    fade_out_ms = _number(record, "fade_out_ms", 0)
    for name, value in (("start_seconds", start), ("source_start_seconds", source_start)):
        if value < 0:
            raise ValueError(f"mix track {track_id} {name} must be zero or greater")
    if not -90 <= gain_db <= 12:
        raise ValueError(f"mix track {track_id} gain_db must be between -90 and 12")
    if not -1 <= pan <= 1:
        raise ValueError(f"mix track {track_id} pan must be between -1 and 1")
    if fade_in_ms < 0 or fade_out_ms < 0:
        raise ValueError(f"mix track {track_id} fades must be zero or greater")
    source_duration_value = media_probe.get("format", {}).get("duration")
    requested_duration = record.get("duration_seconds")
    if requested_duration is None:
        if source_duration_value is None:
            raise ValueError(f"mix track {track_id} requires duration_seconds when source duration is unknown")
        duration = float(source_duration_value) - source_start
    else:
        duration = _number(record, "duration_seconds")
    if duration <= 0:
        raise ValueError(f"mix track {track_id} duration_seconds must be greater than zero")
    if source_duration_value is not None:
        source_duration = float(source_duration_value)
        if source_start >= source_duration or source_start + duration > source_duration + 0.01:
            raise ValueError(
                f"mix track {track_id} selection {source_start:g}s–{source_start + duration:g}s "
                f"exceeds source duration {source_duration:g}s"
            )
    if (fade_in_ms + fade_out_ms) / 1000 > duration:
        raise ValueError(f"mix track {track_id} fades cannot overlap beyond the selected duration")
    pan_filter, pan_law = _pan_filter(channels, pan)
    delay_samples = round(start * sample_rate)
    operations = [
        f"atrim=start={source_start:.12g}:duration={duration:.12g}",
        "asetpts=PTS-STARTPTS",
        f"aresample={sample_rate}",
    ]
    if fade_in_ms:
        operations.append(f"afade=t=in:st=0:d={fade_in_ms / 1000:.12g}")
    if fade_out_ms:
        fade_start = duration - fade_out_ms / 1000
        operations.append(f"afade=t=out:st={fade_start:.12g}:d={fade_out_ms / 1000:.12g}")
    operations.extend([
        f"volume={gain_db:.12g}dB:precision=double",
        pan_filter,
        f"adelay=delays={delay_samples}S:all=1",
    ])
    return {
        "id": track_id,
        "declared_id": raw_id,
        "role": role,
        "intent": intent,
        "source": source,
        "source_path": str(source.relative_to(song.resolve())),
        "source_sha256": sha256(source),
        "source_probe": media_probe,
        "start_seconds": start,
        "source_start_seconds": source_start,
        "duration_seconds": duration,
        "gain_db": gain_db,
        "pan": pan,
        "pan_law": pan_law,
        "fade_in_ms": fade_in_ms,
        "fade_out_ms": fade_out_ms,
        "end_seconds": start + duration,
        "operations": operations,
    }


def resolve_mix_recipe_tracks(song: str | Path, recipe: object) -> list[dict]:
    """Re-resolve a persisted mix recipe for exact downstream adapters."""
    if not isinstance(recipe, dict) or recipe.get("schema") != MIX_SCHEMA:
        raise ValueError("mix recipe is invalid")
    sample_rate = recipe.get("sample_rate")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
        raise ValueError("mix recipe sample rate is invalid")
    values = recipe.get("tracks")
    if not isinstance(values, list) or not values:
        raise ValueError("mix recipe tracks are invalid")
    song_path = Path(song).resolve()
    identifiers: set[str] = set()
    resolved = []
    for expected in values:
        if not isinstance(expected, dict):
            raise ValueError("mix recipe track is invalid")
        requested = {
            "id": expected.get("id"),
            "role": expected.get("role"),
            "intent": expected.get("intent"),
            "path": expected.get("source_path"),
            "start_seconds": expected.get("start_seconds"),
            "source_start_seconds": expected.get("source_start_seconds"),
            "duration_seconds": expected.get("duration_seconds"),
            "gain_db": expected.get("gain_db"),
            "pan": expected.get("pan"),
            "fade_in_ms": expected.get("fade_in_ms"),
            "fade_out_ms": expected.get("fade_out_ms"),
        }
        track = _validated_track(song_path, requested, identifiers, sample_rate)
        normalized = {key: track[key] for key in MIX_TRACK_RECIPE_KEYS}
        if normalized != expected:
            raise ValueError(f"mix recipe track no longer resolves exactly: {expected.get('id')}")
        resolved.append(track)
    return resolved


def render_mix(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Render an inspectable float working mix from a versioned JSON score."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for mix rendering")
    song_path = Path(song)
    song_manifest = load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid mix JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != MIX_SCHEMA:
        raise ValueError(f"unsupported mix schema: {score.get('schema')}")
    title = score.get("title")
    intent = score.get("intent")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("mix requires a title")
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError("mix requires player-facing intent")
    tracks_value = score.get("tracks")
    if not isinstance(tracks_value, list) or not tracks_value:
        raise ValueError("mix requires at least one track")
    output_record = score.get("output", {})
    if not isinstance(output_record, dict):
        raise ValueError("mix output must be an object")
    sample_rate_value = output_record.get("sample_rate", song_manifest.get("sample_rate", 48_000))
    if isinstance(sample_rate_value, bool) or not isinstance(sample_rate_value, int):
        raise ValueError("mix output sample_rate must be an integer")
    if not 8_000 <= sample_rate_value <= 192_000:
        raise ValueError("mix output sample_rate must be between 8000 and 192000")
    identifiers: set[str] = set()
    tracks = [
        _validated_track(song_path, record, identifiers, sample_rate_value)
        for record in tracks_value
    ]
    evidence = bind_song_evidence(song_path, score.get("evidence"), "mix")

    recipe = {
        "schema": MIX_SCHEMA,
        "title": title,
        "intent": intent,
        "sample_rate": sample_rate_value,
        "output_codec": OUTPUT_CODEC,
        "evidence": evidence,
        "tracks": [{
            key: track[key] for key in MIX_TRACK_RECIPE_KEYS
        } for track in tracks],
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("mix title must contain at least one letter or number")
    destination_dir = song_path / "mixes" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"Mix exists without provenance sidecar: {destination}")
        try:
            existing = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise FileExistsError(f"Mix has invalid existing provenance: {sidecar}: {exc.msg}") from exc
        output = existing.get("output", {})
        if existing.get("recipe_id") == recipe_id and output.get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"Mix destination already exists with different provenance: {destination}")

    filters = []
    for index, track in enumerate(tracks):
        filters.append(f"[{index}:a:0]{','.join(track['operations'])}[track{index}]")
    if len(tracks) == 1:
        filters.append("[track0]anull[out]")
    else:
        inputs = "".join(f"[track{index}]" for index in range(len(tracks)))
        filters.append(
            f"{inputs}amix=inputs={len(tracks)}:duration=longest:dropout_transition=0:normalize=0[out]"
        )
    filter_graph = ";".join(filters)
    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.wav"
    if temporary.exists():
        raise FileExistsError(f"Incomplete mix render already exists: {temporary}")
    command = [ffmpeg, "-nostdin", "-v", "error", "-n"]
    for track in tracks:
        command.extend(["-i", str(track["source"])])
    command.extend([
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-c:a", OUTPUT_CODEC,
        "-ar", str(sample_rate_value),
        "-ac", "2",
        str(temporary),
    ])
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Mix renderer could not start: {exc}") from exc
    if completed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr[-3000:])
    changed_sources = [
        track["source_path"]
        for track in tracks
        if sha256(track["source"]) != track["source_sha256"]
    ]
    if changed_sources:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"mix source changed during rendering: {', '.join(changed_sources)}"
        )
    try:
        verify_evidence_bindings(song_path, evidence, "mix render")
    except (FileNotFoundError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"mix evidence changed during rendering: {exc}") from exc

    output_probe = probe(temporary)
    expected_duration = max(track["end_seconds"] for track in tracks)
    actual_duration = float(output_probe.get("format", {}).get("duration", 0))
    if abs(actual_duration - expected_duration) > max(0.03, expected_duration * 0.001):
        raise RuntimeError(f"Mix duration {actual_duration:g}s does not match expected {expected_duration:g}s")
    output_analysis = analyze(temporary)
    output_analysis.pop("path", None)
    true_peak = output_analysis.get("loudness", {}).get("true_peak_dbfs")
    warnings = []
    if isinstance(true_peak, (int, float)) and true_peak >= 0:
        warnings.append(
            "Working float mix reaches or exceeds 0 dBFS; lower explicit track gains before integer export."
        )
    temporary.rename(destination)
    metadata = {
        "schema": MIX_RENDER_SCHEMA,
        "recipe_id": recipe_id,
        "created_at": utc_now(),
        "title": title,
        "intent": intent,
        "recipe": recipe,
        "render": {
            "filter": filter_graph,
            "output_codec": OUTPUT_CODEC,
            "sample_rate": sample_rate_value,
            "channels": 2,
            "automatic_normalization": False,
            "compression": False,
            "limiting": False,
            "time_stretch": False,
            "pitch_correction": False,
        },
        "sources": [{
            "id": track["id"],
            "path": track["source_path"],
            "sha256": track["source_sha256"],
            "probe": track["source_probe"],
        } for track in tracks],
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "analysis": output_analysis,
        },
        "warnings": warnings,
        "review": {
            "decision": "not recorded by renderer",
            "listening_notes": [],
        },
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar


def verify_mix_provenance(
    song: str | Path,
    mix: str | Path,
    *,
    require_approval: bool = False,
) -> tuple[Path, Path, dict]:
    """Verify a working mix, its sources, and optionally its listen decision."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(mix)
    mix_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        mix_path.relative_to((song_path / "mixes").resolve())
    except ValueError as exc:
        raise ValueError("working mix must be inside the song mixes directory") from exc
    if not mix_path.is_file():
        raise FileNotFoundError(mix_path)
    sidecar = mix_path.with_suffix(mix_path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"Mix provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid mix provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") == "eprs.daw-return-mix/v1":
        # Imported lazily to avoid a module cycle: DAW returns verify their
        # parent interchange, whose renderer reuses mix track resolution.
        from .daw_return import verify_daw_return_mix
        return verify_daw_return_mix(
            song_path,
            mix_path,
            require_approval=require_approval,
        )
    if metadata.get("schema") != MIX_RENDER_SCHEMA:
        raise ValueError("unsupported mix provenance schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("mix provenance has an invalid recipe")
    expected_recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("recipe_id") != expected_recipe_id:
        raise ValueError("mix recipe id does not match its recipe")
    verify_evidence_bindings(song_path, recipe.get("evidence", []), "mix")
    output = metadata.get("output")
    relative_mix = str(mix_path.relative_to(song_path))
    if not isinstance(output, dict) or output.get("path") != relative_mix:
        raise ValueError("mix provenance has an invalid output path")
    if output.get("sha256") != sha256(mix_path):
        raise ValueError("mix checksum has changed since rendering")
    sources = metadata.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("mix provenance sources are invalid")
    for source in sources:
        source_value = source.get("path") if isinstance(source, dict) else None
        source_path = (song_path / source_value).resolve() if isinstance(source_value, str) else None
        try:
            if source_path is None:
                raise ValueError
            source_path.relative_to(song_path)
        except ValueError as exc:
            raise ValueError("mix provenance has an unsafe source path") from exc
        if not source_path.is_file() or source.get("sha256") != sha256(source_path):
            raise ValueError("mix source is missing or changed")
    warnings = metadata.get("warnings")
    if not isinstance(warnings, list):
        raise ValueError("mix provenance warnings are invalid")
    if require_approval:
        review = metadata.get("review")
        notes = review.get("listening_notes") if isinstance(review, dict) else None
        has_keep_note = isinstance(notes, list) and any(
            isinstance(record, dict)
            and record.get("decision") == "keep"
            and isinstance(record.get("note"), str)
            and bool(record["note"].strip())
            for record in notes
        )
        if (
            not isinstance(review, dict)
            or review.get("decision") != "keep"
            or not has_keep_note
        ):
            raise ValueError("mastering requires a recorded complete-listen keep decision for the working mix")
    return mix_path, sidecar, metadata


def review_mix(
    song: str | Path,
    mix: str | Path,
    listening_note: str,
    decision: str,
) -> Path:
    """Record a complete working-mix listen without changing the audio."""
    note = listening_note.strip()
    if not note:
        raise ValueError("mix review requires a listening note")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("mix review decision must be keep, change, or stop")
    _, sidecar, metadata = verify_mix_provenance(song, mix)
    review = metadata.setdefault("review", {})
    notes = review.setdefault("listening_notes", [])
    if not isinstance(notes, list):
        raise ValueError("mix listening_notes must be a list")
    duplicate = any(
        isinstance(record, dict)
        and record.get("note") == note
        and record.get("decision") == decision
        for record in notes
    )
    if duplicate and review.get("decision") == decision:
        return sidecar
    if not duplicate:
        notes.append({"reviewed_at": utc_now(), "note": note, "decision": decision})
    review["decision"] = decision
    temporary = sidecar.with_name(f".{sidecar.name}.review.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete mix review exists: {temporary}")
    temporary.write_text(json.dumps(metadata, indent=2) + "\n")
    temporary.replace(sidecar)
    return sidecar
