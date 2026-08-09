"""Reviewed, checksum-bound upload assets for one approved YouTube video."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil

from .delivery import verify_youtube_provenance
from .system import load_song_manifest, probe, sha256, slugify, utc_now


YOUTUBE_ASSETS_SCHEMA = "eprs.youtube-assets/v1"
YOUTUBE_ASSET_BUNDLE_SCHEMA = "eprs.youtube-assets-bundle/v1"
LANGUAGE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
MAX_CAPTION_TRACKS = 20
MAX_CUES = 10_000
MAX_THUMBNAIL_BYTES = 50_000_000
PLATFORM_CONTRACT = {
    "checked_on": "2026-08-03",
    "thumbnail_help": "https://support.google.com/youtube/answer/72431",
    "caption_help": "https://support.google.com/youtube/answer/2734698",
    "chapter_help": "https://support.google.com/youtube/answer/9884579",
    "caption_format": "SubRip plain UTF-8",
    "chapter_rules": "first 00:00; at least three; ascending; minimum 10 seconds",
}


@contextmanager
def _review_lock(path: Path):
    lock = path.parent / ".youtube-assets-review.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(
            f"YouTube asset review is locked by another process: {lock}"
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} created_at={utc_now()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _text(record: dict, key: str, label: str, maximum: int = 8192) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"YouTube assets {label} requires {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"YouTube assets {label} {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _portable_path(song: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"YouTube assets {label} requires a song-relative path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"YouTube assets {label} path must be relative to the song")
    path = (song / requested).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"YouTube assets {label} path escapes the song") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"YouTube assets {label} must be a finite non-negative number")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"YouTube assets {label} must be a finite non-negative number")
    return result


def _video_duration(metadata: dict) -> float:
    value = metadata.get("output", {}).get("probe", {}).get("format", {}).get("duration")
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("YouTube assets approved video duration is unavailable") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("YouTube assets approved video duration is unavailable")
    return duration


def _thumbnail(song: Path, value: object) -> tuple[dict, Path, dict]:
    if not isinstance(value, dict):
        raise ValueError("YouTube assets thumbnail must be an object")
    path = _portable_path(song, value.get("path"), "thumbnail")
    suffix = path.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError("YouTube assets thumbnail must be JPG, PNG, or GIF")
    alt_text = _text(value, "alt_text", "thumbnail", 2048)
    review_question = _text(value, "review_question", "thumbnail", 2048)
    media_probe = probe(path)
    if media_probe.get("error"):
        raise ValueError(f"YouTube assets thumbnail is unreadable: {media_probe['error']}")
    stream = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "video"),
        {},
    )
    width = stream.get("width")
    height = stream.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("YouTube assets thumbnail dimensions are unavailable")
    size = path.stat().st_size
    if size > MAX_THUMBNAIL_BYTES:
        raise ValueError("YouTube assets thumbnail exceeds YouTube's 50 MB desktop limit")
    aspect = width / height
    checks = {
        "supported_image_format": suffix in IMAGE_SUFFIXES,
        "minimum_width_640": width >= 640,
        "aspect_ratio_16_9": abs(aspect - 16 / 9) <= 0.02,
        "desktop_size_limit": size <= MAX_THUMBNAIL_BYTES,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(
            "YouTube assets thumbnail fails platform checks: " + ", ".join(failed)
        )
    normalized = {
        "source": {
            "path": str(path.relative_to(song.resolve())),
            "sha256": sha256(path),
            "size_bytes": size,
        },
        "alt_text": alt_text,
        "review_question": review_question,
        "width": width,
        "height": height,
        "format": suffix.lstrip("."),
        "platform_checks": checks,
        "mobile_size_compatible": size <= 2_000_000,
    }
    return normalized, path, media_probe


def _captions(value: object, duration: float) -> list[dict]:
    if not isinstance(value, list) or not value or len(value) > MAX_CAPTION_TRACKS:
        raise ValueError(
            f"YouTube assets captions must contain 1 to {MAX_CAPTION_TRACKS} tracks"
        )
    tracks = []
    languages: set[str] = set()
    for track_index, track in enumerate(value, start=1):
        if not isinstance(track, dict):
            raise ValueError(f"YouTube assets caption track {track_index} must be an object")
        language = _text(track, "language", f"caption track {track_index}", 64)
        if not LANGUAGE.fullmatch(language):
            raise ValueError(f"YouTube assets caption language is invalid: {language}")
        language_key = language.casefold()
        if language_key in languages:
            raise ValueError(f"YouTube assets caption language is duplicated: {language}")
        languages.add(language_key)
        cues = track.get("cues")
        if not isinstance(cues, list) or not cues or len(cues) > MAX_CUES:
            raise ValueError(
                f"YouTube assets caption track {language} must contain 1 to {MAX_CUES} cues"
            )
        normalized_cues = []
        previous_end = 0.0
        for cue_index, cue in enumerate(cues, start=1):
            if not isinstance(cue, dict):
                raise ValueError(
                    f"YouTube assets caption {language} cue {cue_index} must be an object"
                )
            start = _number(cue.get("start_seconds"), f"caption {language} cue {cue_index} start_seconds")
            end = _number(cue.get("end_seconds"), f"caption {language} cue {cue_index} end_seconds")
            if end <= start:
                raise ValueError(f"YouTube assets caption {language} cue {cue_index} must end after it starts")
            if start < previous_end - 0.0005:
                raise ValueError(f"YouTube assets caption {language} cues must not overlap")
            if end > duration + 0.050:
                raise ValueError(f"YouTube assets caption {language} cue exceeds video duration")
            cue_text = _text(cue, "text", f"caption {language} cue {cue_index}", 8192)
            if "\r" in cue_text or "\n\n" in cue_text or "-->" in cue_text:
                raise ValueError(f"YouTube assets caption {language} cue contains unsafe SRT text")
            normalized_cues.append({
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "text": cue_text,
            })
            previous_end = end
        tracks.append({
            "language": language,
            "label": _text(track, "label", f"caption track {language}", 256),
            "completeness_note": _text(
                track, "completeness_note", f"caption track {language}", 2048
            ),
            "cues": normalized_cues,
        })
    return tracks


def _chapters(value: object, duration: float) -> list[dict]:
    if not isinstance(value, list) or len(value) < 3 or len(value) > 100:
        raise ValueError("YouTube assets chapters must contain 3 to 100 entries")
    result = []
    previous = None
    for index, chapter in enumerate(value, start=1):
        if not isinstance(chapter, dict):
            raise ValueError(f"YouTube assets chapter {index} must be an object")
        start_value = chapter.get("start_seconds")
        if isinstance(start_value, bool) or not isinstance(start_value, int) or start_value < 0:
            raise ValueError(f"YouTube assets chapter {index} start_seconds must be a non-negative integer")
        if index == 1 and start_value != 0:
            raise ValueError("YouTube assets first chapter must start at 00:00")
        if previous is not None and start_value - previous < 10:
            raise ValueError("YouTube assets chapters must be ascending and at least 10 seconds long")
        if start_value >= duration:
            raise ValueError(f"YouTube assets chapter {index} starts outside the video")
        title = _text(chapter, "title", f"chapter {index}", 256)
        if "\r" in title or "\n" in title:
            raise ValueError(f"YouTube assets chapter {index} title must be one line")
        result.append({
            "start_seconds": start_value,
            "title": title,
        })
        previous = start_value
    if duration - result[-1]["start_seconds"] < 10:
        raise ValueError("YouTube assets final chapter must be at least 10 seconds long")
    return result


def _srt_time(value: float) -> str:
    milliseconds = round(value * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _srt(track: dict) -> str:
    blocks = []
    for index, cue in enumerate(track["cues"], start=1):
        blocks.append(
            f"{index}\n{_srt_time(cue['start_seconds'])} --> "
            f"{_srt_time(cue['end_seconds'])}\n{cue['text']}"
        )
    return "\n\n".join(blocks) + "\n"


def _chapter_time(value: int) -> str:
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def _chapter_text(chapters: list[dict]) -> str:
    return "".join(
        f"{_chapter_time(chapter['start_seconds'])} {chapter['title']}\n"
        for chapter in chapters
    )


def create_youtube_asset_bundle(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Create upload-facing assets without changing the approved video or uploading it."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid YouTube assets JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict) or score.get("schema") != YOUTUBE_ASSETS_SCHEMA:
        raise ValueError(f"unsupported YouTube assets schema: {score.get('schema')}")
    title = _text(score, "title", "recipe", 512)
    intent = _text(score, "intent", "recipe")
    accessibility_note = _text(score, "accessibility_note", "recipe", 4096)
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("YouTube assets title must contain at least one letter or number")
    video_value = score.get("approved_video")
    if not isinstance(video_value, str) or not video_value.strip() or Path(video_value).is_absolute():
        raise ValueError("YouTube assets approved_video must be song-relative")
    video, video_sidecar, video_metadata = verify_youtube_provenance(
        song_path, video_value, require_approval=True
    )
    duration = _video_duration(video_metadata)
    thumbnail, thumbnail_path, thumbnail_probe = _thumbnail(song_path, score.get("thumbnail"))
    captions = _captions(score.get("captions"), duration)
    chapters = _chapters(score.get("chapters"), duration)
    recipe = {
        "schema": YOUTUBE_ASSETS_SCHEMA,
        "title": title,
        "intent": intent,
        "accessibility_note": accessibility_note,
        "video": {
            "path": str(video.relative_to(song_path)),
            "sha256": sha256(video),
            "provenance_path": str(video_sidecar.relative_to(song_path)),
            "provenance_sha256": sha256(video_sidecar),
            "recipe_id": video_metadata.get("recipe_id"),
            "duration_seconds": duration,
        },
        "thumbnail": thumbnail,
        "captions": captions,
        "chapters": chapters,
        "platform_contract": PLATFORM_CONTRACT,
    }
    bundle_id = _digest(recipe)
    destination = song_path / "video" / "youtube-assets" / title_slug / bundle_id[:10]
    manifest_path = destination / "bundle.json"
    if destination.exists():
        _, existing = verify_youtube_asset_bundle(
            song_path, destination, require_approval=False
        )
        if existing.get("bundle_id") == bundle_id and existing.get("recipe") == recipe:
            return destination, manifest_path
        raise FileExistsError(f"YouTube asset bundle has different provenance: {destination}")
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"Incomplete YouTube asset bundle exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        thumbnail_copy = temporary / f"thumbnail{thumbnail_path.suffix.lower()}"
        shutil.copy2(thumbnail_path, thumbnail_copy)
        if sha256(thumbnail_copy) != thumbnail["source"]["sha256"]:
            raise RuntimeError("YouTube thumbnail copy verification failed")
        artifacts = [{
            "role": "thumbnail",
            "path": thumbnail_copy.name,
            "sha256": sha256(thumbnail_copy),
        }]
        for track in captions:
            name = f"captions-{track['language'].lower()}.srt"
            caption_path = temporary / name
            caption_path.write_text(_srt(track), encoding="utf-8")
            artifacts.append({
                "role": "captions",
                "language": track["language"],
                "label": track["label"],
                "path": name,
                "sha256": sha256(caption_path),
            })
        chapters_path = temporary / "chapters.txt"
        chapters_path.write_text(_chapter_text(chapters), encoding="utf-8")
        artifacts.append({
            "role": "chapters",
            "path": chapters_path.name,
            "sha256": sha256(chapters_path),
        })
        record = {
            "schema": YOUTUBE_ASSET_BUNDLE_SCHEMA,
            "bundle_id": bundle_id,
            "created_at": utc_now(),
            "recipe": recipe,
            "artifacts": artifacts,
            "verification": {
                "approved_video": True,
                "thumbnail_platform_checks": all(thumbnail["platform_checks"].values()),
                "thumbnail_decodes": bool(thumbnail_probe.get("streams")),
                "captions_timed_within_video": True,
                "chapters_platform_rules": True,
                "copies_match": True,
            },
            "review": {
                "editorial_and_accessibility_review": "not recorded",
                "review_notes": [],
                "promotion_to_FINAL": "not performed",
            },
            "authority": {
                "upload_authorized": False,
                "publication_authorized": False,
                "statement": (
                    "This bundle prepares local upload assets only. It does not transcribe, "
                    "infer creative decisions, authorize upload, or publish anything."
                ),
            },
        }
        (temporary / "bundle.json").write_text(json.dumps(record, indent=2) + "\n")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination, manifest_path


def _resolve_bundle(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    else:
        candidate = (song / requested).resolve()
    if candidate.is_dir():
        candidate = candidate / "bundle.json"
    try:
        candidate.relative_to((song / "video" / "youtube-assets").resolve())
    except ValueError as exc:
        raise ValueError("YouTube asset bundle must be inside video/youtube-assets") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_youtube_asset_bundle(
    song: str | Path,
    value: str | Path,
    *,
    require_approval: bool = True,
    verify_artifacts: bool = True,
) -> tuple[Path, dict]:
    """Verify bundle identity, source evidence, generated files, and review state."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _resolve_bundle(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid YouTube asset bundle JSON: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != YOUTUBE_ASSET_BUNDLE_SCHEMA:
        raise ValueError("unsupported YouTube asset bundle schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("YouTube asset bundle recipe is invalid")
    bundle_id = _digest(recipe)
    if record.get("bundle_id") != bundle_id or path.parent.name != bundle_id[:10]:
        raise ValueError("YouTube asset bundle id does not match its recipe")
    verification = record.get("verification")
    if not isinstance(verification, dict) or not verification or not all(verification.values()):
        raise ValueError("YouTube asset bundle verification is incomplete")
    authority = record.get("authority")
    if (
        not isinstance(authority, dict)
        or authority.get("upload_authorized") is not False
        or authority.get("publication_authorized") is not False
    ):
        raise ValueError("YouTube asset bundle authority boundary has changed")
    video_record = recipe.get("video")
    if not isinstance(video_record, dict):
        raise ValueError("YouTube asset bundle video evidence is invalid")
    video, sidecar, metadata = verify_youtube_provenance(
        song_path, video_record.get("path", ""), require_approval=True
    )
    expected_video = {
        "path": str(video.relative_to(song_path)),
        "sha256": sha256(video),
        "provenance_path": str(sidecar.relative_to(song_path)),
        "provenance_sha256": sha256(sidecar),
        "recipe_id": metadata.get("recipe_id"),
        "duration_seconds": _video_duration(metadata),
    }
    if video_record != expected_video:
        raise ValueError("YouTube asset bundle approved-video evidence has changed")
    if recipe.get("schema") != YOUTUBE_ASSETS_SCHEMA:
        raise ValueError("YouTube asset bundle recipe schema is invalid")
    _text(recipe, "title", "recipe", 512)
    _text(recipe, "intent", "recipe")
    _text(recipe, "accessibility_note", "recipe", 4096)
    if recipe.get("platform_contract") != PLATFORM_CONTRACT:
        raise ValueError("YouTube asset bundle platform contract is unsupported")
    thumbnail = recipe.get("thumbnail")
    if not isinstance(thumbnail, dict) or not isinstance(thumbnail.get("source"), dict):
        raise ValueError("YouTube asset bundle thumbnail evidence is invalid")
    thumbnail_source = _portable_path(
        song_path, thumbnail["source"].get("path"), "thumbnail source"
    )
    if thumbnail["source"].get("sha256") != sha256(thumbnail_source):
        raise ValueError("YouTube asset bundle thumbnail source has changed")
    normalized_thumbnail, _, _ = _thumbnail(song_path, {
        "path": thumbnail["source"].get("path"),
        "alt_text": thumbnail.get("alt_text"),
        "review_question": thumbnail.get("review_question"),
    })
    if thumbnail != normalized_thumbnail:
        raise ValueError("YouTube asset bundle thumbnail recipe is not normalized")
    normalized_captions = _captions(recipe.get("captions"), expected_video["duration_seconds"])
    normalized_chapters = _chapters(recipe.get("chapters"), expected_video["duration_seconds"])
    if recipe.get("captions") != normalized_captions or recipe.get("chapters") != normalized_chapters:
        raise ValueError("YouTube asset bundle timing recipe is not normalized")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 3:
        raise ValueError("YouTube asset bundle artifacts are incomplete")
    role_counts: dict[str, int] = {}
    caption_languages: set[str] = set()
    artifact_by_role: dict[str, list[tuple[dict, Path]]] = {}
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            raise ValueError(f"YouTube asset bundle artifact {index} is invalid")
        role = artifact.get("role")
        value_path = artifact.get("path")
        if role not in {"thumbnail", "captions", "chapters"} or not isinstance(value_path, str):
            raise ValueError(f"YouTube asset bundle artifact {index} has invalid role or path")
        artifact_path = (path.parent / value_path).resolve()
        try:
            artifact_path.relative_to(path.parent.resolve())
        except ValueError as exc:
            raise ValueError(f"YouTube asset bundle artifact escapes bundle: {value_path}") from exc
        if not artifact_path.is_file():
            raise FileNotFoundError(artifact_path)
        if verify_artifacts and artifact.get("sha256") != sha256(artifact_path):
            raise ValueError(f"YouTube asset bundle artifact checksum has changed: {value_path}")
        role_counts[role] = role_counts.get(role, 0) + 1
        artifact_by_role.setdefault(role, []).append((artifact, artifact_path))
        if role == "captions":
            language = artifact.get("language")
            if not isinstance(language, str) or language.casefold() in caption_languages:
                raise ValueError("YouTube asset bundle caption artifact language is invalid")
            caption_languages.add(language.casefold())
    if role_counts.get("thumbnail") != 1 or role_counts.get("chapters") != 1:
        raise ValueError("YouTube asset bundle requires one thumbnail and one chapter artifact")
    captions = recipe.get("captions")
    if not isinstance(captions, list) or role_counts.get("captions") != len(captions):
        raise ValueError("YouTube asset bundle caption artifacts do not match its recipe")
    thumbnail_artifact, thumbnail_copy = artifact_by_role["thumbnail"][0]
    if thumbnail_artifact.get("sha256") != thumbnail["source"]["sha256"]:
        raise ValueError("YouTube asset bundle thumbnail copy does not match its source")
    chapter_artifact, chapter_path = artifact_by_role["chapters"][0]
    if chapter_path.read_text(encoding="utf-8") != _chapter_text(normalized_chapters):
        raise ValueError("YouTube asset bundle chapter text does not match its recipe")
    caption_artifacts = {
        artifact["language"].casefold(): (artifact, artifact_path)
        for artifact, artifact_path in artifact_by_role["captions"]
    }
    for track in normalized_captions:
        pair = caption_artifacts.get(track["language"].casefold())
        if pair is None:
            raise ValueError(f"YouTube asset bundle caption file is missing: {track['language']}")
        artifact, caption_path = pair
        if artifact.get("label") != track["label"] or caption_path.read_text(encoding="utf-8") != _srt(track):
            raise ValueError(f"YouTube asset bundle caption file does not match recipe: {track['language']}")
    review = record.get("review")
    if not isinstance(review, dict):
        raise ValueError("YouTube asset bundle review is invalid")
    review_state = review.get("editorial_and_accessibility_review")
    review_notes = review.get("review_notes")
    if review_state not in {"not recorded", "approved"} or not isinstance(review_notes, list):
        raise ValueError("YouTube asset bundle review state is invalid")
    if review_state == "approved" and not review_notes:
        raise ValueError("YouTube asset bundle approval requires a review note")
    if require_approval and (
        review.get("editorial_and_accessibility_review") != "approved"
    ):
        raise ValueError("YouTube asset bundle requires editorial and accessibility approval")
    return path, record


def review_youtube_asset_bundle(song: str | Path, bundle: str | Path, note: str) -> Path:
    """Record a human review of thumbnail, captions, chapters, and accessibility context."""
    clean = note.strip()
    if not clean:
        raise ValueError("YouTube asset review requires a review note")
    if len(clean.encode("utf-8")) > 8192:
        raise ValueError("YouTube asset review note exceeds 8192 UTF-8 bytes")
    path, record = verify_youtube_asset_bundle(
        song, bundle, require_approval=False, verify_artifacts=True
    )
    with _review_lock(path):
        # Re-read after taking the lock so concurrent edits cannot be lost.
        _, record = verify_youtube_asset_bundle(
            song, path, require_approval=False, verify_artifacts=True
        )
        review = record.setdefault("review", {})
        notes = review.setdefault("review_notes", [])
        if not isinstance(notes, list):
            raise ValueError("YouTube asset review_notes must be a list")
        if any(isinstance(item, dict) and item.get("note") == clean for item in notes):
            return path
        notes.append({"approved_at": utc_now(), "note": clean})
        review["editorial_and_accessibility_review"] = "approved"
        review["promotion_to_FINAL"] = "not performed"
        temporary = path.with_name(f".{path.name}.partial")
        if temporary.exists():
            raise FileExistsError(f"Incomplete YouTube asset review exists: {temporary}")
        temporary.write_text(json.dumps(record, indent=2) + "\n")
        temporary.replace(path)
    return path
