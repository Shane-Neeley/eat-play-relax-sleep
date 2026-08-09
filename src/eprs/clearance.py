"""Recording-use clearance records for consent-aware delivery gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .session import load_recording_session, verify_recording_session
from .system import load_song_manifest, sha256, slugify, utc_now


CLEARANCE_SPEC_SCHEMA = "eprs.recording-clearance/v1"
CLEARANCE_SCHEMA = "eprs.recording-clearance-record/v1"
DECISIONS = {"approved", "declined", "unknown"}
CREDIT_DECISIONS = {"named", "collective", "anonymous", "no-credit"}
VISIBILITY_RANK = {"private": 0, "unlisted": 1, "public": 2}


def _text(record: dict, key: str, *, required: bool = True, maximum: int = 8192) -> str:
    value = record.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        suffix = "" if required else " must be text"
        raise ValueError(f"recording clearance requires {key}{suffix}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"recording clearance {key} is limited to {maximum} characters")
    return clean


def _ids(value: object, kind: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"recording clearance requires {kind}")
    identifiers = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"recording clearance {kind} entries must be objects")
        declared = _text(item, "id", maximum=100)
        identifier = slugify(declared)
        if not identifier or identifier in identifiers:
            raise ValueError(f"recording clearance {kind} id is empty or duplicated: {declared}")
        identifiers.append(identifier)
    return identifiers


def _decision_fields(record: dict, kind: str) -> dict:
    decision = record.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"recording clearance {kind} decision must be approved, declined, or unknown")
    note = _text(record, "permission_note")
    confirmed_by = _text(record, "confirmed_by", required=False, maximum=500)
    confirmed_at = _text(record, "confirmed_at", required=False, maximum=200)
    if decision == "approved" and (not confirmed_by or not confirmed_at):
        raise ValueError(f"approved recording clearance {kind} requires confirmed_by and confirmed_at")
    return {
        "decision": decision,
        "permission_note": note,
        "confirmed_by": confirmed_by,
        "confirmed_at": confirmed_at,
    }


def _take_records(values: object, session: dict) -> list[dict]:
    identifiers = _ids(values, "takes")
    records = []
    for identifier, value in zip(identifiers, values):
        if identifier not in session["takes"]:
            raise ValueError(f"recording clearance references unknown session take: {identifier}")
        records.append({"id": identifier, **_decision_fields(value, f"take {identifier}")})
    return records


def _participant_records(values: object, expected: set[str], session: dict) -> list[dict]:
    if not expected:
        if values not in (None, []):
            raise ValueError("recording clearance has participants but selected takes have none")
        return []
    if not isinstance(values, list) or not values:
        raise ValueError(
            "recording clearance participant coverage is incomplete: missing "
            + ", ".join(sorted(expected))
        )
    identifiers = _ids(values, "participants")
    if set(identifiers) != expected:
        missing = expected - set(identifiers)
        extra = set(identifiers) - expected
        details = []
        if missing:
            details.append(f"missing {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unexpected {', '.join(sorted(extra))}")
        raise ValueError(f"recording clearance participant coverage is incomplete: {'; '.join(details)}")
    records = []
    for identifier, value in zip(identifiers, values):
        if identifier not in session["participants"]:
            raise ValueError(f"recording clearance references unknown participant: {identifier}")
        fields = _decision_fields(value, f"participant {identifier}")
        credit_decision = value.get("credit_decision")
        if credit_decision not in CREDIT_DECISIONS:
            raise ValueError(
                f"recording clearance participant {identifier} credit_decision must be named, collective, anonymous, or no-credit"
            )
        credit = _text(value, "credit", required=False, maximum=500)
        if credit_decision in {"named", "collective"} and not credit:
            raise ValueError(f"recording clearance participant {identifier} requires approved credit wording")
        records.append({
            "id": identifier,
            **fields,
            "credit_decision": credit_decision,
            "credit": credit,
        })
    return records


def create_recording_clearance(spec: str | Path, song: str | Path) -> Path:
    """Create an immutable clearance claim bound to one exact session record."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid recording clearance JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != CLEARANCE_SPEC_SCHEMA:
        raise ValueError(f"unsupported recording clearance schema: {score.get('schema')}")
    title = _text(score, "title", maximum=200)
    intended_use = _text(score, "intended_use")
    visibility = score.get("visibility_limit")
    if visibility not in VISIBILITY_RANK:
        raise ValueError("recording clearance visibility_limit must be private, unlisted, or public")
    session_value = score.get("session")
    if not isinstance(session_value, str) or not session_value:
        raise ValueError("recording clearance requires session")
    session_path, session = verify_recording_session(song_path, session_value)
    takes = _take_records(score.get("takes"), session)
    expected_participants = {
        participant_id
        for take in takes
        for participant_id in session["takes"][take["id"]]["participant_ids"]
    }
    participants = _participant_records(score.get("participants"), expected_participants, session)
    status = (
        "declined" if any(record["decision"] == "declined" for record in [*takes, *participants])
        else "approved" if all(record["decision"] == "approved" for record in [*takes, *participants])
        else "pending"
    )
    recipe = {
        "schema": CLEARANCE_SPEC_SCHEMA,
        "title": title,
        "intended_use": intended_use,
        "visibility_limit": visibility,
        "session": {
            "path": str(session_path.relative_to(song_path)),
            "sha256": sha256(session_path),
            "session_id": session["session_id"],
        },
        "takes": takes,
        "participants": participants,
    }
    clearance_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("recording clearance title must contain a letter or number")
    destination_dir = song_path / "notes" / "clearances" / session_path.parent.name
    destination = destination_dir / f"{title_slug}-{clearance_id[:10]}.json"
    if destination.exists():
        _, existing = verify_recording_clearance(song_path, destination)
        if existing.get("clearance_id") == clearance_id:
            return destination
        raise FileExistsError(f"recording clearance destination has different provenance: {destination}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete recording clearance exists: {temporary}")
    record = {
        "schema": CLEARANCE_SCHEMA,
        "clearance_id": clearance_id,
        "created_at": utc_now(),
        "status": status,
        **{key: value for key, value in recipe.items() if key != "schema"},
        "authority": {
            "statement": "This is project evidence of a stated permission decision, not legal advice or authorization to upload/publish by itself.",
        },
    }
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(destination)
    return destination


