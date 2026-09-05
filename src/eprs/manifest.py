"""Song-level creative method ledger and rebuildable audit manifest.

EPRS deliberately stores detailed provenance beside the artifacts it describes.
This module does not replace those records.  It indexes them, records future CLI
operations, and leaves room for human reasons, prompts, rejected approaches, and
unstructured notes that cannot be reconstructed from media bytes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any, Iterable
from uuid import uuid4
from itertools import combinations

from . import __version__
from .adapters import load_adapter_profiles
from .system import load_song_manifest, load_toolchain, sha256, slugify, utc_now


MANIFEST_SCHEMA = "eprs.song-method-manifest/v1"
EVENT_SCHEMA = "eprs.method-event/v1"
RECORD_SCHEMA = "eprs.method-record/v1"
NOTE_SCHEMA = "eprs.manifest-note/v1"

_MANIFEST_DIR = Path("notes/manifest")
_GENERATED_MANIFEST = Path("song-manifest.json")
_TEXT_SUFFIXES = {
    ".beat",
    ".json",
    ".md",
    ".mlt",
    ".py",
    ".rb",
    ".srt",
    ".toml",
    ".txt",
    ".vtt",
    ".yaml",
    ".yml",
}
_CREATIVE_SOURCE_SUFFIXES = {".beat", ".mlt", ".py", ".rb"}
_CONTEXT_KEYS = {
    "alternatives",
    "avoid",
    "creative_direction",
    "decision",
    "decisions",
    "hypothesis",
    "idea",
    "ideas",
    "intent",
    "listening_note",
    "listening_notes",
    "musical_consequence",
    "note",
    "notes",
    "open_questions",
    "preserve",
    "prompt",
    "prompts",
    "question",
    "questions",
    "rationale",
    "reason",
    "review_note",
    "summary",
    "technical_note",
    "thought",
    "thoughts",
    "title",
    "why",
}
_SOFTWARE_KEYS = {
    "adapter",
    "backend",
    "engine",
    "generator",
    "model",
    "provider",
    "renderer",
    "software",
    "tool",
    "tool_id",
}
_READ_ONLY_COMMANDS = {
    "adapter list",
    "adapter show",
    "analyze",
    "check",
    "context",
    "doctor",
    "frontier validate",
    "groove show",
    "inaturalist models",
    "interchange verify",
    "lyrics show",
    "manifest compare",
    "manifest show",
    "manifest verify",
    "performance",
    "picture show",
    "plan acceptance-show",
    "plan acceptances",
    "plan progress",
    "plan show",
    "request show",
    "research show",
    "runner show",
    "runner validate",
    "session show",
    "clearance show",
    "status",
    "work list",
    "work show",
    "youtube-assets show",
}
_SCHEMA_COMMANDS = {
    "eprs.audio-selection": "select",
    "eprs.bioacoustic-detection": "bioacoustic detect",
    "eprs.comp": "comp",
    "eprs.creative-quality": "quality",
    "eprs.daw-interchange": "interchange prepare",
    "eprs.daw-return": "interchange return",
    "eprs.distribution-package": "distribution",
    "eprs.groove": "groove add",
    "eprs.groove-development": "groove add",
    "eprs.inaturalist-audio": "inaturalist sound",
    "eprs.inaturalist-creative-study": "inaturalist study",
    "eprs.lyric-development": "lyrics add",
    "eprs.master": "master",
    "eprs.master-render": "master",
    "eprs.mix": "mix",
    "eprs.mix-render": "mix",
    "eprs.musical-observation": "observe",
    "eprs.phase-observation": "phase",
    "eprs.picture": "picture add",
    "eprs.picture-candidate": "picture add",
    "eprs.process": "process",
    "eprs.process-render": "process",
    "eprs.pedalboard": "pedalboard",
    "eprs.pedalboard-render": "pedalboard",
    "eprs.production-plan-record": "plan add",
    "eprs.production-request-record": "request add",
    "eprs.recording": "ingest",
    "eprs.recording-clearance-record": "clearance add",
    "eprs.recording-session-record": "session add",
    "eprs.release": "release",
    "eprs.release-package": "release",
    "eprs.research-record": "research add",
    "eprs.rhythm-observation": "rhythm",
    "eprs.song": "new",
    "eprs.source-sketch": "source-sketch",
    "eprs.visual": "visual-prompt",
    "eprs.visual-render": "visual-render",
    "eprs.vgpu-render": "visual-render",
    "eprs.work-item": "work add",
    "eprs.youtube": "youtube",
    "eprs.youtube-assets": "youtube-assets add",
    "eprs.youtube-assets-bundle": "youtube-assets add",
    "eprs.youtube-publication-handoff": "publication prepare",
    "eprs.youtube-publication-receipt": "publication receipt",
    "eprs.youtube-publication-receipt-record": "publication receipt",
    "eprs.youtube-render": "youtube",
}


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _record_path(song: Path, folder: str, stem: str) -> Path:
    parent = song / _MANIFEST_DIR / folder
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return parent / f"{stamp}-{slugify(stem) or 'entry'}-{uuid4().hex[:10]}.json"


def command_path(args: argparse.Namespace) -> str:
    parts: list[str] = []
    for name in (
        "command",
        "adapter_command",
        "chatcut_command",
        "shotcut_command",
        "dispatch_command",
        "runner_command",
        "inaturalist_command",
        "bioacoustic_command",
        "request_command",
        "plan_command",
        "session_command",
        "clearance_command",
        "research_command",
        "lyrics_command",
        "groove_command",
        "interchange_command",
        "picture_command",
        "youtube_assets_command",
        "publication_command",
        "work_command",
        "manifest_command",
    ):
        value = getattr(args, name, None)
        if isinstance(value, str) and value:
            parts.append(value)
    return " ".join(parts)


def should_record_command(path: str) -> bool:
    return (
        bool(path)
        and path not in _READ_ONLY_COMMANDS
        and not path.startswith("manifest ")
    )


def _subparser_action(parser: argparse.ArgumentParser) -> Any | None:
    return next(
        (
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ),  # type: ignore[attr-defined]
        None,
    )


def command_catalog(parser: argparse.ArgumentParser) -> list[dict]:
    """Return the complete public CLI method/parameter surface."""
    records: list[dict] = []

    def visit(
        current: argparse.ArgumentParser, prefix: list[str], summary: str = ""
    ) -> None:
        subparsers = _subparser_action(current)
        if subparsers is None:
            options = []
            for action in current._actions:
                if action.dest in {"help"}:
                    continue
                item: dict[str, Any] = {
                    "name": action.dest,
                    "required": bool(getattr(action, "required", False)),
                }
                if action.option_strings:
                    item["flags"] = action.option_strings
                else:
                    item["positional"] = True
                if action.default != argparse.SUPPRESS:
                    item["default"] = action.default
                choices = getattr(action, "choices", None)
                if choices is not None:
                    item["choices"] = list(choices)
                if action.help:
                    item["help"] = action.help
                options.append(item)
            records.append(
                {
                    "id": " ".join(prefix),
                    "summary": current.description or summary,
                    "parameters": options,
                }
            )
            return
        choice_help = {
            action.dest: action.help
            for action in getattr(subparsers, "_choices_actions", [])
        }
        for name, child in sorted(subparsers.choices.items()):
            visit(child, [*prefix, name], choice_help.get(name, ""))

    visit(parser, [])
    return records


def _find_song(path: Path) -> Path | None:
    try:
        candidate = path.expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        elif candidate.exists():
            candidate = candidate.resolve()
        if candidate.is_file() or (not candidate.exists() and candidate.suffix):
            candidate = candidate.parent
        for parent in (candidate, *candidate.parents):
            if (parent / "song.json").is_file():
                return parent
    except OSError:
        # Free-form prompts, notes, and reasons are not necessarily valid path
        # components (and may exceed NAME_MAX). They are simply not song leads.
        return None
    return None


def resolve_song_from_args(args: argparse.Namespace) -> Path | None:
    explicit = getattr(args, "song", None)
    if isinstance(explicit, str):
        found = _find_song(Path(explicit))
        if found:
            return found
    if getattr(args, "command", None) in {"new", "make-song"} and getattr(
        args, "title", None
    ):
        candidate = Path(getattr(args, "root", "songs")) / slugify(args.title)
        if (candidate / "song.json").is_file():
            return candidate.resolve()
    for value in vars(args).values():
        values: Iterable[Any] = value if isinstance(value, (list, tuple)) else (value,)
        for item in values:
            if isinstance(item, tuple) and len(item) == 2:
                item = item[1]
            if not isinstance(item, str) or not item.strip():
                continue
            found = _find_song(Path(item))
            if found:
                return found
    return None


def snapshot_song(song: str | Path) -> dict[str, tuple[int, int]]:
    root = Path(song).resolve()
    state: dict[str, tuple[int, int]] = {}
    if not root.is_dir():
        return state
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative == _GENERATED_MANIFEST or relative.parts[:2] == _MANIFEST_DIR.parts:
            continue
        stat = path.stat()
        state[str(relative)] = (stat.st_mtime_ns, stat.st_size)
    return state


def _portable_value(value: Any, song: Path) -> Any:
    if isinstance(value, dict):
        return {key: _portable_value(item, song) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable_value(item, song) for item in value]
    if isinstance(value, Path):
        value = str(value)
    if not isinstance(value, str):
        return value
    expanded = Path(value).expanduser()
    candidates = [expanded] if expanded.is_absolute() else [Path.cwd() / expanded]
    for candidate in candidates:
        try:
            return str(candidate.resolve().relative_to(song))
        except (OSError, ValueError):
            pass
    home = str(Path.home())
    if value.startswith(home):
        return value.replace(home, "$HOME", 1)
    # Keep arbitrary prose and URLs intact, but never persist an absolute
    # machine path from an argv/parameter value into a shareable song ledger.
    # Absolute paths outside the song carry only a basename; record inputs and
    # outputs use _file_evidence when a durable checksum is required.
    if expanded.is_absolute() and not value.startswith("//"):
        return str(Path("<external>") / expanded.name)
    return value


def _record_error(value: dict, schema: str) -> str | None:
    """Return a concise structural error for an append-only ledger record."""
    required_strings = {
        EVENT_SCHEMA: ("id", "recorded_at", "method", "outcome"),
        RECORD_SCHEMA: ("id", "recorded_at", "method", "kind", "status", "reason"),
        NOTE_SCHEMA: ("id", "recorded_at", "section", "text"),
    }[schema]
    for field in required_strings:
        if not isinstance(value.get(field), str) or not value[field].strip():
            return f"{field} must be a non-empty string"
    if schema == EVENT_SCHEMA:
        if value["outcome"] not in {"completed", "nonzero"}:
            return "outcome must be completed or nonzero"
        if not isinstance(value.get("parameters"), dict):
            return "parameters must be an object"
        if not isinstance(value.get("argv"), list):
            return "argv must be a list"
        if not isinstance(value.get("artifacts"), list):
            return "artifacts must be a list"
    elif schema == RECORD_SCHEMA:
        if value["status"] not in {
            "used",
            "considered",
            "rejected",
            "failed",
            "superseded",
        }:
            return "unsupported method status"
        for field in ("settings", "inputs", "outputs", "notes", "alternatives", "tags"):
            if not isinstance(value.get(field), list):
                return f"{field} must be a list"
    elif not isinstance(value.get("tags"), list):
        return "tags must be a list"
    return None


def _changed_files(song: Path, before: dict[str, tuple[int, int]]) -> list[dict]:
    after = snapshot_song(song)
    changes: list[dict] = []
    for relative in sorted(set(before) | set(after)):
        if relative not in after:
            changes.append({"path": relative, "change": "removed"})
            continue
        if relative in before and before[relative] == after[relative]:
            continue
        path = song / relative
        record = {
            "path": relative,
            "change": "created" if relative not in before else "modified",
            "size": after[relative][1],
            "sha256": sha256(path),
        }
        changes.append(record)
    return changes


def record_cli_event(
    song: str | Path,
    args: argparse.Namespace,
    argv: list[str],
    before: dict[str, tuple[int, int]],
    *,
    outcome: str = "completed",
) -> Path:
    root = Path(song).resolve()
    load_song_manifest(root)
    method = command_path(args)
    record = {
        "schema": EVENT_SCHEMA,
        "id": uuid4().hex,
        "recorded_at": utc_now(),
        "method": method,
        "eprs_version": __version__,
        "runtime": {"python": platform.python_version(), "platform": sys.platform},
        "parameters": _portable_value(
            {
                key: value
                for key, value in vars(args).items()
                if not key.endswith("_command") and key != "command"
            },
            root,
        ),
        "argv": _portable_value(argv, root),
        "artifacts": _changed_files(root, before),
        "outcome": outcome,
    }
    destination = _record_path(root, "events", method)
    _json_dump(destination, record)
    return destination


def _file_evidence(song: Path, role: str, value: str | Path) -> dict:
    requested = Path(value).expanduser()
    song_candidate = song / requested
    path = (
        song_candidate.resolve()
        if not requested.is_absolute() and song_candidate.is_file()
        else requested.resolve()
    )
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        portable = str(path.relative_to(song))
        location = "song"
    except ValueError:
        portable = path.name
        location = "external-at-record-time"
    return {
        "role": role,
        "path": portable,
        "location": location,
        "sha256": sha256(path),
        "size": path.stat().st_size,
    }


def _verified_song_path(song: Path, relative: str) -> Path:
    candidate = (song / relative).resolve()
    try:
        candidate.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(
            f"manifest evidence escapes the song workspace: {relative}"
        ) from exc
    return candidate


def add_method_record(
    song: str | Path,
    method: str,
    reason: str,
    *,
    kind: str = "creative",
    status: str = "used",
    software_version: str | None = None,
    prompt: str | None = None,
    settings: list[dict] | None = None,
    inputs: list[tuple[str, str | Path]] | None = None,
    outputs: list[tuple[str, str | Path]] | None = None,
    notes: list[str] | None = None,
    alternatives: list[str] | None = None,
    tags: list[str] | None = None,
) -> Path:
    root = Path(song).resolve()
    load_song_manifest(root)
    if status not in {"used", "considered", "rejected", "failed", "superseded"}:
        raise ValueError(
            "method status must be used, considered, rejected, failed, or superseded"
        )
    if not method.strip() or not reason.strip():
        raise ValueError("method and reason must be non-empty")
    record = {
        "schema": RECORD_SCHEMA,
        "id": uuid4().hex,
        "recorded_at": utc_now(),
        "method": method.strip(),
        "kind": kind.strip() or "creative",
        "status": status,
        "reason": reason.strip(),
        "software_version": software_version,
        "prompt": prompt,
        "settings": settings or [],
        "inputs": [_file_evidence(root, role, path) for role, path in (inputs or [])],
        "outputs": [_file_evidence(root, role, path) for role, path in (outputs or [])],
        "notes": [note.strip() for note in (notes or []) if note.strip()],
        "alternatives": [item.strip() for item in (alternatives or []) if item.strip()],
        "tags": sorted({tag.strip() for tag in (tags or []) if tag.strip()}),
    }
    destination = _record_path(root, "records", method)
    _json_dump(destination, record)
    return destination


def add_manifest_note(
    song: str | Path, section: str, text: str, tags: list[str] | None = None
) -> Path:
    root = Path(song).resolve()
    load_song_manifest(root)
    if not section.strip() or not text.strip():
        raise ValueError("manifest note section and text must be non-empty")
    record = {
        "schema": NOTE_SCHEMA,
        "id": uuid4().hex,
        "recorded_at": utc_now(),
        "section": section.strip(),
        "text": text.strip(),
        "tags": sorted({tag.strip() for tag in (tags or []) if tag.strip()}),
    }
    destination = _record_path(root, "notes", section)
    _json_dump(destination, record)
    return destination


def _load_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _extract_context(value: Any, prefix: str = "", *, limit: int = 40) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        for key, item in value.items():
            field = f"{prefix}.{key}" if prefix else key
            if key.lower() in _CONTEXT_KEYS and isinstance(
                item, (str, int, float, bool, list)
            ):
                found.append({"field": field, "value": item})
            if len(found) < limit and isinstance(item, (dict, list)):
                found.extend(_extract_context(item, field, limit=limit - len(found)))
            if len(found) >= limit:
                break
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if len(found) >= limit:
                break
            found.extend(
                _extract_context(item, f"{prefix}[{index}]", limit=limit - len(found))
            )
    return found[:limit]


def _extract_software(value: Any, prefix: str = "", *, limit: int = 24) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        for key, item in value.items():
            field = f"{prefix}.{key}" if prefix else key
            if key.lower() in _SOFTWARE_KEYS and isinstance(
                item, (str, int, float, bool)
            ):
                found.append({"field": field, "value": item})
            if len(found) < limit and isinstance(item, (dict, list)):
                found.extend(_extract_software(item, field, limit=limit - len(found)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if len(found) >= limit:
                break
            found.extend(
                _extract_software(item, f"{prefix}[{index}]", limit=limit - len(found))
            )
    return found[:limit]


def _artifact_index(song: Path) -> tuple[list[dict], list[dict], Counter]:
    artifacts: list[dict] = []
    assets: list[dict] = []
    schemas: Counter = Counter()
    for path in sorted(song.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(song)
        if relative == _GENERATED_MANIFEST or relative.parts[:2] == _MANIFEST_DIR.parts:
            continue
        suffix = path.suffix.lower()
        asset = {
            "path": str(relative),
            "size": path.stat().st_size,
            "type": suffix.lstrip(".") or "file",
        }
        if suffix not in _TEXT_SUFFIXES:
            assets.append(asset)
            continue
        if suffix == ".json":
            value = _load_json(path)
            if value is None:
                artifacts.append({**asset, "valid_json": False, "sha256": sha256(path)})
                continue
            schema = (
                value.get("schema") if isinstance(value.get("schema"), str) else None
            )
            if schema:
                schemas[schema] += 1
            artifacts.append(
                {
                    **asset,
                    "sha256": sha256(path),
                    "schema": schema,
                    "id": value.get("id")
                    or value.get("study_id")
                    or value.get("release_id"),
                    "created_at": value.get("created_at")
                    or value.get("recorded_at")
                    or value.get("rendered_at"),
                    "context": _extract_context(value),
                    "software_evidence": _extract_software(value),
                }
            )
        elif suffix in _CREATIVE_SOURCE_SUFFIXES:
            artifacts.append(
                {
                    **asset,
                    "sha256": sha256(path),
                    "schema": None,
                    "creative_source": True,
                }
            )
        else:
            assets.append(asset)
    return artifacts, assets, schemas


def _load_records(song: Path, folder: str, schema: str) -> list[dict]:
    records: list[dict] = []
    for path in sorted((song / _MANIFEST_DIR / folder).glob("*.json")):
        value = _load_json(path)
        evidence = {"path": str(path.relative_to(song)), "sha256": sha256(path)}
        if value is None:
            records.append(
                {**evidence, "valid_record": False, "error": "invalid JSON object"}
            )
            continue
        if value.get("schema") != schema:
            records.append(
                {
                    **evidence,
                    "valid_record": False,
                    "error": f"expected {schema}; found {value.get('schema')!r}",
                }
            )
            continue
        error = _record_error(value, schema)
        if error:
            records.append({**value, **evidence, "valid_record": False, "error": error})
            continue
        records.append({**value, **evidence, "valid_record": True})
    return records


def _load_adapters() -> list[dict]:
    result = []
    for value in load_adapter_profiles(
        additional_directories=[], toolchain_extensions=[]
    ):
        result.append(
            {
                "id": value.get("id"),
                "provider": value.get("provider"),
                "summary": value.get("summary", ""),
                "capabilities": value.get("capabilities", []),
                "handoffs": [
                    {key: handoff.get(key) for key in ("id", "label", "capabilities")}
                    for handoff in value.get("handoffs", [])
                    if isinstance(handoff, dict)
                ],
            }
        )
    return result


def build_song_method_manifest(
    song: str | Path,
    cli_parser: argparse.ArgumentParser,
    *,
    tool_report: dict | None = None,
) -> Path:
    root = Path(song).resolve()
    song_record = load_song_manifest(root)
    previous = _load_json(root / _GENERATED_MANIFEST) or {}
    artifacts, assets, schemas = _artifact_index(root)
    events = _load_records(root, "events", EVENT_SCHEMA)
    manual_records = _load_records(root, "records", RECORD_SCHEMA)
    notes = _load_records(root, "notes", NOTE_SCHEMA)
    attempted_commands = Counter(
        event.get("method") for event in events if event.get("method")
    )
    completed_commands = Counter(
        event.get("method")
        for event in events
        if event.get("method") and event.get("outcome") == "completed"
    )
    artifact_commands: Counter = Counter()
    inferred_artifact_methods: Counter = Counter()
    for schema, count in schemas.items():
        base = schema.split("/", 1)[0]
        inferred_artifact_methods[base.removeprefix("eprs.")] += count
        command = _SCHEMA_COMMANDS.get(base)
        if command:
            artifact_commands[command] += count
    for artifact in artifacts:
        if not artifact.get("creative_source"):
            continue
        suffix = Path(artifact["path"]).suffix.lower()
        inferred_artifact_methods[
            {
                ".beat": "BeatScript",
                ".rb": "Sonic Pi",
                ".mlt": "Shotcut/MLT",
                ".py": "custom Python",
            }.get(suffix, suffix)
        ] += 1
    commands = command_catalog(cli_parser)
    for record in commands:
        record["status"] = (
            "used"
            if completed_commands[record["id"]]
            else "attempted-nonzero"
            if attempted_commands[record["id"]]
            else "artifact-evidenced"
            if artifact_commands[record["id"]]
            else "not-evidenced"
        )
        record["event_count"] = attempted_commands[record["id"]]
        record["completed_event_count"] = completed_commands[record["id"]]
        record["artifact_count"] = artifact_commands[record["id"]]

    toolchain = load_toolchain(extensions=[])
    previous_method_space = previous.get("method_space")
    if not isinstance(previous_method_space, dict):
        previous_method_space = {}
    prior_software = previous_method_space.get("software", [])
    if not isinstance(prior_software, list):
        prior_software = []
    availability = {
        item["id"]: item["availability"]
        for item in prior_software
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("availability"), dict)
    }
    availability.update(
        {
            item["id"]: {
                "available": item.get("available"),
                "versions": item.get("versions", {}),
            }
            for item in (tool_report or {}).get("tools", [])
        }
    )
    tools = []
    for tool in toolchain.get("tools", []):
        tools.append(
            {
                "id": tool.get("id"),
                "label": tool.get("label"),
                "kind": tool.get("kind"),
                "required": bool(tool.get("required")),
                "capabilities": tool.get("capabilities", []),
                **(
                    {"availability": availability[tool["id"]]}
                    if tool.get("id") in availability
                    else {}
                ),
            }
        )

    status_counts = Counter(
        record.get("status", "unknown") for record in manual_records
    )
    method_counts = Counter(
        event.get("method") for event in events if event.get("method")
    )
    for record in manual_records:
        method_counts[record.get("method", "unknown")] += 1
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": utc_now(),
        "generator": {"name": "eprs", "version": __version__},
        "song": {
            key: song_record.get(key)
            for key in ("title", "slug", "created_at", "status", "sample_rate")
        },
        "audit_scope": {
            "statement": "A rebuildable index of song-local evidence plus append-only method records; absence means not evidenced, not proof of non-use.",
            "strict_facts": [
                "events",
                "manual_records",
                "artifacts",
                "asset_inventory",
            ],
            "loose_context": ["notes", "artifact context excerpts"],
        },
        "summary": {
            "recorded_methods": dict(sorted(method_counts.items())),
            "manual_statuses": dict(sorted(status_counts.items())),
            "invalid_ledger_records": sum(
                record.get("valid_record") is False
                for record in [*events, *manual_records, *notes]
            ),
            "schemas": dict(sorted(schemas.items())),
            "inferred_artifact_methods": dict(
                sorted(inferred_artifact_methods.items())
            ),
            "untried_cli_methods": sum(
                record["status"] == "not-evidenced" for record in commands
            ),
        },
        "events": events,
        "manual_records": manual_records,
        "notes": notes,
        "artifacts": artifacts,
        "asset_inventory": assets,
        "method_space": {
            "eprs_cli": commands,
            "software": tools,
            "adapters": _load_adapters(),
            "workflows": toolchain.get("workflows", []),
        },
    }
    destination = root / _GENERATED_MANIFEST
    _json_dump(destination, manifest)
    return destination


def verify_song_method_manifest(song: str | Path) -> dict:
    root = Path(song).resolve()
    destination = root / _GENERATED_MANIFEST
    value = _load_json(destination)
    if value is None or value.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"missing or unsupported song method manifest: {destination}")
    for section in ("song", "summary", "method_space"):
        if not isinstance(value.get(section), dict):
            raise ValueError(f"song method manifest {section} must be an object")
    if not isinstance(value.get("asset_inventory"), list):
        raise ValueError("song method manifest asset_inventory must be a list")
    checked = 0
    invalid: list[dict] = []
    for section in ("events", "manual_records", "notes", "artifacts"):
        records = value.get(section)
        if not isinstance(records, list):
            raise ValueError(f"song method manifest {section} must be a list")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(
                    f"song method manifest {section} entries must be objects"
                )
            if section != "artifacts" and record.get("valid_record") is False:
                invalid.append(
                    {
                        "path": record.get("path"),
                        "reason": record.get("error", "invalid ledger record"),
                    }
                )
            if section == "artifacts" and record.get("valid_json") is False:
                invalid.append(
                    {
                        "path": record.get("path"),
                        "reason": "structured artifact is not valid JSON",
                    }
                )
            relative = record.get("path")
            expected = record.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected, str):
                continue
            try:
                path = _verified_song_path(root, relative)
            except ValueError:
                checked += 1
                invalid.append(
                    {"path": relative, "reason": "path escapes song workspace"}
                )
                continue
            checked += 1
            if not path.is_file():
                invalid.append({"path": relative, "reason": "missing"})
            elif sha256(path) != expected:
                invalid.append({"path": relative, "reason": "checksum changed"})
    for section, folder, schema in (
        ("events", "events", EVENT_SCHEMA),
        ("manual_records", "records", RECORD_SCHEMA),
        ("notes", "notes", NOTE_SCHEMA),
    ):
        indexed = {
            item.get("path")
            for item in value.get(section, [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        }
        for record in _load_records(root, folder, schema):
            if record["path"] not in indexed:
                invalid.append(
                    {
                        "path": record["path"],
                        "reason": "ledger record is not indexed; rebuild manifest",
                    }
                )
    latest_outputs: dict[str, tuple[str, dict, str | None]] = {}
    for record in value.get("events", []):
        evidence_records = record.get("artifacts")
        if not isinstance(evidence_records, list):
            invalid.append(
                {
                    "path": record.get("path"),
                    "reason": "method event artifacts must be a list",
                }
            )
            continue
        for evidence in evidence_records:
            if not isinstance(evidence, dict) or not isinstance(
                evidence.get("path"), str
            ):
                invalid.append(
                    {
                        "path": record.get("path"),
                        "reason": "method event artifacts entries must be objects with paths",
                    }
                )
                continue
            latest_outputs[evidence["path"]] = (
                str(record.get("recorded_at", "")),
                evidence,
                record.get("id"),
            )
    for record in value.get("manual_records", []):
        for field in ("inputs", "outputs"):
            evidence_records = record.get(field)
            if not isinstance(evidence_records, list):
                invalid.append(
                    {
                        "path": record.get("path"),
                        "reason": f"manual method record {field} must be a list",
                    }
                )
                continue
            for evidence in evidence_records:
                if not isinstance(evidence, dict):
                    invalid.append(
                        {
                            "path": record.get("path"),
                            "reason": f"manual method record {field} entries must be objects",
                        }
                    )
                    continue
                if evidence.get("location") != "song":
                    continue
                relative = evidence.get("path")
                expected = evidence.get("sha256")
                if not isinstance(relative, str) or not isinstance(expected, str):
                    invalid.append(
                        {
                            "path": record.get("path"),
                            "reason": f"manual method record {field} evidence needs path and sha256",
                        }
                    )
                    continue
                if field == "outputs":
                    prior = latest_outputs.get(relative)
                    candidate = (
                        str(record.get("recorded_at", "")),
                        evidence,
                        record.get("id"),
                    )
                    if prior is None or candidate[0] >= prior[0]:
                        latest_outputs[relative] = candidate
                    continue
                try:
                    path = _verified_song_path(root, relative)
                except ValueError:
                    checked += 1
                    invalid.append(
                        {
                            "path": relative,
                            "reason": "path escapes song workspace",
                            "record": record.get("id"),
                        }
                    )
                    continue
                checked += 1
                if not path.is_file():
                    invalid.append(
                        {
                            "path": relative,
                            "reason": "missing",
                            "record": record.get("id"),
                        }
                    )
                elif sha256(path) != expected:
                    invalid.append(
                        {
                            "path": relative,
                            "reason": "checksum changed",
                            "record": record.get("id"),
                        }
                    )
    for relative, (_, evidence, record_id) in sorted(latest_outputs.items()):
        try:
            path = _verified_song_path(root, relative)
        except ValueError:
            checked += 1
            invalid.append(
                {
                    "path": relative,
                    "reason": "path escapes song workspace",
                    "record": record_id,
                }
            )
            continue
        checked += 1
        if evidence.get("change") == "removed":
            if path.exists():
                invalid.append(
                    {
                        "path": relative,
                        "reason": "removed output exists",
                        "record": record_id,
                    }
                )
            continue
        expected = evidence.get("sha256")
        if not isinstance(expected, str):
            invalid.append(
                {
                    "path": relative,
                    "reason": "output checksum missing",
                    "record": record_id,
                }
            )
        elif not path.is_file():
            invalid.append({"path": relative, "reason": "missing", "record": record_id})
        elif sha256(path) != expected:
            invalid.append(
                {"path": relative, "reason": "checksum changed", "record": record_id}
            )
    current_artifacts, current_assets, _ = _artifact_index(root)
    indexed_artifact_paths = {
        item.get("path")
        for item in value.get("artifacts", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    for record in current_artifacts:
        if record["path"] not in indexed_artifact_paths:
            invalid.append(
                {
                    "path": record["path"],
                    "reason": "artifact is not indexed; rebuild manifest",
                }
            )
    indexed_assets = {
        item.get("path"): item.get("size")
        for item in value.get("asset_inventory", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    current_asset_map = {item["path"]: item["size"] for item in current_assets}
    for relative in sorted(set(indexed_assets) | set(current_asset_map)):
        if relative not in current_asset_map:
            invalid.append({"path": relative, "reason": "indexed asset is missing"})
        elif relative not in indexed_assets:
            invalid.append(
                {"path": relative, "reason": "asset is not indexed; rebuild manifest"}
            )
        elif indexed_assets[relative] != current_asset_map[relative]:
            invalid.append(
                {"path": relative, "reason": "asset size changed; rebuild manifest"}
            )
    return {
        "schema": "eprs.song-method-manifest-verification/v1",
        "manifest": str(destination),
        "checked": checked,
        "valid": not invalid,
        "invalid": invalid,
    }


def compare_song_method_manifests(songs: list[str | Path]) -> dict:
    """Compare evidenced method sets without claiming aesthetic similarity."""
    if len(songs) < 2:
        raise ValueError("manifest comparison requires at least two songs")
    song_records: list[dict] = []
    seen_slugs: set[str] = set()
    for song in songs:
        root = Path(song).resolve()
        verification = verify_song_method_manifest(root)
        if not verification["valid"]:
            raise ValueError(
                f"cannot compare invalid or stale song method manifest: {root / _GENERATED_MANIFEST}; "
                f"{len(verification['invalid'])} issue(s)"
            )
        value = _load_json(root / _GENERATED_MANIFEST)
        if value is None or value.get("schema") != MANIFEST_SCHEMA:
            raise ValueError(
                f"missing or unsupported song method manifest: {root / _GENERATED_MANIFEST}"
            )
        identity = value.get("song", {})
        slug = identity.get("slug")
        if not isinstance(slug, str) or not slug or slug in seen_slugs:
            raise ValueError("manifest comparison requires unique song slugs")
        seen_slugs.add(slug)
        event_methods = sorted(
            {
                item.get("method")
                for item in value.get("events", [])
                if isinstance(item, dict)
                and item.get("outcome") == "completed"
                and isinstance(item.get("method"), str)
            }
        )
        declared_methods = sorted(
            {
                item.get("method")
                for item in value.get("manual_records", [])
                if isinstance(item, dict)
                and item.get("status") == "used"
                and isinstance(item.get("method"), str)
            }
        )
        artifact_methods = sorted(
            {
                item.get("id")
                for item in value.get("method_space", {}).get("eprs_cli", [])
                if isinstance(item, dict)
                and item.get("status") == "artifact-evidenced"
                and isinstance(item.get("id"), str)
            }
        )
        evidenced = sorted(
            set(event_methods) | set(declared_methods) | set(artifact_methods)
        )
        song_records.append(
            {
                "title": identity.get("title"),
                "slug": slug,
                "completed_cli_methods": event_methods,
                "declared_used_methods": declared_methods,
                "artifact_evidenced_cli_methods": artifact_methods,
                "all_evidenced_methods": evidenced,
                "considered_or_rejected": [
                    {
                        "method": item.get("method"),
                        "status": item.get("status"),
                        "reason": item.get("reason"),
                    }
                    for item in value.get("manual_records", [])
                    if isinstance(item, dict)
                    and item.get("status") in {"considered", "rejected"}
                ],
            }
        )
    pair_records = []
    for left, right in combinations(song_records, 2):
        left_methods = set(left["all_evidenced_methods"])
        right_methods = set(right["all_evidenced_methods"])
        union = left_methods | right_methods
        pair_records.append(
            {
                "songs": [left["slug"], right["slug"]],
                "shared": sorted(left_methods & right_methods),
                "only": {
                    left["slug"]: sorted(left_methods - right_methods),
                    right["slug"]: sorted(right_methods - left_methods),
                },
                "jaccard": round(len(left_methods & right_methods) / len(union), 6)
                if union
                else 1.0,
                "interpretation_boundary": "Method-set overlap is not a listening judgment or proof of musical similarity.",
            }
        )
    return {
        "schema": "eprs.song-method-manifest-comparison/v1",
        "songs": song_records,
        "pairs": pair_records,
    }
