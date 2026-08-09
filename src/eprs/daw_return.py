"""Capture lossless audio returned from another DAW with honest round-trip provenance."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil

from .interchange import verify_daw_interchange
from .system import load_song_manifest, probe, sha256, slugify, utc_now


DAW_RETURN_SCHEMA = "eprs.daw-return/v1"
DAW_RETURN_MIX_SCHEMA = "eprs.daw-return-mix/v1"
LOSSLESS_CODECS = {"flac", "alac"}
MAX_CHANGES = 64
MAX_UNKNOWNS = 64
MAX_ADDED_SOURCES = 32


def _text(record: dict, key: str, label: str, maximum: int = 4096) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"DAW return {label} requires {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"DAW return {label} {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _string_list(value: object, label: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"DAW return {label} must be a list with at most {maximum} items")
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"DAW return {label} item {index} must be non-empty text")
        clean = item.strip()
        if len(clean.encode("utf-8")) > 4096:
            raise ValueError(f"DAW return {label} item {index} is too long")
        result.append(clean)
    return result


def _song_file(song: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"DAW return {label} requires a path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"DAW return {label} path must be relative to the song")
    candidate = (song / requested).resolve()
    try:
        candidate.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"DAW return {label} path escapes the song workspace") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _changes(value: object) -> list[dict]:
    if not isinstance(value, list) or not value or len(value) > MAX_CHANGES:
        raise ValueError(f"DAW return changes requires 1 to {MAX_CHANGES} records")
    identifiers: set[str] = set()
    changes = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"DAW return change {index} must be an object")
        declared_id = _text(item, "id", f"change {index}", 256)
        change_id = slugify(declared_id)
        if not change_id or change_id in identifiers:
            raise ValueError(f"DAW return change id is invalid or duplicated: {declared_id}")
        identifiers.add(change_id)
        changes.append({
            "id": change_id,
            "declared_id": declared_id,
            "type": _text(item, "type", f"change {change_id}", 512),
            "intent": _text(item, "intent", f"change {change_id}"),
            "details": _text(item, "details", f"change {change_id}"),
            "settings_or_unknown": _text(
                item, "settings_or_unknown", f"change {change_id}", 8192
            ),
        })
    return changes


def _added_sources(song: Path, value: object, original_mix: dict) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_ADDED_SOURCES:
        raise ValueError(
            f"DAW return added_sources must contain at most {MAX_ADDED_SOURCES} records"
        )
    identifiers: set[str] = set()
    paths: set[Path] = set()
    records = []
    original_path = (song / original_mix["path"]).resolve()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"DAW return added source {index} must be an object")
        declared_id = _text(item, "id", f"added source {index}", 256)
        source_id = slugify(declared_id)
        if not source_id or source_id in identifiers:
            raise ValueError(f"DAW return added source id is invalid or duplicated: {declared_id}")
        identifiers.add(source_id)
        path = _song_file(song, item.get("path"), f"added source {source_id}")
        if path == original_path or path in paths:
            raise ValueError("DAW return added source paths must be unique and not repeat the parent mix")
        paths.add(path)
        digest = sha256(path)
        raw_root = (song / "recordings" / "raw").resolve()
        if path.is_relative_to(raw_root):
            sidecar = path.with_suffix(path.suffix + ".json")
            if not sidecar.is_file():
                raise ValueError(f"DAW return raw added source lacks provenance: {path.relative_to(song)}")
            try:
                metadata = json.loads(sidecar.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid raw added-source provenance: {sidecar}: {exc.msg}") from exc
            if metadata.get("schema") != "eprs.recording/v1" or metadata.get("sha256") != digest:
                raise ValueError(f"DAW return raw added-source provenance is invalid: {path.relative_to(song)}")
        records.append({
            "id": source_id,
            "declared_id": declared_id,
            "role": _text(item, "role", f"added source {source_id}", 1024),
            "path": str(path.relative_to(song)),
            "sha256": digest,
            "note": _text(item, "note", f"added source {source_id}"),
            "rights_note": _text(item, "rights_note", f"added source {source_id}"),
        })
    return records


def _lossless_audio(path: Path) -> tuple[dict, dict, float, int, int]:
    media_probe = probe(path)
    stream = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    codec = stream.get("codec_name") if isinstance(stream, dict) else None
    duration = float(media_probe.get("format", {}).get("duration") or 0)
    sample_rate = int(stream.get("sample_rate") or 0) if isinstance(stream, dict) else 0
    channels = int(stream.get("channels") or 0) if isinstance(stream, dict) else 0
    if (
        stream is None
        or not (isinstance(codec, str) and (codec.startswith("pcm_") or codec in LOSSLESS_CODECS))
        or duration <= 0
        or not math.isfinite(duration)
        or not 8_000 <= sample_rate <= 192_000
        or channels not in {1, 2}
    ):
        raise ValueError("DAW return requires mono/stereo lossless audio with known duration and sample rate")
    return media_probe, stream, duration, sample_rate, channels


def _approval(metadata: dict, require_approval: bool) -> None:
    if not require_approval:
        return
    review = metadata.get("review")
    notes = review.get("listening_notes") if isinstance(review, dict) else None
    has_keep_note = isinstance(notes, list) and any(
        isinstance(record, dict)
        and record.get("decision") == "keep"
        and isinstance(record.get("note"), str)
        and bool(record["note"].strip())
        for record in notes
    )
    if not isinstance(review, dict) or review.get("decision") != "keep" or not has_keep_note:
        raise ValueError("mastering requires a recorded complete-listen keep decision for the working mix")


def verify_daw_return_mix(
    song: str | Path,
    mix: str | Path,
    *,
    require_approval: bool = False,
) -> tuple[Path, Path, dict]:
    """Verify a returned mix, its parent interchange, and every declared source."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(mix)
    mix_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        mix_path.relative_to((song_path / "mixes").resolve())
    except ValueError as exc:
        raise ValueError("returned DAW mix must be inside the song mixes directory") from exc
    if not mix_path.is_file():
        raise FileNotFoundError(mix_path)
    sidecar = mix_path.with_suffix(mix_path.suffix + ".json")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid DAW return provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != DAW_RETURN_MIX_SCHEMA:
        raise ValueError("unsupported DAW return mix schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != DAW_RETURN_SCHEMA:
        raise ValueError("DAW return recipe is invalid")
    try:
        normalized_tool_value = recipe.get("tool")
        if not isinstance(normalized_tool_value, dict):
            raise ValueError("DAW return tool must be an object")
        normalized_tool = {
            "name": _text(normalized_tool_value, "name", "tool", 1024),
            "version": _text(normalized_tool_value, "version", "tool", 1024),
            "session_format": _text(
                normalized_tool_value, "session_format", "tool", 1024
            ),
        }
        normalized_changes = _changes(recipe.get("changes"))
        normalized_unknowns = _string_list(
            recipe.get("unknowns"), "unknowns", MAX_UNKNOWNS
        )
        for key, maximum in (
            ("title", 1024),
            ("intent", 4096),
            ("operator", 1024),
            ("rights_note", 4096),
        ):
            _text(recipe, key, "recipe", maximum)
        if recipe.get("timeline_origin") != "package-time-zero":
            raise ValueError("DAW return timeline_origin must be package-time-zero")
        if normalized_tool != normalized_tool_value:
            raise ValueError("DAW return tool record is not normalized")
        if normalized_changes != recipe.get("changes"):
            raise ValueError("DAW return changes are not normalized")
        if normalized_unknowns != recipe.get("unknowns"):
            raise ValueError("DAW return unknowns are not normalized")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"DAW return recipe disclosure is invalid: {exc}") from exc
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("recipe_id") != recipe_id:
        raise ValueError("DAW return recipe id does not match its recipe")
    output = metadata.get("output")
    relative_output = str(mix_path.relative_to(song_path))
    if (
        not isinstance(output, dict)
        or output.get("path") != relative_output
        or output.get("sha256") != sha256(mix_path)
        or recipe.get("returned_audio", {}).get("sha256") != output.get("sha256")
    ):
        raise ValueError("DAW return output provenance is invalid or changed")
    _, actual_stream, actual_duration, actual_rate, actual_channels = _lossless_audio(mix_path)
    returned_audio = recipe.get("returned_audio")
    if (
        not isinstance(returned_audio, dict)
        or not isinstance(returned_audio.get("original_name"), str)
        or not returned_audio["original_name"]
        or returned_audio.get("sha256") != output.get("sha256")
        or returned_audio.get("codec") != actual_stream.get("codec_name")
        or returned_audio.get("sample_rate") != actual_rate
        or returned_audio.get("channels") != actual_channels
        or not isinstance(returned_audio.get("duration_seconds"), (int, float))
        or abs(float(returned_audio["duration_seconds"]) - actual_duration) > 0.001
    ):
        raise ValueError("DAW return audio declaration is invalid or changed")
    package_record = recipe.get("source_interchange")
    if not isinstance(package_record, dict):
        raise ValueError("DAW return source interchange is invalid")
    package_path, package = verify_daw_interchange(
        song_path,
        package_record.get("path", ""),
        verify_checksums=True,
        verify_media=False,
    )
    manifest_path = package_path / "interchange.json"
    if (
        package_record.get("package_id") != package.get("package_id")
        or package_record.get("manifest_sha256") != sha256(manifest_path)
        or recipe.get("source_mix") != package.get("recipe", {}).get("source_mix")
    ):
        raise ValueError("DAW return no longer matches its source interchange package")
    sources = metadata.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("DAW return sources are invalid")
    original_mix = recipe["source_mix"]
    if sources[0].get("path") != original_mix.get("path") or sources[0].get("sha256") != original_mix.get("sha256"):
        raise ValueError("DAW return parent mix source is invalid")
    for source in sources:
        source_path = _song_file(song_path, source.get("path"), "persisted source")
        if source.get("sha256") != sha256(source_path):
            raise ValueError(f"DAW return source is missing or changed: {source_path.relative_to(song_path)}")
    expected_added = recipe.get("added_sources", [])
    if not isinstance(expected_added, list) or len(expected_added) > MAX_ADDED_SOURCES:
        raise ValueError("DAW return added-source provenance is invalid")
    added_ids: set[str] = set()
    for index, added in enumerate(expected_added, start=1):
        if not isinstance(added, dict):
            raise ValueError("DAW return added-source provenance is invalid")
        added_id = _text(added, "id", f"persisted added source {index}", 256)
        declared_id = _text(
            added, "declared_id", f"persisted added source {index}", 256
        )
        if added_id != slugify(declared_id) or added_id in added_ids:
            raise ValueError("DAW return added-source id is invalid or duplicated")
        added_ids.add(added_id)
        for key, maximum in (
            ("role", 1024), ("note", 4096), ("rights_note", 4096)
        ):
            _text(added, key, f"persisted added source {added_id}", maximum)
    if sources[1:] != expected_added:
        raise ValueError("DAW return added-source provenance is invalid")
    external = metadata.get("external_render")
    if (
        not isinstance(external, dict)
        or external.get("tool") != recipe.get("tool")
        or external.get("operator") != recipe.get("operator")
        or external.get("changes") != recipe.get("changes")
        or external.get("unknowns") != recipe.get("unknowns")
        or external.get("copied_without_conversion") is not True
        or external.get("reproducible_by_eprs") is not False
        or metadata.get("title") != recipe.get("title")
        or metadata.get("intent") != recipe.get("intent")
    ):
        raise ValueError("DAW return external-render disclosure is inconsistent")
    warnings = metadata.get("warnings")
    expected_warnings = [
        "This mix was rendered by an external audio tool; EPRS preserves its declarations and bytes but cannot reproduce undisclosed tool state.",
        *(f"Unresolved DAW-return unknown: {item}" for item in recipe["unknowns"]),
    ]
    if warnings != expected_warnings:
        raise ValueError("DAW return warnings are invalid")
    verification = metadata.get("verification")
    if not isinstance(verification, dict) or any(
        verification.get(key) is not True
        for key in (
            "lossless_codec", "checksum_preserved", "known_duration",
            "mono_or_stereo", "timeline_origin_declared",
        )
    ):
        raise ValueError("DAW return verification record is invalid")
    authority = metadata.get("authority")
    if not isinstance(authority, dict) or any(authority.get(key) is not False for key in (
        "creative_approval_inferred", "final_promotion", "upload_authorized",
        "publication_authorized",
    )):
        raise ValueError("DAW return authority record is invalid")
    _approval(metadata, require_approval)
    return mix_path, sidecar, metadata


