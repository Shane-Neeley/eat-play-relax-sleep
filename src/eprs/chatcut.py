"""Prepare a disposable, reviewable ChatCut handoff without remote side effects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from .system import sha256, utc_now


CHATCUT_HANDOFF_SCHEMA = "eprs.chatcut-handoff/v1"
CHATCUT_DOCS_URL = "https://chatcut.io/docs/agent-plugin"
CHATCUT_PLUGIN_URL = "https://github.com/ChatCut-Inc/agent-plugin"
MAX_SECONDS = 600
RESOLUTION_LIMITS = {
    480: (854, 480),
    720: (1280, 720),
    1080: (1920, 1080),
}


def _song_path(value: str | Path) -> Path:
    song = Path(value).expanduser().resolve()
    if not song.is_dir() or not (song / "song.json").is_file():
        raise ValueError(f"ChatCut handoff requires an EPRS song workspace: {song}")
    return song


def _song_relative_input(song: Path, value: str | Path, label: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = song / candidate
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(song)
    except ValueError as exc:
        raise ValueError(f"ChatCut {label} must remain inside the song workspace") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    if "raw" in {part.lower() for part in relative.parts}:
        raise ValueError(f"ChatCut refuses immutable raw material: {relative}")
    return candidate


def _require_tool(name: str) -> str:
    located = shutil.which(name)
    if located is None:
        raise RuntimeError(f"ChatCut handoff requires {name}")
    return located


def _run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"media derivative failed: {detail or 'unknown FFmpeg error'}")


def _safe_prompt(prompt: str | None) -> str:
    if prompt is not None and not prompt.strip():
        raise ValueError("ChatCut prompt cannot be blank")
    return (prompt or "").strip() or (
        "Create an editable visual draft from the supplied disposable preview only. "
        "Keep the music audible and preserve its structure: identity, withheld pocket, "
        "contrast, hook, and turnaround. Use restrained captions and motion that respond "
        "to the musical sections. Do not add faces, stock footage, logos, or invented "
        "animal/documentary claims. Return an editable timeline and a clearly labeled "
        "visual candidate for local EPRS review."
    )


def _asset_record(song: Path, path: Path, role: str, media_type: str) -> dict:
    return {
        "role": role,
        "type": media_type,
        "path": str(path.relative_to(song)),
        "sha256": sha256(path),
        "source_of_truth": False,
    }


def _write_readme(destination: Path, record: dict) -> None:
    lines = [
        "# ChatCut disposable visual handoff",
        "",
        "This package is a local derivative for an optional ChatCut visual-editing pass.",
        "It is not a master, a release package, a provenance source of truth, or a "
        "publication approval.",
        "",
        "## Before using ChatCut",
        "",
        "1. Inspect `handoff.json` and watch `assets/preview-video.mp4` end to end.",
        "2. Confirm the exact prompt below; ChatCut submissions may be paid and upload the listed assets.",
        "3. If using the official Codex surface, authenticate it manually through the ChatCut MCP plugin.",
        "4. Pass only the files listed in `submission.assets`; do not add the EPRS repo, raw takes, masters, credentials, or private recordings.",
        "5. Treat any returned render as an untrusted picture candidate. Verify it locally, then cross the normal EPRS picture-review and YouTube assembly gates.",
        "",
        "## Exact prompt",
        "",
        "```text",
        record["submission"]["prompt"],
        "```",
        "",
        "## Boundary",
        "",
        "- Remote authentication and upload were not performed by EPRS.",
        "- EPRS masters, provenance, rights records, mastering, and YouTube publishing stay local.",
        "- This package contains derived preview media, not the original master bytes.",
        "",
        f"Upstream docs: {CHATCUT_DOCS_URL}",
        f"Upstream plugin repository: {CHATCUT_PLUGIN_URL}",
    ]
    (destination / "README.md").write_text("\n".join(lines) + "\n")


def prepare_chatcut_handoff(
    song: str | Path,
    *,
    video: str | Path,
    audio: str | Path | None = None,
    captions: str | Path | None = None,
    thumbnail: str | Path | None = None,
    prompt: str | None = None,
    seconds: int = 30,
    resolution: int = 720,
    out: str | Path | None = None,
) -> dict:
    """Create local derivatives and a ChatCut asset/prompt manifest.

    This function intentionally has no ChatCut client, network call, login flow,
    upload option, or publication path. A person must operate the remote editor.
    """
    song_path = _song_path(song)
    if not isinstance(seconds, int) or not 1 <= seconds <= MAX_SECONDS:
        raise ValueError(f"ChatCut seconds must be an integer from 1 to {MAX_SECONDS}")
    if resolution not in RESOLUTION_LIMITS:
        raise ValueError("ChatCut resolution must be 480, 720, or 1080")
    video_path = _song_relative_input(song_path, video, "video")
    audio_path = _song_relative_input(song_path, audio, "audio") if audio else None
    captions_path = _song_relative_input(song_path, captions, "captions") if captions else None
    thumbnail_path = _song_relative_input(song_path, thumbnail, "thumbnail") if thumbnail else None
    prompt_text = _safe_prompt(prompt)

    source_fingerprint = {
        "video": {"path": str(video_path.relative_to(song_path)), "sha256": sha256(video_path)},
        "audio": ({"path": str(audio_path.relative_to(song_path)), "sha256": sha256(audio_path)}
                  if audio_path else None),
        "captions": ({"path": str(captions_path.relative_to(song_path)), "sha256": sha256(captions_path)}
                     if captions_path else None),
        "thumbnail": ({"path": str(thumbnail_path.relative_to(song_path)), "sha256": sha256(thumbnail_path)}
                      if thumbnail_path else None),
        "seconds": seconds,
        "resolution": resolution,
        "prompt": prompt_text,
    }
    package_id = hashlib.sha256(
        json.dumps(source_fingerprint, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    if out is None:
        destination = song_path / "chatcut" / f"disposable-preview-{package_id}"
    else:
        destination = Path(out).expanduser()
        if not destination.is_absolute():
            destination = song_path / destination
        destination = destination.resolve()
        try:
            destination.relative_to(song_path)
        except ValueError as exc:
            raise ValueError("ChatCut output must remain inside the song workspace") from exc
    if destination.exists():
        raise FileExistsError(f"ChatCut handoff already exists: {destination}")
    destination.mkdir(parents=True)
    assets_dir = destination / "assets"
    assets_dir.mkdir()

    ffmpeg = _require_tool("ffmpeg")
    width, height = RESOLUTION_LIMITS[resolution]
    preview = assets_dir / "preview-video.mp4"
    command = [ffmpeg, "-y", "-v", "error", "-i", str(video_path)]
    if audio_path:
        command.extend(["-i", str(audio_path)])
    command.extend(["-t", str(seconds), "-map", "0:v:0"])
    if audio_path:
        command.extend(["-map", "1:a:0"])
    else:
        command.extend(["-map", "0:a:0?"])
    command.extend([
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart", "-shortest", str(preview),
    ])
    _run(command)

    guide_audio: Path | None = None
    if audio_path:
        guide_audio = assets_dir / "guide-audio.m4a"
        _run([
            ffmpeg, "-y", "-v", "error", "-i", str(audio_path), "-t", str(seconds),
            "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
            str(guide_audio),
        ])

    copied_assets: list[dict] = [
        _asset_record(song_path, preview, "disposable_music_video_preview", "video"),
    ]
    if guide_audio:
        copied_assets.append(_asset_record(song_path, guide_audio, "disposable_guide_audio", "audio"))
    if captions_path:
        target = assets_dir / f"captions{captions_path.suffix.lower() or '.txt'}"
        shutil.copy2(captions_path, target)
        copied_assets.append(_asset_record(song_path, target, "captions", "text"))
    if thumbnail_path:
        target = assets_dir / f"thumbnail{thumbnail_path.suffix.lower() or '.png'}"
        shutil.copy2(thumbnail_path, target)
        copied_assets.append(_asset_record(song_path, target, "thumbnail", "image"))

    record = {
        "schema": CHATCUT_HANDOFF_SCHEMA,
        "handoff_id": package_id,
        "created_at": utc_now(),
        "song": {"name": song_path.name},
        "source_inputs": source_fingerprint,
        "derived_assets": copied_assets,
        "submission": {
            "surface": "chatcut-codex-mcp",
            "prompt": prompt_text,
            "assets": [
                {"path": item["path"], "type": item["type"], "role": item["role"]}
                for item in copied_assets
            ],
            "upload_performed": False,
            "requires_explicit_user_operation": True,
        },
        "authority": {
            "software_installed": False,
            "application_started": False,
            "remote_authenticated": False,
            "remote_upload": False,
            "media_changed": False,
            "creative_approval": False,
            "publication_authorized": False,
        },
        "safety": {
            "disposable_derivatives_only": True,
            "local_master_preserved": True,
            "raw_material_rejected": True,
            "publication_stays_local": True,
        },
    }
    manifest = destination / "handoff.json"
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    _write_readme(destination, record)
    return {
        "package": str(destination),
        "manifest": str(manifest),
        "assets": [item["path"] for item in copied_assets],
        "upload_performed": False,
        "publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    """Standalone wrapper for operators who do not use the eprs entrypoint."""
    import argparse

    parser = argparse.ArgumentParser(description="Prepare a local ChatCut handoff")
    parser.add_argument("song")
    parser.add_argument("--video", required=True)
    parser.add_argument("--audio")
    parser.add_argument("--captions")
    parser.add_argument("--thumbnail")
    parser.add_argument("--prompt")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--resolution", type=int, choices=sorted(RESOLUTION_LIMITS), default=720)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    print(json.dumps(prepare_chatcut_handoff(
        args.song,
        video=args.video,
        audio=args.audio,
        captions=args.captions,
        thumbnail=args.thumbnail,
        prompt=args.prompt,
        seconds=args.seconds,
        resolution=args.resolution,
        out=args.out,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
