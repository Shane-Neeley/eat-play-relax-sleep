"""Project, experiment, recording, media, and environment operations."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_TOOLCHAIN_PATH = PROJECT_ROOT / "config" / "toolchain.json"
INSTALLED_TOOLCHAIN_PATH = Path(sys.prefix) / "share" / "eprs" / "toolchain.json"
TOOLCHAIN_PATH = (
    REPOSITORY_TOOLCHAIN_PATH
    if REPOSITORY_TOOLCHAIN_PATH.is_file()
    else INSTALLED_TOOLCHAIN_PATH
)
REPOSITORY_LOCAL_CONFIG_DIR = PROJECT_ROOT / ".eprs-local"
REPOSITORY_LOCAL_TOOLCHAIN_PATH = REPOSITORY_LOCAL_CONFIG_DIR / "toolchain.json"
TOOLCHAIN_EXTENSION_SCHEMA = "eprs.toolchain-extension/v1"
SAFE_VERSION_ARGUMENTS = {
    ("--version",),
    ("-version",),
    ("-V",),
    ("version",),
}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    clean = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in clean.split("-") if part)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def toolchain_extension_paths(
    toolchain: str | Path = TOOLCHAIN_PATH,
    extensions: list[str | Path] | None = None,
) -> list[Path]:
    """Resolve explicit extensions or the ignored checkout-local default."""
    registry_path = Path(toolchain).resolve()
    if extensions is None:
        candidates = (
            [REPOSITORY_LOCAL_TOOLCHAIN_PATH]
            if registry_path == Path(TOOLCHAIN_PATH).resolve()
            and REPOSITORY_LOCAL_TOOLCHAIN_PATH.is_file()
            else []
        )
    else:
        if not isinstance(extensions, list):
            raise ValueError("toolchain extensions must be a list of paths")
        candidates = [Path(value).expanduser() for value in extensions]
    resolved: list[Path] = []
    for candidate in candidates:
        path = candidate.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if path in resolved:
            raise ValueError(f"duplicate toolchain extension path: {path}")
        resolved.append(path)
    return resolved


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}: {exc.msg}") from exc


def _validate_toolchain(registry: object) -> dict:
    if not isinstance(registry, dict):
        raise ValueError("toolchain registry must be an object")
    if registry.get("schema") != "eprs.toolchain/v1":
        raise ValueError("unsupported toolchain schema")
    tools = registry.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("toolchain registry requires a non-empty tools list")
    seen: set[str] = set()
    declared_capabilities: set[str] = set()
    for record in tools:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("each toolchain entry requires a string id")
        tool_id = record["id"]
        if tool_id in seen:
            raise ValueError(f"duplicate toolchain id: {tool_id}")
        seen.add(tool_id)
        if record.get("kind") not in {"command-set", "project-path", "application"}:
            raise ValueError(f"unsupported toolchain kind for {tool_id}")
        if "required" in record and not isinstance(record["required"], bool):
            raise ValueError(f"toolchain required flag for {tool_id} must be boolean")
        supported_platforms = record.get("platforms")
        if supported_platforms is not None and (
            not isinstance(supported_platforms, list)
            or not all(isinstance(item, str) and item.strip() for item in supported_platforms)
            or len(supported_platforms) != len(set(supported_platforms))
        ):
            raise ValueError(
                f"toolchain platforms for {tool_id} must be unique non-empty strings"
            )
        if record["kind"] == "command-set":
            commands = record.get("commands")
            if not isinstance(commands, list) or not commands:
                raise ValueError(f"command-set {tool_id} requires commands")
            for command in commands:
                if (
                    not isinstance(command, dict)
                    or not isinstance(command.get("name"), str)
                    or not command["name"].strip()
                ):
                    raise ValueError(f"toolchain command for {tool_id} requires a name")
                arguments = command.get("version_args")
                if arguments is not None and (
                    not isinstance(arguments, list)
                    or not all(isinstance(item, str) for item in arguments)
                    or (arguments and tuple(arguments) not in SAFE_VERSION_ARGUMENTS)
                ):
                    raise ValueError(
                        f"toolchain command {command['name']} for {tool_id} has an unsafe "
                        "version probe"
                    )
        else:
            configured_paths = record.get("paths")
            if (
                not isinstance(configured_paths, list)
                or not configured_paths
                or not all(isinstance(item, str) and item.strip() for item in configured_paths)
            ):
                raise ValueError(f"{record['kind']} {tool_id} requires non-empty paths")
        tool_capabilities = record.get("capabilities", [])
        if (
            not isinstance(tool_capabilities, list)
            or not all(isinstance(item, str) and item.strip() for item in tool_capabilities)
            or len(tool_capabilities) != len(set(tool_capabilities))
        ):
            raise ValueError(f"toolchain capabilities for {tool_id} must be unique non-empty strings")
        declared_capabilities.update(tool_capabilities)
    workflows = registry.get("workflows", [])
    if not isinstance(workflows, list):
        raise ValueError("toolchain workflows must be a list")
    workflow_ids: set[str] = set()
    for workflow in workflows:
        if not isinstance(workflow, dict) or not isinstance(workflow.get("id"), str):
            raise ValueError("each toolchain workflow requires a string id")
        workflow_id = workflow["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", workflow_id):
            raise ValueError(f"toolchain workflow id must be a portable slug: {workflow_id}")
        if workflow_id in workflow_ids:
            raise ValueError(f"duplicate toolchain workflow id: {workflow_id}")
        workflow_ids.add(workflow_id)
        for field in ("label", "description"):
            if not isinstance(workflow.get(field), str) or not workflow[field].strip():
                raise ValueError(f"toolchain workflow {workflow_id} requires a non-empty {field}")
        required = workflow.get("capabilities")
        if (
            not isinstance(required, list)
            or not required
            or not all(isinstance(item, str) and item.strip() for item in required)
            or len(required) != len(set(required))
        ):
            raise ValueError(
                f"toolchain workflow {workflow_id} capabilities must be unique non-empty strings"
            )
        unknown = sorted(set(required) - declared_capabilities)
        if unknown:
            raise ValueError(
                f"toolchain workflow {workflow_id} references unknown capabilities: "
                f"{', '.join(unknown)}"
            )
    return registry


def _apply_toolchain_extensions(registry: dict, paths: list[Path]) -> dict:
    merged = copy.deepcopy(registry)
    tool_ids = {record.get("id") for record in merged["tools"] if isinstance(record, dict)}
    workflow_ids = {
        record.get("id")
        for record in merged.get("workflows", [])
        if isinstance(record, dict)
    }
    for path in paths:
        extension = _read_json(path, "toolchain extension")
        if not isinstance(extension, dict) or extension.get("schema") != TOOLCHAIN_EXTENSION_SCHEMA:
            raise ValueError(f"unsupported toolchain extension schema: {path}")
        unexpected = sorted(set(extension) - {"schema", "tools", "workflows"})
        if unexpected:
            raise ValueError(
                f"toolchain extension {path} has unknown fields: {', '.join(unexpected)}"
            )
        tools = extension.get("tools", [])
        workflows = extension.get("workflows", [])
        if not isinstance(tools, list) or not isinstance(workflows, list):
            raise ValueError(f"toolchain extension {path} tools and workflows must be lists")
        if not tools and not workflows:
            raise ValueError(f"toolchain extension {path} must add a tool or workflow")
        for record in tools:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise ValueError(f"toolchain extension {path} tool requires a string id")
            tool_id = record["id"]
            if tool_id in tool_ids:
                raise ValueError(
                    f"toolchain extension may not replace existing tool id: {tool_id}"
                )
            if record.get("required") is True:
                raise ValueError(
                    f"toolchain extension tool must remain optional: {tool_id}"
                )
            if record.get("kind") in {"application", "project-path"} and any(
                not Path(value).expanduser().is_absolute()
                for value in record.get("paths", [])
                if isinstance(value, str)
            ):
                raise ValueError(
                    f"toolchain extension paths must be absolute for local tool: {tool_id}"
                )
            tool_ids.add(tool_id)
            merged["tools"].append(copy.deepcopy(record))
        for record in workflows:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise ValueError(f"toolchain extension {path} workflow requires a string id")
            workflow_id = record["id"]
            if workflow_id in workflow_ids:
                raise ValueError(
                    f"toolchain extension may not replace existing workflow id: {workflow_id}"
                )
            workflow_ids.add(workflow_id)
            merged.setdefault("workflows", []).append(copy.deepcopy(record))
    return merged


def load_toolchain(
    path: str | Path = TOOLCHAIN_PATH,
    *,
    extensions: list[str | Path] | None = None,
) -> dict:
    """Load the shared tool registry plus explicit additive local extensions."""
    registry_path = Path(path)
    registry = _validate_toolchain(_read_json(registry_path, "toolchain"))
    extension_paths = toolchain_extension_paths(registry_path, extensions)
    return _validate_toolchain(_apply_toolchain_extensions(registry, extension_paths))


def _command_version(command: str, arguments: object) -> str | None:
    if (
        not isinstance(arguments, list)
        or tuple(arguments) not in SAFE_VERSION_ARGUMENTS
    ):
        return None
    try:
        completed = subprocess.run(
            [command, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0] if completed.returncode == 0 and output else None


def doctor(
    toolchain: str | Path = TOOLCHAIN_PATH,
    *,
    extensions: list[str | Path] | None = None,
    workflows: list[str] | None = None,
    required_capabilities: list[str] | None = None,
) -> dict:
    """Inspect the versioned toolchain registry without installing anything."""
    registry_path = Path(toolchain)
    extension_paths = toolchain_extension_paths(registry_path, extensions)
    registry = load_toolchain(registry_path, extensions=extension_paths)
    system_name = platform.system()
    commands: dict[str, str | None] = {}
    apps: dict[str, str | None] = {}
    adapters: dict[str, str | None] = {}
    capabilities: dict[str, bool] = {}
    tool_reports: list[dict] = []
    next_actions: list[str] = []
    required_ready = True

    for record in registry["tools"]:
        tool_id = record["id"]
        supported_platforms = record.get("platforms")
        applicable = not isinstance(supported_platforms, list) or system_name in supported_platforms
        located: list[str] = []
        versions: dict[str, str] = {}
        kind = record["kind"]
        if applicable and kind == "command-set":
            command_records = record.get("commands", [])
            if not isinstance(command_records, list) or not command_records:
                raise ValueError(f"command-set {tool_id} requires commands")
            for command_record in command_records:
                if not isinstance(command_record, dict) or not isinstance(command_record.get("name"), str):
                    raise ValueError(f"toolchain command for {tool_id} requires a name")
                name = command_record["name"]
                found = shutil.which(name)
                commands[name] = found
                if found:
                    located.append(found)
                    version = _command_version(found, command_record.get("version_args", []))
                    if version:
                        versions[name] = version
            available = len(located) == len(command_records)
        elif applicable:
            configured_paths = record.get("paths", [])
            if not isinstance(configured_paths, list) or not configured_paths:
                raise ValueError(f"{kind} {tool_id} requires paths")
            candidates = [
                candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
                for value in configured_paths
                if isinstance(value, str)
                for candidate in [Path(value)]
            ]
            located = [str(candidate) for candidate in candidates if candidate.exists()]
            available = bool(located)
            if kind == "application":
                apps[tool_id] = located[0] if located else None
            else:
                adapters[tool_id] = located[0] if located else None
        else:
            available = False

        for capability in record.get("capabilities", []):
            if isinstance(capability, str):
                capabilities[capability] = capabilities.get(capability, False) or available
        required = record.get("required") is True and applicable
        if required and not available:
            required_ready = False
        hint_map = record.get("install_hints", {})
        hint = hint_map.get(system_name) or hint_map.get("default") if isinstance(hint_map, dict) else None
        if applicable and not available and isinstance(hint, str):
            next_actions.append(f"{record.get('label', tool_id)}: {hint}")
        tool_reports.append({
            "id": tool_id,
            "label": record.get("label", tool_id),
            "kind": kind,
            "required": required,
            "applicable": applicable,
            "available": available,
            "located": located,
            "versions": versions,
            "capabilities": [item for item in record.get("capabilities", []) if isinstance(item, str)],
            "install_hint": hint if isinstance(hint, str) else None,
        })

    python_ready = sys.version_info >= (3, 11) and bool(commands.get("python3"))
    capabilities["beat_render"] = capabilities.get("beat_render", False) and python_ready
    if not python_ready:
        required_ready = False
        next_actions.insert(0, "Python runtime: use Python 3.11 or newer.")

    requested_workflows: list[str] = []
    for value in workflows or []:
        clean = value.strip() if isinstance(value, str) else ""
        if not clean:
            raise ValueError("doctor workflow requirements cannot be blank")
        if clean not in requested_workflows:
            requested_workflows.append(clean)
    requested_capabilities: list[str] = []
    for value in required_capabilities or []:
        clean = value.strip() if isinstance(value, str) else ""
        if not clean:
            raise ValueError("doctor capability requirements cannot be blank")
        if clean not in requested_capabilities:
            requested_capabilities.append(clean)

    workflow_catalog = []
    for workflow in registry.get("workflows", []):
        missing = [
            capability for capability in workflow["capabilities"]
            if capabilities.get(capability) is not True
        ]
        workflow_catalog.append({
            "id": workflow["id"],
            "label": workflow["label"],
            "description": workflow["description"],
            "capabilities": list(workflow["capabilities"]),
            "ready": not missing,
            "missing_capabilities": missing,
        })
    workflow_map = {workflow["id"]: workflow for workflow in workflow_catalog}
    unknown_workflows = [item for item in requested_workflows if item not in workflow_map]
    if unknown_workflows:
        raise ValueError(
            f"unknown doctor workflow: {', '.join(unknown_workflows)}; available workflows: "
            f"{', '.join(workflow_map) or 'none'}"
        )
    declared_capabilities = {
        capability
        for report in tool_reports
        for capability in report["capabilities"]
    }
    unknown_capabilities = [
        item for item in requested_capabilities if item not in declared_capabilities
    ]
    if unknown_capabilities:
        raise ValueError(
            f"unknown doctor capability: {', '.join(unknown_capabilities)}"
        )
    workflow_reports = []
    resolved_requirements = list(requested_capabilities)
    for workflow_id in requested_workflows:
        workflow = workflow_map[workflow_id]
        for capability in workflow["capabilities"]:
            if capability not in resolved_requirements:
                resolved_requirements.append(capability)
        workflow_reports.append({
            **workflow,
        })
    missing_requirements = [
        capability for capability in resolved_requirements
        if capabilities.get(capability) is not True
    ]
    provider_reports = {}
    requirement_actions = []
    for capability in missing_requirements:
        providers = [
            {
                "tool_id": report["id"],
                "label": report["label"],
                "applicable": report["applicable"],
                "available": report["available"],
                "install_hint": report["install_hint"],
            }
            for report in tool_reports
            if capability in report["capabilities"]
        ]
        provider_reports[capability] = providers
        applicable = [provider for provider in providers if provider["applicable"]]
        hints = [
            f"{provider['label']}: {provider['install_hint']}"
            for provider in applicable
            if provider["install_hint"]
        ]
        action = f"Missing capability `{capability}`."
        if hints:
            action += f" {' Or '.join(hints)}"
        elif applicable:
            action += " Configure one applicable provider declared in the toolchain registry."
        else:
            action += " Add an applicable provider to the toolchain registry for this platform."
        requirement_actions.append(action)
    requirements_ready = not missing_requirements
    return {
        "schema": "eprs.doctor/v1",
        "ok": required_ready and requirements_ready,
        "core_ready": required_ready,
        "platform": system_name,
        "python_runtime": platform.python_version(),
        "registry": str(registry_path),
        "extensions": [str(path) for path in extension_paths],
        "tools": tool_reports,
        # Compatibility summaries for existing automations.
        "commands": commands,
        "apps": apps,
        "adapters": adapters,
        "capabilities": capabilities,
        "workflow_catalog": workflow_catalog,
        "requirements": {
            "requested_workflows": requested_workflows,
            "requested_capabilities": requested_capabilities,
            "resolved_capabilities": resolved_requirements,
            "workflows": workflow_reports,
            "ready": requirements_ready,
            "missing_capabilities": missing_requirements,
            "providers": provider_reports,
            "next_actions": requirement_actions,
        },
        "next_actions": next_actions,
    }


SONG_DIRS = (
    "briefs", "code", "experiments", "recordings/raw", "recordings/selected",
    "stems", "mixes", "interchange", "masters", "video", "visuals", "notes", "FINAL",
)

FINAL_README = """# Final deliverables

