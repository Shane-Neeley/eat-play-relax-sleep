"""DAW-neutral common-start stem packages derived from verified working mixes."""

from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from .mix import resolve_mix_recipe_tracks, verify_mix_provenance
from .system import load_song_manifest, probe, sha256, slugify, utc_now


INTERCHANGE_SCHEMA = "eprs.daw-interchange/v1"
OUTPUT_CODEC = "pcm_f32le"
MAX_TRACKS = 64
MAX_RECONSTRUCTION_ERROR = 1e-5


def _run(command: list[str], description: str) -> None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        raise RuntimeError(f"{description} could not start: {exc}") from exc
    if completed.returncode:
        raise RuntimeError(f"{description} failed: {completed.stderr[-5000:]}")


def _audio_stream(report: dict) -> dict | None:
    return next(
        (stream for stream in report.get("streams", []) if stream.get("codec_type") == "audio"),
        None,
    )


def _decode_raw(ffmpeg: str, source: Path, destination: Path, sample_rate: int) -> None:
    _run([
        ffmpeg, "-nostdin", "-v", "error", "-n", "-i", str(source),
        "-map", "0:a:0", "-f", "f32le", "-acodec", "pcm_f32le",
        "-ar", str(sample_rate), "-ac", "2", str(destination),
    ], "interchange reconstruction decoder")


def _sample_comparison(reference_raw: Path, reconstruction_raw: Path) -> dict:
    count = 0
    max_error = 0.0
    reference_energy = 0.0
    error_energy = 0.0
    with reference_raw.open("rb") as reference, reconstruction_raw.open("rb") as reconstruction:
        while True:
            left = reference.read(256 * 1024)
            right = reconstruction.read(256 * 1024)
            if not left and not right:
                break
            if len(left) != len(right) or len(left) % 4:
                raise RuntimeError("interchange reconstruction has a different decoded sample count")
            reference_values = array("f")
            reconstruction_values = array("f")
            reference_values.frombytes(left)
            reconstruction_values.frombytes(right)
            if sys.byteorder != "little":
                reference_values.byteswap()
                reconstruction_values.byteswap()
            for expected, actual in zip(reference_values, reconstruction_values):
                if not math.isfinite(expected) or not math.isfinite(actual):
                    raise RuntimeError("interchange reconstruction contains non-finite samples")
                difference = float(actual) - float(expected)
                max_error = max(max_error, abs(difference))
                reference_energy += float(expected) * float(expected)
                error_energy += difference * difference
                count += 1
    if not count:
        raise RuntimeError("interchange reconstruction comparison decoded no audio")
    reference_rms = math.sqrt(reference_energy / count)
    error_rms = math.sqrt(error_energy / count)

    def db(value: float) -> float:
        return -300.0 if value <= 1e-15 else 20 * math.log10(value)

    snr = 300.0 if error_rms <= 1e-15 else 20 * math.log10(max(reference_rms, 1e-15) / error_rms)
    return {
        "decoded_interleaved_samples": count,
        "max_absolute_error": max_error,
        "max_error_dbfs": db(max_error),
        "rms_error": error_rms,
        "rms_error_dbfs": db(error_rms),
        "reference_rms": reference_rms,
        "signal_to_error_db": snr,
        "maximum_allowed_absolute_error": MAX_RECONSTRUCTION_ERROR,
        "passed": max_error <= MAX_RECONSTRUCTION_ERROR,
    }