def capture_daw_return(spec: str | Path, song: str | Path) -> tuple[Path, Path, dict]:
    """Copy one external lossless mix into the song without rewriting its audio."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid DAW return JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != DAW_RETURN_SCHEMA:
        raise ValueError(f"unsupported DAW return schema: {score.get('schema')}")
    title = _text(score, "title", "spec", 1024)
    intent = _text(score, "intent", "spec")
    operator = _text(score, "operator", "spec", 1024)
    rights_note = _text(score, "rights_note", "spec")
    timeline_origin = score.get("timeline_origin")
    if timeline_origin != "package-time-zero":
        raise ValueError("DAW return timeline_origin must be package-time-zero")
    tool_value = score.get("tool")
    if not isinstance(tool_value, dict):
        raise ValueError("DAW return tool must be an object")
    tool = {
        "name": _text(tool_value, "name", "tool", 1024),
        "version": _text(tool_value, "version", "tool", 1024),
        "session_format": _text(tool_value, "session_format", "tool", 1024),
    }
    changes = _changes(score.get("changes"))
    unknowns = _string_list(score.get("unknowns", []), "unknowns", MAX_UNKNOWNS)
    package_path, package = verify_daw_interchange(
        song_path,
        score.get("interchange_package", ""),
        verify_checksums=True,
        verify_media=True,
    )
    package_manifest = package_path / "interchange.json"
    source_mix = package["recipe"]["source_mix"]
    original_mix_path = _song_file(song_path, source_mix.get("path"), "parent mix")
    if sha256(original_mix_path) != source_mix.get("sha256"):
        raise ValueError("DAW return parent mix is missing or changed")
    added_sources = _added_sources(song_path, score.get("added_sources"), source_mix)
    returned_value = score.get("returned_mix")
    if not isinstance(returned_value, str) or not returned_value:
        raise ValueError("DAW return requires returned_mix")
    returned_path = Path(returned_value).expanduser().resolve()
    if not returned_path.is_file():
        raise FileNotFoundError(returned_path)
    returned_digest = sha256(returned_path)
    _, stream, duration, sample_rate, channels = _lossless_audio(returned_path)
    returned_audio = {
        "original_name": returned_path.name,
        "sha256": returned_digest,
        "codec": stream.get("codec_name"),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_seconds": duration,
    }
    recipe = {
        "schema": DAW_RETURN_SCHEMA,
        "title": title,
        "intent": intent,
        "operator": operator,
        "tool": tool,
        "timeline_origin": timeline_origin,
        "source_interchange": {
            "path": str(package_path.relative_to(song_path)),
            "package_id": package["package_id"],
            "manifest_sha256": sha256(package_manifest),
        },
        "source_mix": source_mix,
        "returned_audio": returned_audio,
        "changes": changes,
        "unknowns": unknowns,
        "added_sources": added_sources,
        "rights_note": rights_note,
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("DAW return title must contain at least one letter or number")
    suffix = returned_path.suffix.lower() or ".wav"
    destination_dir = song_path / "mixes" / "daw-return" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}{suffix}"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        existing_path, existing_sidecar, existing = verify_daw_return_mix(song_path, destination)
        if existing.get("recipe_id") != recipe_id:
            raise FileExistsError(f"DAW return destination has different provenance: {destination}")
        return existing_path, existing_sidecar, existing
    temporary = destination.with_name(f".{destination.name}.partial")
    sidecar_temporary = sidecar.with_name(f".{sidecar.name}.partial")
    if temporary.exists() or sidecar_temporary.exists():
        raise FileExistsError(f"Incomplete DAW return capture exists beside: {destination}")
    shutil.copy2(returned_path, temporary)
    try:
        if sha256(temporary) != returned_digest:
            raise RuntimeError("DAW return copy verification failed")
        output_probe, output_stream, output_duration, output_rate, output_channels = _lossless_audio(temporary)
        if (
            output_stream.get("codec_name") != returned_audio["codec"]
            or output_rate != sample_rate
            or output_channels != channels
            or abs(output_duration - duration) > 0.001
        ):
            raise RuntimeError("DAW return copy media properties changed")
        sources = [{
            "id": "parent-mix",
            "role": "source DAW interchange reference mix",
            "path": source_mix["path"],
            "sha256": source_mix["sha256"],
        }, *added_sources]
        warnings = [
            "This mix was rendered by an external audio tool; EPRS preserves its declarations and bytes but cannot reproduce undisclosed tool state."
        ]
        warnings.extend(f"Unresolved DAW-return unknown: {item}" for item in unknowns)
        metadata = {
            "schema": DAW_RETURN_MIX_SCHEMA,
            "recipe_id": recipe_id,
            "captured_at": utc_now(),
            "title": title,
            "intent": intent,
            "recipe": recipe,
            "sources": sources,
            "external_render": {
                "tool": tool,
                "operator": operator,
                "copied_without_conversion": True,
                "reproducible_by_eprs": False,
                "changes": changes,
                "unknowns": unknowns,
            },
            "output": {
                "path": str(destination.relative_to(song_path)),
                "sha256": returned_digest,
                "probe": output_probe,
            },
            "verification": {
                "lossless_codec": True,
                "checksum_preserved": True,
                "known_duration": True,
                "mono_or_stereo": True,
                "timeline_origin_declared": True,
            },
            "warnings": warnings,
            "review": {
                "decision": "not recorded by capture",
                "listening_notes": [],
            },
            "authority": {
                "creative_approval_inferred": False,
                "final_promotion": False,
                "upload_authorized": False,
                "publication_authorized": False,
            },
        }
        sidecar_temporary.write_text(json.dumps(metadata, indent=2) + "\n")
        temporary.replace(destination)
        sidecar_temporary.replace(sidecar)
    except Exception:
        temporary.unlink(missing_ok=True)
        sidecar_temporary.unlink(missing_ok=True)
        raise
    return verify_daw_return_mix(song_path, destination)
