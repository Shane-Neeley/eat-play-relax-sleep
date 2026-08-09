"""Versioned recording-session intake with capture and consent context."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from .system import ingest, load_song_manifest, probe, sha256, slugify, utc_now


SESSION_SPEC_SCHEMA = "eprs.recording-session/v1"
SESSION_SCHEMA = "eprs.recording-session-record/v1"
DEFAULT_RIGHTS = "rights and performer permissions not yet confirmed; do not publish"


def _required_text(record: dict, key: str, *, maximum: int = 8192) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"recording session requires {key}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"recording session {key} is limited to {maximum} characters")
    return clean


def _optional_text(record: dict, key: str, *, maximum: int = 8192) -> str:
    value = record.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"recording session {key} must be text")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"recording session {key} is limited to {maximum} characters")
    return clean


def _identifier(record: dict, key: str, kind: str, identifiers: set[str]) -> tuple[str, str]:
    declared = _required_text(record, key, maximum=100)
    identifier = slugify(declared)
    if not identifier or identifier in identifiers:
        raise ValueError(f"recording session {kind} id is empty or duplicated: {declared}")
    identifiers.add(identifier)
    return identifier, declared


def _id_list(record: dict, key: str, kind: str, *, allow_empty: bool) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"recording session {kind} {key} must be a list of ids")
    identifiers = [slugify(item) for item in value]
    if (not allow_empty and not identifiers) or any(not item for item in identifiers):
        raise ValueError(f"recording session {kind} {key} must contain valid ids")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"recording session {kind} {key} must not contain duplicates")
    return identifiers


def _source_path(value: object, song: Path, spec: Path, take_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"recording session take {take_id} requires a path")
    requested = Path(value)
    candidates = [requested] if requested.is_absolute() else [song / requested, spec.parent / requested]
    source = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
    if source is None:
        raise FileNotFoundError(candidates[0])
    return source


def _participants(values: object) -> list[dict]:
    if not isinstance(values, list) or len(values) > 100:
        raise ValueError("recording session participants must be a list of at most 100 items")
    identifiers: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"recording session participant {index} must be an object")
        participant_id, declared_id = _identifier(value, "id", "participant", identifiers)
        records.append({
            "id": participant_id,
            "declared_id": declared_id,
            "role": _required_text(value, "role", maximum=200),
            "credit": _optional_text(value, "credit", maximum=500),
            "consent_note": _required_text(value, "consent_note"),
        })
    return records


def _setups(values: object) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 100:
        raise ValueError("recording session setups must contain 1 to 100 items")
    identifiers: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"recording session setup {index} must be an object")
        setup_id, declared_id = _identifier(value, "id", "setup", identifiers)
        records.append({
            "id": setup_id,
            "declared_id": declared_id,
            "source": _required_text(value, "source", maximum=200),
            "capture_chain": _required_text(value, "capture_chain", maximum=1000),
            "input": _optional_text(value, "input", maximum=500),
            "placement": _optional_text(value, "placement", maximum=1000),
            "monitoring": _optional_text(value, "monitoring", maximum=1000),
        })
    return records


def _takes(
    values: object,
    song: Path,
    spec: Path,
    participant_ids: set[str],
    setup_ids: set[str],
) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 200:
        raise ValueError("recording session takes must contain 1 to 200 items")
    identifiers: set[str] = set()
    source_digests: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"recording session take {index} must be an object")
        take_id, declared_id = _identifier(value, "id", "take", identifiers)
        participants = _id_list(value, "participant_ids", f"take {take_id}", allow_empty=True)
        setups = _id_list(value, "setup_ids", f"take {take_id}", allow_empty=False)
        unknown_participants = set(participants) - participant_ids
        unknown_setups = set(setups) - setup_ids
        if unknown_participants:
            raise ValueError(f"recording session take {take_id} references unknown participants: {', '.join(sorted(unknown_participants))}")
        if unknown_setups:
            raise ValueError(f"recording session take {take_id} references unknown setups: {', '.join(sorted(unknown_setups))}")
        source = _source_path(value.get("path"), song, spec, take_id)
        source_probe = probe(source)
        if not any(stream.get("codec_type") == "audio" for stream in source_probe.get("streams", [])):
            raise ValueError(f"recording session take {take_id} has no readable audio stream")
        rights_note = value.get("rights_note", DEFAULT_RIGHTS)
        if not isinstance(rights_note, str) or not rights_note.strip():
            raise ValueError(f"recording session take {take_id} requires a rights_note")
        if len(rights_note.strip()) > 8192:
            raise ValueError(f"recording session take {take_id} rights_note is limited to 8192 characters")
        source_digest = sha256(source)
        if source_digest in source_digests:
            raise ValueError(
                f"recording session take {take_id} duplicates another take's media; use one take with complete relationships"
            )
        source_digests.add(source_digest)
        records.append({
            "id": take_id,
            "declared_id": declared_id,
            "role": _required_text(value, "role", maximum=200),
            "participant_ids": participants,
            "setup_ids": setups,
            "note": _optional_text(value, "note"),
            "rights_note": rights_note.strip(),
            "source": source,
            "source_sha256": source_digest,
            "source_probe": source_probe,
        })
    return records


def _raw_record(song: Path, source: Path) -> tuple[Path, Path] | None:
    try:
        source.relative_to((song / "recordings" / "raw").resolve())
    except ValueError:
        return None
    sidecar = source.with_suffix(source.suffix + ".json")
    if not sidecar.is_file():
        raise ValueError(f"raw recording lacks provenance sidecar: {source.relative_to(song)}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid recording provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != "eprs.recording/v1" or metadata.get("sha256") != sha256(source):
        raise ValueError(f"raw recording provenance is invalid or changed: {source.relative_to(song)}")
    return source, sidecar


def create_recording_session(spec: str | Path, song: str | Path) -> Path:
    """Preserve a recording day as raw takes plus one atomic context manifest."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid recording session JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != SESSION_SPEC_SCHEMA:
        raise ValueError(f"unsupported recording session schema: {score.get('schema')}")
    title = _required_text(score, "title", maximum=200)
    intent = _required_text(score, "intent")
    captured_at = _required_text(score, "captured_at", maximum=200)
    session_context = {
        "location_note": _optional_text(score, "location_note"),
        "tempo_or_time_reference": _required_text(score, "tempo_or_time_reference", maximum=1000),
        "tuning_or_reference": _optional_text(score, "tuning_or_reference", maximum=1000),
        "room_note": _optional_text(score, "room_note"),
    }
    participants = _participants(score.get("participants", []))
    setups = _setups(score.get("setups"))
    takes = _takes(
        score.get("takes"),
        song_path,
        spec_path,
        {record["id"] for record in participants},
        {record["id"] for record in setups},
    )
    recipe = {
        "schema": SESSION_SPEC_SCHEMA,
        "title": title,
        "intent": intent,
        "captured_at": captured_at,
        **session_context,
        "participants": participants,
        "setups": setups,
        "takes": [{key: value for key, value in record.items() if key not in {"source", "source_probe"}} for record in takes],
    }
    session_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("recording session title must contain a letter or number")
    session_dir = song_path / "notes" / "sessions" / f"{title_slug}-{session_id[:10]}"
    manifest_path = session_dir / "session.json"
    if session_dir.exists():
        if not manifest_path.is_file():
            raise FileExistsError(f"recording session exists without a manifest: {session_dir}")
        existing = json.loads(manifest_path.read_text())
        if existing.get("schema") == SESSION_SCHEMA and existing.get("session_id") == session_id:
            verify_recording_session(song_path, manifest_path)
            return manifest_path
        raise FileExistsError(f"recording session destination has conflicting provenance: {session_dir}")
    temporary = session_dir.with_name(f".{session_dir.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete recording session already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        take_records = {}
        for take in takes:
            if sha256(take["source"]) != take["source_sha256"]:
                raise RuntimeError(f"recording session source changed during intake: {take['source']}")
            raw = _raw_record(song_path, take["source"])
            if raw is None:
                destination, sidecar = ingest(
                    take["source"],
                    song_path,
                    take["role"],
                    f"Recording session {title}: {take['note']}".strip(),
                    rights_note=take["rights_note"],
                )
            else:
                destination, sidecar = raw
            if sha256(destination) != take["source_sha256"]:
                raise RuntimeError(f"recording session take changed while being preserved: {take['source']}")
            take_records[take["id"]] = {
                "id": take["id"],
                "declared_id": take["declared_id"],
                "role": take["role"],
                "participant_ids": take["participant_ids"],
                "setup_ids": take["setup_ids"],
                "note": take["note"],
                "rights_note": take["rights_note"],
                "path": str(destination.relative_to(song_path)),
                "sha256": sha256(destination),
                "provenance_path": str(sidecar.relative_to(song_path)),
                "provenance_sha256": sha256(sidecar),
                "original_name": take["source"].name,
                "probe": take["source_probe"],
            }
        repeated_roles = sorted({
            record["role"] for record in take_records.values()
            if sum(other["role"] == record["role"] for other in take_records.values()) > 1
        })
        suggestions = [
            "Listen to every take and its surrounding silence before selecting or processing it.",
            "Review participant consent, credit wording, and take-level rights before sharing or delivery.",
        ]
        if repeated_roles:
            suggestions.append(
                f"Compare meaningful alternatives before choosing among repeated roles: {', '.join(repeated_roles)}."
            )
        manifest = {
            "schema": SESSION_SCHEMA,
            "session_id": session_id,
            "created_at": utc_now(),
            "title": title,
            "intent": intent,
            "captured_at": captured_at,
            **session_context,
            "participants": {record["id"]: record for record in participants},
            "setups": {record["id"]: record for record in setups},
            "takes": take_records,
            "suggested_next_actions": suggestions,
            "authority": {
                "statement": "This session records capture context and evidence; it does not authorize processing, sharing, uploading, or publishing.",
            },
        }
        (temporary / "session.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(session_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest_path


def resolve_recording_session(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
        if candidate.is_dir():
            candidate = candidate / "session.json"
    else:
        candidate = (song_path / "notes" / "sessions" / str(value) / "session.json").resolve()
    try:
        candidate.relative_to((song_path / "notes" / "sessions").resolve())
    except ValueError as exc:
        raise ValueError("recording session must be inside the song notes/sessions directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_recording_session(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    """Load a session and verify all raw take and provenance checksums."""
    song_path = Path(song).resolve()
    path = resolve_recording_session(song_path, value)
    try:
        session = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid recording session manifest: {path}: {exc.msg}") from exc
    if session.get("schema") != SESSION_SCHEMA:
        raise ValueError("unsupported recording session record schema")
    participants = session.get("participants")
    setups = session.get("setups")
    takes = session.get("takes")
    if not isinstance(participants, dict) or not isinstance(setups, dict) or not isinstance(takes, dict) or not takes:
        raise ValueError("recording session participants, setups, or takes are invalid")
    for participant_id, participant in participants.items():
        if (
            not isinstance(participant, dict)
            or participant.get("id") != participant_id
            or not isinstance(participant.get("consent_note"), str)
            or not participant["consent_note"].strip()
        ):
            raise ValueError(f"recording session participant is invalid: {participant_id}")
    for setup_id, setup in setups.items():
        if (
            not isinstance(setup, dict)
            or setup.get("id") != setup_id
            or not isinstance(setup.get("capture_chain"), str)
            or not setup["capture_chain"].strip()
        ):
            raise ValueError(f"recording session setup is invalid: {setup_id}")
    take_hashes: set[str] = set()
    for take_id, take in takes.items():
        if not isinstance(take, dict) or take.get("id") != take_id:
            raise ValueError(f"recording session take identity is invalid: {take_id}")
        participant_values = take.get("participant_ids")
        setup_values = take.get("setup_ids")
        if not isinstance(participant_values, list) or not all(isinstance(value, str) for value in participant_values):
            raise ValueError(f"recording session take participants are invalid: {take_id}")
        if not isinstance(setup_values, list) or not setup_values or not all(isinstance(value, str) for value in setup_values):
            raise ValueError(f"recording session take setups are invalid: {take_id}")
        if set(participant_values) - set(participants):
            raise ValueError(f"recording session take has unknown participants: {take_id}")
        if set(setup_values) - set(setups):
            raise ValueError(f"recording session take has invalid setups: {take_id}")
        if not isinstance(take.get("rights_note"), str) or not take["rights_note"].strip():
            raise ValueError(f"recording session take rights are invalid: {take_id}")
        media_value = take.get("path")
        provenance_value = take.get("provenance_path")
        media = (song_path / media_value).resolve() if isinstance(media_value, str) else None
        provenance = (song_path / provenance_value).resolve() if isinstance(provenance_value, str) else None
        try:
            if media is None or provenance is None:
                raise ValueError
            media.relative_to((song_path / "recordings" / "raw").resolve())
            provenance.relative_to((song_path / "recordings" / "raw").resolve())
        except ValueError as exc:
            raise ValueError(f"recording session take has unsafe evidence paths: {take_id}") from exc
        if not media.is_file() or take.get("sha256") != sha256(media):
            raise ValueError(f"recording session take is missing or changed: {take_id}")
        if take["sha256"] in take_hashes:
            raise ValueError("recording session contains duplicate take media")
        take_hashes.add(take["sha256"])
        if not provenance.is_file() or take.get("provenance_sha256") != sha256(provenance):
            raise ValueError(f"recording session take provenance is missing or changed: {take_id}")
    recipe = {
        "schema": SESSION_SPEC_SCHEMA,
        "title": session.get("title"),
        "intent": session.get("intent"),
        "captured_at": session.get("captured_at"),
        "location_note": session.get("location_note", ""),
        "tempo_or_time_reference": session.get("tempo_or_time_reference"),
        "tuning_or_reference": session.get("tuning_or_reference", ""),
        "room_note": session.get("room_note", ""),
        "participants": list(participants.values()),
        "setups": list(setups.values()),
        "takes": [{
            "id": take["id"],
            "declared_id": take.get("declared_id"),
            "role": take.get("role"),
            "participant_ids": take["participant_ids"],
            "setup_ids": take["setup_ids"],
            "note": take.get("note", ""),
            "rights_note": take["rights_note"],
            "source_sha256": take.get("sha256"),
        } for take in takes.values()],
    }
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if session.get("session_id") != expected_id or not path.parent.name.endswith(expected_id[:10]):
        raise ValueError("recording session id does not match its normalized contents")
    return path, session


def load_recording_session(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    return verify_recording_session(song, value)
