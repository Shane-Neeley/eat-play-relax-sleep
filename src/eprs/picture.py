"""Renderer-neutral capture and review of finished picture candidates."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

from .master import verify_master_provenance
from .system import load_song_manifest, probe, sha256, slugify, utc_now


PICTURE_SCHEMA = "eprs.picture/v1"
PICTURE_CANDIDATE_SCHEMA = "eprs.picture-candidate/v1"
REVIEW_DECISIONS = {"keep", "change", "stop"}
MAX_CHANGES = 64
MAX_UNKNOWNS = 64
MAX_EVIDENCE = 32


@contextmanager
def _review_lock(path: Path):
    lock = path.parent / ".picture-review.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f"picture review is locked by another process: {lock}") from exc
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


def _text(record: dict, key: str, label: str, maximum: int = 4096) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"picture {label} requires {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"picture {label} {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _text_list(value: object, label: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"picture {label} must contain at most {maximum} text items")
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"picture {label} item {index} must be non-empty text")
        clean = item.strip()
        if len(clean.encode("utf-8")) > 4096:
            raise ValueError(f"picture {label} item {index} is too long")
        result.append(clean)
    return result


def _tool(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("picture tool must be an object")
    return {
        "name": _text(value, "name", "tool", 1024),
        "version": _text(value, "version", "tool", 1024),
        "session_format": _text(value, "session_format", "tool", 1024),
    }


def _changes(value: object) -> list[dict]:
    if not isinstance(value, list) or not value or len(value) > MAX_CHANGES:
        raise ValueError(f"picture changes must contain 1 to {MAX_CHANGES} records")
    identifiers: set[str] = set()
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"picture change {index} must be an object")
        declared_id = _text(item, "id", f"change {index}", 256)
        change_id = slugify(declared_id)
        if not change_id or change_id in identifiers:
            raise ValueError(f"picture change id is invalid or duplicated: {declared_id}")
        identifiers.add(change_id)
        result.append({
            "id": change_id,
            "declared_id": declared_id,
            "type": _text(item, "type", f"change {change_id}", 512),
            "intent": _text(item, "intent", f"change {change_id}"),
            "details": _text(item, "details", f"change {change_id}", 8192),
            "settings_or_unknown": _text(
                item, "settings_or_unknown", f"change {change_id}", 8192
            ),
        })
    return result


def _source_locator(song: Path, path: Path) -> dict:
    try:
        relative = path.resolve().relative_to(song.resolve())
    except ValueError:
        return {"scope": "external", "original_name": path.name}
    return {"scope": "song", "path": str(relative)}


def _source_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"picture {label} requires a path")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _rate(value: object) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    numerator, separator, denominator = value.partition("/")
    try:
        result = float(numerator) / float(denominator) if separator else float(numerator)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return result if math.isfinite(result) and result > 0 else 0.0


def _media(path: Path) -> tuple[dict, dict]:
    media_probe = probe(path)
    if media_probe.get("error"):
        raise ValueError(f"picture source video is unreadable: {media_probe['error']}")
    video = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "video"),
        None,
    )
    if not isinstance(video, dict):
        raise ValueError("picture source requires a video stream")
    duration_value = media_probe.get("format", {}).get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("picture source duration is unavailable") from exc
    width = video.get("width")
    height = video.get("height")
    average_rate = video.get("avg_frame_rate")
    raw_rate = video.get("r_frame_rate")
    rate_value = average_rate if _rate(average_rate) > 0 else raw_rate
    fps = _rate(rate_value)
    if (
        not math.isfinite(duration)
        or duration <= 0
        or isinstance(width, bool)
        or not isinstance(width, int)
        or width <= 0
        or isinstance(height, bool)
        or not isinstance(height, int)
        or height <= 0
        or fps <= 0
    ):
        raise ValueError("picture source has invalid duration, dimensions, or frame rate")
    audio = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    normalized = {
        "container": media_probe.get("format", {}).get("format_name"),
        "duration_seconds": duration,
        "video": {
            "codec": video.get("codec_name"),
            "profile": video.get("profile"),
            "width": width,
            "height": height,
            "pixel_format": video.get("pix_fmt"),
            "color_space": video.get("color_space"),
            "color_transfer": video.get("color_transfer"),
            "color_primaries": video.get("color_primaries"),
            "field_order": video.get("field_order"),
            "frame_rate": rate_value,
            "frame_rate_decimal": fps,
        },
        "guide_audio": {
            "present": audio is not None,
            "codec": audio.get("codec_name") if isinstance(audio, dict) else None,
            "sample_rate": audio.get("sample_rate") if isinstance(audio, dict) else None,
            "channels": audio.get("channels") if isinstance(audio, dict) else None,
        },
    }
    return normalized, media_probe


def _evidence_inputs(song: Path, value: object) -> list[tuple[dict, Path]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_EVIDENCE:
        raise ValueError(f"picture evidence must contain at most {MAX_EVIDENCE} records")
    identifiers: set[str] = set()
    digests: set[str] = set()
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"picture evidence {index} must be an object")
        declared_id = _text(item, "id", f"evidence {index}", 256)
        evidence_id = slugify(declared_id)
        if not evidence_id or evidence_id in identifiers:
            raise ValueError(f"picture evidence id is invalid or duplicated: {declared_id}")
        identifiers.add(evidence_id)
        path = _source_path(item.get("path"), f"evidence {evidence_id}")
        digest = sha256(path)
        if digest in digests:
            raise ValueError("picture evidence files must be unique")
        digests.add(digest)
        result.append(({
            "id": evidence_id,
            "declared_id": declared_id,
            "role": _text(item, "role", f"evidence {evidence_id}", 1024),
            "source": _source_locator(song, path),
            "original_name": path.name,
            "sha256": digest,
            "copy_name": f"{evidence_id}-{path.name}",
            "note": _text(item, "note", f"evidence {evidence_id}"),
            "rights_note": _text(item, "rights_note", f"evidence {evidence_id}"),
        }, path))
    return result


def _review(metadata: dict, require_keep: bool) -> None:
    review = metadata.get("review")
    if not isinstance(review, dict):
        raise ValueError("picture review record is invalid")
    decision = review.get("decision")
    notes = review.get("notes")
    if decision not in {*REVIEW_DECISIONS, "not recorded by capture"} or not isinstance(notes, list):
        raise ValueError("picture review state is invalid")
    if decision in REVIEW_DECISIONS and not any(
        isinstance(item, dict)
        and item.get("decision") == decision
        and isinstance(item.get("note"), str)
        and bool(item["note"].strip())
        for item in notes
    ):
        raise ValueError("picture review decision lacks a matching note")
    if require_keep and decision != "keep":
        raise ValueError("YouTube assembly requires a complete-picture keep decision")


def capture_picture(spec: str | Path, song: str | Path) -> tuple[Path, Path, dict]:
    """Copy one rendered picture unchanged and bind it to the intended approved master."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid picture JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict) or score.get("schema") != PICTURE_SCHEMA:
        raise ValueError(f"unsupported picture schema: {score.get('schema')}")
    title = _text(score, "title", "spec", 1024)
    intent = _text(score, "intent", "spec")
    operator = _text(score, "operator", "spec", 1024)
    rights_note = _text(score, "rights_note", "spec")
    if score.get("timeline_origin") != "master-time-zero":
        raise ValueError("picture timeline_origin must be master-time-zero")
    if score.get("audio_policy") != "replace-with-approved-master":
        raise ValueError("picture audio_policy must be replace-with-approved-master")
    tool = _tool(score.get("tool"))
    changes = _changes(score.get("changes"))
    unknowns = _text_list(score.get("unknowns", []), "unknowns", MAX_UNKNOWNS)
    master_value = score.get("approved_master")
    if not isinstance(master_value, str) or not master_value or Path(master_value).is_absolute():
        raise ValueError("picture approved_master must be song-relative")
    master, master_sidecar, master_metadata = verify_master_provenance(
        song_path, master_value, require_approval=True
    )
    master_duration = float(
        master_metadata.get("output", {}).get("probe", {}).get("format", {}).get("duration") or 0
    )
    source = _source_path(score.get("source_video"), "source_video")
    source_digest = sha256(source)
    media, _ = _media(source)
    frame_tolerance = 1 / media["video"]["frame_rate_decimal"] + 0.02
    if abs(media["duration_seconds"] - master_duration) > max(0.1, frame_tolerance):
        raise ValueError("picture duration does not match the approved master")
    evidence_inputs = _evidence_inputs(song_path, score.get("evidence"))
    evidence = [item for item, _ in evidence_inputs]
    recipe = {
        "schema": PICTURE_SCHEMA,
        "title": title,
        "intent": intent,
        "operator": operator,
        "tool": tool,
        "timeline_origin": "master-time-zero",
        "audio_policy": "replace-with-approved-master",
        "master": {
            "path": str(master.relative_to(song_path)),
            "sha256": sha256(master),
            "provenance_path": str(master_sidecar.relative_to(song_path)),
            "provenance_sha256": sha256(master_sidecar),
            "recipe_id": master_metadata.get("recipe_id"),
            "duration_seconds": master_duration,
        },
        "source_video": {
            "source": _source_locator(song_path, source),
            "original_name": source.name,
            "sha256": source_digest,
            "media": media,
        },
        "changes": changes,
        "unknowns": unknowns,
        "evidence": evidence,
        "rights_note": rights_note,
    }
    recipe_id = _digest(recipe)
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("picture title must contain at least one letter or number")
    suffix = source.suffix.lower() or ".mp4"
    root = song_path / "video" / "pictures" / title_slug
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{recipe_id[:10]}-{title_slug}{suffix}"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        existing_path, existing_sidecar, existing = verify_picture(
            song_path, destination, require_keep=False
        )
        if existing.get("recipe_id") != recipe_id:
            raise FileExistsError(f"picture destination has different provenance: {destination}")
        return existing_path, existing_sidecar, existing
    temporary = destination.with_name(f".{destination.name}.partial")
    sidecar_temporary = sidecar.with_name(f".{sidecar.name}.partial")
    evidence_temporary = root / f".{recipe_id[:10]}.evidence.partial"
    evidence_final = root / "evidence" / recipe_id[:10]
    if (
        temporary.exists()
        or sidecar_temporary.exists()
        or evidence_temporary.exists()
        or evidence_final.exists()
    ):
        raise FileExistsError(f"incomplete picture capture exists beside: {destination}")
    shutil.copy2(source, temporary)
    try:
        if sha256(temporary) != source_digest:
            raise RuntimeError("picture copy verification failed")
        copied_media, output_probe = _media(temporary)
        if copied_media != media:
            raise RuntimeError("picture copy media properties changed")
        copied_evidence = []
        if evidence_inputs:
            evidence_temporary.mkdir()
            for record, evidence_source in evidence_inputs:
                evidence_copy = evidence_temporary / record["copy_name"]
                shutil.copy2(evidence_source, evidence_copy)
                if sha256(evidence_copy) != record["sha256"]:
                    raise RuntimeError("picture evidence copy verification failed")
                copied_evidence.append({
                    **record,
                    "path": str(
                        (root / "evidence" / recipe_id[:10] / record["copy_name"])
                        .relative_to(song_path)
                    ),
                })
        warnings = [
            "Captured picture bytes are preserved, but any embedded guide audio is non-authoritative and will be replaced by the approved master during YouTube assembly.",
            "EPRS records external renderer declarations but cannot reproduce undisclosed tool or session state.",
            *(f"Unresolved picture unknown: {item}" for item in unknowns),
        ]
        metadata = {
            "schema": PICTURE_CANDIDATE_SCHEMA,
            "recipe_id": recipe_id,
            "captured_at": utc_now(),
            "title": title,
            "intent": intent,
            "recipe": recipe,
            "external_render": {
                "tool": tool,
                "operator": operator,
                "copied_without_conversion": True,
                "reproducible_by_eprs": False,
                "changes": changes,
                "unknowns": unknowns,
            },
            "evidence": copied_evidence,
            "output": {
                "path": str(destination.relative_to(song_path)),
                "sha256": source_digest,
                "probe": output_probe,
            },
            "verification": {
                "video_stream_present": True,
                "known_duration": True,
                "duration_matches_master": True,
                "timeline_origin_declared": True,
                "guide_audio_non_authoritative": True,
                "checksum_preserved": True,
            },
            "warnings": warnings,
            "review": {"decision": "not recorded by capture", "notes": []},
            "authority": {
                "creative_approval_inferred": False,
                "final_promotion": False,
                "upload_authorized": False,
                "publication_authorized": False,
            },
        }
        sidecar_temporary.write_text(json.dumps(metadata, indent=2) + "\n")
        temporary.replace(destination)
        if evidence_inputs:
            evidence_root = root / "evidence"
            evidence_root.mkdir(exist_ok=True)
            evidence_temporary.replace(evidence_final)
        sidecar_temporary.replace(sidecar)
    except Exception:
        temporary.unlink(missing_ok=True)
        sidecar_temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        shutil.rmtree(evidence_temporary, ignore_errors=True)
        shutil.rmtree(evidence_final, ignore_errors=True)
        raise
    return verify_picture(song_path, destination, require_keep=False)


