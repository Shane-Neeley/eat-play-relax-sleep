"""Approval-gated, provenance-rich YouTube listening-video preparation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess

from .master import verify_master_provenance
from .picture import verify_picture
from .system import load_song_manifest, probe, sha256, slugify, utc_now


YOUTUBE_SCHEMA = "eprs.youtube/v1"
YOUTUBE_PICTURE_SCHEMA = "eprs.youtube/v2"
YOUTUBE_RENDER_SCHEMAS = {"eprs.youtube-render/v1", "eprs.youtube-render/v2"}
HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _color(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"YouTube {name} must be a six-digit hex color")
    match = HEX_COLOR.fullmatch(value)
    if not match:
        raise ValueError(f"YouTube {name} must be a six-digit hex color")
    return match.group(1).lower()


def _integer(record: dict, key: str, default: int, low: int, high: int) -> int:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"YouTube {key} must be an integer between {low} and {high}")
    return value


def _filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _top_level_atoms(path: Path) -> list[tuple[str, int]]:
    atoms: list[tuple[str, int]] = []
    file_size = path.stat().st_size
    with path.open("rb") as handle:
        position = 0
        while position + 8 <= file_size:
            handle.seek(position)
            header = handle.read(8)
            if len(header) != 8:
                break
            size, atom_type = struct.unpack(">I4s", header)
            header_size = 8
            if size == 1:
                extended = handle.read(8)
                if len(extended) != 8:
                    break
                size = struct.unpack(">Q", extended)[0]
                header_size = 16
            elif size == 0:
                size = file_size - position
            if size < header_size or position + size > file_size:
                break
            atoms.append((atom_type.decode("ascii", errors="replace"), position))
            position += size
    return atoms


def _fast_start(path: Path) -> bool:
    atoms = _top_level_atoms(path)
    positions = {name: position for name, position in atoms if name in {"moov", "mdat"}}
    return "moov" in positions and "mdat" in positions and positions["moov"] < positions["mdat"]


def _stream_packet_hashes(path: Path, selector: str, label: str) -> list[str]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required to verify picture stream copying")
    completed = subprocess.run([
        ffprobe,
        "-v", "error",
        "-select_streams", selector,
        "-show_packets",
        "-show_entries", "packet=data_hash",
        "-show_data_hash", "sha256",
        "-of", "json",
        str(path),
    ], capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip())
    try:
        packets = json.loads(completed.stdout).get("packets", [])
    except json.JSONDecodeError as exc:
        raise RuntimeError("FFprobe returned invalid packet-hash JSON") from exc
    hashes = [
        packet.get("data_hash") for packet in packets
        if isinstance(packet, dict) and isinstance(packet.get("data_hash"), str)
    ]
    if not hashes or len(hashes) != len(packets):
        raise RuntimeError(f"FFprobe could not hash every {label} packet")
    return hashes


def _video_packet_hashes(path: Path) -> list[str]:
    return _stream_packet_hashes(path, "v:0", "picture")


def _audio_packet_hashes(path: Path) -> list[str]:
    return _stream_packet_hashes(path, "a:0", "audio")


def _render_picture_youtube(
    *,
    score_schema: str,
    song: Path,
    title: str,
    intent: str,
    title_slug: str,
    master: Path,
    master_sidecar: Path,
    master_metadata: dict,
    master_duration: float,
    visual: dict,
    ffmpeg: str,
) -> tuple[Path, Path]:
    if visual.get("kind") != "picture-candidate":
        raise ValueError("YouTube v2 visual kind must be picture-candidate")
    picture_value = visual.get("path")
    if not isinstance(picture_value, str) or not picture_value or Path(picture_value).is_absolute():
        raise ValueError("YouTube v2 picture path must be song-relative")
    picture, picture_sidecar, picture_metadata = verify_picture(
        song, picture_value, require_keep=True
    )
    picture_master = picture_metadata["recipe"]["master"]
    master_relative = str(master.relative_to(song.resolve()))
    master_digest = sha256(master)
    if (
        picture_master.get("path") != master_relative
        or picture_master.get("sha256") != master_digest
    ):
        raise ValueError("YouTube v2 picture was not created against the approved master")
    media = picture_metadata["recipe"]["source_video"]["media"]
    video = media["video"]
    if video.get("codec") != "h264":
        raise ValueError("YouTube v2 stream-copy delivery requires an H.264 picture candidate")
    if video.get("pixel_format") != "yuv420p":
        raise ValueError("YouTube v2 stream-copy delivery requires yuv420p picture")
    if video.get("field_order") not in {None, "progressive"}:
        raise ValueError("YouTube v2 stream-copy delivery requires progressive picture")
    # Remotion's --color-space=bt709 currently writes the matrix tag but may
    # omit transfer/primaries tags. The assembler makes all three explicit on
    # the output while preserving the compressed picture packets.
    if video.get("color_space") != "bt709":
        raise ValueError("YouTube v2 stream-copy delivery requires BT.709 picture tags")
    if video["width"] % 2 or video["height"] % 2:
        raise ValueError("YouTube v2 picture dimensions must be even")
    picture_record = {
        "path": str(picture.relative_to(song.resolve())),
        "sha256": sha256(picture),
        "provenance_path": str(picture_sidecar.relative_to(song.resolve())),
        "provenance_sha256": sha256(picture_sidecar),
        "recipe_id": picture_metadata["recipe_id"],
        "review_decision": picture_metadata["review"]["decision"],
    }
    recipe = {
        "schema": score_schema,
        "title": title,
        "intent": intent,
        "master_path": master_relative,
        "master_sha256": master_digest,
        "master_recipe_id": master_metadata.get("recipe_id"),
        "visual": {
            "kind": "picture-candidate",
            **picture_record,
            "video_codec": video["codec"],
            "video_profile": video["profile"],
            "pixel_format": video["pixel_format"],
            "color_space": "bt709",
            "width": video["width"],
            "height": video["height"],
            "frame_rate": video["frame_rate"],
        },
        "assembly": {
            "picture": "stream-copy without re-encoding",
            "embedded_guide_audio": "discard",
            "approved_master": "encode once to AAC-LC",
            "audio_codec": "aac",
            "audio_sample_rate": 48_000,
            "audio_channels": 2,
            "audio_bitrate": "320k",
        },
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song / "video" / "youtube" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}-youtube.mp4"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    sidecar_temporary = sidecar.with_name(f".{sidecar.name}.partial")
    if destination.exists():
        existing_path, existing_sidecar, existing = verify_youtube_provenance(
            song, destination, require_approval=False
        )
        if existing.get("recipe_id") != recipe_id:
            raise FileExistsError(f"YouTube destination has different provenance: {destination}")
        return existing_path, existing_sidecar
    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.mp4"
    reference_audio = destination_dir / f".{recipe_id[:10]}-{title_slug}.reference.m4a"
    if temporary.exists() or reference_audio.exists() or sidecar_temporary.exists():
        raise FileExistsError(f"Incomplete YouTube picture assembly exists: {temporary}")
    command = [
        ffmpeg,
        "-nostdin", "-v", "error", "-n",
        "-i", str(picture),
        "-i", str(master),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "48000",
        "-ac", "2",
        "-t", f"{master_duration:.12g}",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-metadata", f"title={title}",
        str(temporary),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"YouTube picture assembler could not start: {exc}") from exc
    if completed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr[-5000:])
    reference_command = [
        ffmpeg,
        "-nostdin", "-v", "error", "-n",
        "-i", str(master),
        "-map", "0:a:0",
        "-vn",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "48000",
        "-ac", "2",
        "-t", f"{master_duration:.12g}",
        "-map_metadata", "-1",
        str(reference_audio),
    ]
    try:
        try:
            reference = subprocess.run(reference_command, capture_output=True, text=True)
        except OSError as exc:
            raise RuntimeError(f"YouTube master reference encoder could not start: {exc}") from exc
        if reference.returncode:
            raise RuntimeError(reference.stderr[-5000:])
        output_probe = probe(temporary)
        video_stream = next(
            (item for item in output_probe.get("streams", []) if item.get("codec_type") == "video"),
            {},
        )
        audio_stream = next(
            (item for item in output_probe.get("streams", []) if item.get("codec_type") == "audio"),
            {},
        )
        actual_duration = float(output_probe.get("format", {}).get("duration") or 0)
        source_packets = _video_packet_hashes(picture)
        output_packets = _video_packet_hashes(temporary)
        reference_audio_packets = _audio_packet_hashes(reference_audio)
        output_audio_packets = _audio_packet_hashes(temporary)
        fps = float(video["frame_rate_decimal"])
        verification = {
            "container_mp4": "mp4" in str(output_probe.get("format", {}).get("format_name", "")),
            "video_stream_copy": bool(output_packets) and source_packets[:len(output_packets)] == output_packets,
            "video_codec_preserved": video_stream.get("codec_name") == video["codec"],
            "video_profile_preserved": video_stream.get("profile") == video["profile"],
            "progressive": video_stream.get("field_order") in {None, "progressive"},
            "dimensions_preserved": (
                video_stream.get("width") == video["width"]
                and video_stream.get("height") == video["height"]
            ),
            "pixel_format_preserved": video_stream.get("pix_fmt") == video["pixel_format"],
            "color_bt709": video_stream.get("color_space") == "bt709",
            "frame_rate_preserved": (
                video_stream.get("avg_frame_rate") == video["frame_rate"]
                or video_stream.get("r_frame_rate") == video["frame_rate"]
            ),
            "embedded_guide_audio_discarded": (
                bool(output_audio_packets) and output_audio_packets == reference_audio_packets
            ),
            "approved_master_encoded_aac": (
                audio_stream.get("codec_name") == "aac"
                and output_audio_packets == reference_audio_packets
            ),
            "audio_48khz": audio_stream.get("sample_rate") == "48000",
            "audio_stereo": audio_stream.get("channels") == 2,
            "duration_matches_master": abs(actual_duration - master_duration) <= max(0.1, 1 / fps + 0.02),
            "fast_start": _fast_start(temporary),
        }
        failed = [name for name, passed in verification.items() if not passed]
        if failed:
            raise RuntimeError(f"YouTube picture assembly failed verification: {', '.join(failed)}")
        temporary.rename(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        reference_audio.unlink(missing_ok=True)
    metadata = {
        "schema": "eprs.youtube-render/v2",
        "recipe_id": recipe_id,
        "rendered_at": utc_now(),
        "title": title,
        "intent": intent,
        "recipe": recipe,
        "master": {
            "path": master_relative,
            "sha256": master_digest,
            "provenance_path": str(master_sidecar.relative_to(song.resolve())),
            "provenance_sha256": sha256(master_sidecar),
            "approval": master_metadata["approval"],
        },
        "picture": picture_record,
        "output": {
            "path": str(destination.relative_to(song)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "video_packet_count": len(output_packets),
            "source_video_packet_count": len(source_packets),
            "audio_packet_count": len(output_audio_packets),
        },
        "verification": verification,
        "approval": {
            "technical_render": "passed",
            "visual_and_sync_review": "not recorded by renderer",
            "review_notes": [],
            "promotion_to_FINAL": "not performed",
        },
        "publication": {"uploaded": False, "published": False, "platform_id": None},
    }
    try:
        sidecar_temporary.write_text(json.dumps(metadata, indent=2) + "\n")
        sidecar_temporary.replace(sidecar)
    except Exception:
        sidecar_temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise
    return destination, sidecar


def render_youtube(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Assemble a verified title-card or reviewed-picture MP4 from an approved master."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required for YouTube rendering")
    song_path = Path(song)
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid YouTube JSON: {spec_path}: {exc.msg}") from exc
    score_schema = score.get("schema")
    if score_schema not in {YOUTUBE_SCHEMA, YOUTUBE_PICTURE_SCHEMA}:
        raise ValueError(f"unsupported YouTube schema: {score.get('schema')}")
    title = score.get("title")
    intent = score.get("intent")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("YouTube video requires a title")
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError("YouTube video requires visual and delivery intent")
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("YouTube title must contain at least one letter or number")
    master_value = score.get("master")
    if not isinstance(master_value, str) or not master_value:
        raise ValueError("YouTube video requires an approved master path")
    master_path, master_sidecar, master_metadata = verify_master_provenance(
        song_path,
        master_value,
        require_approval=True,
    )
    master_probe = master_metadata["output"]["probe"]
    master_duration = float(master_probe.get("format", {}).get("duration", 0))
    if master_duration <= 0:
        raise ValueError("approved master duration is unavailable")

    visual = score.get("visual", {})
    if not isinstance(visual, dict):
        raise ValueError("YouTube visual must be an object")
    if score_schema == YOUTUBE_PICTURE_SCHEMA:
        return _render_picture_youtube(
            score_schema=score_schema,
            song=song_path.resolve(),
            title=title,
            intent=intent,
            title_slug=title_slug,
            master=master_path,
            master_sidecar=master_sidecar,
            master_metadata=master_metadata,
            master_duration=master_duration,
            visual=visual,
            ffmpeg=ffmpeg,
        )
    if visual.get("kind", "title-card") != "title-card":
        raise ValueError("YouTube v1 visual kind must be title-card")
    background = _color(visual.get("background_color", "15151a"), "background_color")
    text_color = _color(visual.get("text_color", "ffffff"), "text_color")
    output = score.get("output", {})
    if not isinstance(output, dict):
        raise ValueError("YouTube output must be an object")
    width = _integer(output, "width", 1920, 640, 3840)
    height = _integer(output, "height", 1080, 360, 2160)
    fps = _integer(output, "fps", 30, 24, 60)
    if width % 2 or height % 2:
        raise ValueError("YouTube width and height must be even for yuv420p")
    font_size = _integer(visual, "font_size", max(36, round(height / 15)), 24, 240)

    master_relative = str(master_path.relative_to(song_path.resolve()))
    master_digest = sha256(master_path)
    recipe = {
        "schema": YOUTUBE_SCHEMA,
        "title": title,
        "intent": intent,
        "master_path": master_relative,
        "master_sha256": master_digest,
        "master_recipe_id": master_metadata.get("recipe_id"),
        "visual": {
            "kind": "title-card",
            "background_color": background,
            "text_color": text_color,
            "font_size": font_size,
        },
        "output": {
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": "h264",
            "video_profile": "high",
            "pixel_format": "yuv420p",
            "color_space": "bt709",
            "audio_codec": "aac",
            "audio_sample_rate": 48_000,
            "audio_channels": 2,
            "audio_bitrate": "320k",
        },
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination_dir = song_path / "video" / "youtube" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}-youtube.mp4"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"YouTube video exists without provenance sidecar: {destination}")
        try:
            existing = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise FileExistsError(f"YouTube video has invalid provenance: {sidecar}: {exc.msg}") from exc
        existing_output = existing.get("output", {})
        if existing.get("recipe_id") == recipe_id and existing_output.get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"YouTube destination exists with different provenance: {destination}")

    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.mp4"
    title_file = destination_dir / f".{recipe_id[:10]}-{title_slug}.title.txt"
    if temporary.exists() or title_file.exists():
        raise FileExistsError("Incomplete YouTube render artifacts already exist")
    title_file.write_text(title, encoding="utf-8")
    text_path = _filter_path(title_file.resolve())
    font_option = ""
    for candidate_font in [
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]:
        if candidate_font.is_file():
            font_option = f":fontfile='{_filter_path(candidate_font)}'"
            break
    video_filter = (
        f"drawtext=textfile='{text_path}'{font_option}:fontcolor=0x{text_color}:"
        f"fontsize={font_size}:x=(w-text_w)/2:y=(h-text_h)/2,"
        "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
    )
    command = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-n",
        "-f", "lavfi",
        "-i", f"color=c=0x{background}:s={width}x{height}:r={fps}",
        "-i", str(master_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", video_filter,
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-r", str(fps),
        "-g", str(max(1, fps // 2)),
        "-b:v", "8M",
        "-maxrate", "8M",
        "-bufsize", "16M",
        "-c:a", "aac",
        "-b:a", "320k",
        "-ar", "48000",
        "-ac", "2",
        "-t", f"{master_duration:.12g}",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-metadata", f"title={title}",
        str(temporary),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"YouTube renderer could not start: {exc}") from exc
    finally:
        title_file.unlink(missing_ok=True)
    if completed.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr[-5000:])

    output_probe = probe(temporary)
    video_stream = next(
        (stream for stream in output_probe.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    audio_stream = next(
        (stream for stream in output_probe.get("streams", []) if stream.get("codec_type") == "audio"),
        {},
    )
    actual_duration = float(output_probe.get("format", {}).get("duration", 0))
    verification = {
        "container_mp4": "mp4" in str(output_probe.get("format", {}).get("format_name", "")),
        "video_h264": video_stream.get("codec_name") == "h264",
        "video_high_profile": str(video_stream.get("profile", "")).lower() == "high",
        "progressive": video_stream.get("field_order") in {None, "progressive"},
        "dimensions": video_stream.get("width") == width and video_stream.get("height") == height,
        "pixel_format_yuv420p": video_stream.get("pix_fmt") == "yuv420p",
        "color_bt709": all(
            video_stream.get(key) == "bt709"
            for key in ("color_space", "color_transfer", "color_primaries")
        ),
        "frame_rate": video_stream.get("r_frame_rate") == f"{fps}/1",
        "audio_aac": audio_stream.get("codec_name") == "aac",
        "audio_48khz": audio_stream.get("sample_rate") == "48000",
        "audio_stereo": audio_stream.get("channels") == 2,
        "duration_matches_master": abs(actual_duration - master_duration) <= max(0.1, 1 / fps + 0.02),
        "fast_start": _fast_start(temporary),
    }
    failed = [name for name, passed in verification.items() if not passed]
    if failed:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"YouTube render failed verification: {', '.join(failed)}")
    temporary.rename(destination)
    metadata = {
        "schema": "eprs.youtube-render/v1",
        "recipe_id": recipe_id,
        "rendered_at": utc_now(),
        "title": title,
        "intent": intent,
        "recipe": recipe,
        "master": {
            "path": master_relative,
            "sha256": master_digest,
            "provenance_path": str(master_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": sha256(master_sidecar),
            "approval": master_metadata["approval"],
        },
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
        },
        "verification": verification,
        "approval": {
            "technical_render": "passed",
            "visual_and_sync_review": "not recorded by renderer",
            "review_notes": [],
            "promotion_to_FINAL": "not performed",
        },
        "publication": {
            "uploaded": False,
            "published": False,
            "platform_id": None,
        },
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar


def approve_youtube_video(
    song: str | Path,
    video: str | Path,
    review_note: str,
) -> Path:
    """Record full picture/sync review without promotion or publication."""
    note = review_note.strip()
    if not note:
        raise ValueError("YouTube approval requires a visual and sync review note")
    _, sidecar, metadata = verify_youtube_provenance(song, video, require_approval=False)
    approval = metadata.setdefault("approval", {})
    notes = approval.setdefault("review_notes", [])
    if not isinstance(notes, list):
        raise ValueError("YouTube approval review_notes must be a list")
    if any(isinstance(item, dict) and item.get("note") == note for item in notes):
        return sidecar
    notes.append({"approved_at": utc_now(), "note": note})
    approval["visual_and_sync_review"] = "approved"
    approval["promotion_to_FINAL"] = "not performed"
    metadata["publication"] = {
        "uploaded": False,
        "published": False,
        "platform_id": None,
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return sidecar


def verify_youtube_provenance(
    song: str | Path,
    video: str | Path,
    *,
    require_approval: bool = True,
) -> tuple[Path, Path, dict]:
    """Verify a rendered YouTube file, its approved master, and review state."""
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(video)
    video_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        video_path.relative_to((song_path / "video").resolve())
    except ValueError as exc:
        raise ValueError("approved YouTube video must be inside the song video directory") from exc
    if not video_path.is_file():
        raise FileNotFoundError(video_path)
    sidecar = video_path.with_suffix(video_path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"YouTube provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid YouTube provenance JSON: {sidecar}: {exc.msg}") from exc
    schema = metadata.get("schema")
    if schema not in YOUTUBE_RENDER_SCHEMAS:
        raise ValueError("unsupported YouTube provenance schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("YouTube recipe provenance is invalid")
    expected_recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("recipe_id") != expected_recipe_id:
        raise ValueError("YouTube recipe id does not match its recipe")
    output = metadata.get("output")
    if (
        not isinstance(output, dict)
        or output.get("path") != str(video_path.relative_to(song_path.resolve()))
        or output.get("sha256") != sha256(video_path)
    ):
        raise ValueError("YouTube video checksum has changed; approval was not recorded")
    verification = metadata.get("verification")
    if not isinstance(verification, dict) or not verification or not all(verification.values()):
        raise ValueError("YouTube technical verification is incomplete")
    master = metadata.get("master", {})
    master_path, master_sidecar, master_metadata = verify_master_provenance(
        song_path,
        master.get("path", ""),
        require_approval=True,
    )
    if master.get("sha256") != sha256(master_path) or master.get("provenance_sha256") != sha256(master_sidecar):
        raise ValueError("YouTube master provenance has changed")
    if (
        recipe.get("master_path") != str(master_path.relative_to(song_path.resolve()))
        or recipe.get("master_sha256") != sha256(master_path)
        or recipe.get("master_recipe_id") != master_metadata.get("recipe_id")
    ):
        raise ValueError("YouTube recipe no longer matches its approved master")
    if schema == "eprs.youtube-render/v2":
        if recipe.get("schema") != YOUTUBE_PICTURE_SCHEMA:
            raise ValueError("YouTube v2 render has an invalid assembly recipe")
        picture_record = metadata.get("picture")
        visual = recipe.get("visual")
        if not isinstance(picture_record, dict) or not isinstance(visual, dict):
            raise ValueError("YouTube v2 picture evidence is invalid")
        picture_path, picture_sidecar, picture_metadata = verify_picture(
            song_path, picture_record.get("path", ""), require_keep=True
        )
        expected_picture = {
            "path": str(picture_path.relative_to(song_path.resolve())),
            "sha256": sha256(picture_path),
            "provenance_path": str(picture_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": sha256(picture_sidecar),
            "recipe_id": picture_metadata["recipe_id"],
            "review_decision": picture_metadata["review"]["decision"],
        }
        picture_video = picture_metadata["recipe"]["source_video"]["media"]["video"]
        expected_visual = {
            "kind": "picture-candidate",
            **expected_picture,
            "video_codec": picture_video["codec"],
            "video_profile": picture_video["profile"],
            "pixel_format": picture_video["pixel_format"],
            "color_space": "bt709",
            "width": picture_video["width"],
            "height": picture_video["height"],
            "frame_rate": picture_video["frame_rate"],
        }
        if picture_record != expected_picture or visual != expected_visual:
            raise ValueError("YouTube v2 picture provenance has changed")
        if picture_metadata["recipe"]["master"] != {
            "path": str(master_path.relative_to(song_path.resolve())),
            "sha256": sha256(master_path),
            "provenance_path": str(master_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": sha256(master_sidecar),
            "recipe_id": master_metadata.get("recipe_id"),
            "duration_seconds": float(
                master_metadata.get("output", {})
                .get("probe", {}).get("format", {}).get("duration") or 0
            ),
        }:
            raise ValueError("YouTube v2 picture is no longer bound to the approved master")
        if recipe.get("assembly") != {
            "picture": "stream-copy without re-encoding",
            "embedded_guide_audio": "discard",
            "approved_master": "encode once to AAC-LC",
            "audio_codec": "aac",
            "audio_sample_rate": 48_000,
            "audio_channels": 2,
            "audio_bitrate": "320k",
        }:
            raise ValueError("YouTube v2 assembly policy has changed")
    approval = metadata.get("approval")
    if require_approval and (
        not isinstance(approval, dict)
        or approval.get("visual_and_sync_review") != "approved"
    ):
        raise ValueError("YouTube video requires complete visual and sync approval")
    publication = metadata.get("publication")
    if (
        not isinstance(publication, dict)
        or publication.get("uploaded") is not False
        or publication.get("published") is not False
        or publication.get("platform_id") is not None
    ):
        raise ValueError("YouTube local render publication state has changed")
    return video_path, sidecar, metadata
