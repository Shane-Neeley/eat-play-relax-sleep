"""Offline publication handoffs and append-only external-state receipts."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, urlparse

from .system import load_song_manifest, sha256, slugify, utc_now


HANDOFF_SCHEMA = "eprs.youtube-publication-handoff/v1"
RECEIPT_SPEC_SCHEMA = "eprs.youtube-publication-receipt/v1"
RECEIPT_SCHEMA = "eprs.youtube-publication-receipt-record/v1"
PUBLICATION_LIST_SCHEMA = "eprs.publication-list/v1"
RELEASE_SCHEMA = "eprs.release-package/v1"
VISIBILITY_RANK = {"private": 0, "unlisted": 1, "public": 2}
PLATFORM_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def _digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _text(record: dict, key: str, maximum: int = 8192) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"publication receipt requires {key}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"publication receipt {key} is limited to {maximum} characters")
    return clean


def _moment(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO 8601 date-time with a timezone")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO 8601 date-time with a timezone") from exc
    if moment.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def _publication_lock(root: Path):
    lock = root / ".publication.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(
            f"Publication history is locked by another process: {lock}. "
            "Inspect the handoff before removing a stale lock."
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} created_at={utc_now()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _resolve_release(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    elif "/" in str(value):
        candidate = (song / requested).resolve()
    else:
        candidate = (song / "FINAL" / requested).resolve()
    if candidate.is_dir():
        candidate = candidate / "release.json"
    try:
        candidate.relative_to((song / "FINAL").resolve())
    except ValueError as exc:
        raise ValueError("publication release must be inside the song FINAL directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_release_package(
    song: str | Path,
    value: str | Path,
    *,
    verify_artifacts: bool = True,
) -> tuple[Path, dict, dict[str, object]]:
    """Verify one immutable FINAL package and its upload-facing artifacts."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    manifest_path = _resolve_release(song_path, value)
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid FINAL release JSON: {manifest_path}: {exc.msg}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != RELEASE_SCHEMA:
        raise ValueError("unsupported FINAL release schema")
    recipe = manifest.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("FINAL release recipe is invalid")
    release_id = _digest(recipe)
    if manifest.get("release_id") != release_id or not manifest_path.parent.name.endswith(release_id[:10]):
        raise ValueError("FINAL release id does not match its recipe")
    verification = manifest.get("verification")
    if not isinstance(verification, dict) or not verification or not all(verification.values()):
        raise ValueError("FINAL release verification is incomplete")
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("uploaded") is not False or publication.get("published") is not False:
        raise ValueError("FINAL release manifest must remain an unpublished local handoff")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("FINAL release requires artifacts")
    by_role: dict[str, list[dict]] = {}
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            raise ValueError(f"FINAL release artifact {index} is invalid")
        role = artifact.get("role")
        path_value = artifact.get("path")
        if not isinstance(role, str) or not isinstance(path_value, str):
            raise ValueError(f"FINAL release artifact {index} requires role and path")
        artifact_path = (song_path / path_value).resolve()
        try:
            artifact_path.relative_to(manifest_path.parent.resolve())
        except ValueError as exc:
            raise ValueError(f"FINAL release artifact escapes its package: {path_value}") from exc
        if not artifact_path.is_file():
            raise FileNotFoundError(artifact_path)
        if verify_artifacts and artifact.get("sha256") != sha256(artifact_path):
            raise ValueError(f"FINAL release artifact checksum has changed: {path_value}")
        by_role.setdefault(role, []).append({**artifact, "resolved_path": artifact_path})
    required = {}
    for role in ("approved YouTube video", "YouTube metadata"):
        records = by_role.get(role, [])
        if len(records) != 1:
            raise ValueError(f"FINAL release requires exactly one {role} artifact")
        required[role] = records[0]
    optional_single = (
        "YouTube asset bundle manifest",
        "approved YouTube thumbnail",
        "YouTube chapters",
    )
    optional_present = any(by_role.get(role) for role in optional_single) or bool(
        by_role.get("YouTube captions")
    )
    if optional_present:
        for role in optional_single:
            records = by_role.get(role, [])
            if len(records) != 1:
                raise ValueError(f"FINAL release requires exactly one {role} artifact when assets are present")
            required[role] = records[0]
        caption_records = by_role.get("YouTube captions", [])
        if not caption_records:
            raise ValueError("FINAL release requires at least one YouTube captions artifact when assets are present")
        languages = [record.get("language") for record in caption_records]
        if (
            not all(isinstance(language, str) and language for language in languages)
            or len(languages) != len(set(language.casefold() for language in languages))
        ):
            raise ValueError("FINAL release YouTube caption languages are invalid or duplicated")
        required["YouTube captions"] = caption_records
    return manifest_path, manifest, required