def verify_picture(
    song: str | Path,
    picture: str | Path,
    *,
    require_keep: bool = False,
) -> tuple[Path, Path, dict]:
    """Verify one captured picture, master binding, disclosures, evidence, and review."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(picture)
    path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        path.relative_to((song_path / "video" / "pictures").resolve())
    except ValueError as exc:
        raise ValueError("picture candidate must be inside video/pictures") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    sidecar = path.with_suffix(path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(sidecar)
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid picture provenance JSON: {sidecar}: {exc.msg}") from exc
    if not isinstance(metadata, dict) or metadata.get("schema") != PICTURE_CANDIDATE_SCHEMA:
        raise ValueError("unsupported picture candidate schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != PICTURE_SCHEMA:
        raise ValueError("picture recipe is invalid")
    for key, maximum in (
        ("title", 1024), ("intent", 4096), ("operator", 1024), ("rights_note", 4096)
    ):
        _text(recipe, key, "recipe", maximum)
    if recipe.get("tool") != _tool(recipe.get("tool")):
        raise ValueError("picture tool record is not normalized")
    if recipe.get("changes") != _changes(recipe.get("changes")):
        raise ValueError("picture changes are not normalized")
    if recipe.get("unknowns") != _text_list(recipe.get("unknowns"), "unknowns", MAX_UNKNOWNS):
        raise ValueError("picture unknowns are not normalized")
    if recipe.get("timeline_origin") != "master-time-zero":
        raise ValueError("picture timeline origin is invalid")
    if recipe.get("audio_policy") != "replace-with-approved-master":
        raise ValueError("picture audio policy is invalid")
    recipe_id = _digest(recipe)
    if metadata.get("recipe_id") != recipe_id or not path.name.startswith(recipe_id[:10]):
        raise ValueError("picture recipe id does not match its recipe")
    master_record = recipe.get("master")
    if not isinstance(master_record, dict):
        raise ValueError("picture master evidence is invalid")
    master, master_sidecar, master_metadata = verify_master_provenance(
        song_path, master_record.get("path", ""), require_approval=True
    )
    master_duration = float(
        master_metadata.get("output", {}).get("probe", {}).get("format", {}).get("duration") or 0
    )
    expected_master = {
        "path": str(master.relative_to(song_path)),
        "sha256": sha256(master),
        "provenance_path": str(master_sidecar.relative_to(song_path)),
        "provenance_sha256": sha256(master_sidecar),
        "recipe_id": master_metadata.get("recipe_id"),
        "duration_seconds": master_duration,
    }
    if master_record != expected_master:
        raise ValueError("picture approved-master evidence has changed")
    source_video = recipe.get("source_video")
    output = metadata.get("output")
    if (
        not isinstance(source_video, dict)
        or not isinstance(source_video.get("source"), dict)
        or not isinstance(source_video.get("original_name"), str)
        or not isinstance(output, dict)
        or output.get("path") != str(path.relative_to(song_path))
        or output.get("sha256") != sha256(path)
        or source_video.get("sha256") != output.get("sha256")
    ):
        raise ValueError("picture output provenance is invalid or changed")
    source_locator = source_video["source"]
    if source_locator.get("scope") == "song":
        source_value = source_locator.get("path")
        if (
            not isinstance(source_value, str)
            or not source_value
            or Path(source_value).is_absolute()
        ):
            raise ValueError("picture song-local source locator is invalid")
        resolved_source = (song_path / source_value).resolve()
        try:
            normalized_source = str(resolved_source.relative_to(song_path))
        except ValueError as exc:
            raise ValueError("picture song-local source locator is invalid") from exc
        if source_locator != {"scope": "song", "path": normalized_source}:
            raise ValueError("picture song-local source locator is invalid")
    elif source_locator != {
        "scope": "external", "original_name": source_video["original_name"]
    }:
        raise ValueError("picture external source locator is invalid")
    media, _ = _media(path)
    if source_video.get("media") != media:
        raise ValueError("picture media declaration is invalid or changed")
    tolerance = max(0.1, 1 / media["video"]["frame_rate_decimal"] + 0.02)
    if abs(media["duration_seconds"] - master_duration) > tolerance:
        raise ValueError("picture duration no longer matches its approved master")
    evidence_recipe = recipe.get("evidence")
    evidence = metadata.get("evidence")
    if not isinstance(evidence_recipe, list) or not isinstance(evidence, list):
        raise ValueError("picture evidence is invalid")
    if len(evidence_recipe) != len(evidence) or len(evidence) > MAX_EVIDENCE:
        raise ValueError("picture evidence count is invalid")
    for expected, artifact in zip(evidence_recipe, evidence, strict=True):
        if not isinstance(expected, dict) or not isinstance(artifact, dict):
            raise ValueError("picture evidence record is invalid")
        expected_path = str(
            (path.parent / "evidence" / recipe_id[:10] / expected.get("copy_name", ""))
            .relative_to(song_path)
        )
        if artifact != {**expected, "path": expected_path}:
            raise ValueError("picture evidence declaration is inconsistent")
        artifact_path = (song_path / expected_path).resolve()
        try:
            artifact_path.relative_to((path.parent / "evidence" / recipe_id[:10]).resolve())
        except ValueError as exc:
            raise ValueError("picture evidence path escapes its capture") from exc
        if not artifact_path.is_file() or sha256(artifact_path) != expected.get("sha256"):
            raise ValueError("picture evidence copy is missing or changed")
    external = metadata.get("external_render")
    if (
        not isinstance(external, dict)
        or external.get("tool") != recipe.get("tool")
        or external.get("operator") != recipe.get("operator")
        or external.get("changes") != recipe.get("changes")
        or external.get("unknowns") != recipe.get("unknowns")
        or external.get("copied_without_conversion") is not True
        or external.get("reproducible_by_eprs") is not False
    ):
        raise ValueError("picture external-render disclosure is inconsistent")
    if metadata.get("title") != recipe.get("title") or metadata.get("intent") != recipe.get("intent"):
        raise ValueError("picture title or intent disclosure is inconsistent")
    expected_warnings = [
        "Captured picture bytes are preserved, but any embedded guide audio is non-authoritative and will be replaced by the approved master during YouTube assembly.",
        "EPRS records external renderer declarations but cannot reproduce undisclosed tool or session state.",
        *(f"Unresolved picture unknown: {item}" for item in recipe["unknowns"]),
    ]
    if metadata.get("warnings") != expected_warnings:
        raise ValueError("picture warnings are invalid")
    verification = metadata.get("verification")
    expected_verification = {
        "video_stream_present", "known_duration", "duration_matches_master",
        "timeline_origin_declared", "guide_audio_non_authoritative",
        "checksum_preserved",
    }
    if (
        not isinstance(verification, dict)
        or set(verification) != expected_verification
        or not all(value is True for value in verification.values())
    ):
        raise ValueError("picture technical verification is incomplete")
    authority = metadata.get("authority")
    if not isinstance(authority, dict) or any(
        authority.get(key) is not False
        for key in (
            "creative_approval_inferred", "final_promotion",
            "upload_authorized", "publication_authorized",
        )
    ):
        raise ValueError("picture authority record is invalid")
    _review(metadata, require_keep)
    return path, sidecar, metadata


def review_picture(
    song: str | Path,
    picture: str | Path,
    decision: str,
    note: str,
) -> Path:
    """Record a complete-picture decision without altering the captured video."""
    if decision not in REVIEW_DECISIONS:
        raise ValueError("picture review decision must be keep, change, or stop")
    clean = note.strip()
    if not clean:
        raise ValueError("picture review requires a complete-picture note")
    if len(clean.encode("utf-8")) > 8192:
        raise ValueError("picture review note exceeds 8192 UTF-8 bytes")
    _, sidecar, metadata = verify_picture(song, picture, require_keep=False)
    with _review_lock(sidecar):
        _, _, metadata = verify_picture(song, picture, require_keep=False)
        review = metadata["review"]
        notes = review["notes"]
        if any(
            isinstance(item, dict)
            and item.get("decision") == decision
            and item.get("note") == clean
            for item in notes
        ):
            return sidecar
        notes.append({"reviewed_at": utc_now(), "decision": decision, "note": clean})
        review["decision"] = decision
        temporary = sidecar.with_name(f".{sidecar.name}.partial")
        if temporary.exists():
            raise FileExistsError(f"incomplete picture review exists: {temporary}")
        temporary.write_text(json.dumps(metadata, indent=2) + "\n")
        temporary.replace(sidecar)
    return sidecar
