"""Reusable checksum-bound evidence references for consequential render recipes."""

from __future__ import annotations

import json
from pathlib import Path

from .system import sha256, slugify


EVIDENCE_BINDING_SCHEMA = "eprs.evidence-binding/v1"
MAX_EVIDENCE_BINDINGS = 32


def _text(record: dict, key: str, owner: str, maximum: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} evidence binding requires {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"{owner} evidence binding {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _path(song: Path, value: object, owner: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{owner} evidence binding requires path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"{owner} evidence path must be relative to the song")
    candidate = (song / requested).resolve()
    try:
        relative = candidate.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"{owner} evidence path escapes the song workspace") from exc
    if any(part.startswith(".") for part in relative.parts):
        raise ValueError(f"{owner} evidence path cannot reference hidden or partial files")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _declared_schema(path: Path) -> str | None:
    if path.suffix.lower() != ".json" or path.stat().st_size > 2_000_000:
        return None
    try:
        value = json.loads(path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    schema = value.get("schema") if isinstance(value, dict) else None
    return schema if isinstance(schema, str) and schema.strip() else None


def bind_song_evidence(song: str | Path, values: object, owner: str) -> list[dict]:
    """Resolve optional recipe evidence into deterministic song-local bindings."""
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{owner} evidence must be a list")
    if len(values) > MAX_EVIDENCE_BINDINGS:
        raise ValueError(f"{owner} evidence supports at most {MAX_EVIDENCE_BINDINGS} bindings")
    song_path = Path(song).resolve()
    bindings: list[dict] = []
    identifiers: set[str] = set()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"{owner} evidence binding {index} must be an object")
        declared_id = _text(value, "id", owner, 256)
        binding_id = slugify(declared_id)
        if not binding_id:
            raise ValueError(f"{owner} evidence binding id must contain a letter or number")
        if binding_id in identifiers:
            raise ValueError(f"duplicate {owner} evidence binding id: {declared_id}")
        identifiers.add(binding_id)
        role = _text(value, "role", owner, 1024)
        use = _text(value, "use", owner, 4096)
        path = _path(song_path, value.get("path"), owner)
        bindings.append({
            "schema": EVIDENCE_BINDING_SCHEMA,
            "id": binding_id,
            "declared_id": declared_id,
            "role": role,
            "use": use,
            "path": str(path.relative_to(song_path)),
            "sha256": sha256(path),
            "declared_schema": _declared_schema(path),
        })
    return bindings


def verify_evidence_bindings(
    song: str | Path,
    values: object,
    owner: str,
    *,
    verify_checksums: bool = True,
) -> list[Path]:
    """Validate persisted bindings and optionally detect evidence-byte drift."""
    if values is None:
        values = []
    if not isinstance(values, list):
        raise ValueError(f"{owner} evidence bindings are invalid")
    if len(values) > MAX_EVIDENCE_BINDINGS:
        raise ValueError(f"{owner} evidence exceeds {MAX_EVIDENCE_BINDINGS} bindings")
    identifiers: set[str] = set()
    paths: list[Path] = []
    song_path = Path(song).resolve()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict) or value.get("schema") != EVIDENCE_BINDING_SCHEMA:
            raise ValueError(f"{owner} evidence binding {index} has an unsupported schema")
        binding_id = value.get("id")
        declared_id = value.get("declared_id")
        if (
            not isinstance(binding_id, str)
            or not binding_id
            or not isinstance(declared_id, str)
            or slugify(declared_id) != binding_id
        ):
            raise ValueError(f"{owner} evidence binding {index} has an invalid id")
        if binding_id in identifiers:
            raise ValueError(f"duplicate {owner} evidence binding id: {binding_id}")
        identifiers.add(binding_id)
        for field in ("role", "use"):
            maximum = 1024 if field == "role" else 4096
            if (
                not isinstance(value.get(field), str)
                or not value[field].strip()
                or len(value[field].encode("utf-8")) > maximum
            ):
                raise ValueError(f"{owner} evidence binding {binding_id} has invalid {field}")
        expected = value.get("sha256")
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(character not in "0123456789abcdef" for character in expected)
        ):
            raise ValueError(f"{owner} evidence binding {binding_id} has an invalid checksum")
        declared_schema = value.get("declared_schema")
        if declared_schema is not None and (
            not isinstance(declared_schema, str)
            or not declared_schema.strip()
            or len(declared_schema.encode("utf-8")) > 512
        ):
            raise ValueError(f"{owner} evidence binding {binding_id} has an invalid declared schema")
        path = _path(song_path, value.get("path"), owner)
        if verify_checksums and sha256(path) != expected:
            raise ValueError(f"{owner} evidence is missing or changed: {path.relative_to(song_path)}")
        paths.append(path)
    return paths