def resolve_recording_clearance(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = (song_path / "notes" / "clearances").resolve()
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    else:
        matches = [
            path.resolve() for path in root.rglob("*.json")
            if path.stem == str(value) or path.stem.endswith(f"-{value}")
        ] if root.is_dir() else []
        if len(matches) != 1:
            raise FileNotFoundError(f"recording clearance id is missing or ambiguous: {value}")
        candidate = matches[0]
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("recording clearance must be inside the song notes/clearances directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_recording_clearance(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    path = resolve_recording_clearance(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid recording clearance record: {path}: {exc.msg}") from exc
    if record.get("schema") != CLEARANCE_SCHEMA:
        raise ValueError("unsupported recording clearance record schema")
    session = record.get("session")
    if not isinstance(session, dict):
        raise ValueError("recording clearance session evidence is invalid")
    session_path, session_record = verify_recording_session(song_path, session.get("path", ""))
    if (
        session.get("sha256") != sha256(session_path)
        or session.get("session_id") != session_record.get("session_id")
    ):
        raise ValueError("recording clearance session evidence is missing or changed")
    takes = record.get("takes")
    participants = record.get("participants")
    if not isinstance(takes, list) or not takes or not isinstance(participants, list):
        raise ValueError("recording clearance takes or participants are invalid")
    expected_participants = {
        participant_id
        for take in takes if isinstance(take, dict) and take.get("id") in session_record["takes"]
        for participant_id in session_record["takes"][take["id"]]["participant_ids"]
    }
    rebuilt_takes = _take_records(takes, session_record)
    rebuilt_participants = _participant_records(participants, expected_participants, session_record)
    visibility = record.get("visibility_limit")
    if visibility not in VISIBILITY_RANK:
        raise ValueError("recording clearance visibility is invalid")
    recipe = {
        "schema": CLEARANCE_SPEC_SCHEMA,
        "title": record.get("title"),
        "intended_use": record.get("intended_use"),
        "visibility_limit": visibility,
        "session": session,
        "takes": rebuilt_takes,
        "participants": rebuilt_participants,
    }
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    expected_status = (
        "declined" if any(item["decision"] == "declined" for item in [*rebuilt_takes, *rebuilt_participants])
        else "approved" if all(item["decision"] == "approved" for item in [*rebuilt_takes, *rebuilt_participants])
        else "pending"
    )
    if record.get("clearance_id") != expected_id or not path.stem.endswith(expected_id[:10]):
        raise ValueError("recording clearance id does not match its normalized contents")
    if record.get("status") != expected_status:
        raise ValueError("recording clearance status is inconsistent")
    return path, record


def load_recording_clearance(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    return verify_recording_clearance(song, value)


def recording_session_matches(song: str | Path, raw_paths: set[str]) -> dict[str, list[dict]]:
    """Find valid session takes that represent each used raw recording."""
    song_path = Path(song).resolve()
    root = song_path / "notes" / "sessions"
    matches = {path: [] for path in raw_paths}
    if not root.is_dir():
        return matches
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if directory.name.startswith("."):
            raise ValueError(f"incomplete recording session blocks clearance audit: {directory.name}")
        session_path, session = load_recording_session(song_path, directory.name)
        for take_id, take in session["takes"].items():
            raw_path = take.get("path")
            if raw_path in matches:
                matches[raw_path].append({
                    "session_path": str(session_path.relative_to(song_path)),
                    "session_id": session["session_id"],
                    "take_id": take_id,
                    "participant_ids": take["participant_ids"],
                })
    return matches


def approved_clearance_coverage(record: dict, visibility: str) -> dict[str, dict]:
    """Return approved take coverage or an empty map when visibility/state fails."""
    if record.get("status") != "approved" or visibility not in VISIBILITY_RANK:
        return {}
    limit = record.get("visibility_limit")
    if limit not in VISIBILITY_RANK or VISIBILITY_RANK[limit] < VISIBILITY_RANK[visibility]:
        return {}
    participants = {item["id"]: item for item in record.get("participants", []) if isinstance(item, dict)}
    coverage = {}
    for take in record.get("takes", []):
        if not isinstance(take, dict) or take.get("decision") != "approved":
            continue
        coverage[take["id"]] = {
            "take": take,
            "participants": participants,
        }
    return coverage
