"""Explicit, refusal-first lossless mastering for approved working mixes."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from .mix import verify_mix_provenance
from .system import analyze, load_song_manifest, probe, sha256, slugify, utc_now


MASTER_SCHEMA = "eprs.master/v1"
MASTER_CODEC = "pcm_s24le"


def _finite_number(record: dict, key: str, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"master {key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"master {key} must be finite")
    return number


def _master_source(song: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("master requires a source path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError("master source path must be relative to the song")
    source = (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError("master source path escapes the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def render_master(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Render a 24-bit lossless master without normalization or limiting."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for master rendering")
    song_path = Path(song)
    song_manifest = load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid master JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != MASTER_SCHEMA:
        raise ValueError(f"unsupported master schema: {score.get('schema')}")
    title = score.get("title")
    intent = score.get("intent")
    destination_intent = score.get("destination")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("master requires a title")
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError("master requires listening intent")
    if not isinstance(destination_intent, str) or not destination_intent.strip():
        raise ValueError("master requires a destination such as lossless archive or YouTube source")
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("master title must contain at least one letter or number")
    source = _master_source(song_path, score.get("source"))
    source, source_sidecar, source_metadata = verify_mix_provenance(
        song_path,
        source,
        require_approval=True,
    )
    source_sidecar_digest = sha256(source_sidecar)
    source_probe = probe(source)
    audio_stream = next(
        (stream for stream in source_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )
    if audio_stream is None:
        raise ValueError("master source has no audio stream")
    source_duration_value = source_probe.get("format", {}).get("duration")
    if source_duration_value is None:
        raise ValueError("master source duration is unavailable")
    source_duration = float(source_duration_value)
    source_sample_rate = int(audio_stream.get("sample_rate") or 0)
    source_channels = int(audio_stream.get("channels") or 0)
    if source_channels not in {1, 2}:
        raise ValueError("master v1 accepts mono or stereo sources; prepare a derived stereo mix first")

    gain_db = _finite_number(score, "gain_db", 0)
    ceiling_dbfs = _finite_number(score, "true_peak_ceiling_dbfs", -1)
    if not -60 <= gain_db <= 24:
        raise ValueError("master gain_db must be between -60 and 24")
    if not -30 <= ceiling_dbfs <= 0:
        raise ValueError("master true_peak_ceiling_dbfs must be between -30 and 0")
    output_record = score.get("output", {})
    if not isinstance(output_record, dict):
        raise ValueError("master output must be an object")
    sample_rate = output_record.get(
        "sample_rate",
        source_sample_rate or song_manifest.get("sample_rate", 48_000),
    )
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
        raise ValueError("master output sample_rate must be an integer")
    if not 8_000 <= sample_rate <= 192_000:
        raise ValueError("master output sample_rate must be between 8000 and 192000")
    bit_depth = output_record.get("bit_depth", 24)
    if bit_depth != 24:
        raise ValueError("master v1 output bit_depth must be 24")

    source_analysis = analyze(source)
    source_true_peak = source_analysis.get("loudness", {}).get("true_peak_dbfs")
    if not isinstance(source_true_peak, (int, float)):
        raise ValueError("master source true peak could not be measured")
    predicted_true_peak = source_true_peak + gain_db
    if predicted_true_peak > ceiling_dbfs + 0.01:
        raise ValueError(
            f"master would reach {predicted_true_peak:.2f} dBFS, above the declared "
            f"{ceiling_dbfs:.2f} dBFS ceiling; lower gain_db explicitly"
        )

    source_digest = sha256(source)
    recipe = {
        "schema": MASTER_SCHEMA,
        "title": title,
        "intent": intent,
        "destination": destination_intent,
        "source_path": str(source.relative_to(song_path.resolve())),
        "source_sha256": source_digest,
        "source_provenance_path": str(source_sidecar.relative_to(song_path.resolve())),
        "source_provenance_sha256": source_sidecar_digest,
        "gain_db": gain_db,
        "true_peak_ceiling_dbfs": ceiling_dbfs,
        "output": {
            "sample_rate": sample_rate,
            "bit_depth": 24,
            "codec": MASTER_CODEC,
            "channels": 2,
        },
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "masters" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"Master exists without provenance sidecar: {destination}")
        try:
            existing = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise FileExistsError(f"Master has invalid existing provenance: {sidecar}: {exc.msg}") from exc
        output = existing.get("output", {})
        if existing.get("recipe_id") == recipe_id and output.get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"Master destination already exists with different provenance: {destination}")

    filter_graph = (
        f"volume={gain_db:.12g}dB:precision=double,"
        f"aresample={sample_rate},"
        "aformat=sample_fmts=s32:channel_layouts=stereo"
    )
    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.wav"
    if temporary.exists():
        raise FileExistsError(f"Incomplete master render already exists: {temporary}")
    command = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-n",
        "-i", str(source),
        "-map", "0:a:0",
        "-af", filter_graph,
        "-c:a", MASTER_CODEC,
        "-ar", str(sample_rate),
        "-ac", "2",
        str(temporary),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-3000:])

    output_probe = probe(temporary)
    actual_duration = float(output_probe.get("format", {}).get("duration", 0))
    if abs(actual_duration - source_duration) > max(0.03, source_duration * 0.001):
        raise RuntimeError(
            f"Master duration {actual_duration:g}s does not match source duration {source_duration:g}s"
        )
    output_analysis = analyze(temporary)
    output_analysis.pop("path", None)
    actual_true_peak = output_analysis.get("loudness", {}).get("true_peak_dbfs")
    if not isinstance(actual_true_peak, (int, float)):
        raise RuntimeError("Rendered master true peak could not be measured")
    if actual_true_peak > ceiling_dbfs + 0.1:
        raise RuntimeError(
            f"Rendered master reaches {actual_true_peak:.2f} dBFS, above the declared "
            f"{ceiling_dbfs:.2f} dBFS ceiling"
        )
    temporary.rename(destination)
    conversion_notes = []
    if source_sample_rate and source_sample_rate != sample_rate:
        conversion_notes.append(f"Resampled from {source_sample_rate} Hz to {sample_rate} Hz as declared.")
    if source_channels == 1:
        conversion_notes.append("Duplicated the mono source to stereo as declared by master v1 output.")
    metadata = {
        "schema": "eprs.master-render/v1",
        "recipe_id": recipe_id,
        "created_at": utc_now(),
        "title": title,
        "intent": intent,
        "destination": destination_intent,
        "recipe": recipe,
        "source": {
            "path": recipe["source_path"],
            "sha256": source_digest,
            "provenance": {
                "path": recipe["source_provenance_path"],
                "sha256": source_sidecar_digest,
                "schema": source_metadata["schema"],
                "review_decision": source_metadata["review"]["decision"],
            },
            "probe": source_probe,
            "analysis": {key: value for key, value in source_analysis.items() if key != "path"},
        },
        "render": {
            "filter": filter_graph,
            "explicit_gain_db": gain_db,
            "true_peak_ceiling_dbfs": ceiling_dbfs,
            "predicted_true_peak_dbfs": round(predicted_true_peak, 2),
            "codec": MASTER_CODEC,
            "bit_depth": 24,
            "sample_rate": sample_rate,
            "channels": 2,
            "automatic_normalization": False,
            "compression": False,
            "limiting": False,
            "soft_clipping": False,
            "dither_added": False,
        },
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "analysis": output_analysis,
        },
        "conversion_notes": conversion_notes,
        "approval": {
            "technical_render": "passed",
            "creative_listen_through": "not recorded by renderer",
            "listening_notes": [],
            "promotion_to_FINAL": "not performed",
        },
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar


def verify_master_provenance(
    song: str | Path,
    master: str | Path,
    *,
    require_approval: bool = False,
) -> tuple[Path, Path, dict]:
    """Verify master/source lineage and optionally require listen approval."""
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(master)
    master_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    masters_root = (song_path / "masters").resolve()
    try:
        master_path.relative_to(masters_root)
    except ValueError as exc:
        raise ValueError("approved master must be inside the song masters directory") from exc
    if not master_path.is_file():
        raise FileNotFoundError(master_path)
    sidecar = master_path.with_suffix(master_path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"Master provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid master provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != "eprs.master-render/v1":
        raise ValueError("unsupported master provenance schema")
    output = metadata.get("output", {})
    if output.get("sha256") != sha256(master_path):
        raise ValueError("master checksum has changed since rendering; approval was not recorded")
    source = metadata.get("source", {})
    source_value = source.get("path")
    if not isinstance(source_value, str):
        raise ValueError("master provenance has no valid source path")
    source_path = (song_path / source_value).resolve()
    try:
        source_path.relative_to(song_path.resolve())
    except ValueError as exc:
        raise ValueError("master provenance source escapes the song workspace") from exc
    if not source_path.is_file() or source.get("sha256") != sha256(source_path):
        raise ValueError("master source is missing or changed")
    provenance = source.get("provenance") if isinstance(source, dict) else None
    provenance_value = provenance.get("path") if isinstance(provenance, dict) else None
    provenance_path = (song_path / provenance_value).resolve() if isinstance(provenance_value, str) else None
    try:
        if provenance_path is None:
            raise ValueError
        provenance_path.relative_to(song_path.resolve())
    except ValueError as exc:
        raise ValueError("master source provenance has an unsafe path") from exc
    if not provenance_path.is_file() or provenance.get("sha256") != sha256(provenance_path):
        raise ValueError("approved mix provenance is missing or changed")
    verify_mix_provenance(song_path, source_path, require_approval=True)
    if require_approval:
        approval = metadata.get("approval")
        notes = approval.get("listening_notes") if isinstance(approval, dict) else None
        if (
            not isinstance(approval, dict)
            or approval.get("creative_listen_through") != "approved"
            or not isinstance(notes, list)
            or not notes
        ):
            raise ValueError("master requires a recorded full-listen approval before delivery encoding")
    return master_path, sidecar, metadata


def approve_master(song: str | Path, master: str | Path, listening_note: str) -> Path:
    """Record an explicit full-listen approval without promoting or publishing."""
    note = listening_note.strip()
    if not note:
        raise ValueError("master approval requires a listening note")
    master_path, sidecar, metadata = verify_master_provenance(song, master)
    approval = metadata.setdefault("approval", {})
    notes = approval.setdefault("listening_notes", [])
    if not isinstance(notes, list):
        raise ValueError("master approval listening_notes must be a list")
    if any(isinstance(item, dict) and item.get("note") == note for item in notes):
        return sidecar
    notes.append({"approved_at": utc_now(), "note": note})
    approval["creative_listen_through"] = "approved"
    approval["promotion_to_FINAL"] = "not performed"
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return sidecar
