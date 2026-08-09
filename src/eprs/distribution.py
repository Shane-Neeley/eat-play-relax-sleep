"""Approval-gated, distributor-ready streaming handoff packages."""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil

from .clearance import approved_clearance_coverage, recording_session_matches, verify_recording_clearance
from .lineage import trace_audio_lineage
from .master import verify_master_provenance
from .system import load_song_manifest, probe, sha256, slugify, utc_now


DISTRIBUTION_SCHEMA = "eprs.distribution/v1"
DISTRIBUTION_PACKAGE_SCHEMA = "eprs.distribution-package/v1"
DESTINATIONS = {"spotify", "apple-music"}
RELEASE_TYPES = {"single", "ep", "album"}
EXPLICIT_VALUES = {"not-explicit", "explicit", "clean"}
ISRC_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$")


def _text(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"distribution requires {key}")
    return value.strip()


def _relative_file(song: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or Path(value).is_absolute():
        raise ValueError(f"distribution {label} must be a song-relative path")
    path = (song / value).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"distribution {label} escapes the song workspace") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _credits(value: object) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("distribution requires at least one credit")
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"distribution credit {index} must be an object")
        result.append({"name": _text(item, "name"), "role": _text(item, "role")})
    return result


def _date(value: object, key: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"distribution {key} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError(f"distribution {key} must use YYYY-MM-DD") from exc


def _public_recording_clearance(song: Path, master: Path, values: object) -> tuple[dict, list[Path]]:
    """Require public clearance for every session-linked raw recording in the master."""
    lineage = trace_audio_lineage(song, master)
    raw_paths = {item["path"] for item in lineage["raw_recordings"]}
    matches = recording_session_matches(song, raw_paths)
    if values is None:
        values = []
    if not isinstance(values, list) or not all(isinstance(item, str) and item for item in values):
        raise ValueError("distribution clearances must be recording-clearance paths")
    records = [verify_recording_clearance(song, item) for item in values]
    if len({path.resolve() for path, _ in records}) != len(records):
        raise ValueError("distribution clearances must be unique")

    coverage: dict[tuple[str, str], list[tuple[Path, dict, dict]]] = {}
    for path, record in records:
        for take_id, take in approved_clearance_coverage(record, "public").items():
            coverage.setdefault((record["session"]["path"], take_id), []).append((path, record, take))

    resolved = []
    used: set[Path] = set()
    for raw_path in sorted(raw_paths):
        candidates = matches.get(raw_path, [])
        if not candidates:
            raise ValueError(
                f"distribution raw recording requires a verified recording session and public clearance: {raw_path}"
            )
        accepted = None
        for candidate in candidates:
            for clearance_path, clearance, take in coverage.get(
                (candidate["session_path"], candidate["take_id"]), []
            ):
                participants = take["participants"]
                if all(
                    isinstance(participants.get(participant_id), dict)
                    and participants[participant_id].get("decision") == "approved"
                    for participant_id in candidate["participant_ids"]
                ):
                    accepted = {
                        "raw_path": raw_path,
                        "session_path": candidate["session_path"],
                        "take_id": candidate["take_id"],
                        "clearance_id": clearance["clearance_id"],
                        "clearance_path": str(clearance_path.relative_to(song.resolve())),
                    }
                    used.add(clearance_path.resolve())
                    break
            if accepted:
                break
        if not accepted:
            raise ValueError(f"distribution requires approved public clearance for raw recording: {raw_path}")
        resolved.append(accepted)
    unused = [str(path.relative_to(song.resolve())) for path, _ in records if path.resolve() not in used]
    if unused:
        raise ValueError(f"distribution clearance does not cover a used take: {', '.join(unused)}")
    return {"audio_lineage": lineage, "recording_coverage": resolved}, [path for path, _ in records]


def package_distribution(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    """Create one local DSP handoff without contacting a distributor or platform."""
    song_path = Path(song)
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid distribution JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != DISTRIBUTION_SCHEMA:
        raise ValueError(f"unsupported distribution schema: {score.get('schema')}")

    title = _text(score, "title")
    artist = _text(score, "artist")
    release_type = score.get("release_type", "single")
    if release_type not in RELEASE_TYPES:
        raise ValueError("distribution release_type must be single, ep, or album")
    destinations = score.get("destinations")
    if (
        not isinstance(destinations, list)
        or not destinations
        or not all(item in DESTINATIONS for item in destinations)
        or len(destinations) != len(set(destinations))
    ):
        raise ValueError("distribution destinations must uniquely select spotify and/or apple-music")
    explicit = score.get("explicit")
    if explicit not in EXPLICIT_VALUES:
        raise ValueError("distribution explicit must be not-explicit, explicit, or clean")
    credits = _credits(score.get("credits"))
    rights = score.get("rights")
    if not isinstance(rights, dict) or rights.get("confirmed") is not True:
        raise ValueError("distribution rights.confirmed must be true after human rights review")
    normalized_rights = {
        "confirmed": True,
        "copyright": _text(rights, "copyright"),
        "phonographic_copyright": _text(rights, "phonographic_copyright"),
        "note": _text(rights, "note"),
    }

    master_value = score.get("approved_master")
    if not isinstance(master_value, str) or Path(master_value).is_absolute():
        raise ValueError("distribution approved_master must be song-relative")
    master, master_sidecar, master_record = verify_master_provenance(
        song_path, master_value, require_approval=True
    )
    artwork = _relative_file(song_path, score.get("artwork"), "artwork")
    if artwork.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("distribution artwork must be JPEG or PNG")
    artwork_probe = probe(artwork)
    stream = next((item for item in artwork_probe.get("streams", []) if item.get("codec_type") == "video"), None)
    width = int(stream.get("width", 0)) if stream else 0
    height = int(stream.get("height", 0)) if stream else 0
    if width != height or width < 3000:
        raise ValueError("distribution artwork must be square and at least 3000x3000 pixels")

    identifiers = score.get("identifiers", {})
    if not isinstance(identifiers, dict):
        raise ValueError("distribution identifiers must be an object")
    isrc = identifiers.get("isrc") or None
    upc = identifiers.get("upc") or None
    if isrc is not None and (not isinstance(isrc, str) or not ISRC_PATTERN.fullmatch(isrc.upper())):
        raise ValueError("distribution ISRC must be a 12-character ISRC or null")
    if upc is not None and (not isinstance(upc, str) or not upc.isdigit() or len(upc) not in {12, 13, 14}):
        raise ValueError("distribution UPC/EAN must contain 12, 13, or 14 digits or be null")

    lyrics = None
    if score.get("lyrics") is not None:
        lyrics = _relative_file(song_path, score.get("lyrics"), "lyrics")
    clearance_evidence, clearance_paths = _public_recording_clearance(
        song_path, master, score.get("clearances")
    )
    metadata = {
        "title": title,
        "artist": artist,
        "release_type": release_type,
        "version": score.get("version") or None,
        "genre": _text(score, "genre"),
        "language": _text(score, "language"),
        "explicit": explicit,
        "label": _text(score, "label"),
        "release_date": _date(score.get("release_date"), "release_date"),
        "original_release_date": _date(score.get("original_release_date"), "original_release_date"),
        "credits": credits,
        "rights": normalized_rights,
        "identifiers": {"isrc": isrc.upper() if isinstance(isrc, str) else None, "upc": upc},
        "destinations": destinations,
    }
    sources = {
        "master": {
            "path": str(master.relative_to(song_path.resolve())),
            "sha256": sha256(master),
            "provenance_path": str(master_sidecar.relative_to(song_path.resolve())),
            "provenance_sha256": sha256(master_sidecar),
            "recipe_id": master_record.get("recipe_id"),
        },
        "artwork": {
            "path": str(artwork.relative_to(song_path.resolve())),
            "sha256": sha256(artwork),
            "width": width,
            "height": height,
        },
    }
    if lyrics:
        sources["lyrics"] = {"path": str(lyrics.relative_to(song_path.resolve())), "sha256": sha256(lyrics)}
    recipe = {
        "schema": DISTRIBUTION_SCHEMA,
        "metadata": metadata,
        "sources": sources,
        **clearance_evidence,
    }
    package_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("distribution title must contain a letter or number")
    final_root = song_path / "FINAL"
    destination = final_root / f"{title_slug}-dsp-{package_id[:10]}"
    manifest_path = destination / "release.json"
    if destination.exists():
        if not manifest_path.is_file():
            raise FileExistsError(f"DSP package exists without manifest: {destination}")
        existing = json.loads(manifest_path.read_text())
        if existing.get("package_id") == package_id:
            for artifact in existing.get("artifacts", []):
                path = song_path / artifact.get("path", "")
                if not path.is_file() or sha256(path) != artifact.get("sha256"):
                    raise FileExistsError(f"DSP package artifact has changed: {path}")
            return destination, manifest_path
        raise FileExistsError(f"DSP package destination has different provenance: {destination}")

    temporary = final_root / f".{title_slug}-dsp-{package_id[:10]}.partial"
    if temporary.exists():
        raise FileExistsError(f"Incomplete DSP package exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        copies: list[tuple[Path, str]] = []
        master_copy = temporary / f"{title_slug}-master.wav"
        artwork_copy = temporary / f"{title_slug}-artwork{artwork.suffix.lower()}"
        shutil.copy2(master, master_copy)
        shutil.copy2(artwork, artwork_copy)
        copies.extend([(master_copy, "approved lossless master"), (artwork_copy, "release artwork")])
        if lyrics:
            lyrics_copy = temporary / f"{title_slug}-lyrics{lyrics.suffix.lower()}"
            shutil.copy2(lyrics, lyrics_copy)
            copies.append((lyrics_copy, "lyrics"))
        if clearance_paths:
            clearances_dir = temporary / "clearances"
            clearances_dir.mkdir()
            for index, source in enumerate(clearance_paths, start=1):
                copy = clearances_dir / f"clearance-{index}-{source.name}"
                shutil.copy2(source, copy)
                copies.append((copy, "recording clearance"))

        metadata_path = temporary / "metadata.json"
        metadata_path.write_text(json.dumps({**metadata, "submitted": False, "distributed": False}, indent=2) + "\n")
        copies.append((metadata_path, "distributor metadata"))
        handoff = temporary / "HANDOFF.md"
        handoff.write_text(
            f"# {title} — streaming handoff\n\n"
            f"Artist: {artist}\n\nDestinations: {', '.join(destinations)}\n\n"
            "This package was prepared and verified locally. It has not been submitted or distributed. "
            "Spotify and Apple Music delivery still requires a distributor account, its current metadata "
            "forms, a human rights check, and separate authorization.\n"
        )
        copies.append((handoff, "human handoff notes"))

        artifacts = []
        for path, role in copies:
            source_digest = None
            if path == master_copy:
                source_digest = sources["master"]["sha256"]
            elif path == artwork_copy:
                source_digest = sources["artwork"]["sha256"]
            elif lyrics and role == "lyrics":
                source_digest = sources["lyrics"]["sha256"]
            if source_digest and sha256(path) != source_digest:
                raise RuntimeError(f"DSP {role} copy verification failed")
            artifacts.append({
                "role": role,
                "path": str((destination / path.relative_to(temporary)).relative_to(song_path)),
                "sha256": sha256(path),
            })
        manifest = {
            "schema": DISTRIBUTION_PACKAGE_SCHEMA,
            "package_id": package_id,
            "packaged_at": utc_now(),
            "recipe": recipe,
            "artifacts": artifacts,
            "verification": {
                "approved_master": True,
                "artwork_dimensions": True,
                "rights_confirmed": True,
                "public_recording_clearance": True,
                "copies_match": True,
            },
            "distribution": {"submitted": False, "distributed": False, "distributor": None},
        }
        (temporary / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination, manifest_path