This is the approved handoff folder. Start with the newest release directory in
this folder. Its main files are the approved lossless master, approved YouTube
video, `youtube-metadata.json`, `release.json`, and `HANDOFF.md`.

Keep experiments and works in progress in `experiments/`, `mixes/`, `masters/`,
or `video/`. Never render directly here or replace an editable source. Nothing
in this folder is uploaded or published automatically.
"""

SONG_README = """# {title}

Start with `_LISTEN.*`, `_WATCH.*`, and `_CHANGE_ME.md` at this folder's root.
They are stable, top-sorted pointers to the version that needs attention now;
the canonical files and provenance remain safely below. Point an agent at this
song folder or `_CHANGE_ME.md` and describe what should change.

`_CURRENT.json` records exactly what those pointers target. `FINAL/` remains
the home for approved delivery packages; use the other folders only when you
need to revise or regenerate something.

## Folder guide

- `code/` — editable recipes
- `recordings/raw/` — immutable original recordings
- `recordings/selected/` — selected performance material
- `stems/`, `mixes/`, `masters/` — audio work and master lineage
- `video/` — visual source, picture candidates, YouTube renders, and previews
- `visuals/` — editable visual scores and thumbnails
- `notes/` — sessions, clearances, reviews, and evidence
- `FINAL/` — approved, verified release packages only

The root pointers optimize review, not release state. The package inside
`FINAL/` remains the immutable finished handoff.
"""

VIDEO_README = """# Video workspace

- The rendered visual source belongs at the song's top-level video path or in a
  clearly named source folder.
- `pictures/` holds preserved picture candidates and review provenance.
- `youtube/` holds delivery renders and provenance sidecars.
- `previews/` holds one-off exploratory exports and is never the release source.

