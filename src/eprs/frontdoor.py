"""Stable, top-sorted pointers to the media a person should review now."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .system import load_song_manifest, sha256, utc_now


CURRENT_SCHEMA = "eprs.current-media/v1"
AUDIO_SUFFIXES = {".wav", ".flac", ".aif", ".aiff", ".mp3", ".m4a", ".ogg"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}


def _source(song: Path, value: str | Path, kind: str) -> Path:
    requested = Path(value)
    source = requested.resolve() if requested.is_absolute() else (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"current {kind} must be inside the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    allowed = AUDIO_SUFFIXES if kind == "audio" else VIDEO_SUFFIXES
    if source.suffix.lower() not in allowed:
        raise ValueError(f"current {kind} has an unsupported extension: {source.suffix}")
    return source


def _replace_link(song: Path, name: str, source: Path) -> Path:
    destination = song / name
    if destination.exists() and not destination.is_symlink():
        raise FileExistsError(f"refusing to replace non-link song front-door file: {destination}")
    temporary = song / f".{name}.partial"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    os.symlink(os.path.relpath(source, song), temporary)
    temporary.replace(destination)
    return destination


def _remove_previous_link(song: Path, record: dict, kind: str) -> None:
    value = record.get("pointers", {}).get(kind)
    if not isinstance(value, str):
        return
    path = song / value
    if path.is_symlink():
        path.unlink()


def expose_current_media(
    song: str | Path,
    audio: str | Path,
    *,
    video: str | Path | None = None,
    label: str,
    status: str = "review",
    note: str = "",
) -> Path:
    """Expose current media at song root while preserving canonical files below."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    if not isinstance(label, str) or not label.strip():
        raise ValueError("current media requires a label")
    if status not in {"diagnostic", "review", "approved"}:
        raise ValueError("current media status must be diagnostic, review, or approved")
    audio_source = _source(song_path, audio, "audio")
    video_source = _source(song_path, video, "video") if video is not None else None
    record_path = song_path / "_CURRENT.json"
    previous = {}
    if record_path.is_file():
        try:
            previous = json.loads(record_path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid current-media record: {record_path}: {exc.msg}") from exc
        if previous.get("schema") != CURRENT_SCHEMA:
            raise ValueError("refusing to replace an unsupported _CURRENT.json")

    audio_name = f"_LISTEN{audio_source.suffix.lower()}"
    video_name = f"_WATCH{video_source.suffix.lower()}" if video_source else None
    for kind, next_name in (("audio", audio_name), ("video", video_name)):
        old_name = previous.get("pointers", {}).get(kind)
        if isinstance(old_name, str) and old_name != next_name:
            _remove_previous_link(song_path, previous, kind)
    audio_link = _replace_link(song_path, audio_name, audio_source)
    video_link = _replace_link(song_path, video_name, video_source) if video_source and video_name else None
    if video_source is None:
        _remove_previous_link(song_path, previous, "video")

    source_record = {
        "audio": {
            "path": str(audio_source.relative_to(song_path)),
            "sha256": sha256(audio_source),
        },
        "video": (
            {"path": str(video_source.relative_to(song_path)), "sha256": sha256(video_source)}
            if video_source else None
        ),
    }
    record = {
        "schema": CURRENT_SCHEMA,
        "updated_at": utc_now(),
        "label": label.strip(),
        "status": status,
        "note": note.strip(),
        "pointers": {"audio": audio_link.name, "video": video_link.name if video_link else None},
        "sources": source_record,
    }
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    watch_line = f"- Watch: `{video_link.name}`\n" if video_link else "- Watch: not available for this version\n"
    caution = {
        "diagnostic": "This is a diagnostic starter, not a source-aware arrangement or approval.",
        "review": "This version needs a complete human listen/watch and a specific change note.",
        "approved": "This points to approved local media; platform submission remains separate.",
    }[status]
    (song_path / "_CHANGE_ME.md").write_text(
        f"# Change this version\n\n{label.strip()}\n\n"
        f"- Listen: `{audio_link.name}`\n{watch_line}"
        f"- Canonical audio: `{source_record['audio']['path']}`\n"
        + (f"- Canonical video: `{source_record['video']['path']}`\n" if source_record["video"] else "")
        + f"- State: **{status}**\n\n{caution}\n\n"
        "Point an agent at this song directory or `_CHANGE_ME.md`, describe what you hear/see, "
        "and ask it to preserve the old version while exposing the revision here.\n"
    )
    return record_path


def verify_current_media(song: str | Path, *, verify_checksums: bool = True) -> tuple[Path, dict]:
    """Verify root pointers still resolve to the exact recorded canonical media."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    record_path = song_path / "_CURRENT.json"
    if not record_path.is_file():
        raise FileNotFoundError(record_path)
    try:
        record = json.loads(record_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid current-media record: {record_path}: {exc.msg}") from exc
    if record.get("schema") != CURRENT_SCHEMA:
        raise ValueError("unsupported current-media schema")
    pointers = record.get("pointers")
    sources = record.get("sources")
    if not isinstance(pointers, dict) or not isinstance(sources, dict):
        raise ValueError("current-media pointers and sources must be objects")
    for kind in ("audio", "video"):
        pointer_value = pointers.get(kind)
        source_record = sources.get(kind)
        if pointer_value is None and source_record is None and kind == "video":
            continue
        if not isinstance(pointer_value, str) or not isinstance(source_record, dict):
            raise ValueError(f"current-media {kind} pointer/source is incomplete")
        pointer = song_path / pointer_value
        source_value = source_record.get("path")
        if not pointer.is_symlink() or not isinstance(source_value, str):
            raise ValueError(f"current-media {kind} must use a recorded root symlink")
        source = (song_path / source_value).resolve()
        try:
            source.relative_to(song_path)
        except ValueError as exc:
            raise ValueError(f"current-media {kind} source escapes the song") from exc
        if not source.is_file() or pointer.resolve() != source:
            raise ValueError(f"current-media {kind} pointer is missing or targets the wrong file")
        if verify_checksums and source_record.get("sha256") != sha256(source):
            raise ValueError(f"current-media {kind} source checksum changed")
    return record_path, record
