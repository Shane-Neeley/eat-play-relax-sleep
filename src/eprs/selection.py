"""Reversible selection and looping for supplied performances and sounds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .system import ingest, load_song_manifest, probe, sha256, slugify, utc_now


PCM_WAV_CODECS = {
    "pcm_u8",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "pcm_s64le",
    "pcm_f32le",
    "pcm_f64le",
}


def _is_within(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
        return True
    except ValueError:
        return False


def _audio_stream(media_probe: dict, source: Path) -> dict:
    stream = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    if stream is None:
        raise ValueError(f"Source has no audio stream: {source}")
    return stream


def _lossless_wav_codec(stream: dict) -> str:
    codec = str(stream.get("codec_name", ""))
    if codec in PCM_WAV_CODECS:
        return codec
    sample_format = str(stream.get("sample_fmt", ""))
    raw_bits = str(stream.get("bits_per_raw_sample", ""))
    if sample_format.startswith("u8"):
        return "pcm_u8"
    if sample_format.startswith("s16"):
        return "pcm_s16le"
    if sample_format.startswith("s32"):
        return "pcm_s24le" if raw_bits == "24" else "pcm_s32le"
    if sample_format.startswith("s64"):
        return "pcm_s64le"
    if sample_format.startswith("dbl"):
        return "pcm_f64le"
    if sample_format.startswith("flt"):
        return "pcm_f32le"
    # Decode compressed or unknown input once into a lossless working selection.
    return "pcm_s24le"


def _selection_filter(start: float, duration: float, repeat: int, crossfade: float) -> str:
    trim = f"[0:a:0]atrim=start={start:.12g}:duration={duration:.12g},asetpts=PTS-STARTPTS"
    if repeat == 1:
        return f"{trim}[out]"
    branches = "".join(f"[part{index}]" for index in range(repeat))
    pieces = [f"{trim},asplit={repeat}{branches}"]
    if crossfade == 0:
        inputs = "".join(f"[part{index}]" for index in range(repeat))
        pieces.append(f"{inputs}concat=n={repeat}:v=0:a=1[out]")
        return ";".join(pieces)
    previous = "part0"
    for index in range(1, repeat):
        output = "out" if index == repeat - 1 else f"joined{index}"
        pieces.append(
            f"[{previous}][part{index}]acrossfade=d={crossfade:.12g}:c1=tri:c2=tri[{output}]"
        )
        previous = output
    return ";".join(pieces)


def select_audio(
    source: str | Path,
    song: str | Path,
    role: str,
    start: float,
    duration: float,
    repeat: int = 1,
    crossfade_ms: float = 0,
    note: str = "",
) -> tuple[Path, Path]:
    """Render a non-destructive selection into a song's selected recordings.

    External input is ingested first so every transformation retains an
    immutable source. Repeating preserves speed and pitch; crossfade is opt-in.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for audio selection")
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe is required for audio selection verification")
    song_path = Path(song)
    load_song_manifest(song_path)
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("selection role must contain at least one letter or number")
    if start < 0:
        raise ValueError("selection start must be zero or greater")
    if duration <= 0:
        raise ValueError("selection duration must be greater than zero")
    if repeat < 1 or repeat > 128:
        raise ValueError("selection repeat must be between 1 and 128")
    if crossfade_ms < 0:
        raise ValueError("selection crossfade must be zero or greater")
    crossfade = crossfade_ms / 1000
    if repeat == 1 and crossfade:
        raise ValueError("selection crossfade requires repeat greater than one")
    if crossfade * 2 >= duration:
        raise ValueError("selection crossfade must be shorter than half the selected phrase")

    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if not _is_within(source_path, song_path):
        source_path, _ = ingest(
            source_path,
            song_path,
            role,
            f"Automatically ingested before non-destructive selection. {note}".strip(),
        )
        source_path = source_path.resolve()

    source_probe = probe(source_path)
    stream = _audio_stream(source_probe, source_path)
    source_duration_value = source_probe.get("format", {}).get("duration")
    if source_duration_value is not None:
        source_duration = float(source_duration_value)
        if start >= source_duration or start + duration > source_duration + 0.002:
            raise ValueError(
                f"selection {start:g}s–{start + duration:g}s exceeds source duration {source_duration:g}s"
            )
    source_digest = sha256(source_path)
    recipe = {
        "source_sha256": source_digest,
        "role": role,
        "start_seconds": start,
        "duration_seconds": duration,
        "repeat": repeat,
        "crossfade_ms": crossfade_ms,
        "note": note,
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "recordings" / "selected" / role_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    source_stem = source_path.stem
    intake_prefix = f"{source_digest[:10]}-"
    if source_stem.startswith(intake_prefix):
        source_stem = source_stem[len(intake_prefix):]
    source_name = slugify(source_stem) or "source"
    destination = destination_dir / f"{source_digest[:10]}-{recipe_id[:8]}-{source_name}.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"Selection exists without provenance sidecar: {destination}")
        existing = json.loads(sidecar.read_text())
        output_record = existing.get("output", {})
        if existing.get("recipe_id") == recipe_id and output_record.get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"Selection destination already exists with different provenance: {destination}")

    codec = _lossless_wav_codec(stream)
    sample_rate = int(stream.get("sample_rate") or 48_000)
    filter_graph = _selection_filter(start, duration, repeat, crossfade)
    command = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-n",
        "-i", str(source_path),
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-c:a", codec,
        "-ar", str(sample_rate),
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-3000:])

    output_probe = probe(destination)
    output_duration = float(output_probe.get("format", {}).get("duration", 0))
    expected_duration = duration * repeat - crossfade * (repeat - 1)
    if abs(output_duration - expected_duration) > max(0.03, expected_duration * 0.001):
        raise RuntimeError(
            f"Selection duration {output_duration:g}s does not match expected {expected_duration:g}s"
        )
    metadata = {
        "schema": "eprs.audio-selection/v1",
        "recipe_id": recipe_id,
        "created_at": utc_now(),
        "role": role,
        "note": note,
        "source": {
            "path": str(source_path.relative_to(song_path.resolve())),
            "sha256": source_digest,
            "probe": source_probe,
        },
        "selection": {
            "start_seconds": start,
            "duration_seconds": duration,
            "repeat": repeat,
            "crossfade_ms": crossfade_ms,
            "expected_duration_seconds": expected_duration,
        },
        "processing": {
            "filter": filter_graph,
            "output_codec": codec,
            "sample_rate": sample_rate,
            "automatic_normalization": False,
            "time_stretch": False,
            "pitch_shift": False,
            "dynamics_processing": False,
        },
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
        },
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar
