"""Atomic, approval-gated local handoff packaging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from .clearance import (
    approved_clearance_coverage,
    recording_session_matches,
    verify_recording_clearance,
)
from .delivery import verify_youtube_provenance
from .lineage import trace_audio_lineage, validate_external_audio_visibility
from .master import verify_master_provenance
from .quality import verify_creative_quality
from .system import load_song_manifest, sha256, slugify, utc_now
from .youtube_assets import verify_youtube_asset_bundle


RELEASE_SCHEMA = "eprs.release/v1"
RELEASE_MANIFEST_SCHEMA = "eprs.release-package/v1"
VISIBILITY_INTENTS = {"private", "unlisted", "public"}
YOUTUBE_TITLE_CHARACTERS = 100
YOUTUBE_DESCRIPTION_BYTES = 5000
YOUTUBE_TAG_CHARACTERS = 500
DESCRIPTION_ASSEMBLY_POLICY = "append-missing-chapters-and-credits/v1"


def _text(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"release requires {key}")
    return value.strip()


def _portable_path(record: dict, key: str) -> str:
    value = _text(record, key)
    if Path(value).is_absolute():
        raise ValueError(f"release {key} must be relative to the song")
    return value


def _credits(value: object) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("release requires at least one credit")
    credits = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"release credit {index} must be an object")
        name = _text(item, "name")
        role = _text(item, "role")
        note = item.get("note", "")
        if not isinstance(note, str):
            raise ValueError(f"release credit {index} note must be text")
        credits.append({"name": name, "role": role, "note": note.strip()})
    return credits


def _clearances(value: object, song: Path) -> list[tuple[Path, dict]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError("release clearances must be recording-clearance paths")
    records = [verify_recording_clearance(song, item) for item in value]
    resolved = [path.resolve() for path, _ in records]
    if len(resolved) != len(set(resolved)):
        raise ValueError("release clearances must be unique")
    return records


def _verify_youtube_text(title: str, description: str, tags: list[str]) -> None:
    if len(title) > YOUTUBE_TITLE_CHARACTERS or "<" in title or ">" in title:
        raise ValueError("release YouTube title exceeds 100 characters or contains < or >")
    if len(description.encode("utf-8")) > YOUTUBE_DESCRIPTION_BYTES or "<" in description or ">" in description:
        raise ValueError("release assembled YouTube description exceeds 5000 UTF-8 bytes or contains < or >")
    tag_characters = sum(len(tag) + (2 if " " in tag else 0) for tag in tags)
    tag_characters += max(0, len(tags) - 1)
    if tag_characters > YOUTUBE_TAG_CHARACTERS:
        raise ValueError("release YouTube tags exceed the 500-character API limit")


def _has_description_section(description: str, heading: str) -> bool:
    """Return whether a description contains a standalone plain or Markdown heading."""
    expected = heading.casefold()
    for line in description.splitlines():
        candidate = line.strip()
        while candidate.startswith("#"):
            candidate = candidate[1:].lstrip()
        if candidate.rstrip(":").strip().casefold() == expected:
            return True
    return False


def _assemble_youtube_description(
    description: str,
    chapter_text: str,
    credit_text: str,
) -> str:
    """Append reviewed chapter and credit blocks only when the author omitted them."""
    blocks = [description.rstrip()]
    if not _has_description_section(description, "Chapters"):
        blocks.append(f"Chapters\n{chapter_text}")
    if not _has_description_section(description, "Credits"):
        blocks.append(f"Credits\n{credit_text}")
    return "\n\n".join(blocks)


def package_release(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Copy approved media and declared metadata into one immutable FINAL package."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid release JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != RELEASE_SCHEMA:
        raise ValueError(f"unsupported release schema: {score.get('schema')}")
    title = _text(score, "title")
    intent = _text(score, "intent")
    rights_note = _text(score, "rights_note")
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("release title must contain at least one letter or number")
    credits = _credits(score.get("credits"))
    master_value = _portable_path(score, "approved_master")
    video_value = _portable_path(score, "approved_video")
    master, master_sidecar, master_metadata = verify_master_provenance(
        song_path, master_value, require_approval=True,
    )
    video, video_sidecar, video_metadata = verify_youtube_provenance(
        song_path, video_value, require_approval=True,
    )
    video_master = video_metadata.get("master", {})
    if video_master.get("path") != str(master.resolve().relative_to(song_path)):
        raise ValueError("release master is not the approved master used by the YouTube video")
    # Hash large immutable inputs once for this packaging operation. Copies are
    # still hashed independently below, so provenance verification is not
    # weakened and no digest survives beyond this call.
    master_digest = sha256(master)
    video_digest = sha256(video)

    asset_manifest = None
    asset_bundle = None
    youtube_assets_value = score.get("youtube_assets")
    if youtube_assets_value is not None:
        if not isinstance(youtube_assets_value, str) or not youtube_assets_value.strip():
            raise ValueError("release youtube_assets must be a song-relative bundle path")
        if Path(youtube_assets_value).is_absolute():
            raise ValueError("release youtube_assets must be relative to the song")
        asset_manifest, asset_bundle = verify_youtube_asset_bundle(
            song_path, youtube_assets_value, require_approval=True
        )
        asset_video = asset_bundle.get("recipe", {}).get("video", {})
        if (
            asset_video.get("path") != str(video.relative_to(song_path.resolve()))
            or asset_video.get("sha256") != video_digest
        ):
            raise ValueError("release YouTube assets were not reviewed against the approved video")

    youtube = score.get("youtube")
    if not isinstance(youtube, dict):
        raise ValueError("release requires youtube metadata")
    youtube_title = _text(youtube, "title")
    description = _text(youtube, "description")
    visibility = youtube.get("visibility_intent", "private")
    if visibility not in VISIBILITY_INTENTS:
        raise ValueError("release YouTube visibility_intent must be private, unlisted, or public")
    tags_value = youtube.get("tags", [])
    if not isinstance(tags_value, list) or not all(isinstance(tag, str) and tag.strip() for tag in tags_value):
        raise ValueError("release YouTube tags must be non-empty strings")
    tags = [tag.strip() for tag in tags_value]
    if len(tags) != len(set(tag.casefold() for tag in tags)):
        raise ValueError("release YouTube tags must be unique")
    _verify_youtube_text(youtube_title, description, tags)

    quality_report = None
    quality_record = None
    quality_value = score.get("creative_quality")
    if quality_value is not None:
        if not isinstance(quality_value, str) or not quality_value.strip():
            raise ValueError("release creative_quality must be a song-relative report path")
        quality_report, quality_record = verify_creative_quality(song_path, quality_value)

    lineage = trace_audio_lineage(song_path, master)
    validate_external_audio_visibility(lineage, visibility, "release")
    raw_paths = {record["path"] for record in lineage["raw_recordings"]}
    session_matches = recording_session_matches(song_path, raw_paths)
    clearance_records = _clearances(score.get("clearances"), song_path)
    credit_names = {credit["name"].casefold() for credit in credits}
    clearance_evidence = []
    coverage_index: dict[tuple[str, str], list[tuple[dict, dict]]] = {}
    for clearance_path, clearance in clearance_records:
        coverage = approved_clearance_coverage(clearance, visibility)
        session_path = clearance["session"]["path"]
        evidence = {
            "path": str(clearance_path.relative_to(song_path.resolve())),
            "sha256": sha256(clearance_path),
            "clearance_id": clearance["clearance_id"],
            "status": clearance["status"],
            "visibility_limit": clearance["visibility_limit"],
            "session_path": session_path,
            "session_sha256": clearance["session"]["sha256"],
            "covered_take_ids": sorted(coverage),
        }
        clearance_evidence.append(evidence)
        for take_id, covered in coverage.items():
            coverage_index.setdefault((session_path, take_id), []).append((evidence, covered))

    used_clearance_ids: set[str] = set()
    recording_coverage = []
    for raw_path in sorted(raw_paths):
        candidates = session_matches.get(raw_path, [])
        if not candidates:
            raise ValueError(
                f"release raw recording requires a verified recording session and clearance: {raw_path}"
            )
        for candidate in candidates:
            accepted = None
            credit_errors = []
            key = (candidate["session_path"], candidate["take_id"])
            for evidence, covered in coverage_index.get(key, []):
                participant_records = covered["participants"]
                required_credits = []
                participant_ok = True
                for participant_id in candidate["participant_ids"]:
                    participant = participant_records.get(participant_id)
                    if not isinstance(participant, dict) or participant.get("decision") != "approved":
                        participant_ok = False
                        break
                    if participant.get("credit_decision") in {"named", "collective"}:
                        required_credits.append(participant.get("credit"))
                if not participant_ok:
                    continue
                missing_credits = [
                    value for value in required_credits
                    if not isinstance(value, str) or value.casefold() not in credit_names
                ]
                if missing_credits:
                    credit_errors.extend(str(value) for value in missing_credits)
                    continue
                accepted = {
                    "raw_path": raw_path,
                    "session_linked": True,
                    **candidate,
                    "clearance_id": evidence["clearance_id"],
                    "clearance_path": evidence["path"],
                    "required_credits": required_credits,
                }
                used_clearance_ids.add(evidence["clearance_id"])
                break
            if accepted is None:
                if credit_errors:
                    raise ValueError(
                        "release credits do not include clearance-approved wording: "
                        + ", ".join(sorted(set(credit_errors)))
                    )
                raise ValueError(
                    f"release requires approved {visibility} clearance for session-linked raw recording: "
                    f"{raw_path} ({candidate['session_path']} take {candidate['take_id']})"
                )
            recording_coverage.append(accepted)
    unused = [
        record["path"] for record in clearance_evidence
        if record["clearance_id"] not in used_clearance_ids
    ]
    if unused:
        raise ValueError(f"release clearance does not cover a used session take: {', '.join(unused)}")

    # Validate the public creative gate after recording rights so a release with
    # an unresolved raw take reports the actionable clearance failure first.
    if visibility == "public":
        if quality_report is None or quality_record is None:
            raise ValueError(
                "public release requires a verified creative_quality report; "
                "technical approval alone is not a public quality gate"
            )
        human_status = quality_record["human_approval"]["status"]
        if human_status != "approved":
            raise ValueError(
                "public release requires explicit human creative approval; "
                "technical and automated quality checks cannot self-publish"
            )

    # Sidecars are needed only after all semantic and public-release gates pass.
    # Deferring these small hashes preserves actionable gate ordering for callers
    # that provide mocked provenance records while still hashing each input once.
    master_sidecar_digest = sha256(master_sidecar)
    video_sidecar_digest = sha256(video_sidecar)

    sources = {
        "master": {
            "path": str(master.relative_to(song_path.resolve())),
            "sha256": master_digest,
            "provenance_path": str(master_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": master_sidecar_digest,
            "recipe_id": master_metadata.get("recipe_id"),
        },
        "youtube_video": {
            "path": str(video.relative_to(song_path.resolve())),
            "sha256": video_digest,
            "provenance_path": str(video_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": video_sidecar_digest,
            "recipe_id": video_metadata.get("recipe_id"),
        },
    }
    if asset_manifest is not None and asset_bundle is not None:
        sources["youtube_assets"] = {
            "path": str(asset_manifest.relative_to(song_path.resolve())),
            "sha256": sha256(asset_manifest),
            "bundle_id": asset_bundle["bundle_id"],
            "artifacts": [
                {
                    key: artifact[key]
                    for key in ("role", "path", "sha256", "language", "label")
                    if key in artifact
                }
                for artifact in asset_bundle["artifacts"]
            ],
        }
    if quality_report is not None and quality_record is not None:
        sources["creative_quality"] = {
            "path": str(quality_report.relative_to(song_path.resolve())),
            "sha256": sha256(quality_report),
            "schema": quality_record["schema"],
            "decision": quality_record["decision"],
            "auto_publish_eligible": quality_record["auto_publish_eligible"],
            "human_approval": quality_record["human_approval"]["status"],
        }
    recipe = {
        "schema": RELEASE_SCHEMA,
        "title": title,
        "intent": intent,
        "rights_note": rights_note,
        "credits": credits,
        "youtube": {
            "title": youtube_title,
            "description": description,
            "tags": tags,
            "visibility_intent": visibility,
            **(
                {"description_assembly": DESCRIPTION_ASSEMBLY_POLICY}
                if asset_bundle is not None else {}
            ),
        },
        "audio_lineage": lineage,
        "recording_coverage": recording_coverage,
        "clearances": clearance_evidence,
        "sources": sources,
    }
    if quality_report is not None:
        recipe["creative_quality"] = str(quality_report.relative_to(song_path.resolve()))
    release_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    final_root = song_path / "FINAL"
    destination = final_root / f"{title_slug}-{release_id[:10]}"
    manifest_path = destination / "release.json"
    if destination.exists():
        if not manifest_path.is_file():
            raise FileExistsError(f"FINAL release exists without manifest: {destination}")
        existing = json.loads(manifest_path.read_text())
        if existing.get("release_id") == release_id:
            for artifact in existing.get("artifacts", []):
                path = song_path / artifact.get("path", "")
                if not path.is_file() or sha256(path) != artifact.get("sha256"):
                    raise FileExistsError(f"FINAL release artifact has changed: {path}")
            return destination, manifest_path
        raise FileExistsError(f"FINAL release destination has different provenance: {destination}")
    temporary = final_root / f".{title_slug}-{release_id[:10]}.partial"
    if temporary.exists():
        raise FileExistsError(f"Incomplete FINAL release already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        master_copy = temporary / f"{title_slug}-master{master.suffix.lower()}"
        video_copy = temporary / f"{title_slug}-youtube{video.suffix.lower()}"
        shutil.copy2(master, master_copy)
        shutil.copy2(video, video_copy)
        master_copy_digest = sha256(master_copy)
        video_copy_digest = sha256(video_copy)
        if (
            master_copy_digest != sources["master"]["sha256"]
            or video_copy_digest != sources["youtube_video"]["sha256"]
        ):
            raise RuntimeError("FINAL release copy verification failed")
        copied_quality = None
        copied_quality_digest = None
        if quality_report is not None:
            copied_quality = temporary / "creative-quality.json"
            shutil.copy2(quality_report, copied_quality)
            copied_quality_digest = sha256(copied_quality)
            if copied_quality_digest != sources["creative_quality"]["sha256"]:
                raise RuntimeError("FINAL creative quality copy verification failed")
        copied_asset_artifacts = []
        if asset_manifest is not None and asset_bundle is not None:
            asset_dir = temporary / "youtube-assets"
            asset_dir.mkdir()
            bundle_copy = asset_dir / "bundle.json"
            shutil.copy2(asset_manifest, bundle_copy)
            bundle_copy_digest = sha256(bundle_copy)
            if bundle_copy_digest != sources["youtube_assets"]["sha256"]:
                raise RuntimeError("FINAL YouTube asset manifest copy verification failed")
            copied_asset_artifacts.append({
                "source_role": "bundle",
                "role": "YouTube asset bundle manifest",
                "path": bundle_copy,
                "sha256": bundle_copy_digest,
            })
            for artifact in asset_bundle["artifacts"]:
                source = asset_manifest.parent / artifact["path"]
                copy = asset_dir / artifact["path"]
                shutil.copy2(source, copy)
                copy_digest = sha256(copy)
                if copy_digest != artifact["sha256"]:
                    raise RuntimeError("FINAL YouTube asset copy verification failed")
                role = {
                    "thumbnail": "approved YouTube thumbnail",
                    "captions": "YouTube captions",
                    "chapters": "YouTube chapters",
                }[artifact["role"]]
                copied_asset_artifacts.append({
                    "source_role": artifact["role"],
                    "role": role,
                    "path": copy,
                    "sha256": copy_digest,
                    **({"language": artifact["language"], "label": artifact["label"]}
                       if artifact["role"] == "captions" else {}),
                })
        upload_description = description
        asset_metadata = {}
        if asset_bundle is not None:
            chapter_copy = next(
                item for item in copied_asset_artifacts if item["source_role"] == "chapters"
            )
            thumbnail_copy_record = next(
                item for item in copied_asset_artifacts if item["source_role"] == "thumbnail"
            )
            caption_copy_records = [
                item for item in copied_asset_artifacts if item["source_role"] == "captions"
            ]
            chapter_text = chapter_copy["path"].read_text(encoding="utf-8").strip()
            credit_text = "\n".join(
                f"{credit['name']} — {credit['role']}"
                + (f" ({credit['note']})" if credit["note"] else "")
                for credit in credits
            )
            thumbnail_recipe = asset_bundle["recipe"]["thumbnail"]
            natural_history_source = thumbnail_recipe.get("iNaturalist_source")
            if isinstance(natural_history_source, dict):
                photo_credit = (
                    f"{natural_history_source['attribution']} — iNaturalist photo "
                    f"({natural_history_source['license_code'].upper()}): "
                    f"{natural_history_source['observation_url']}"
                )
                credit_text = f"{credit_text}\n{photo_credit}" if credit_text else photo_credit
            upload_description = _assemble_youtube_description(
                description,
                chapter_text,
                credit_text,
            )
            asset_metadata = {
                "asset_bundle": {
                    "bundle_id": asset_bundle["bundle_id"],
                    "path": str((destination / "youtube-assets" / "bundle.json").relative_to(song_path)),
                    "sha256": sources["youtube_assets"]["sha256"],
                },
                "thumbnail": {
                    "path": str((destination / "youtube-assets" / thumbnail_copy_record["path"].name).relative_to(song_path)),
                    "sha256": thumbnail_copy_record["sha256"],
                    "alt_text": thumbnail_recipe["alt_text"],
                    "width": thumbnail_recipe["width"],
                    "height": thumbnail_recipe["height"],
                    **({"iNaturalist_source": natural_history_source}
                       if isinstance(natural_history_source, dict) else {}),
                },
                "caption_tracks": [
                    {
                        "language": item["language"],
                        "label": item["label"],
                        "path": str((destination / "youtube-assets" / item["path"].name).relative_to(song_path)),
                        "sha256": item["sha256"],
                    }
                    for item in caption_copy_records
                ],
                "chapters": {
                    "path": str((destination / "youtube-assets" / chapter_copy["path"].name).relative_to(song_path)),
                    "sha256": chapter_copy["sha256"],
                    "entries": asset_bundle["recipe"]["chapters"],
                },
                "accessibility_note": asset_bundle["recipe"]["accessibility_note"],
            }
        _verify_youtube_text(youtube_title, upload_description, tags)
        metadata_file = temporary / "youtube-metadata.json"
        metadata_file.write_text(json.dumps({
            "title": youtube_title,
            "description": upload_description,
            "tags": tags,
            "visibility_intent": visibility,
            **asset_metadata,
            "uploaded": False,
            "published": False,
        }, indent=2) + "\n")
        notes_file = temporary / "HANDOFF.md"
        credit_lines = "\n".join(
            f"- {credit['name']} — {credit['role']}" + (f" ({credit['note']})" if credit["note"] else "")
            for credit in credits
        )
        clearance_lines = (
            "\n".join(
                f"- `{record['clearance_id']}` — {record['visibility_limit']} maximum; "
                f"takes: {', '.join(record['covered_take_ids'])}"
                for record in clearance_evidence
            )
            if clearance_evidence else
            "- No raw recordings were found in known audio provenance; the declared rights note still requires human review."
        )
        asset_lines = (
            "- Reviewed thumbnail, caption track(s), chapters, and accessibility context are copied under `youtube-assets/`.\n"
            "- `youtube-metadata.json` contains their exact checksums and an upload-ready description."
            if asset_bundle is not None else
            "- No reviewed YouTube publishing-asset bundle was selected for this package."
        )
        notes_file.write_text(
            f"# {title}\n\n{intent}\n\n## Credits\n\n{credit_lines}\n\n"
            f"## Rights note\n\n{rights_note}\n\n"
            f"## Recording clearances\n\n{clearance_lines}\n\n"
            f"## YouTube publishing assets\n\n{asset_lines}\n\n"
            "## Publication\n\nThis package was prepared locally. It has not been uploaded or published.\n"
        )
        artifacts = []
        for path, role, digest in (
            (master_copy, "lossless master", master_copy_digest),
            (video_copy, "approved YouTube video", video_copy_digest),
            (metadata_file, "YouTube metadata", None),
            (notes_file, "human handoff notes", None),
        ):
            artifacts.append({
                "role": role,
                "path": str((destination / path.name).relative_to(song_path)),
                "sha256": digest or sha256(path),
            })
        if copied_quality is not None:
            artifacts.append({
                "role": "creative quality report",
                "path": str((destination / copied_quality.name).relative_to(song_path)),
                "sha256": copied_quality_digest,
            })
        for item in copied_asset_artifacts:
            artifacts.append({
                "role": item["role"],
                "path": str(
                    (destination / "youtube-assets" / item["path"].name).relative_to(song_path)
                ),
                "sha256": item["sha256"],
                **({"language": item["language"], "label": item["label"]}
                   if item["source_role"] == "captions" else {}),
            })
        if clearance_records:
            clearance_dir = temporary / "clearances"
            clearance_dir.mkdir()
            copied_sessions: dict[str, Path] = {}
            for index, (source_path, clearance) in enumerate(clearance_records, start=1):
                clearance_copy = clearance_dir / f"clearance-{index}-{clearance['clearance_id'][:10]}.json"
                shutil.copy2(source_path, clearance_copy)
                if sha256(clearance_copy) != sha256(source_path):
                    raise RuntimeError("FINAL recording-clearance copy verification failed")
                artifacts.append({
                    "role": "recording clearance",
                    "path": str((destination / "clearances" / clearance_copy.name).relative_to(song_path)),
                    "sha256": sha256(clearance_copy),
                })
                session_value = clearance["session"]["path"]
                if session_value not in copied_sessions:
                    session_source = song_path / session_value
                    session_copy = clearance_dir / f"session-{clearance['session']['session_id'][:10]}.json"
                    shutil.copy2(session_source, session_copy)
                    if sha256(session_copy) != clearance["session"]["sha256"]:
                        raise RuntimeError("FINAL recording-session copy verification failed")
                    copied_sessions[session_value] = session_copy
                    artifacts.append({
                        "role": "recording session evidence",
                        "path": str((destination / "clearances" / session_copy.name).relative_to(song_path)),
                        "sha256": sha256(session_copy),
                    })
        manifest = {
            "schema": RELEASE_MANIFEST_SCHEMA,
            "release_id": release_id,
            "packaged_at": utc_now(),
            "recipe": recipe,
            "artifacts": artifacts,
            "verification": {
                "approved_master": True,
                "approved_video": True,
                "youtube_assets": asset_bundle is None or bool(
                    asset_bundle.get("review", {}).get("editorial_and_accessibility_review")
                    == "approved"
                ),
                "copies_match": True,
                "recording_clearance": all(
                    not record["session_linked"] or bool(record["clearance_id"])
                    for record in recording_coverage
                ),
            },
            "publication": {"uploaded": False, "published": False, "platform_id": None},
        }
        (temporary / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination, manifest_path