def _metadata(artifact: dict) -> dict:
    path = artifact["resolved_path"]
    try:
        metadata = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid YouTube metadata JSON: {path}: {exc.msg}") from exc
    if not isinstance(metadata, dict):
        raise ValueError("YouTube metadata must be an object")
    for key in ("title", "description", "visibility_intent"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"YouTube metadata requires {key}")
    tags = metadata.get("tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags):
        raise ValueError("YouTube metadata tags must be non-empty strings")
    visibility = metadata["visibility_intent"]
    if visibility not in VISIBILITY_RANK:
        raise ValueError("YouTube metadata visibility must be private, unlisted, or public")
    if metadata.get("uploaded") is not False or metadata.get("published") is not False:
        raise ValueError("YouTube metadata must remain an unuploaded local handoff")
    title = metadata["title"].strip()
    description = metadata["description"].strip()
    normalized_tags = [tag.strip() for tag in tags]
    if len(title) > 100 or "<" in title or ">" in title:
        raise ValueError("YouTube metadata title exceeds 100 characters or contains < or >")
    if len(description.encode("utf-8")) > 5000 or "<" in description or ">" in description:
        raise ValueError("YouTube metadata description exceeds 5000 UTF-8 bytes or contains < or >")
    tag_characters = sum(len(tag) + (2 if " " in tag else 0) for tag in normalized_tags)
    tag_characters += max(0, len(normalized_tags) - 1)
    if tag_characters > 500:
        raise ValueError("YouTube metadata tags exceed the 500-character API limit")
    normalized = {
        "title": title,
        "description": description,
        "tags": normalized_tags,
        "visibility_intent": visibility,
    }
    asset_keys = ("asset_bundle", "thumbnail", "caption_tracks", "chapters", "accessibility_note")
    present = [key for key in asset_keys if key in metadata]
    if present and len(present) != len(asset_keys):
        raise ValueError("YouTube metadata upload assets are incomplete")
    if present:
        if not isinstance(metadata["asset_bundle"], dict):
            raise ValueError("YouTube metadata asset_bundle must be an object")
        thumbnail = metadata["thumbnail"]
        if (
            not isinstance(thumbnail, dict)
            or not isinstance(thumbnail.get("alt_text"), str)
            or not thumbnail["alt_text"].strip()
        ):
            raise ValueError("YouTube metadata thumbnail requires alt_text")
        tracks = metadata["caption_tracks"]
        if not isinstance(tracks, list) or not tracks:
            raise ValueError("YouTube metadata caption_tracks must be a non-empty list")
        chapters = metadata["chapters"]
        if not isinstance(chapters, dict) or not isinstance(chapters.get("entries"), list):
            raise ValueError("YouTube metadata chapters are invalid")
        if not isinstance(metadata["accessibility_note"], str) or not metadata["accessibility_note"].strip():
            raise ValueError("YouTube metadata accessibility_note is required")
        normalized.update({key: metadata[key] for key in asset_keys})
    return normalized


def _upload_assets(artifacts: dict[str, object], metadata: dict) -> list[dict]:
    """Normalize optional upload files and cross-check metadata path/checksum references."""
    bundle = artifacts.get("YouTube asset bundle manifest")
    if bundle is None:
        if any(key in metadata for key in ("asset_bundle", "thumbnail", "caption_tracks", "chapters")):
            raise ValueError("YouTube metadata references upload assets missing from FINAL")
        return []
    thumbnail = artifacts["approved YouTube thumbnail"]
    chapters = artifacts["YouTube chapters"]
    captions = artifacts["YouTube captions"]
    assert isinstance(bundle, dict)
    assert isinstance(thumbnail, dict)
    assert isinstance(chapters, dict)
    assert isinstance(captions, list)
    expected_bundle = {key: bundle[key] for key in ("path", "sha256")}
    declared_bundle = metadata.get("asset_bundle")
    if not isinstance(declared_bundle, dict) or any(
        declared_bundle.get(key) != value for key, value in expected_bundle.items()
    ):
        raise ValueError("YouTube metadata asset_bundle does not match FINAL")
    expected_thumbnail = {key: thumbnail[key] for key in ("path", "sha256")}
    declared_thumbnail = metadata.get("thumbnail")
    if not isinstance(declared_thumbnail, dict) or any(
        declared_thumbnail.get(key) != value for key, value in expected_thumbnail.items()
    ):
        raise ValueError("YouTube metadata thumbnail does not match FINAL")
    expected_chapters = {key: chapters[key] for key in ("path", "sha256")}
    declared_chapters = metadata.get("chapters")
    if not isinstance(declared_chapters, dict) or any(
        declared_chapters.get(key) != value for key, value in expected_chapters.items()
    ):
        raise ValueError("YouTube metadata chapters do not match FINAL")
    declared_tracks = metadata.get("caption_tracks")
    if not isinstance(declared_tracks, list) or len(declared_tracks) != len(captions):
        raise ValueError("YouTube metadata caption_tracks do not match FINAL")
    declared_by_language = {
        item.get("language", "").casefold(): item
        for item in declared_tracks
        if isinstance(item, dict) and isinstance(item.get("language"), str)
    }
    if len(declared_by_language) != len(captions):
        raise ValueError("YouTube metadata caption languages do not match FINAL")
    normalized = [{"role": "asset bundle", **expected_bundle}]
    normalized.append({"role": "thumbnail", **expected_thumbnail})
    normalized.append({"role": "chapters", **expected_chapters})
    for caption in captions:
        language = caption["language"]
        declared = declared_by_language.get(language.casefold())
        expected = {key: caption[key] for key in ("path", "sha256")}
        if not isinstance(declared, dict) or any(
            declared.get(key) != value for key, value in expected.items()
        ):
            raise ValueError(f"YouTube metadata caption track does not match FINAL: {language}")
        normalized.append({
            "role": "captions",
            "language": language,
            "label": caption.get("label"),
            **expected,
        })
    return normalized


def prepare_publication_handoff(
    song: str | Path,
    release: str | Path,
) -> Path:
    """Prepare exact offline uploader inputs without authorizing or performing upload."""
    song_path = Path(song).resolve()
    release_path, release_manifest, artifacts = verify_release_package(song_path, release)
    video = artifacts["approved YouTube video"]
    metadata_artifact = artifacts["YouTube metadata"]
    assert isinstance(video, dict)
    assert isinstance(metadata_artifact, dict)
    youtube_metadata = _metadata(metadata_artifact)
    upload_assets = _upload_assets(artifacts, youtube_metadata)
    recipe = {
        "release": {
            "release_id": release_manifest["release_id"],
            "path": str(release_path.relative_to(song_path)),
            "sha256": sha256(release_path),
        },
        "platform": "youtube",
        "video": {key: video[key] for key in ("path", "sha256")},
        "metadata_artifact": {
            key: metadata_artifact[key] for key in ("path", "sha256")
        },
        "metadata": youtube_metadata,
        "upload_assets": upload_assets,
    }
    handoff_id = _digest(recipe)
    destination = (
        song_path / "notes" / "publications" / release_manifest["release_id"] / "handoff.json"
    )
    if destination.exists():
        _, existing = verify_publication_handoff(song_path, destination)
        existing_recipe = existing.get("recipe")
        normalized_existing = (
            {**existing_recipe, "upload_assets": existing_recipe.get("upload_assets", [])}
            if isinstance(existing_recipe, dict) else None
        )
        if (
            existing.get("handoff_id") == handoff_id
            and existing_recipe == recipe
        ) or normalized_existing == recipe:
            return destination
        raise FileExistsError(f"Publication handoff has different provenance: {destination}")
    root = destination.parent
    temporary = root.with_name(f".{root.name}.partial")
    if root.exists() or temporary.exists():
        raise FileExistsError(f"Incomplete or conflicting publication handoff exists: {root}")
    temporary.mkdir(parents=True)
    try:
        record = {
            "schema": HANDOFF_SCHEMA,
            "handoff_id": handoff_id,
            "created_at": utc_now(),
            "recipe": recipe,
            "authorization": {
                "upload_authorized": False,
                "publication_authorized": False,
                "statement": (
                    "This handoff identifies exact local inputs only. It does not authorize or "
                    "perform network access, upload, visibility changes, or publication."
                ),
            },
            "receipt_contract": {
                "schema": RECEIPT_SPEC_SCHEMA,
                "required_after_external_upload": [
                    "platform_id", "canonical_url", "visibility", "uploaded_at",
                    "performed_by", "authorization_note",
                ],
            },
        }
        (temporary / "handoff.json").write_text(json.dumps(record, indent=2) + "\n")
        temporary.rename(root)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _resolve_handoff(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    else:
        candidate = (song / requested).resolve()
    if candidate.is_dir():
        candidate = candidate / "handoff.json"
    try:
        candidate.relative_to((song / "notes" / "publications").resolve())
    except ValueError as exc:
        raise ValueError("publication handoff must be inside song notes/publications") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_publication_handoff(
    song: str | Path,
    value: str | Path,
    *,
    verify_artifacts: bool = True,
) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _resolve_handoff(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid publication handoff JSON: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != HANDOFF_SCHEMA:
        raise ValueError("unsupported publication handoff schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or record.get("handoff_id") != _digest(recipe):
        raise ValueError("publication handoff id does not match its recipe")
    authorization = record.get("authorization")
    if (
        not isinstance(authorization, dict)
        or authorization.get("upload_authorized") is not False
        or authorization.get("publication_authorized") is not False
    ):
        raise ValueError("publication handoff authorization boundary has changed")
    release = recipe.get("release")
    if not isinstance(release, dict):
        raise ValueError("publication handoff release evidence is invalid")
    release_path, manifest, artifacts = verify_release_package(
        song_path,
        release.get("path", ""),
        verify_artifacts=verify_artifacts,
    )
    if (
        release.get("release_id") != manifest["release_id"]
        or release.get("sha256") != sha256(release_path)
        or recipe.get("platform") != "youtube"
    ):
        raise ValueError("publication handoff release evidence has changed")
    video = artifacts["approved YouTube video"]
    metadata_artifact = artifacts["YouTube metadata"]
    assert isinstance(video, dict)
    assert isinstance(metadata_artifact, dict)
    if recipe.get("video") != {key: video[key] for key in ("path", "sha256")}:
        raise ValueError("publication handoff video evidence has changed")
    if recipe.get("metadata_artifact") != {
        key: metadata_artifact[key] for key in ("path", "sha256")
    }:
        raise ValueError("publication handoff metadata evidence has changed")
    if recipe.get("metadata") != _metadata(metadata_artifact):
        raise ValueError("publication handoff normalized metadata has changed")
    if recipe.get("upload_assets", []) != _upload_assets(artifacts, recipe["metadata"]):
        raise ValueError("publication handoff upload assets have changed")
    return path, record


def _youtube_url(value: str, platform_id: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "publication receipt canonical_url must be an HTTPS YouTube URL matching platform_id"
        )
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    matches = False
    if host == "youtu.be":
        matches = parsed.path.strip("/") == platform_id
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        matches = parsed.path == "/watch" and parse_qs(parsed.query).get("v") == [platform_id]
    if parsed.scheme != "https" or not matches:
        raise ValueError("publication receipt canonical_url must be an HTTPS YouTube URL matching platform_id")
    return value


def record_publication_receipt(spec: str | Path, song: str | Path) -> Path:
    """Record external YouTube state without performing or claiming authorization for it."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid publication receipt JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict) or score.get("schema") != RECEIPT_SPEC_SCHEMA:
        raise ValueError(f"unsupported publication receipt schema: {score.get('schema')}")
    handoff_path, handoff = verify_publication_handoff(song_path, _text(score, "handoff", 4096))
    platform_id = _text(score, "platform_id", 64)
    if not PLATFORM_ID.fullmatch(platform_id):
        raise ValueError("publication receipt platform_id must use 6 to 64 URL-safe characters")
    canonical_url = _youtube_url(_text(score, "canonical_url", 2048), platform_id)
    visibility = _text(score, "visibility", 20)
    if visibility not in VISIBILITY_RANK:
        raise ValueError("publication receipt visibility must be private, unlisted, or public")
    intended = handoff["recipe"]["metadata"]["visibility_intent"]
    if VISIBILITY_RANK[visibility] > VISIBILITY_RANK[intended]:
        raise ValueError(
            f"publication receipt visibility {visibility} is broader than release intent {intended}"
        )
    uploaded_at = _moment(score.get("uploaded_at"), "publication receipt uploaded_at")
    published_value = score.get("published_at")
    if visibility == "public":
        published_at = _moment(published_value, "publication receipt published_at")
        if published_at < uploaded_at:
            raise ValueError("publication receipt published_at cannot be before uploaded_at")
    elif published_value not in (None, ""):
        raise ValueError("publication receipt published_at is allowed only for public visibility")
    else:
        published_at = None
    recipe = {
        "handoff": {
            "handoff_id": handoff["handoff_id"],
            "path": str(handoff_path.relative_to(song_path)),
            "sha256": sha256(handoff_path),
        },
        "platform": "youtube",
        "platform_id": platform_id,
        "canonical_url": canonical_url,
        "visibility": visibility,
        "uploaded_at": uploaded_at,
        "published_at": published_at,
        "performed_by": _text(score, "performed_by", 512),
        "authorization_note": _text(score, "authorization_note", 4096),
    }
    receipt_id = _digest(recipe)
    root = handoff_path.parent
    receipts = root / "receipts"
    receipts.mkdir(exist_ok=True)
    destination = receipts / f"{slugify(platform_id)}-{receipt_id[:10]}.json"
    with _publication_lock(root):
        for existing_path in receipts.glob("*.json"):
            # The current handoff and FINAL bytes were verified once above;
            # revalidate receipt structure without re-hashing large media per receipt.
            _, existing = verify_publication_receipt(
                song_path, existing_path, verify_artifacts=False
            )
            existing_recipe = existing.get("recipe", {})
            if (
                existing_recipe.get("handoff", {}).get("handoff_id") == handoff["handoff_id"]
                and existing_recipe.get("platform_id") != platform_id
            ):
                raise ValueError(
                    "publication handoff already has a receipt for a different platform_id; "
                    "refuse an unreviewed duplicate upload"
                )
        if destination.exists():
            existing = json.loads(destination.read_text())
            if existing.get("receipt_id") == receipt_id and existing.get("recipe") == recipe:
                return destination
            raise FileExistsError(f"Publication receipt has different provenance: {destination}")
        temporary = destination.with_name(f".{destination.name}.partial")
        if temporary.exists():
            raise FileExistsError(f"Incomplete publication receipt exists: {temporary}")
        record = {
            "schema": RECEIPT_SCHEMA,
            "receipt_id": receipt_id,
            "recorded_at": utc_now(),
            "recipe": recipe,
            "external_state": {
                "uploaded": True,
                "visibility": visibility,
                "published": visibility == "public",
                "platform_id": platform_id,
            },
            "authority": {
                "statement": (
                    "This append-only receipt records caller-declared external state. It does not "
                    "perform an upload or independently prove that authorization was valid."
                ),
            },
        }
        temporary.write_text(json.dumps(record, indent=2) + "\n")
        os.replace(temporary, destination)
    return destination


def _resolve_receipt(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    else:
        candidate = (song / requested).resolve()
    try:
        candidate.relative_to((song / "notes" / "publications").resolve())
    except ValueError as exc:
        raise ValueError("publication receipt must be inside song notes/publications") from exc
    if candidate.parent.name != "receipts":
        raise ValueError("publication receipt must be inside a handoff receipts directory")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_publication_receipt(
    song: str | Path,
    value: str | Path,
    *,
    verify_artifacts: bool = True,
) -> tuple[Path, dict]:
    """Verify one append-only receipt against current handoff and FINAL bytes."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _resolve_receipt(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid publication receipt JSON: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unsupported publication receipt record schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or record.get("receipt_id") != _digest(recipe):
        raise ValueError("publication receipt id does not match its recipe")
    handoff_evidence = recipe.get("handoff")
    if not isinstance(handoff_evidence, dict):
        raise ValueError("publication receipt handoff evidence is invalid")
    handoff_path, handoff = verify_publication_handoff(
        song_path,
        handoff_evidence.get("path", ""),
        verify_artifacts=verify_artifacts,
    )
    if (
        handoff_evidence.get("handoff_id") != handoff["handoff_id"]
        or handoff_evidence.get("sha256") != sha256(handoff_path)
    ):
        raise ValueError("publication receipt handoff evidence has changed")
    platform_id = recipe.get("platform_id")
    if (
        recipe.get("platform") != "youtube"
        or not isinstance(platform_id, str)
        or not PLATFORM_ID.fullmatch(platform_id)
    ):
        raise ValueError("publication receipt platform identity is invalid")
    if recipe.get("canonical_url") != _youtube_url(recipe.get("canonical_url", ""), platform_id):
        raise ValueError("publication receipt canonical URL is not normalized")
    visibility = recipe.get("visibility")
    intended = handoff["recipe"]["metadata"]["visibility_intent"]
    if visibility not in VISIBILITY_RANK or VISIBILITY_RANK[visibility] > VISIBILITY_RANK[intended]:
        raise ValueError("publication receipt visibility exceeds release intent")
    uploaded_at = _moment(recipe.get("uploaded_at"), "publication receipt uploaded_at")
    if recipe.get("uploaded_at") != uploaded_at:
        raise ValueError("publication receipt uploaded_at is not normalized")
    published_at = recipe.get("published_at")
    if visibility == "public":
        normalized_published = _moment(published_at, "publication receipt published_at")
        if published_at != normalized_published or published_at < uploaded_at:
            raise ValueError("publication receipt public timing is invalid")
    elif published_at is not None:
        raise ValueError("publication receipt non-public state cannot include published_at")
    for key in ("performed_by", "authorization_note"):
        if not isinstance(recipe.get(key), str) or not recipe[key].strip():
            raise ValueError(f"publication receipt requires {key}")
    expected_state = {
        "uploaded": True,
        "visibility": visibility,
        "published": visibility == "public",
        "platform_id": platform_id,
    }
    if record.get("external_state") != expected_state:
        raise ValueError("publication receipt external state does not match its recipe")
    return path, record


def publication_status(song: str | Path, *, verify: bool = False) -> dict:
    """Return verified publication continuity without contacting a platform."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = song_path / "notes" / "publications"
    items = []
    errors = []
    if root.is_dir():
        for directory in sorted(
            path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
        ):
            handoff_path = directory / "handoff.json"
            try:
                _, handoff = verify_publication_handoff(
                    song_path, handoff_path, verify_artifacts=verify
                )
            except (FileNotFoundError, ValueError) as exc:
                errors.append({"path": str(handoff_path.relative_to(song_path)), "error": str(exc)})
                continue
            receipts = []
            receipt_root = directory / "receipts"
            if receipt_root.is_dir():
                for receipt_path in sorted(receipt_root.glob("*.json")):
                    try:
                        # The parent handoff was already verified at the requested
                        # depth, so do not hash the same FINAL video once per receipt.
                        _, receipt = verify_publication_receipt(
                            song_path, receipt_path, verify_artifacts=False
                        )
                    except (FileNotFoundError, ValueError) as exc:
                        errors.append({
                            "path": str(receipt_path.relative_to(song_path)),
                            "error": str(exc),
                        })
                        continue
                    recipe = receipt["recipe"]
                    receipts.append({
                        "receipt_id": receipt["receipt_id"],
                        "path": str(receipt_path.relative_to(song_path)),
                        "platform_id": recipe["platform_id"],
                        "canonical_url": recipe["canonical_url"],
                        "visibility": recipe["visibility"],
                        "uploaded_at": recipe["uploaded_at"],
                        "published_at": recipe["published_at"],
                        "performed_by": recipe["performed_by"],
                    })
            items.append({
                "handoff_id": handoff["handoff_id"],
                "path": str(handoff_path.relative_to(song_path)),
                "release_id": handoff["recipe"]["release"]["release_id"],
                "title": handoff["recipe"]["metadata"]["title"],
                "visibility_intent": handoff["recipe"]["metadata"]["visibility_intent"],
                "upload_authorized": False,
                "publication_authorized": False,
                "receipts": receipts,
            })
    receipts = [receipt for item in items for receipt in item["receipts"]]
    return {
        "schema": PUBLICATION_LIST_SCHEMA,
        "generated_at": utc_now(),
        "counts": {
            "handoffs": len(items),
            "receipts": len(receipts),
            "public_receipts": sum(receipt["visibility"] == "public" for receipt in receipts),
            "invalid": len(errors),
        },
        "items": items,
        "errors": errors,
        "network_contacted": False,
    }