Use `FINAL/` for approved handoff files, not a working video folder.
"""


def new_song(root: str | Path, title: str) -> Path:
    destination = Path(root) / slugify(title)
    if destination.exists():
        raise FileExistsError(f"Song project already exists: {destination}")
    for folder in SONG_DIRS:
        (destination / folder).mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "eprs.song/v1", "title": title, "slug": destination.name,
        "created_at": utc_now(), "status": "seed", "sample_rate": 48000,
        "source_policy": "recordings/raw is immutable; create derived files elsewhere",
        "delivery_policy": "FINAL contains approved, verified copies only; never publish automatically",
    }
    (destination / "song.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (destination / "README.md").write_text(
        SONG_README.format(title=title), encoding="utf-8"
    )
    (destination / "FINAL" / "README.md").write_text(FINAL_README, encoding="utf-8")
    (destination / "video" / "README.md").write_text(VIDEO_README, encoding="utf-8")
    return destination


def load_song_manifest(song: Path) -> dict:
    manifest_path = song / "song.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Song manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid song manifest JSON: {manifest_path}: {exc.msg}") from exc
    if manifest.get("schema") != "eprs.song/v1":
        raise ValueError("unsupported song manifest schema")
    return manifest


def probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    completed = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries",
            (
                "format=duration,format_name:"
                "stream=codec_type,codec_name,sample_fmt,sample_rate,channels,"
                "bits_per_sample,bits_per_raw_sample,width,height,profile,pix_fmt,"
                "color_space,color_transfer,color_primaries,r_frame_rate,avg_frame_rate,"
                "field_order"
            ),
            "-of", "json", str(path),
        ],
        check=False, capture_output=True, text=True,
    )
    if completed.returncode:
        return {"error": completed.stderr.strip()}
    return json.loads(completed.stdout)


def ingest(
    source: str | Path,
    song: str | Path,
    role: str | None = None,
    note: str = "",
    *,
    rights_note: str = "rights and performer permissions not yet confirmed; do not publish",
    instrument: str | None = None,
) -> tuple[Path, Path]:
    if role is not None and instrument is not None:
        raise ValueError("provide source role or instrument compatibility value, not both")
    source_role = role if role is not None else instrument
    if source_role is None:
        raise ValueError("source role is required")
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    song_path = Path(song)
    load_song_manifest(song_path)
    role_slug = slugify(source_role)
    if not role_slug:
        raise ValueError("source role must contain at least one letter or number")
    raw = song_path / "recordings" / "raw" / role_slug
    raw.mkdir(parents=True, exist_ok=True)
    digest = sha256(source_path)
    destination = raw / f"{digest[:10]}-{source_path.name}"
    if destination.exists() and sha256(destination) != digest:
        # A ten-character prefix collision must never alias different media.
        destination = raw / f"{digest}-{source_path.name}"
    if not destination.exists():
        shutil.copy2(source_path, destination)
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if sidecar.exists():
        try:
            existing = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise FileExistsError(f"Recording has invalid existing provenance: {sidecar}: {exc.msg}") from exc
        if existing.get("schema") == "eprs.recording/v1" and existing.get("sha256") == digest:
            return destination, sidecar
        raise FileExistsError(f"Recording has conflicting existing provenance: {sidecar}")
    metadata = {
        "schema": "eprs.recording/v1", "id": digest, "ingested_at": utc_now(),
        "original_name": source_path.name,
        "stored_path": str(destination.relative_to(song_path)),
        # ``instrument`` remains as a compatibility field for eprs.recording/v1
        # readers; ``role`` covers voices, verbal beat ideas, rooms, and found sound.
        "role": source_role, "instrument": source_role, "note": note, "sha256": digest,
        "probe": probe(destination), "rights": rights_note,
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar


def _unique_experiment_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{name}-{suffix}"
        suffix += 1
    return candidate


def _freeze_experiment_input(song: Path, experiment: Path, role: str, source: Path) -> dict:
    """Freeze a source by copy, or reference it when raw intake is immutable."""
    source_path = source.resolve()
    digest = sha256(source_path)
    song_root = song.resolve()
    raw_root = (song / "recordings" / "raw").resolve()
    try:
        source_path.relative_to(raw_root)
        return {
            "role": role,
            "path": str(source_path.relative_to(song_root)),
            "base": "song",
            "storage": "song-reference",
            "original_name": source_path.name,
            "sha256": digest,
        }
    except ValueError:
        pass

    inputs_dir = experiment / "inputs"
    inputs_dir.mkdir(exist_ok=True)
    input_id = slugify(role)
    destination = inputs_dir / f"{input_id}-{source_path.name}"
    if destination.exists() and sha256(destination) != digest:
        destination = inputs_dir / f"{input_id}-{digest[:10]}-{source_path.name}"
    if not destination.exists():
        shutil.copy2(source_path, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"experiment source changed while it was being frozen: {source_path}")
    return {
        "role": role,
        "path": str(destination.relative_to(experiment)),
        "base": "experiment",
        "storage": "experiment-copy",
        "original_name": source_path.name,
        "sha256": digest,
    }


def create_experiment(
    song: str | Path,
    beat: str | Path | None,
    brief: str | Path | None,
    note: str,
    seed: int,
    sources: list[tuple[str, str | Path]] | None = None,
    origin: dict | None = None,
) -> Path:
    """Create a v2 experiment from any role-labeled creative sources.

    ``beat`` and ``brief`` remain convenience inputs for existing callers. Raw
    intake is referenced by checksum; every other source is copied so later
    edits cannot silently change the evidence behind a decision.
    """
    song_path = Path(song)
    load_song_manifest(song_path)
    requested: list[tuple[str, Path]] = []
    if beat is not None:
        requested.append(("beat", Path(beat)))
    if brief is not None:
        requested.append(("brief", Path(brief)))
    requested.extend((role, Path(path)) for role, path in (sources or []))
    if not requested:
        raise ValueError("experiment requires --beat, --brief, or at least one --source ROLE=PATH")

    validated: list[tuple[str, str, Path]] = []
    input_ids: set[str] = set()
    for role, source_path in requested:
        input_id = slugify(role)
        if not input_id:
            raise ValueError("experiment source role must contain at least one letter or number")
        if input_id in input_ids:
            raise ValueError(f"duplicate experiment source role: {role}")
        resolved_source = source_path.resolve()
        if not resolved_source.is_file():
            raise FileNotFoundError(resolved_source)
        input_ids.add(input_id)
        validated.append((input_id, role, resolved_source))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    subject = slugify(note) or validated[0][0] or "experiment"
    experiment = _unique_experiment_path(song_path / "experiments", f"{stamp}-{subject}")
    temporary = experiment.with_name(f".{experiment.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"Incomplete experiment creation already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        frozen_inputs = {
            input_id: _freeze_experiment_input(song_path, temporary, role, source_path)
            for input_id, role, source_path in validated
        }
        manifest = {
            "schema": "eprs.experiment/v2", "created_at": utc_now(), "status": "planned",
            "hypothesis": note, "seed": seed, "inputs": frozen_inputs,
            "results": [], "listening_notes": [], "decision": None,
        }
        if origin is not None:
            manifest["origin"] = origin
        (temporary / "experiment.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(experiment)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return experiment


def _experiment_result(experiment_path: Path, result: str | Path) -> tuple[Path, dict]:
    """Preserve one result and return its portable evidence record."""
    result_path = Path(result).resolve()
    if not result_path.is_file():
        raise FileNotFoundError(result_path)
    try:
        recorded_path = str(result_path.relative_to(experiment_path))
    except ValueError:
        # Experiment manifests must remain portable and self-contained. Preserve
        # an external render as evidence without moving or changing its source.
        result_digest = sha256(result_path)
        results_dir = experiment_path / "results"
        results_dir.mkdir(exist_ok=True)
        preserved_result = results_dir / result_path.name
        if preserved_result.exists() and sha256(preserved_result) != result_digest:
            preserved_result = results_dir / f"{result_digest[:10]}-{result_path.name}"
        if not preserved_result.exists():
            shutil.copy2(result_path, preserved_result)
        result_path = preserved_result
        recorded_path = str(result_path.relative_to(experiment_path))
    return result_path, {
        "path": recorded_path,
        "sha256": sha256(result_path),
        "probe": probe(result_path),
    }


def record_experiment_result(
    experiment: str | Path,
    result: str | Path,
    technical_note: str = "",
) -> Path:
    """Attach a render without pretending that a creative listen occurred."""
    experiment_path = Path(experiment).resolve()
    manifest_path = experiment_path / "experiment.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Experiment manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") not in {"eprs.experiment/v1", "eprs.experiment/v2"}:
        raise ValueError("unsupported experiment manifest schema")
    if manifest.get("status") == "decided":
        raise ValueError("decided experiment results are immutable; create a new experiment")
    _, record = _experiment_result(experiment_path, result)
    results = manifest.setdefault("results", [])
    if not any(
        isinstance(existing, dict)
        and existing.get("path") == record["path"]
        and existing.get("sha256") == record["sha256"]
        for existing in results
    ):
        results.append(record)
    manifest["status"] = "rendered"
    manifest["rendered_at"] = utc_now()
    manifest["decision"] = None
    if technical_note:
        if not isinstance(technical_note, str) or not technical_note.strip():
            raise ValueError("technical_note must be non-empty text when supplied")
        manifest.setdefault("render_notes", []).append(technical_note.strip())
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def finish_experiment(experiment: str | Path, result: str | Path, listening_note: str, decision: str) -> Path:
    if decision not in {"keep", "change", "stop"}:
        raise ValueError("decision must be keep, change, or stop")
    if not isinstance(listening_note, str) or not listening_note.strip():
        raise ValueError("listening_note must be non-empty text")
    experiment_path = Path(experiment).resolve()
    manifest_path = experiment_path / "experiment.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Experiment manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") not in {"eprs.experiment/v1", "eprs.experiment/v2"}:
        raise ValueError("unsupported experiment manifest schema")
    _, record = _experiment_result(experiment_path, result)
    results = manifest.setdefault("results", [])
    if not any(
        isinstance(existing, dict)
        and existing.get("path") == record["path"]
        and existing.get("sha256") == record["sha256"]
        for existing in results
    ):
        results.append(record)
    manifest["status"] = "decided"
    manifest["completed_at"] = utc_now()
    manifest.setdefault("listening_notes", []).append(listening_note.strip())
    manifest["decision"] = decision
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def _project_files(folder: Path, *, exclude: set[str] | None = None) -> list[Path]:
    """Return user artifacts recursively, excluding hidden files and policy docs."""
    excluded = exclude or set()
    if not folder.is_dir():
        return []
    return sorted(
        path for path in folder.rglob("*")
        if path.is_file()
        and path.name not in excluded
        and not any(part.startswith(".") for part in path.relative_to(folder).parts)
    )


def _local_experiment_result(experiment: Path, value: object) -> Path | None:
    """Resolve a portable result reference without allowing it to escape."""
    if not isinstance(value, str) or not value:
        return None
    candidate = experiment / value
    try:
        candidate.resolve().relative_to(experiment.resolve())
    except ValueError:
        return None
    return candidate


def _local_experiment_input(song: Path, experiment: Path, record: object) -> Path | None:
    """Resolve v1/v2 input records while keeping references inside their base."""
    if not isinstance(record, dict):
        return None
    value = record.get("path")
    if not isinstance(value, str) or not value:
        return None
    base_name = record.get("base", "experiment")
    if base_name == "experiment":
        base = experiment
    elif base_name == "song":
        base = song
    else:
        return None
    candidate = base / value
    try:
        candidate.resolve().relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def song_status(song: str | Path, verify: bool = False) -> dict:
    """Summarize a song workspace for a returning human or agent.

    This is read-only. Ordinary status validates manifests and referenced file
    presence; ``verify`` also hashes evidence and can be slower for large media.
    """
    song_path = Path(song)
    manifest = load_song_manifest(song_path)
    # Local import avoids a module-initialization cycle: evidence bindings use
    # the shared checksum and slug helpers defined above.
    from .evidence import verify_evidence_bindings
    from .daw_return import verify_daw_return_mix
    from .groove import verify_groove_development
    from .interchange import verify_daw_interchange
    from .musical_observation import verify_musical_observation
    from .rhythm import verify_rhythm_observation

    attention: list[str] = []
    checksum_cache: dict[Path, str] = {}

    def checksum(path: Path) -> str:
        resolved = path.resolve()
        if resolved not in checksum_cache:
            checksum_cache[resolved] = sha256(resolved)
        return checksum_cache[resolved]

    def check_expected_checksum(path: Path, record: object, description: str) -> None:
        if not verify or not isinstance(record, dict):
            return
        expected = record.get("sha256")
        if not isinstance(expected, str) or not expected:
            attention.append(f"Missing checksum for {description}")
        elif checksum(path) != expected:
            attention.append(f"Checksum mismatch for {description}")

    missing_folders = [folder for folder in SONG_DIRS if not (song_path / folder).is_dir()]
    if missing_folders:
        attention.append(f"Missing workspace folders: {', '.join(missing_folders)}")

    briefs = _project_files(song_path / "briefs")
    code = _project_files(song_path / "code")
    raw_files = _project_files(song_path / "recordings" / "raw")
    raw_recordings = [path for path in raw_files if not path.name.endswith(".json")]
    for recording in raw_recordings:
        sidecar = recording.with_suffix(recording.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Raw recording lacks provenance sidecar: {recording.relative_to(song_path)}")
        elif verify:
            try:
                recording_metadata = json.loads(sidecar.read_text())
            except json.JSONDecodeError as exc:
                attention.append(f"Invalid recording sidecar {sidecar.relative_to(song_path)}: {exc.msg}")
            else:
                check_expected_checksum(
                    recording,
                    recording_metadata,
                    f"raw recording {recording.relative_to(song_path)}",
                )

    selected_files = _project_files(song_path / "recordings" / "selected")
    selected_recordings = [path for path in selected_files if not path.name.endswith(".json")]
    for selected in selected_recordings:
        sidecar = selected.with_suffix(selected.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Selected recording lacks provenance sidecar: {selected.relative_to(song_path)}")
            continue
        if not verify:
            continue
        try:
            selection_metadata = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            attention.append(f"Invalid selection sidecar {sidecar.relative_to(song_path)}: {exc.msg}")
            continue
        check_expected_checksum(
            selected,
            selection_metadata.get("output"),
            f"selected recording {selected.relative_to(song_path)}",
        )
        source_record = selection_metadata.get("source")
        source_value = source_record.get("path") if isinstance(source_record, dict) else None
        source_path = song_path / source_value if isinstance(source_value, str) else None
        try:
            if source_path is None:
                raise ValueError
            source_path.resolve().relative_to(song_path.resolve())
        except ValueError:
            attention.append(f"Selected recording has invalid source reference: {selected.relative_to(song_path)}")
        else:
            if not source_path.is_file():
                attention.append(f"Selected recording source is missing: {selected.relative_to(song_path)}")
            else:
                check_expected_checksum(
                    source_path,
                    source_record,
                    f"source for selected recording {selected.relative_to(song_path)}",
                )

    rhythm_observations = [
        path for path in _project_files(song_path / "notes" / "rhythm")
        if path.suffix == ".json"
    ]
    invalid_rhythm_observations = 0
    for observation_path in rhythm_observations:
        try:
            _, observation = verify_rhythm_observation(
                song_path, observation_path, verify_checksum=verify
            )
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            invalid_rhythm_observations += 1
            attention.append(f"Invalid rhythm observation {observation_path.relative_to(song_path)}: {exc}")
            continue

    musical_observations = [
        path for path in _project_files(song_path / "notes" / "musical-observations")
        if path.suffix == ".json"
    ]
    invalid_musical_observations = 0
    for observation_path in musical_observations:
        try:
            verify_musical_observation(
                song_path, observation_path, verify_checksum=verify
            )
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            invalid_musical_observations += 1
            attention.append(
                f"Invalid musical observation {observation_path.relative_to(song_path)}: {exc}"
            )

    groove_counts = {"total": 0, "invalid": 0, "pending": 0, "keep": 0, "change": 0, "stop": 0}
    groove_manifests = [
        path for path in _project_files(song_path / "notes" / "grooves")
        if path.name == "groove.json"
    ]
    for groove_manifest in groove_manifests:
        groove_counts["total"] += 1
        try:
            _, groove = verify_groove_development(song_path, groove_manifest)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            groove_counts["invalid"] += 1
            groove_counts["pending"] += 1
            attention.append(
                f"Invalid groove development {groove_manifest.relative_to(song_path)}: {exc}"
            )
            continue
        review = groove.get("review")
        decision = review.get("decision") if isinstance(review, dict) else None
        notes = review.get("listening_notes") if isinstance(review, dict) else None
        has_matching_note = isinstance(notes, list) and any(
            isinstance(note, dict)
            and note.get("decision") == decision
            and isinstance(note.get("note"), str)
            and bool(note["note"].strip())
            for note in notes
        )
        if decision in {"keep", "change", "stop"} and has_matching_note:
            groove_counts[decision] += 1
        else:
            groove_counts["pending"] += 1

    phase_observations = [
        path for path in _project_files(song_path / "notes" / "phase")
        if path.suffix == ".json"
    ]
    invalid_phase_observations = 0
    for observation_path in phase_observations:
        relative_observation = observation_path.relative_to(song_path)
        try:
            observation = json.loads(observation_path.read_text())
            if observation.get("schema") != "eprs.phase-observation/v1":
                raise ValueError("unsupported schema")
            observation_id = observation.get("observation_id")
            if not isinstance(observation_id, str) or len(observation_id) != 64:
                raise ValueError("observation_id is invalid")
            recipe = observation.get("recipe")
            if not isinstance(recipe, dict):
                raise ValueError("recipe is invalid")
            expected_id = hashlib.sha256(
                json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if observation_id != expected_id:
                raise ValueError("observation_id does not match recipe")
            sources = observation.get("sources")
            if not isinstance(sources, dict):
                raise ValueError("sources are invalid")
            actions = observation.get("actions_performed")
            if not isinstance(actions, dict) or any(actions.get(key) is not False for key in (
                "source_audio_modified", "delay_applied", "polarity_inverted", "audio_rendered",
            )):
                raise ValueError("non-destructive action record is invalid")
        except (json.JSONDecodeError, ValueError) as exc:
            invalid_phase_observations += 1
            attention.append(f"Invalid phase observation {relative_observation}: {exc}")
            continue
        observation_invalid = False
        for channel in ("a", "b"):
            source_record = sources.get(channel)
            source_value = source_record.get("path") if isinstance(source_record, dict) else None
            source_path = song_path / source_value if isinstance(source_value, str) else None
            try:
                if source_path is None:
                    raise ValueError
                source_path.resolve().relative_to(song_path.resolve())
            except ValueError:
                observation_invalid = True
                attention.append(
                    f"Phase observation has invalid source {channel}: {relative_observation}"
                )
                continue
            if not source_path.is_file():
                observation_invalid = True
                attention.append(
                    f"Phase observation source {channel} is missing: {relative_observation}"
                )
            else:
                before_attention = len(attention)
                check_expected_checksum(
                    source_path,
                    source_record,
                    f"source {channel} for phase observation {relative_observation}",
                )
                if len(attention) > before_attention:
                    observation_invalid = True
        if observation_invalid:
            invalid_phase_observations += 1

    request_counts = {"total": 0, "invalid": 0, "recordings": 0, "evidence": 0}
    request_root = song_path / "notes" / "requests"
    if request_root.is_dir():
        for request_dir in sorted(path for path in request_root.iterdir() if path.is_dir()):
            if request_dir.name.startswith("."):
                request_counts["invalid"] += 1
                attention.append(f"Incomplete production request directory: {request_dir.name}")
                continue
            request_counts["total"] += 1
            manifest_path = request_dir / "request.json"
            try:
                request = json.loads(manifest_path.read_text())
                if request.get("schema") != "eprs.production-request-record/v1":
                    raise ValueError("unsupported schema")
                if request.get("id") != request_dir.name:
                    raise ValueError("id does not match directory")
                provided = request.get("provided")
                if not isinstance(provided, dict):
                    raise ValueError("provided must be an object")
                for field in ("title", "prompt", "intended_experience"):
                    if not isinstance(request.get(field), str) or not request[field].strip():
                        raise ValueError(f"{field} is missing")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                request_counts["invalid"] += 1
                attention.append(f"Invalid production request {request_dir.name}: {exc}")
                continue
            for item_id, record in provided.items():
                handling = record.get("handling") if isinstance(record, dict) else None
                rights_note = record.get("rights_note") if isinstance(record, dict) else None
                if not isinstance(rights_note, str) or not rights_note.strip():
                    attention.append(f"Production request {request_dir.name} lacks a rights note for {item_id}")
                base_name = record.get("base") if isinstance(record, dict) else None
                value = record.get("path") if isinstance(record, dict) else None
                if handling == "immutable-recording":
                    request_counts["recordings"] += 1
                elif handling == "frozen-evidence":
                    request_counts["evidence"] += 1
                else:
                    attention.append(f"Production request {request_dir.name} has invalid handling for {item_id}")
                base = song_path if base_name == "song" else request_dir if base_name == "request" else None
                source_path = base / value if base is not None and isinstance(value, str) else None
                try:
                    if source_path is None:
                        raise ValueError
                    source_path.resolve().relative_to(base.resolve())
                except ValueError:
                    attention.append(f"Production request {request_dir.name} has invalid path for {item_id}")
                    continue
                if not source_path.is_file():
                    attention.append(f"Production request {request_dir.name} source is missing: {item_id}")
                    continue
                check_expected_checksum(
                    source_path,
                    record,
                    f"source {item_id} for production request {request_dir.name}",
                )
                provenance_value = record.get("provenance_path") if isinstance(record, dict) else None
                if handling == "immutable-recording":
                    provenance_path = song_path / provenance_value if isinstance(provenance_value, str) else None
                    try:
                        if provenance_path is None:
                            raise ValueError
                        provenance_path.resolve().relative_to(song_path.resolve())
                    except ValueError:
                        attention.append(f"Production request {request_dir.name} has invalid provenance for {item_id}")
                    else:
                        if not provenance_path.is_file():
                            attention.append(f"Production request {request_dir.name} provenance is missing: {item_id}")
                        elif verify and record.get("provenance_sha256") != checksum(provenance_path):
                            attention.append(f"Checksum mismatch for production request provenance {item_id}")

    plan_counts = {
        "total": 0,
        "invalid": 0,
        "steps": 0,
        "entry_steps": 0,
        "gated_steps": 0,
        "revisions": 0,
        "complete_steps": 0,
        "active_steps": 0,
        "actionable_steps": 0,
        "queueable_steps": 0,
        "blocked_steps": 0,
        "stopped_steps": 0,
        "complete_plans": 0,
        "acceptances": 0,
        "invalid_acceptances": 0,
    }
    valid_plan_manifests: list[Path] = []
    plan_root = song_path / "notes" / "plans"
    if plan_root.is_dir():
        for plan_dir in sorted(path for path in plan_root.iterdir() if path.is_dir()):
            if plan_dir.name.startswith("."):
                plan_counts["invalid"] += 1
                attention.append(f"Incomplete production plan directory: {plan_dir.name}")
                continue
            plan_counts["total"] += 1
            manifest_path = plan_dir / "plan.json"
            try:
                plan = json.loads(manifest_path.read_text())
                if plan.get("schema") not in {
                    "eprs.production-plan-record/v1",
                    "eprs.production-plan-record/v2",
                }:
                    raise ValueError("unsupported schema")
                plan_id = plan.get("plan_id")
                if not isinstance(plan_id, str) or not plan_dir.name.endswith(plan_id[:10]):
                    raise ValueError("id does not match directory")
                recipe = plan.get("recipe")
                steps = recipe.get("steps") if isinstance(recipe, dict) else None
                entry_steps = plan.get("entry_steps")
                if not isinstance(steps, list) or not steps or not isinstance(entry_steps, list):
                    raise ValueError("steps or entry steps are invalid")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                plan_counts["invalid"] += 1
                attention.append(f"Invalid production plan {plan_dir.name}: {exc}")
                continue
            if verify:
                try:
                    from .plan import verify_production_plan
                    _, plan = verify_production_plan(song_path, manifest_path)
                    recipe = plan["recipe"]
                    steps = recipe["steps"]
                    entry_steps = plan["entry_steps"]
                except (FileNotFoundError, ValueError) as exc:
                    plan_counts["invalid"] += 1
                    attention.append(f"Production plan verification failed for {plan_dir.name}: {exc}")
                    continue
            plan_counts["steps"] += len(steps)
            plan_counts["entry_steps"] += len(entry_steps)
            plan_counts["gated_steps"] += sum(
                bool(step.get("gates")) for step in steps if isinstance(step, dict)
            )
            plan_counts["revisions"] += int(recipe.get("supersedes") is not None)
            acceptance_root = plan_dir / "acceptances"
            if acceptance_root.is_dir():
                for acceptance_path in sorted(acceptance_root.iterdir()):
                    if acceptance_path.name.startswith("."):
                        plan_counts["invalid_acceptances"] += 1
                        attention.append(
                            f"Incomplete production plan acceptance: "
                            f"{acceptance_path.relative_to(song_path)}"
                        )
                        continue
                    if not acceptance_path.is_file() or acceptance_path.suffix != ".json":
                        continue
                    plan_counts["acceptances"] += 1
                    try:
                        acceptance = json.loads(acceptance_path.read_text())
                        if (
                            not isinstance(acceptance, dict)
                            or acceptance.get("schema")
                            != "eprs.production-plan-acceptance/v1"
                        ):
                            raise ValueError("unsupported schema")
                        if verify:
                            from .planning import verify_plan_acceptance
                            verify_plan_acceptance(song_path, acceptance_path)
                    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                        plan_counts["invalid_acceptances"] += 1
                        attention.append(
                            f"Production plan acceptance verification failed for "
                            f"{acceptance_path.relative_to(song_path)}: {exc}"
                        )
            valid_plan_manifests.append(manifest_path)

    session_counts = {"total": 0, "invalid": 0, "takes": 0, "participants": 0, "setups": 0}
    session_root = song_path / "notes" / "sessions"
    if session_root.is_dir():
        for session_dir in sorted(path for path in session_root.iterdir() if path.is_dir()):
            if session_dir.name.startswith("."):
                session_counts["invalid"] += 1
                attention.append(f"Incomplete recording session directory: {session_dir.name}")
                continue
            session_counts["total"] += 1
            manifest_path = session_dir / "session.json"
            try:
                session = json.loads(manifest_path.read_text())
                if session.get("schema") != "eprs.recording-session-record/v1":
                    raise ValueError("unsupported schema")
                session_id = session.get("session_id")
                if not isinstance(session_id, str) or not session_dir.name.endswith(session_id[:10]):
                    raise ValueError("id does not match directory")
                participants = session.get("participants")
                setups = session.get("setups")
                takes = session.get("takes")
                if not isinstance(participants, dict) or not isinstance(setups, dict) or not isinstance(takes, dict) or not takes:
                    raise ValueError("participants, setups, or takes are invalid")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                session_counts["invalid"] += 1
                attention.append(f"Invalid recording session {session_dir.name}: {exc}")
                continue
            session_counts["participants"] += len(participants)
            session_counts["setups"] += len(setups)
            session_counts["takes"] += len(takes)
            for participant_id, participant in participants.items():
                consent = participant.get("consent_note") if isinstance(participant, dict) else None
                if not isinstance(participant, dict) or participant.get("id") != participant_id:
                    attention.append(f"Recording session {session_dir.name} has invalid participant: {participant_id}")
                elif not isinstance(consent, str) or not consent.strip():
                    attention.append(f"Recording session {session_dir.name} lacks consent context for {participant_id}")
            for setup_id, setup in setups.items():
                if not isinstance(setup, dict) or setup.get("id") != setup_id or not setup.get("capture_chain"):
                    attention.append(f"Recording session {session_dir.name} has invalid setup: {setup_id}")
            for take_id, take in takes.items():
                if not isinstance(take, dict) or take.get("id") != take_id:
                    attention.append(f"Recording session {session_dir.name} has invalid take: {take_id}")
                    continue
                participant_values = take.get("participant_ids")
                setup_values = take.get("setup_ids")
                if not isinstance(participant_values, list) or not all(isinstance(value, str) for value in participant_values):
                    attention.append(f"Recording session {session_dir.name} take has invalid participants: {take_id}")
                    participant_values = []
                if not isinstance(setup_values, list) or not all(isinstance(value, str) for value in setup_values):
                    attention.append(f"Recording session {session_dir.name} take has invalid setups: {take_id}")
                    setup_values = []
                if set(participant_values) - set(participants):
                    attention.append(f"Recording session {session_dir.name} take has unknown participants: {take_id}")
                if not setup_values or set(setup_values) - set(setups):
                    attention.append(f"Recording session {session_dir.name} take has invalid setups: {take_id}")
                rights = take.get("rights_note")
                if not isinstance(rights, str) or not rights.strip():
                    attention.append(f"Recording session {session_dir.name} lacks a rights note for {take_id}")
                media_value = take.get("path")
                provenance_value = take.get("provenance_path")
                media_path = song_path / media_value if isinstance(media_value, str) else None
                provenance_path = song_path / provenance_value if isinstance(provenance_value, str) else None
                try:
                    if media_path is None or provenance_path is None:
                        raise ValueError
                    media_path.resolve().relative_to((song_path / "recordings" / "raw").resolve())
                    provenance_path.resolve().relative_to((song_path / "recordings" / "raw").resolve())
                except ValueError:
                    attention.append(f"Recording session {session_dir.name} has unsafe evidence for {take_id}")
                    continue
                if not media_path.is_file():
                    attention.append(f"Recording session {session_dir.name} take is missing: {take_id}")
                else:
                    check_expected_checksum(media_path, take, f"take {take_id} for recording session {session_dir.name}")
                if not provenance_path.is_file():
                    attention.append(f"Recording session {session_dir.name} provenance is missing: {take_id}")
                elif verify and take.get("provenance_sha256") != checksum(provenance_path):
                    attention.append(f"Checksum mismatch for recording session provenance {take_id}")
            if verify:
                try:
                    # Local import avoids a module cycle: session intake uses
                    # the system's immutable recording primitives.
                    from .session import verify_recording_session
                    verify_recording_session(song_path, manifest_path)
                except (FileNotFoundError, ValueError) as exc:
                    session_counts["invalid"] += 1
                    attention.append(f"Recording session verification failed for {session_dir.name}: {exc}")

    clearance_counts = {"total": 0, "invalid": 0, "approved": 0, "pending": 0, "declined": 0, "takes": 0}
    clearance_root = song_path / "notes" / "clearances"
    if clearance_root.is_dir():
        partials = [path for path in clearance_root.rglob(".*.partial") if path.is_file()]
        for partial in partials:
            clearance_counts["invalid"] += 1
            attention.append(f"Incomplete recording clearance: {partial.relative_to(song_path)}")
        clearance_files = [
            path for path in _project_files(clearance_root)
            if path.suffix == ".json"
        ]
        for clearance_path in clearance_files:
            clearance_counts["total"] += 1
            try:
                clearance = json.loads(clearance_path.read_text())
                if clearance.get("schema") != "eprs.recording-clearance-record/v1":
                    raise ValueError("unsupported schema")
                status_value = clearance.get("status")
                if status_value not in {"approved", "pending", "declined"}:
                    raise ValueError("invalid status")
                takes = clearance.get("takes")
                participants = clearance.get("participants")
                if not isinstance(takes, list) or not takes or not isinstance(participants, list):
                    raise ValueError("takes or participants are invalid")
                session_evidence = clearance.get("session")
                if not isinstance(session_evidence, dict):
                    raise ValueError("session evidence is invalid")
            except (json.JSONDecodeError, ValueError) as exc:
                clearance_counts["invalid"] += 1
                attention.append(f"Invalid recording clearance {clearance_path.relative_to(song_path)}: {exc}")
                continue
            if verify:
                try:
                    from .clearance import verify_recording_clearance
                    verify_recording_clearance(song_path, clearance_path)
                except (FileNotFoundError, ValueError) as exc:
                    clearance_counts["invalid"] += 1
                    attention.append(
                        f"Recording clearance verification failed for {clearance_path.relative_to(song_path)}: {exc}"
                    )
                    continue
            clearance_counts[status_value] += 1
            clearance_counts["takes"] += len(takes)

    research_counts = {
        "total": 0,
        "invalid": 0,
        "sources": 0,
        "findings": 0,
        "experiments": 0,
        "work_origins": 0,
    }
    research_root = song_path / "notes" / "research"
    if research_root.is_dir():
        for research_dir in sorted(path for path in research_root.iterdir() if path.is_dir()):
            if research_dir.name.startswith("."):
                research_counts["invalid"] += 1
                attention.append(f"Incomplete research record directory: {research_dir.name}")
                continue
            research_counts["total"] += 1
            manifest_path = research_dir / "research.json"
            try:
                research = json.loads(manifest_path.read_text())
                if research.get("schema") != "eprs.research-record/v1":
                    raise ValueError("unsupported schema")
                research_id = research.get("research_id")
                if not isinstance(research_id, str) or not research_dir.name.endswith(research_id[:10]):
                    raise ValueError("id does not match directory")
                recipe = research.get("recipe")
                sources = research.get("sources")
                if not isinstance(recipe, dict) or not isinstance(sources, dict) or not sources:
                    raise ValueError("recipe or sources are invalid")
                findings = recipe.get("findings")
                experiments = recipe.get("experiments")
                if not isinstance(findings, list) or not findings or not isinstance(experiments, list):
                    raise ValueError("findings or experiments are invalid")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                research_counts["invalid"] += 1
                attention.append(f"Invalid research record {research_dir.name}: {exc}")
                continue
            if verify:
                try:
                    # Local import avoids a module cycle: research intake uses
                    # song and checksum primitives from this module.
                    from .research import verify_research_record
                    _, research = verify_research_record(song_path, manifest_path)
                    recipe = research["recipe"]
                    sources = research["sources"]
                    findings = recipe["findings"]
                    experiments = recipe["experiments"]
                except (FileNotFoundError, ValueError) as exc:
                    research_counts["invalid"] += 1
                    attention.append(f"Research verification failed for {research_dir.name}: {exc}")
                    continue
            research_counts["sources"] += len(sources)
            research_counts["findings"] += len(findings)
            research_counts["experiments"] += len(experiments)
            research_counts["work_origins"] += int(recipe.get("work_origin") is not None)

    lyric_counts = {
        "total": 0,
        "invalid": 0,
        "sources": 0,
        "variants": 0,
        "pending": 0,
        "keep": 0,
        "alternate": 0,
        "stop": 0,
        "complete_records": 0,
        "work_origins": 0,
    }
    lyric_root = song_path / "notes" / "lyrics"
    if lyric_root.is_dir():
        for lyric_dir in sorted(path for path in lyric_root.iterdir() if path.is_dir()):
            if lyric_dir.name.startswith("."):
                lyric_counts["invalid"] += 1
                attention.append(f"Incomplete lyrics record directory: {lyric_dir.name}")
                continue
            if (lyric_dir / ".lyrics-review.lock").exists():
                attention.append(f"Lyrics review lock requires inspection: {lyric_dir.name}")
            if (lyric_dir / ".lyrics.json.partial").exists():
                lyric_counts["invalid"] += 1
                attention.append(f"Incomplete lyrics review update: {lyric_dir.name}")
            lyric_counts["total"] += 1
            manifest_path = lyric_dir / "lyrics.json"
            try:
                lyric = json.loads(manifest_path.read_text())
                if lyric.get("schema") != "eprs.lyric-development/v1":
                    raise ValueError("unsupported schema")
                development_id = lyric.get("development_id")
                if not isinstance(development_id, str) or not lyric_dir.name.endswith(development_id[:10]):
                    raise ValueError("id does not match directory")
                recipe = lyric.get("recipe")
                sources = lyric.get("sources")
                variants = recipe.get("variants") if isinstance(recipe, dict) else None
                reviews = lyric.get("reviews")
                if not isinstance(sources, dict) or not isinstance(variants, list) or not variants or not isinstance(reviews, dict):
                    raise ValueError("sources, variants, or reviews are invalid")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                lyric_counts["invalid"] += 1
                attention.append(f"Invalid lyrics record {lyric_dir.name}: {exc}")
                continue
            if verify:
                try:
                    from .lyrics import verify_lyric_development
                    _, lyric = verify_lyric_development(song_path, manifest_path)
                    recipe = lyric["recipe"]
                    sources = lyric["sources"]
                    variants = recipe["variants"]
                    reviews = lyric["reviews"]
                except (FileNotFoundError, ValueError) as exc:
                    lyric_counts["invalid"] += 1
                    attention.append(f"Lyrics verification failed for {lyric_dir.name}: {exc}")
                    continue
            lyric_counts["sources"] += len(sources)
            lyric_counts["variants"] += len(variants)
            lyric_counts["work_origins"] += int(recipe.get("work_origin") is not None)
            lyric_counts["complete_records"] += int(lyric.get("review_state") == "complete")
            for review in reviews.values():
                decision = review.get("decision") if isinstance(review, dict) else None
                if decision == "not-reviewed":
                    lyric_counts["pending"] += 1
                elif decision in {"keep", "alternate", "stop"}:
                    lyric_counts[decision] += 1

    performance_comparisons = [
        path for path in _project_files(song_path / "notes" / "comparisons")
        if path.suffix == ".json" and not path.name.startswith(".")
    ]
    comparisons_pending_review = 0
    comparison_take_decisions = {"keep": 0, "alternate": 0, "stop": 0}
    for comparison_path in performance_comparisons:
        try:
            comparison = json.loads(comparison_path.read_text())
            if comparison.get("schema") != "eprs.performance-comparison/v1":
                raise ValueError("unsupported schema")
            takes = comparison.get("takes")
            reviews = comparison.get("reviews")
            if not isinstance(takes, list) or len(takes) < 2 or not isinstance(reviews, dict):
                raise ValueError("takes or reviews are invalid")
        except (json.JSONDecodeError, ValueError) as exc:
            attention.append(f"Invalid performance comparison {comparison_path.relative_to(song_path)}: {exc}")
            comparisons_pending_review += 1
            continue
        reviewed_take_ids = set()
        for take in takes:
            take_id = take.get("id", "<unknown>") if isinstance(take, dict) else "<unknown>"
            source_record = take.get("source") if isinstance(take, dict) else None
            source_value = source_record.get("path") if isinstance(source_record, dict) else None
            source_path = song_path / source_value if isinstance(source_value, str) else None
            try:
                if source_path is None:
                    raise ValueError
                source_path.resolve().relative_to(song_path.resolve())
            except ValueError:
                attention.append(f"Performance comparison has invalid source for {take_id}: {comparison_path.relative_to(song_path)}")
            else:
                if not source_path.is_file():
                    attention.append(f"Performance comparison source is missing for {take_id}: {comparison_path.relative_to(song_path)}")
                else:
                    check_expected_checksum(
                        source_path,
                        source_record,
                        f"source {take_id} for performance comparison {comparison_path.relative_to(song_path)}",
                    )
            review = reviews.get(take_id)
            decision = review.get("decision") if isinstance(review, dict) else None
            if decision in comparison_take_decisions:
                comparison_take_decisions[decision] += 1
                reviewed_take_ids.add(take_id)
        derived_complete = len(reviewed_take_ids) == len(takes)
        if comparison.get("review_state") != ("complete" if derived_complete else "pending"):
            attention.append(f"Performance comparison has inconsistent review state: {comparison_path.relative_to(song_path)}")
        if not derived_complete:
            comparisons_pending_review += 1

    work_counts = {
        "total": 0,
        "queued": 0,
        "due": 0,
        "in_progress": 0,
        "completed": 0,
        "stopped": 0,
        "invalid": 0,
        "promotions": 0,
        "released_claims": 0,
        "plan_step_items": 0,
        "plan_step_completed": 0,
        "request_origin_items": 0,
        "request_origin_completed": 0,
    }
    work_root = song_path / "notes" / "work"
    status_now = datetime.now(timezone.utc)
    if work_root.is_dir():
        for item_dir in sorted(path for path in work_root.iterdir() if path.is_dir()):
            work_counts["total"] += 1
            item_path = item_dir / "work.json"
            try:
                item = json.loads(item_path.read_text())
                if item.get("schema") != "eprs.work-item/v1":
                    raise ValueError("unsupported schema")
                if item.get("id") != item_dir.name:
                    raise ValueError("id does not match directory")
                runs = item.get("runs")
                if not isinstance(runs, list) or not runs:
                    raise ValueError("runs must be a non-empty list")
                state = item.get("status")
                if state not in {"queued", "in_progress", "completed", "stopped"}:
                    raise ValueError("unsupported status")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                work_counts["invalid"] += 1
                attention.append(f"Invalid work item {item_dir.name}: {exc}")
                continue
            origin = item.get("origin")
            request_origin = item.get("request_origin")
            if origin is not None and request_origin is not None:
                work_counts["invalid"] += 1
                attention.append(f"Work item has conflicting origins: {item_dir.name}")
                continue
            if origin is not None:
                if (
                    not isinstance(origin, dict)
                    or origin.get("schema") not in {
                        "eprs.production-plan-step-origin/v1",
                        "eprs.production-plan-step-origin/v2",
                    }
                    or not isinstance(origin.get("step"), dict)
                ):
                    work_counts["invalid"] += 1
                    attention.append(f"Work item has an invalid production-plan origin: {item_dir.name}")
                    continue
                if verify:
                    try:
                        from .work import load_work_item
                        load_work_item(song_path, item_path)
                    except (FileNotFoundError, ValueError) as exc:
                        work_counts["invalid"] += 1
                        attention.append(
                            f"Work-item production-plan verification failed for {item_dir.name}: {exc}"
                        )
                        continue
                work_counts["plan_step_items"] += 1
                work_counts["plan_step_completed"] += int(state == "completed")
            if request_origin is not None:
                if (
                    not isinstance(request_origin, dict)
                    or request_origin.get("schema")
                    != "eprs.production-request-work-origin/v1"
                ):
                    work_counts["invalid"] += 1
                    attention.append(
                        f"Work item has an invalid production-request origin: {item_dir.name}"
                    )
                    continue
                if verify:
                    try:
                        from .work import load_work_item
                        load_work_item(song_path, item_path)
                    except (FileNotFoundError, ValueError) as exc:
                        work_counts["invalid"] += 1
                        attention.append(
                            f"Work-item production-request verification failed for "
                            f"{item_dir.name}: {exc}"
                        )
                        continue
                work_counts["request_origin_items"] += 1
                work_counts["request_origin_completed"] += int(state == "completed")
            work_counts[state] += 1
            current_run = runs[-1]
            if not isinstance(current_run, dict) or current_run.get("status") != state and state in {"queued", "in_progress"}:
                attention.append(f"Work item has inconsistent current run: {item_dir.name}")
            due_value = current_run.get("due_at") if isinstance(current_run, dict) else None
            if state == "queued" and isinstance(due_value, str):
                try:
                    due_moment = datetime.fromisoformat(due_value.replace("Z", "+00:00"))
                    if due_moment.tzinfo is None:
                        raise ValueError
                    if due_moment.astimezone(timezone.utc) <= status_now:
                        work_counts["due"] += 1
                except ValueError:
                    attention.append(f"Work item has invalid due time: {item_dir.name}")

            source_records = item.get("sources", {})
            if not isinstance(source_records, dict):
                attention.append(f"Work item has invalid sources: {item_dir.name}")
                source_records = {}
            for source_id, source_record in source_records.items():
                base_name = source_record.get("base") if isinstance(source_record, dict) else None
                source_value = source_record.get("path") if isinstance(source_record, dict) else None
                base = song_path if base_name == "song" else item_dir if base_name == "work-item" else None
                source_path = base / source_value if base is not None and isinstance(source_value, str) else None
                try:
                    if source_path is None:
                        raise ValueError
                    source_path.resolve().relative_to(base.resolve())
                except ValueError:
                    attention.append(f"Work item {item_dir.name} has invalid source: {source_id}")
                else:
                    if not source_path.is_file():
                        attention.append(f"Work item {item_dir.name} source is missing: {source_id}")
                    else:
                        check_expected_checksum(
                            source_path,
                            source_record,
                            f"source {source_id} for work item {item_dir.name}",
                        )

            for run in runs:
                if not isinstance(run, dict):
                    attention.append(f"Work item has an invalid run: {item_dir.name}")
                    continue
                claims = run.get("claims")
                if claims is not None:
                    if not isinstance(claims, list) or not all(isinstance(claim, dict) for claim in claims):
                        attention.append(f"Work item {item_dir.name} has invalid claim history")
                    else:
                        open_claims = [
                            claim for claim in claims
                            if claim.get("released_at") is None and claim.get("completed_at") is None
                        ]
                        if run.get("status") == "in_progress":
                            if len(open_claims) != 1 or open_claims[0].get("agent") != run.get("agent"):
                                attention.append(
                                    f"Work item {item_dir.name} claim history does not match its owner"
                                )
                        elif open_claims:
                            attention.append(
                                f"Work item {item_dir.name} has an open claim while not in progress"
                            )
                        work_counts["released_claims"] += sum(
                            1 for claim in claims if claim.get("released_at") is not None
                        )
                result_records = run.get("results", {})
                if isinstance(result_records, list) and not result_records:
                    continue
                if not isinstance(result_records, dict):
                    attention.append(f"Work item {item_dir.name} has invalid run results")
                    continue
                for result_id, result_record in result_records.items():
                    result_value = result_record.get("path") if isinstance(result_record, dict) else None
                    result_path = item_dir / result_value if isinstance(result_value, str) else None
                    try:
                        if result_path is None:
                            raise ValueError
                        result_path.resolve().relative_to(item_dir.resolve())
                    except ValueError:
                        attention.append(f"Work item {item_dir.name} has invalid result: {result_id}")
                    else:
                        if not result_path.is_file():
                            attention.append(f"Work item {item_dir.name} result is missing: {result_id}")
                        else:
                            check_expected_checksum(
                                result_path,
                                result_record,
                                f"result {result_id} for work item {item_dir.name}",
                            )

    for plan_manifest in valid_plan_manifests:
        try:
            from .plan_progress import production_plan_progress
            progress = production_plan_progress(song_path, plan_manifest)
        except (FileNotFoundError, ValueError) as exc:
            attention.append(
                f"Production plan progress unavailable for {plan_manifest.parent.name}: {exc}"
            )
            continue
        summary = progress["summary"]
        plan_counts["complete_steps"] += summary["complete"]
        plan_counts["active_steps"] += summary["active"]
        plan_counts["actionable_steps"] += summary["actionable"]
        plan_counts["queueable_steps"] += summary["queueable"]
        plan_counts["blocked_steps"] += summary["blocked"]
        plan_counts["stopped_steps"] += summary["stopped"]
        plan_counts["complete_plans"] += int(progress["state"] == "complete")

    experiment_counts = {"total": 0, "planned": 0, "rendered": 0, "decided": 0, "other": 0, "invalid": 0}
    kept_experiments = 0
    experiments_dir = song_path / "experiments"
    if experiments_dir.is_dir():
        for experiment_dir in sorted(path for path in experiments_dir.iterdir() if path.is_dir()):
            experiment_counts["total"] += 1
            experiment_manifest = experiment_dir / "experiment.json"
            try:
                experiment = json.loads(experiment_manifest.read_text())
                if experiment.get("schema") not in {"eprs.experiment/v1", "eprs.experiment/v2"}:
                    raise ValueError("unsupported schema")
                if not isinstance(experiment.get("inputs", {}), dict):
                    raise ValueError("inputs must be an object")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                experiment_counts["invalid"] += 1
                attention.append(f"Invalid experiment {experiment_dir.name}: {exc}")
                continue
            state = experiment.get("status")
            if state in {"planned", "rendered", "decided"}:
                experiment_counts[state] += 1
            else:
                experiment_counts["other"] += 1
            if experiment.get("decision") == "keep":
                kept_experiments += 1
            for input_id, input_record in experiment.get("inputs", {}).items():
                if input_record is None:  # v1 optional brief
                    continue
                input_path = _local_experiment_input(song_path, experiment_dir, input_record)
                if input_path is None or not input_path.is_file():
                    attention.append(
                        f"Experiment {experiment_dir.name} references a missing input: {input_id}"
                    )
                else:
                    check_expected_checksum(
                        input_path,
                        input_record,
                        f"experiment {experiment_dir.name} input {input_id}",
                    )
            origin = experiment.get("origin")
            if isinstance(origin, dict) and origin.get("schema") == "eprs.work-run-origin/v1":
                try:
                    snapshot_id = origin.get("work_item_snapshot_input")
                    source_ids = origin.get("work_source_inputs")
                    result_ids = origin.get("work_result_inputs")
                    run_number = origin.get("run_number")
                    if (
                        not isinstance(snapshot_id, str)
                        or not isinstance(source_ids, list)
                        or not all(isinstance(value, str) for value in source_ids)
                        or not isinstance(result_ids, list)
                        or not result_ids
                        or not all(isinstance(value, str) for value in result_ids)
                        or isinstance(run_number, bool)
                        or not isinstance(run_number, int)
                        or run_number < 1
                    ):
                        raise ValueError("invalid work-run origin fields")
                    required_ids = [snapshot_id, *source_ids, *result_ids]
                    if len(required_ids) != len(set(required_ids)):
                        raise ValueError("duplicate promoted input ids")
                    if any(value not in experiment["inputs"] for value in required_ids):
                        raise ValueError("promoted input is missing")
                    snapshot_path = _local_experiment_input(
                        song_path,
                        experiment_dir,
                        experiment["inputs"][snapshot_id],
                    )
                    if snapshot_path is None or not snapshot_path.is_file():
                        raise ValueError("work-item snapshot is missing")
                    snapshot = json.loads(snapshot_path.read_text())
                    if (
                        snapshot.get("schema") != "eprs.work-item/v1"
                        or snapshot.get("id") != origin.get("work_item_id")
                    ):
                        raise ValueError("work-item snapshot identity does not match")
                    promoted_run = next(
                        (
                            run for run in snapshot.get("runs", [])
                            if isinstance(run, dict) and run.get("number") == run_number
                        ),
                        None,
                    )
                    if (
                        not isinstance(promoted_run, dict)
                        or promoted_run.get("status") != "completed"
                        or promoted_run.get("decision") != origin.get("run_decision")
                    ):
                        raise ValueError("promoted work run does not match its snapshot")
                    snapshot_sources = snapshot.get("sources")
                    promoted_results = promoted_run.get("results")
                    if not isinstance(snapshot_sources, dict) or not isinstance(promoted_results, dict):
                        raise ValueError("work snapshot evidence collections are invalid")
                    expected_source_ids = {
                        slugify(f"work source: {record.get('role', source_id)}")
                        for source_id, record in snapshot_sources.items()
                        if isinstance(record, dict)
                    }
                    expected_result_ids = {
                        slugify(f"work result: {record.get('role', result_id)}")
                        for result_id, record in promoted_results.items()
                        if isinstance(record, dict)
                    }
                    if set(source_ids) != expected_source_ids or set(result_ids) != expected_result_ids:
                        raise ValueError("promoted evidence ids do not match the work snapshot")
                except (json.JSONDecodeError, ValueError) as exc:
                    attention.append(f"Invalid work promotion {experiment_dir.name}: {exc}")
                else:
                    work_counts["promotions"] += 1
            for result in experiment.get("results", []):
                relative_result = result.get("path") if isinstance(result, dict) else None
                result_path = _local_experiment_result(experiment_dir, relative_result)
                if result_path is None or not result_path.is_file():
                    attention.append(
                        f"Experiment {experiment_dir.name} references a missing result: {relative_result or '<no path>'}"
                    )
                else:
                    check_expected_checksum(
                        result_path,
                        result,
                        f"experiment {experiment_dir.name} result {relative_result}",
                    )

    stem_files = [
        path for path in _project_files(song_path / "stems")
        if not path.name.endswith(".json")
    ]
    stem_reviews = {"pending": 0, "keep": 0, "change": 0, "stop": 0}
    stem_kinds = {"processed": 0, "comp": 0}
    render_evidence = {"bindings": 0, "invalid_renders": 0}
    for stem_path in stem_files:
        sidecar = stem_path.with_suffix(stem_path.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Stem lacks provenance sidecar: {stem_path.relative_to(song_path)}")
            stem_reviews["pending"] += 1
            continue
        try:
            stem_metadata = json.loads(sidecar.read_text())
            stem_schema = stem_metadata.get("schema")
            if stem_schema not in {"eprs.process-render/v1", "eprs.comp-render/v1"}:
                raise ValueError("unsupported schema")
        except (json.JSONDecodeError, ValueError) as exc:
            attention.append(f"Invalid stem provenance {sidecar.relative_to(song_path)}: {exc}")
            stem_reviews["pending"] += 1
            continue
        output_record = stem_metadata.get("output")
        if not isinstance(output_record, dict) or output_record.get("path") != str(stem_path.relative_to(song_path)):
            attention.append(f"Stem has invalid output reference: {stem_path.relative_to(song_path)}")
        check_expected_checksum(stem_path, output_record, f"stem {stem_path.relative_to(song_path)}")
        if stem_schema == "eprs.process-render/v1":
            stem_kinds["processed"] += 1
            source_records = [stem_metadata.get("source")]
            recipe = stem_metadata.get("recipe")
            try:
                if not isinstance(recipe, dict):
                    raise ValueError("recipe is invalid")
                expected_recipe_id = hashlib.sha256(
                    json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                if stem_metadata.get("recipe_id") != expected_recipe_id:
                    raise ValueError("recipe id does not match recipe")
                bindings = recipe.get("evidence", [])
                verify_evidence_bindings(
                    song_path,
                    bindings,
                    f"processed stem {stem_path.relative_to(song_path)}",
                    verify_checksums=verify,
                )
                render_evidence["bindings"] += len(bindings)
            except (FileNotFoundError, ValueError) as exc:
                render_evidence["invalid_renders"] += 1
                attention.append(
                    f"Invalid processed-stem evidence {stem_path.relative_to(song_path)}: {exc}"
                )
        else:
            stem_kinds["comp"] += 1
            source_records = stem_metadata.get("sources", [])
            if not isinstance(source_records, list) or not source_records:
                attention.append(f"Comp stem has invalid sources: {stem_path.relative_to(song_path)}")
                source_records = []
        for source_index, source_record in enumerate(source_records, start=1):
            source_value = source_record.get("path") if isinstance(source_record, dict) else None
            source_path = song_path / source_value if isinstance(source_value, str) else None
            try:
                if source_path is None:
                    raise ValueError
                source_path.resolve().relative_to(song_path.resolve())
            except ValueError:
                attention.append(f"Stem has invalid source reference {source_index}: {stem_path.relative_to(song_path)}")
            else:
                if not source_path.is_file():
                    attention.append(f"Stem source is missing {source_index}: {stem_path.relative_to(song_path)}")
                else:
                    check_expected_checksum(
                        source_path,
                        source_record,
                        f"source {source_index} for stem {stem_path.relative_to(song_path)}",
                    )
        verification = stem_metadata.get("verification")
        if not isinstance(verification, dict) or not verification or not all(verification.values()):
            attention.append(f"Stem has incomplete render verification: {stem_path.relative_to(song_path)}")
        warnings = stem_metadata.get("warnings", [])
        if not isinstance(warnings, list):
            attention.append(f"Stem has invalid warnings: {stem_path.relative_to(song_path)}")
        else:
            attention.extend(f"Stem {stem_path.relative_to(song_path)}: {warning}" for warning in warnings)
        review = stem_metadata.get("review")
        decision = review.get("decision") if isinstance(review, dict) else None
        if decision in {"keep", "change", "stop"}:
            stem_reviews[decision] += 1
        else:
            stem_reviews["pending"] += 1

    mix_files = _project_files(song_path / "mixes")
    working_mixes = [path for path in mix_files if not path.name.endswith(".json")]
    mix_reviews = {"pending": 0, "keep": 0, "change": 0, "stop": 0}
    daw_return_mixes = 0
    for mix_path in working_mixes:
        sidecar = mix_path.with_suffix(mix_path.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Working mix lacks provenance sidecar: {mix_path.relative_to(song_path)}")
            mix_reviews["pending"] += 1
            continue
        try:
            mix_metadata = json.loads(sidecar.read_text())
            mix_schema = mix_metadata.get("schema")
            if mix_schema not in {"eprs.mix-render/v1", "eprs.daw-return-mix/v1"}:
                raise ValueError("unsupported schema")
            if mix_schema == "eprs.daw-return-mix/v1":
                _, _, mix_metadata = verify_daw_return_mix(song_path, mix_path)
                daw_return_mixes += 1
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            attention.append(f"Invalid mix provenance {sidecar.relative_to(song_path)}: {exc}")
            mix_reviews["pending"] += 1
            continue
        recipe = mix_metadata.get("recipe")
        try:
            if not isinstance(recipe, dict):
                raise ValueError("recipe is invalid")
            expected_recipe_id = hashlib.sha256(
                json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            if mix_metadata.get("recipe_id") != expected_recipe_id:
                raise ValueError("recipe id does not match recipe")
            bindings = recipe.get("evidence", [])
            if not isinstance(bindings, list):
                raise ValueError("evidence is invalid")
            verify_evidence_bindings(
                song_path,
                bindings,
                f"mix {mix_path.relative_to(song_path)}",
                verify_checksums=verify,
            )
            render_evidence["bindings"] += len(bindings)
        except (FileNotFoundError, ValueError) as exc:
            render_evidence["invalid_renders"] += 1
            attention.append(
                f"Invalid mix evidence {mix_path.relative_to(song_path)}: {exc}"
            )
        output_record = mix_metadata.get("output")
        output_value = output_record.get("path") if isinstance(output_record, dict) else None
        if output_value != str(mix_path.relative_to(song_path)):
            attention.append(f"Working mix has invalid output reference: {mix_path.relative_to(song_path)}")
        check_expected_checksum(
            mix_path,
            output_record,
            f"working mix {mix_path.relative_to(song_path)}",
        )
        warnings = mix_metadata.get("warnings", [])
        if not isinstance(warnings, list):
            attention.append(f"Working mix has invalid warnings: {mix_path.relative_to(song_path)}")
            warnings = []
        for warning in warnings:
            attention.append(f"Mix {mix_path.relative_to(song_path)}: {warning}")
        sources = mix_metadata.get("sources", [])
        if not isinstance(sources, list):
            attention.append(f"Working mix has invalid sources: {mix_path.relative_to(song_path)}")
            sources = []
        for source_record in sources:
            source_id = source_record.get("id", "<unknown>") if isinstance(source_record, dict) else "<unknown>"
            source_value = source_record.get("path") if isinstance(source_record, dict) else None
            source_path = song_path / source_value if isinstance(source_value, str) else None
            try:
                if source_path is None:
                    raise ValueError
                source_path.resolve().relative_to(song_path.resolve())
            except ValueError:
                attention.append(
                    f"Working mix {mix_path.relative_to(song_path)} has invalid source: {source_id}"
                )
            else:
                if not source_path.is_file():
                    attention.append(
                        f"Working mix {mix_path.relative_to(song_path)} source is missing: {source_id}"
                    )
                else:
                    check_expected_checksum(
                        source_path,
                        source_record,
                        f"source {source_id} for working mix {mix_path.relative_to(song_path)}",
                    )
        review = mix_metadata.get("review")
        decision = review.get("decision") if isinstance(review, dict) else None
        notes = review.get("listening_notes") if isinstance(review, dict) else None
        has_matching_note = isinstance(notes, list) and any(
            isinstance(record, dict)
            and record.get("decision") == decision
            and isinstance(record.get("note"), str)
            and bool(record["note"].strip())
            for record in notes
        )
        if decision in {"keep", "change", "stop"} and has_matching_note:
            mix_reviews[decision] += 1
        else:
            mix_reviews["pending"] += 1
            if decision in {"keep", "change", "stop"}:
                attention.append(f"Working mix has a decision without a matching listening note: {mix_path.relative_to(song_path)}")

    master_files = _project_files(song_path / "masters")
    working_masters = [path for path in master_files if not path.name.endswith(".json")]
    masters_pending_listen = 0
    for master_path in working_masters:
        sidecar = master_path.with_suffix(master_path.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Lossless master lacks provenance sidecar: {master_path.relative_to(song_path)}")
            masters_pending_listen += 1
            continue
        try:
            master_metadata = json.loads(sidecar.read_text())
            if master_metadata.get("schema") != "eprs.master-render/v1":
                raise ValueError("unsupported schema")
        except (json.JSONDecodeError, ValueError) as exc:
            attention.append(f"Invalid master provenance {sidecar.relative_to(song_path)}: {exc}")
            masters_pending_listen += 1
            continue
        output_record = master_metadata.get("output")
        output_value = output_record.get("path") if isinstance(output_record, dict) else None
        if output_value != str(master_path.relative_to(song_path)):
            attention.append(f"Lossless master has invalid output reference: {master_path.relative_to(song_path)}")
        check_expected_checksum(
            master_path,
            output_record,
            f"lossless master {master_path.relative_to(song_path)}",
        )
        source_record = master_metadata.get("source")
        source_value = source_record.get("path") if isinstance(source_record, dict) else None
        source_path = song_path / source_value if isinstance(source_value, str) else None
        try:
            if source_path is None:
                raise ValueError
            source_path.resolve().relative_to(song_path.resolve())
        except ValueError:
            attention.append(f"Lossless master has invalid source: {master_path.relative_to(song_path)}")
        else:
            if not source_path.is_file():
                attention.append(f"Lossless master source is missing: {master_path.relative_to(song_path)}")
            else:
                check_expected_checksum(
                    source_path,
                    source_record,
                    f"source for lossless master {master_path.relative_to(song_path)}",
                )
        provenance = source_record.get("provenance") if isinstance(source_record, dict) else None
        provenance_value = provenance.get("path") if isinstance(provenance, dict) else None
        provenance_path = song_path / provenance_value if isinstance(provenance_value, str) else None
        try:
            if provenance_path is None:
                raise ValueError
            provenance_path.resolve().relative_to(song_path.resolve())
        except ValueError:
            attention.append(f"Lossless master has invalid mix provenance: {master_path.relative_to(song_path)}")
        else:
            if not provenance_path.is_file():
                attention.append(f"Lossless master mix provenance is missing: {master_path.relative_to(song_path)}")
            else:
                check_expected_checksum(
                    provenance_path,
                    provenance,
                    f"mix provenance for lossless master {master_path.relative_to(song_path)}",
                )
        approval = master_metadata.get("approval", {})
        if not isinstance(approval, dict):
            attention.append(f"Lossless master has invalid approval state: {master_path.relative_to(song_path)}")
            masters_pending_listen += 1
        elif approval.get("creative_listen_through") != "approved":
            masters_pending_listen += 1

    video_files = [
        path for path in _project_files(song_path / "video")
        if not path.name.endswith(".json") and path.name != "README.md" and not path.name.startswith(".")
        and "youtube-assets" not in path.relative_to(song_path / "video").parts
        and "previews" not in path.relative_to(song_path / "video").parts
        and not {
            "pictures", "evidence"
        }.issubset(set(path.relative_to(song_path / "video").parts))
    ]
    youtube_videos = 0
    videos_approved = 0
    picture_counts = {"total": 0, "pending": 0, "keep": 0, "change": 0, "stop": 0, "invalid": 0}
    for video_path in video_files:
        sidecar = video_path.with_suffix(video_path.suffix + ".json")
        if not sidecar.is_file():
            attention.append(f"Video lacks provenance sidecar: {video_path.relative_to(song_path)}")
            continue
        try:
            video_metadata = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            attention.append(f"Invalid video provenance {sidecar.relative_to(song_path)}: {exc.msg}")
            continue
        schema = video_metadata.get("schema")
        if schema in {"eprs.youtube-render/v1", "eprs.youtube-render/v2"}:
            youtube_videos += 1
            output_record = video_metadata.get("output")
            output_value = output_record.get("path") if isinstance(output_record, dict) else None
            if output_value != str(video_path.relative_to(song_path)):
                attention.append(f"YouTube video has invalid output reference: {video_path.relative_to(song_path)}")
            check_expected_checksum(
                video_path,
                output_record,
                f"YouTube video {video_path.relative_to(song_path)}",
            )
            verification = video_metadata.get("verification")
            if not isinstance(verification, dict) or not verification or not all(verification.values()):
                attention.append(f"YouTube video has incomplete technical verification: {video_path.relative_to(song_path)}")
            master_record = video_metadata.get("master")
            master_value = master_record.get("path") if isinstance(master_record, dict) else None
            master_path = song_path / master_value if isinstance(master_value, str) else None
            try:
                if master_path is None:
                    raise ValueError
                master_path.resolve().relative_to((song_path / "masters").resolve())
            except ValueError:
                attention.append(f"YouTube video has invalid master reference: {video_path.relative_to(song_path)}")
            else:
                master_sidecar = master_path.with_suffix(master_path.suffix + ".json")
                if not master_path.is_file() or not master_sidecar.is_file():
                    attention.append(f"YouTube video master evidence is missing: {video_path.relative_to(song_path)}")
                elif verify:
                    if master_record.get("sha256") != checksum(master_path):
                        attention.append(f"Checksum mismatch for YouTube master {master_path.relative_to(song_path)}")
                    if master_record.get("provenance_sha256") != checksum(master_sidecar):
                        attention.append(f"Checksum mismatch for YouTube master provenance {master_sidecar.relative_to(song_path)}")
            approval = video_metadata.get("approval")
            if isinstance(approval, dict) and approval.get("visual_and_sync_review") == "approved":
                videos_approved += 1
        elif schema == "eprs.picture-candidate/v1":
            picture_counts["total"] += 1
            try:
                from .picture import verify_picture
                _, _, picture = verify_picture(song_path, video_path.resolve(), require_keep=False)
            except (FileNotFoundError, UnicodeDecodeError, ValueError) as exc:
                picture_counts["invalid"] += 1
                attention.append(
                    f"Invalid picture candidate {video_path.relative_to(song_path)}: {exc}"
                )
                continue
            decision = picture.get("review", {}).get("decision")
            if decision in {"keep", "change", "stop"}:
                picture_counts[decision] += 1
            else:
                picture_counts["pending"] += 1
        elif schema == "eprs.visual-render/v1":
            if video_metadata.get("output") != video_path.name:
                attention.append(f"Visual render has invalid output reference: {video_path.relative_to(song_path)}")
            if verify and video_metadata.get("output_sha256") != checksum(video_path):
                attention.append(f"Checksum mismatch for visual render {video_path.relative_to(song_path)}")
        else:
            attention.append(f"Video has unsupported provenance schema: {video_path.relative_to(song_path)}")

    from .youtube_assets import verify_youtube_asset_bundle

    youtube_asset_counts = {"total": 0, "pending": 0, "approved": 0, "invalid": 0}
    youtube_asset_root = song_path / "video" / "youtube-assets"
    if youtube_asset_root.is_dir():
        for manifest_path in sorted(youtube_asset_root.glob("*/*/bundle.json")):
            youtube_asset_counts["total"] += 1
            try:
                _, bundle = verify_youtube_asset_bundle(
                    song_path,
                    manifest_path,
                    require_approval=False,
                    verify_artifacts=verify,
                )
            except (FileNotFoundError, UnicodeDecodeError, ValueError) as exc:
                youtube_asset_counts["invalid"] += 1
                attention.append(
                    f"Invalid YouTube asset bundle {manifest_path.parent.name}: {exc}"
                )
                continue
            review = bundle.get("review", {})
            if review.get("editorial_and_accessibility_review") == "approved":
                youtube_asset_counts["approved"] += 1
            else:
                youtube_asset_counts["pending"] += 1
        for partial in sorted(youtube_asset_root.rglob(".*.partial")):
            youtube_asset_counts["invalid"] += 1
            attention.append(f"Incomplete YouTube asset bundle: {partial.relative_to(song_path)}")

    interchange_counts = {"packages": 0, "tracks": 0, "invalid": 0}
    interchange_root = song_path / "interchange"
    if interchange_root.is_dir():
        for package_dir in sorted(path for path in interchange_root.iterdir() if path.is_dir()):
            if package_dir.name.startswith("."):
                interchange_counts["invalid"] += 1
                attention.append(f"Incomplete DAW interchange package: {package_dir.name}")
                continue
            try:
                _, package = verify_daw_interchange(
                    song_path,
                    package_dir,
                    verify_checksums=verify,
                    verify_media=verify,
                )
            except (FileNotFoundError, ValueError) as exc:
                interchange_counts["invalid"] += 1
                attention.append(f"Invalid DAW interchange {package_dir.name}: {exc}")
                continue
            interchange_counts["packages"] += 1
            interchange_counts["tracks"] += len(package["tracks"])

    final_root = song_path / "FINAL"
    final_files = _project_files(final_root, exclude={"README.md"})
    release_packages = 0
    distribution_packages = 0
    invalid_releases = 0
    if final_root.is_dir():
        for release_dir in sorted(path for path in final_root.iterdir() if path.is_dir()):
            if release_dir.name.startswith("."):
                attention.append(f"Incomplete FINAL release directory: {release_dir.name}")
                invalid_releases += 1
                continue
            manifest_path = release_dir / "release.json"
            try:
                release_manifest = json.loads(manifest_path.read_text())
                package_schema = release_manifest.get("schema")
                if package_schema not in {
                    "eprs.release-package/v1",
                    "eprs.distribution-package/v1",
                }:
                    raise ValueError("unsupported schema")
                artifacts = release_manifest.get("artifacts")
                if not isinstance(artifacts, list) or not artifacts:
                    raise ValueError("artifacts must be a non-empty list")
                verification = release_manifest.get("verification")
                if not isinstance(verification, dict) or not verification or not all(verification.values()):
                    raise ValueError("verification is incomplete")
                recipe = release_manifest.get("recipe")
                if not isinstance(recipe, dict):
                    raise ValueError("recipe is invalid")
                expected_package_id = hashlib.sha256(
                    json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                id_key = "release_id" if package_schema == "eprs.release-package/v1" else "package_id"
                if (
                    release_manifest.get(id_key) != expected_package_id
                    or not release_dir.name.endswith(expected_package_id[:10])
                ):
                    raise ValueError("package id does not match its normalized recipe")
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
                attention.append(f"Invalid FINAL release {release_dir.name}: {exc}")
                invalid_releases += 1
                continue
            if package_schema == "eprs.release-package/v1":
                release_packages += 1
            else:
                distribution_packages += 1
            for artifact in artifacts:
                value = artifact.get("path") if isinstance(artifact, dict) else None
                artifact_path = song_path / value if isinstance(value, str) else None
                try:
                    if artifact_path is None:
                        raise ValueError
                    artifact_path.resolve().relative_to(release_dir.resolve())
                except ValueError:
                    attention.append(f"FINAL release {release_dir.name} has an invalid artifact path")
                else:
                    if not artifact_path.is_file():
                        attention.append(f"FINAL release artifact is missing: {artifact_path.relative_to(song_path)}")
                    else:
                        check_expected_checksum(
                            artifact_path,
                            artifact,
                            f"FINAL release artifact {artifact_path.relative_to(song_path)}",
                        )
            state_key = "publication" if package_schema == "eprs.release-package/v1" else "distribution"
            if not isinstance(release_manifest.get(state_key), dict):
                attention.append(f"FINAL release {release_dir.name} has invalid {state_key} state")

    from .publication import publication_status
    publication_report = publication_status(song_path, verify=verify)
    for error in publication_report["errors"]:
        attention.append(f"Invalid publication history {error['path']}: {error['error']}")
    publication_counts = publication_report["counts"]

    from .mix import verify_mix_provenance
    from .source_sketch import verify_source_sketch
    source_sketch_counts = {
        "total": 0, "invalid": 0, "pending": 0,
        "keep": 0, "change": 0, "stop": 0,
        "shapes": {"one-pass": 0, "call-response": 0, "loop": 0},
    }
    for source_sketch_path in sorted(
        (song_path / "notes" / "source-sketches").glob("*/*/source-sketch.json")
    ):
        try:
            _, source_sketch_record = verify_source_sketch(song_path, source_sketch_path)
            _, _, source_mix = verify_mix_provenance(
                song_path, source_sketch_record["paths"]["mix"]
            )
        except (FileNotFoundError, ValueError) as exc:
            source_sketch_counts["invalid"] += 1
            attention.append(
                f"Invalid source sketch {source_sketch_path.relative_to(song_path)}: {exc}"
            )
            continue
        source_sketch_counts["total"] += 1
        shape = source_sketch_record.get("arrangement", {}).get("shape", "one-pass")
        if shape in source_sketch_counts["shapes"]:
            source_sketch_counts["shapes"][shape] += 1
        decision = source_mix.get("review", {}).get("decision")
        if decision in {"keep", "change", "stop"}:
            source_sketch_counts[decision] += 1
        else:
            source_sketch_counts["pending"] += 1

    from .frontdoor import verify_current_media
    current_media = {"available": False, "status": None, "audio": None, "video": None}
    if (song_path / "_CURRENT.json").is_file():
        try:
            _, current_record = verify_current_media(song_path, verify_checksums=verify)
        except (FileNotFoundError, ValueError) as exc:
            attention.append(f"Invalid current review media: {exc}")
        else:
            current_media = {
                "available": True,
                "status": current_record.get("status"),
                "audio": current_record.get("pointers", {}).get("audio"),
                "video": current_record.get("pointers", {}).get("video"),
            }

    inventory = {
        "briefs": len(briefs),
        "code_sources": len(code),
        "raw_recordings": len(raw_recordings),
        "selected_recordings": len(selected_recordings),
        "rhythm_observations": len(rhythm_observations),
        "invalid_rhythm_observations": invalid_rhythm_observations,
        "musical_observations": len(musical_observations),
        "invalid_musical_observations": invalid_musical_observations,
        "groove_developments": groove_counts,
        "phase_observations": len(phase_observations),
        "invalid_phase_observations": invalid_phase_observations,
        "production_requests": request_counts,
        "production_plans": plan_counts,
        "recording_sessions": session_counts,
        "recording_clearances": clearance_counts,
        "research_records": research_counts,
        "lyric_developments": lyric_counts,
        "performance_comparisons": len(performance_comparisons),
        "comparisons_pending_review": comparisons_pending_review,
        "comparison_take_decisions": comparison_take_decisions,
        "work_items": work_counts,
        "experiments": experiment_counts,
        "source_sketches": source_sketch_counts,
        "stems": len(stem_files),
        "comp_stems": stem_kinds["comp"],
        "processed_stems": stem_kinds["processed"],
        "render_evidence": render_evidence,
        "stems_pending_review": stem_reviews["pending"],
        "stems_kept": stem_reviews["keep"],
        "stems_change": stem_reviews["change"],
        "stems_stopped": stem_reviews["stop"],
        "mixes": len(working_mixes),
        "daw_return_mixes": daw_return_mixes,
        "mixes_pending_review": mix_reviews["pending"],
        "mixes_kept": mix_reviews["keep"],
        "mixes_change": mix_reviews["change"],
        "mixes_stopped": mix_reviews["stop"],
        "daw_interchange": interchange_counts,
        "masters": len(working_masters),
        "masters_pending_listen": masters_pending_listen,
        "masters_approved": max(0, len(working_masters) - masters_pending_listen),
        "videos": len(video_files),
        "youtube_videos": youtube_videos,
        "videos_pending_review": max(0, youtube_videos - videos_approved),
        "videos_approved": videos_approved,
        "picture_candidates": picture_counts,
        "youtube_asset_bundles": youtube_asset_counts,
        "visuals": len(_project_files(song_path / "visuals")),
        "current_media": current_media,
        "final_deliverables": len(final_files),
        "release_packages": release_packages,
        "distribution_packages": distribution_packages,
        "invalid_releases": invalid_releases,
        "publication_handoffs": publication_counts["handoffs"],
        "publication_receipts": publication_counts["receipts"],
        "public_publication_receipts": publication_counts["public_receipts"],
        "invalid_publications": publication_counts["invalid"],
    }

    next_actions: list[str] = []
    if missing_folders:
        next_actions.append("Restore the missing workspace folders before production continues.")
    if (inventory["mixes"] or inventory["masters"] or inventory["videos"]) and not current_media["available"]:
        next_actions.append("Expose the version needing attention at song root with `eprs expose`.")
    if not briefs:
        next_actions.append("Write the musical intent and delivery target in briefs/.")
    if not raw_recordings and not code:
        next_actions.append("Ingest a performance or add an editable musical source in code/.")
    if work_counts["due"]:
        next_actions.append("Review due agent work with `eprs work list --due` and claim one narrow request.")
    if work_counts["in_progress"]:
        next_actions.append("Finish claimed agent work with frozen result evidence, or leave a clear follow-up decision.")
    if (
        request_counts["total"]
        and plan_counts["total"] == 0
        and work_counts["request_origin_items"] == 0
    ):
        next_actions.append(
            "Turn the captured request into an explicit dependency-aware roadmap: queue "
            "checksum-bound agent planning with `eprs work add --request <request-id>`, "
            "or author and freeze it directly with `eprs plan add`."
        )
    elif (
        request_counts["total"]
        and plan_counts["total"] == 0
        and work_counts["request_origin_completed"]
    ):
        next_actions.append(
            "Review the completed request-origin work result, then validate and freeze the "
            "exact authored roadmap with `eprs plan add`."
        )
    elif (
        request_counts["total"]
        and plan_counts["total"] == 0
        and work_counts["request_origin_items"]
        and not work_counts["due"]
        and not work_counts["in_progress"]
    ):
        next_actions.append(
            "Inspect the stopped or deferred request-origin planning work and queue one "
            "explicit follow-up if a roadmap is still wanted."
        )
    elif plan_counts["queueable_steps"] and work_counts["due"] == 0:
        next_actions.append(
            "Review an unstarted actionable production-plan step and its gates, then prepare "
            "one smallest work request with `eprs plan queue-next`."
        )
    if session_counts["total"] and experiment_counts["total"] == 0 and work_counts["total"] == 0:
        next_actions.append("Review the recording session's take, setup, consent, and rights context; then compare alternatives or freeze one narrow musical question.")
    if clearance_counts["pending"] or clearance_counts["declined"]:
        next_actions.append("Resolve pending or declined take/participant clearance before using that recording in a release package.")
    if research_counts["experiments"] and experiment_counts["total"] == 0:
        next_actions.append("Choose one research experiment idea and freeze its smallest audible test with `eprs experiment` or `eprs work promote`.")
    if lyric_counts["pending"]:
        next_actions.append("Read or sing every pending lyric variant in musical context and record keep/alternate/stop notes with `eprs lyrics review`.")
    if experiment_counts["rendered"]:
        next_actions.append("Listen to each rendered experiment end to end, then record keep/change/stop with `eprs finish`.")
    elif experiment_counts["planned"]:
        next_actions.append("Render, listen to, and finish the planned experiment(s).")
    elif experiment_counts["total"] == 0 and not session_counts["total"] and (briefs or raw_recordings or code):
        next_actions.append("Freeze one narrow musical hypothesis with `eprs experiment`.")
    if request_counts["recordings"] and source_sketch_counts["total"] == 0:
        next_actions.append(
            "Make one explicit source-aware diagnostic with `eprs source-sketch <song> "
            "--intent \"Describe who invites, answers, and leaves space\"`; capture alone never processes recordings."
        )
    if source_sketch_counts["pending"]:
        next_actions.append(
            "Listen through each source-aware sketch and record keep/change/stop with `eprs mix-review`."
        )
    if kept_experiments and not inventory["masters"]:
        next_actions.append("Develop the kept experiment into an arrangement or mix; preserve the experiment evidence.")
    if inventory["stems_pending_review"]:
        next_actions.append("Audition comps/processed stems against their sources and record `comp-review` or `process-review` decisions.")
    if inventory["comparisons_pending_review"]:
        next_actions.append("Audition comparison takes in both orders and record take-specific `eprs compare-review` decisions.")
    if inventory["invalid_phase_observations"]:
        next_actions.append("Restore or re-observe drifted multi-microphone phase evidence before relying on it in processing or mixing decisions.")
    if inventory["invalid_rhythm_observations"]:
        next_actions.append("Restore or re-observe drifted performed-rhythm evidence before interpreting it as a groove.")
    if inventory["invalid_musical_observations"]:
        next_actions.append("Restore or re-observe drifted phrase, pitch, and pulse evidence before using it in an arrangement.")
    if inventory["rhythm_observations"] and inventory["groove_developments"]["total"] == 0:
        next_actions.append("If a drummer-facing grid audition serves the current intent, author one explicit interpretation with `eprs groove add`; free-time remains valid.")
    if inventory["groove_developments"]["pending"]:
        next_actions.append("Audition each groove prototype against its performed idea and record `eprs groove review` keep/change/stop notes.")
    if inventory["groove_developments"]["change"]:
        next_actions.append("Author a new groove interpretation for changed prototypes; preserve the earlier evidence and listening note.")
    if inventory["render_evidence"]["invalid_renders"]:
        next_actions.append("Restore or supersede drifted evidence bound to processing or mix recipes before review or mastering.")
    if inventory["stems_change"]:
        next_actions.append("Revise changed processing recipes as new stems; preserve the rejected render and listening note.")
    if inventory["mixes_pending_review"]:
        next_actions.append("Listen through each working mix and record a `mix-review` balance/headroom decision before mastering.")
    if inventory["mixes_change"]:
        next_actions.append("Revise changed mix scores as new renders; preserve the rejected mix and listening note.")
    if inventory["daw_interchange"]["invalid"]:
        next_actions.append("Restore or regenerate invalid DAW interchange packages before handing them to another tool or collaborator.")
    if inventory["mixes_kept"] and not inventory["masters"]:
        next_actions.append("Master a chosen kept mix from an explicit lossless recipe.")
    if inventory["masters_pending_listen"]:
        next_actions.append("Listen through the lossless master and record creative approval before promotion to FINAL/.")
    if inventory["videos_pending_review"]:
        next_actions.append("Watch each video end to end, check picture and sync, then record approval for the chosen render.")
    if inventory["picture_candidates"]["pending"]:
        next_actions.append(
            "Watch each captured picture end to end and record a `picture review` keep/change/stop decision."
        )
    if inventory["picture_candidates"]["change"]:
        next_actions.append(
            "Return changed picture candidates to their declared renderer or editor; preserve the captured version and review note."
        )
    if inventory["picture_candidates"]["keep"] and not inventory["youtube_videos"]:
        next_actions.append(
            "Assemble a kept picture with its exact approved master using an `eprs.youtube/v2` recipe, then review the final sync."
        )
    if inventory["videos_approved"] and inventory["youtube_asset_bundles"]["total"] == 0:
        next_actions.append(
            "Author a checksum-bound thumbnail, captions, chapters, and accessibility bundle "
            "with `eprs youtube-assets add`."
        )
    if inventory["youtube_asset_bundles"]["pending"]:
        next_actions.append(
            "Review the complete thumbnail, captions, chapters, and accessibility context with "
            "`eprs youtube-assets review` before FINAL packaging."
        )
    if inventory["youtube_asset_bundles"]["invalid"]:
        next_actions.append(
            "Restore or supersede invalid YouTube asset evidence before using it in a release."
        )
    if (inventory["masters_approved"] or inventory["videos_approved"]) and not inventory["final_deliverables"]:
        next_actions.append(
            "Prepare an approved delivery: `eprs distribution` for distributor-ready streaming assets, "
            "or `eprs release` for YouTube video and metadata."
        )
    if inventory["release_packages"] and not inventory["publication_handoffs"]:
        next_actions.append(
            "Prepare exact offline uploader inputs with `eprs publication prepare`; this does "
            "not authorize or perform an upload."
        )
    elif inventory["publication_handoffs"] > inventory["publication_receipts"]:
        next_actions.append(
            "Publication handoff is ready. Upload only after explicit current-user authorization, "
            "then record the external result with `eprs publication receipt`."
        )
    elif inventory["final_deliverables"]:
        next_actions.append(
            "Preserve FINAL and append-only publication receipts; further visibility changes "
            "remain separate explicitly authorized actions."
        )

    return {
        "schema": "eprs.status/v1",
        "checksums_verified": verify,
        "song": {
            "title": manifest.get("title", song_path.name),
            "slug": manifest.get("slug", song_path.name),
            "declared_status": manifest.get("status"),
            "path": str(song_path),
        },
        "inventory": inventory,
        "attention": attention,
        "next_actions": next_actions,
    }


def format_song_status(status: dict) -> str:
    """Format ``song_status`` for quick terminal orientation."""
    song = status["song"]
    inventory = status["inventory"]
    experiments = inventory["experiments"]
    work_items = inventory["work_items"]
    lines = [
        f"{song['title']} ({song['declared_status'] or 'unspecified'})",
        f"Workspace: {song['path']}",
        (
            "Review now: "
            + (
                f"{inventory['current_media']['audio']}"
                + (f" + {inventory['current_media']['video']}" if inventory['current_media']['video'] else "")
                + f" ({inventory['current_media']['status']})"
                if inventory["current_media"]["available"] else "not exposed"
            )
        ),
        (
            "Sources: "
            f"{inventory['briefs']} brief(s), {inventory['code_sources']} code source(s), "
            f"{inventory['raw_recordings']} raw recording(s), "
            f"{inventory['selected_recordings']} selected recording(s), "
            f"{inventory['rhythm_observations']} rhythm observation(s), "
            f"{inventory['musical_observations']} musical observation(s), "
            f"{inventory['groove_developments']['total']} groove interpretation(s) "
            f"({inventory['groove_developments']['pending']} pending review), "
            f"{inventory['phase_observations']} phase observation(s), "
            f"{inventory['render_evidence']['bindings']} render evidence binding(s), "
            f"{inventory['performance_comparisons']} performance comparison(s), "
            f"{inventory['production_requests']['total']} production request(s), "
            f"{inventory['production_plans']['total']} production plan(s), "
            f"{inventory['recording_sessions']['total']} recording session(s), "
            f"{inventory['recording_clearances']['approved']} approved recording clearance(s), "
            f"{inventory['research_records']['total']} research record(s)"
            f", {inventory['lyric_developments']['total']} lyric development(s), "
            f"{inventory['source_sketches']['total']} source-aware sketch(es) "
            f"({inventory['source_sketches']['pending']} pending review)"
        ),
        (
            "Experiments: "
            f"{experiments['total']} total, {experiments['planned']} planned, "
            f"{experiments['rendered']} rendered pending listen, "
            f"{experiments['decided']} decided, {experiments['invalid']} invalid"
        ),
        (
            "Agent work: "
            f"{work_items['total']} total, {work_items['queued']} queued ({work_items['due']} due), "
            f"{work_items['in_progress']} in progress, {work_items['promotions']} promotion(s), "
            f"{work_items['request_origin_items']} request-origin item(s) "
            f"({work_items['request_origin_completed']} completed), "
            f"{work_items['plan_step_items']} plan-step item(s) "
            f"({work_items['plan_step_completed']} completed), "
            f"{work_items['released_claims']} released claim(s), {work_items['invalid']} invalid"
        ),
        (
            "Plan progress: "
            f"{inventory['production_plans']['complete_steps']} complete step(s), "
            f"{inventory['production_plans']['active_steps']} active, "
            f"{inventory['production_plans']['actionable_steps']} actionable, "
            f"{inventory['production_plans']['queueable_steps']} queueable, "
            f"{inventory['production_plans']['blocked_steps']} blocked, "
            f"{inventory['production_plans']['stopped_steps']} stopped, "
            f"{inventory['production_plans']['acceptances']} agent-plan acceptance(s)"
        ),
        (
            "Production: "
            f"{inventory['stems']} stem(s): {inventory['comp_stems']} comp(s), "
            f"{inventory['processed_stems']} processed ({inventory['stems_pending_review']} pending review), "
            f"{inventory['mixes']} mix(es) ({inventory['mixes_pending_review']} pending review), "
            f"{inventory['daw_return_mixes']} returned from a DAW, "
            f"{inventory['daw_interchange']['packages']} DAW interchange package(s), "
            f"{inventory['masters']} master(s) ({inventory['masters_pending_listen']} pending listen), "
            f"{inventory['videos']} video(s) ({inventory['videos_pending_review']} pending review), "
            f"{inventory['picture_candidates']['total']} picture candidate(s) "
            f"({inventory['picture_candidates']['pending']} pending, "
            f"{inventory['picture_candidates']['keep']} kept), "
            f"{inventory['youtube_asset_bundles']['total']} YouTube asset bundle(s) "
            f"({inventory['youtube_asset_bundles']['pending']} pending review), "
            f"{inventory['final_deliverables']} final file(s) in "
            f"{inventory['release_packages']} YouTube release package(s) and "
            f"{inventory['distribution_packages']} streaming package(s)"
        ),
        (
            "Publication: "
            f"{inventory['publication_handoffs']} offline handoff(s), "
            f"{inventory['publication_receipts']} receipt(s) "
            f"({inventory['public_publication_receipts']} public), "
            f"{inventory['invalid_publications']} invalid"
        ),
    ]
    if status["attention"]:
        lines.append("Attention:")
        lines.extend(f"  - {item}" for item in status["attention"])
    if status["next_actions"]:
        lines.append("Next:")
        lines.extend(f"  - {item}" for item in status["next_actions"])
    return "\n".join(lines)


def analyze(path: str | Path) -> dict:
    media = Path(path)
    result = {"path": str(media), "sha256": sha256(media), "probe": probe(media)}
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-nostats", "-i", str(media), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        summary_parts = completed.stderr.rsplit("Summary:", 1)
        if len(summary_parts) == 2:
            summary = summary_parts[1]
            integrated = re.search(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", summary)
            range_match = re.search(r"LRA:\s+(\d+(?:\.\d+)?) LU", summary)
            peak = re.search(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", summary)
            result["loudness"] = {
                "integrated_lufs": None if not integrated else float(integrated.group(1)),
                "range_lu": None if not range_match else float(range_match.group(1)),
                "true_peak_dbfs": None if not peak else float(peak.group(1)),
            }
    return result