def _safe_package_path(package: Path, value: object, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{description} path is invalid")
    candidate = (package / value).resolve()
    try:
        candidate.relative_to(package.resolve())
    except ValueError as exc:
        raise ValueError(f"{description} escapes the interchange package") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _resolve_package(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif "/" not in str(value) and not (song / requested).exists():
        candidate = (song / "interchange" / requested).resolve()
    else:
        candidate = (song / requested).resolve()
    root = (song / "interchange").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("DAW interchange package must be inside the song interchange directory") from exc
    if not candidate.is_dir():
        raise FileNotFoundError(candidate)
    return candidate


def verify_daw_interchange(
    song: str | Path,
    package: str | Path,
    *,
    verify_checksums: bool = True,
    verify_media: bool = False,
) -> tuple[Path, dict]:
    """Verify a self-contained common-start package without changing it."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    package_path = _resolve_package(song_path, package)
    manifest_path = package_path / "interchange.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid DAW interchange JSON: {manifest_path}: {exc.msg}") from exc
    if manifest.get("schema") != INTERCHANGE_SCHEMA:
        raise ValueError("unsupported DAW interchange schema")
    recipe = manifest.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("DAW interchange recipe is invalid")
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if manifest.get("package_id") != expected_id:
        raise ValueError("DAW interchange package id does not match its recipe")
    title_slug = slugify(str(recipe.get("title", "")))
    if not title_slug:
        raise ValueError("DAW interchange recipe title is invalid")
    expected_name = f"{title_slug}-{expected_id[:10]}"
    if package_path.name != expected_name:
        raise ValueError("DAW interchange directory does not match its package id")
    sample_rate = recipe.get("sample_rate")
    channels = recipe.get("channels")
    duration = recipe.get("duration_seconds")
    if (
        isinstance(sample_rate, bool)
        or not isinstance(sample_rate, int)
        or not 8_000 <= sample_rate <= 192_000
        or channels != 2
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(float(duration))
        or duration <= 0
        or recipe.get("codec") != OUTPUT_CODEC
        or recipe.get("timeline_start_seconds") != 0
    ):
        raise ValueError("DAW interchange format recipe is invalid")
    tracks = manifest.get("tracks")
    recipe_tracks = recipe.get("tracks")
    if (
        not isinstance(tracks, list)
        or not isinstance(recipe_tracks, list)
        or not tracks
        or len(tracks) != len(recipe_tracks)
        or len(tracks) > MAX_TRACKS
    ):
        raise ValueError("DAW interchange tracks are invalid")
    artifacts = [
        (manifest.get("reference_mix"), "DAW interchange reference mix"),
        (manifest.get("mix_provenance_snapshot"), "DAW interchange provenance snapshot"),
        *((track, f"DAW interchange stem {index}") for index, track in enumerate(tracks, start=1)),
    ]
    for record, description in artifacts:
        if not isinstance(record, dict):
            raise ValueError(f"{description} record is invalid")
        artifact = _safe_package_path(package_path, record.get("path"), description)
        digest = record.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"{description} checksum is invalid")
        if verify_checksums and sha256(artifact) != digest:
            raise ValueError(f"{description} checksum has changed")
        if verify_media and description != "DAW interchange provenance snapshot":
            media_probe = probe(artifact)
            stream = _audio_stream(media_probe)
            if (
                stream is None
                or stream.get("codec_name") != OUTPUT_CODEC
                or stream.get("sample_rate") != str(sample_rate)
                or stream.get("channels") != 2
            ):
                raise ValueError(f"{description} media format is invalid")
            media_duration = float(media_probe.get("format", {}).get("duration") or 0)
            if abs(media_duration - float(recipe.get("duration_seconds", 0))) > 0.002:
                raise ValueError(f"{description} duration is invalid")
    source_mix = recipe.get("source_mix")
    reference_mix = manifest.get("reference_mix")
    provenance_snapshot = manifest.get("mix_provenance_snapshot")
    if (
        not isinstance(source_mix, dict)
        or not isinstance(reference_mix, dict)
        or not isinstance(provenance_snapshot, dict)
        or reference_mix.get("sha256") != source_mix.get("sha256")
        or provenance_snapshot.get("sha256") != source_mix.get("provenance_sha256")
    ):
        raise ValueError("DAW interchange source snapshot binding is invalid")
    for index, (track, expected) in enumerate(zip(tracks, recipe_tracks), start=1):
        if track.get("id") != expected.get("id") or track.get("source") != expected:
            raise ValueError(f"DAW interchange stem {index} does not match its recipe track")
        if (
            track.get("timeline_start_seconds") != 0
            or track.get("common_start") is not True
            or track.get("duration_seconds") != duration
            or track.get("codec") != OUTPUT_CODEC
            or track.get("sample_rate") != sample_rate
            or track.get("channels") != 2
        ):
            raise ValueError(f"DAW interchange stem {index} is not declared common-start")
    reconstruction = manifest.get("reconstruction_verification")
    maximum_error = reconstruction.get("max_absolute_error") if isinstance(reconstruction, dict) else None
    allowed_error = reconstruction.get("maximum_allowed_absolute_error") if isinstance(reconstruction, dict) else None
    if (
        not isinstance(reconstruction, dict)
        or reconstruction.get("passed") is not True
        or isinstance(maximum_error, bool)
        or not isinstance(maximum_error, (int, float))
        or not math.isfinite(float(maximum_error))
        or maximum_error < 0
        or allowed_error != MAX_RECONSTRUCTION_ERROR
        or maximum_error > allowed_error
        or isinstance(reconstruction.get("decoded_interleaved_samples"), bool)
        or not isinstance(reconstruction.get("decoded_interleaved_samples"), int)
        or reconstruction["decoded_interleaved_samples"] < 1
    ):
        raise ValueError("DAW interchange reconstruction verification is invalid")
    actions = manifest.get("actions_performed")
    if not isinstance(actions, dict) or any(actions.get(key) is not False for key in (
        "source_audio_modified", "normalization", "compression", "limiting",
        "time_stretch", "pitch_correction", "phase_alignment",
    )):
        raise ValueError("DAW interchange action record is invalid")
    authority = manifest.get("authority")
    if not isinstance(authority, dict) or any(authority.get(key) is not False for key in (
        "creative_approval_inferred", "final_promotion", "upload_authorized",
        "publication_authorized",
    )):
        raise ValueError("DAW interchange authority record is invalid")
    return package_path, manifest


def prepare_daw_interchange(song: str | Path, mix: str | Path) -> tuple[Path, Path, dict]:
    """Create common-start float stems and prove they reconstruct one exact mix."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for DAW interchange")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    mix_path, mix_sidecar, mix_metadata = verify_mix_provenance(song_path, mix)
    recipe = mix_metadata["recipe"]
    tracks = resolve_mix_recipe_tracks(song_path, recipe)
    if len(tracks) > MAX_TRACKS:
        raise ValueError(f"DAW interchange supports at most {MAX_TRACKS} tracks")
    mix_probe = probe(mix_path)
    mix_stream = _audio_stream(mix_probe)
    duration = float(mix_probe.get("format", {}).get("duration") or 0)
    sample_rate = int(recipe.get("sample_rate") or 0)
    if (
        mix_stream is None
        or mix_stream.get("codec_name") != OUTPUT_CODEC
        or mix_stream.get("channels") != 2
        or mix_stream.get("sample_rate") != str(sample_rate)
        or duration <= 0
    ):
        raise ValueError("DAW interchange requires a verified stereo float working mix")
    mix_digest = sha256(mix_path)
    sidecar_digest = sha256(mix_sidecar)
    interchange_recipe = {
        "schema": INTERCHANGE_SCHEMA,
        "title": mix_metadata.get("title"),
        "intent": mix_metadata.get("intent"),
        "source_mix": {
            "path": str(mix_path.relative_to(song_path)),
            "sha256": mix_digest,
            "provenance_path": str(mix_sidecar.relative_to(song_path)),
            "provenance_sha256": sidecar_digest,
            "recipe_id": mix_metadata.get("recipe_id"),
        },
        "sample_rate": sample_rate,
        "channels": 2,
        "codec": OUTPUT_CODEC,
        "duration_seconds": duration,
        "timeline_start_seconds": 0,
        "tracks": recipe["tracks"],
        "evidence": recipe.get("evidence", []),
        "review_snapshot": mix_metadata.get("review"),
    }
    package_id = hashlib.sha256(
        json.dumps(interchange_recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(str(mix_metadata.get("title", "")))
    if not title_slug:
        raise ValueError("DAW interchange mix title is invalid")
    root = song_path / "interchange"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{title_slug}-{package_id[:10]}"
    if destination.exists():
        package_path, existing = verify_daw_interchange(
            song_path, destination, verify_checksums=True, verify_media=True
        )
        return package_path, package_path / "interchange.json", existing
    temporary = root / f".{title_slug}-{package_id[:10]}.partial"
    if temporary.exists():
        raise FileExistsError(f"Incomplete DAW interchange package exists: {temporary}")
    stems_dir = temporary / "stems"
    stems_dir.mkdir(parents=True)
    try:
        reference_mix = temporary / "reference-mix.wav"
        provenance_snapshot = temporary / "mix-provenance.json"
        shutil.copy2(mix_path, reference_mix)
        shutil.copy2(mix_sidecar, provenance_snapshot)
        stem_records = []
        for index, track in enumerate(tracks, start=1):
            stem_path = stems_dir / f"{index:02d}-{track['id']}.wav"
            filter_chain = [
                *track["operations"],
                "apad",
                f"atrim=duration={duration:.12g}",
            ]
            _run([
                ffmpeg, "-nostdin", "-v", "error", "-n", "-i", str(track["source"]),
                "-map", "0:a:0", "-af", ",".join(filter_chain), "-map_metadata", "-1",
                "-c:a", OUTPUT_CODEC, "-ar", str(sample_rate), "-ac", "2", str(stem_path),
            ], f"DAW interchange stem renderer for {track['id']}")
            stem_probe = probe(stem_path)
            stem_stream = _audio_stream(stem_probe)
            stem_duration = float(stem_probe.get("format", {}).get("duration") or 0)
            if (
                stem_stream is None
                or stem_stream.get("codec_name") != OUTPUT_CODEC
                or stem_stream.get("sample_rate") != str(sample_rate)
                or stem_stream.get("channels") != 2
                or abs(stem_duration - duration) > 0.002
            ):
                raise RuntimeError(f"DAW interchange stem failed format verification: {track['id']}")
            stem_records.append({
                "id": track["id"],
                "role": track["role"],
                "intent": track["intent"],
                "path": str(stem_path.relative_to(temporary)),
                "sha256": sha256(stem_path),
                "common_start": True,
                "timeline_start_seconds": 0,
                "duration_seconds": duration,
                "codec": OUTPUT_CODEC,
                "sample_rate": sample_rate,
                "channels": 2,
                "source": {key: track[key] for key in (
                    "id", "role", "intent", "source_path", "source_sha256",
                    "start_seconds", "source_start_seconds", "duration_seconds",
                    "gain_db", "pan", "pan_law", "fade_in_ms", "fade_out_ms",
                )},
            })
        reconstruction = temporary / ".reconstructed-sum.wav"
        command = [ffmpeg, "-nostdin", "-v", "error", "-n"]
        for record in stem_records:
            command.extend(["-i", str(temporary / record["path"])])
        if len(stem_records) == 1:
            command.extend(["-map", "0:a:0"])
        else:
            inputs = "".join(f"[{index}:a:0]" for index in range(len(stem_records)))
            command.extend([
                "-filter_complex",
                f"{inputs}amix=inputs={len(stem_records)}:duration=longest:dropout_transition=0:normalize=0[out]",
                "-map", "[out]",
            ])
        command.extend([
            "-c:a", OUTPUT_CODEC, "-ar", str(sample_rate), "-ac", "2", str(reconstruction),
        ])
        _run(command, "DAW interchange stem reconstruction")
        reference_raw = temporary / ".reference.raw"
        reconstruction_raw = temporary / ".reconstruction.raw"
        _decode_raw(ffmpeg, reference_mix, reference_raw, sample_rate)
        _decode_raw(ffmpeg, reconstruction, reconstruction_raw, sample_rate)
        comparison = _sample_comparison(reference_raw, reconstruction_raw)
        for scratch in (reference_raw, reconstruction_raw, reconstruction):
            scratch.unlink(missing_ok=True)
        if not comparison["passed"]:
            raise RuntimeError(
                "DAW interchange stems do not reconstruct the working mix within tolerance: "
                f"{comparison['max_absolute_error']:.6g}"
            )
        if sha256(mix_path) != mix_digest or sha256(mix_sidecar) != sidecar_digest:
            raise RuntimeError("mix or mix provenance changed during DAW interchange preparation")
        manifest = {
            "schema": INTERCHANGE_SCHEMA,
            "package_id": package_id,
            "created_at": utc_now(),
            "recipe": interchange_recipe,
            "reference_mix": {
                "path": reference_mix.name,
                "sha256": sha256(reference_mix),
            },
            "mix_provenance_snapshot": {
                "path": provenance_snapshot.name,
                "sha256": sha256(provenance_snapshot),
            },
            "tracks": stem_records,
            "reconstruction_verification": comparison,
            "actions_performed": {
                "source_audio_modified": False,
                "normalization": False,
                "compression": False,
                "limiting": False,
                "time_stretch": False,
                "pitch_correction": False,
                "phase_alignment": False,
            },
            "authority": {
                "creative_approval_inferred": False,
                "final_promotion": False,
                "upload_authorized": False,
                "publication_authorized": False,
            },
        }
        manifest_path = temporary / "interchange.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        readme = temporary / "README.md"
        readme.write_text(
            f"# DAW interchange: {mix_metadata.get('title')}\n\n"
            "Import every WAV in `stems/` at session time 0. They are stereo 32-bit "
            f"float PCM at {sample_rate} Hz and all have the same {duration:g}-second length.\n\n"
            "`reference-mix.wav` is an exact copy of the verified working mix. Summing the "
            "stems at unity reproduces it within the tolerance recorded in `interchange.json`. "
            "Do not add automatic normalization, fades, time alignment, or polarity changes on "
            "import. The package is an editable working handoff, not creative approval, FINAL "
            "promotion, upload permission, or a substitute for the immutable source recordings.\n"
        )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    package_path, verified = verify_daw_interchange(
        song_path, destination, verify_checksums=True, verify_media=True
    )
    return package_path, package_path / "interchange.json", verified
