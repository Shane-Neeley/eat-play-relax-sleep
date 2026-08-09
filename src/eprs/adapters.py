"""Read-only discovery of portable, tool-specific production handoff guides."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from .system import (
    PROJECT_ROOT,
    REPOSITORY_LOCAL_CONFIG_DIR,
    TOOLCHAIN_PATH,
    doctor,
    load_toolchain,
)


ADAPTER_PROFILE_SCHEMA = "eprs.software-adapter/v1"
ADAPTER_CATALOG_SCHEMA = "eprs.adapter-catalog/v1"
ADAPTER_GUIDE_SCHEMA = "eprs.adapter-guide/v1"
ADAPTER_FIT_SCHEMA = "eprs.adapter-fit/v1"
REPOSITORY_ADAPTER_PROFILE_DIR = PROJECT_ROOT / "config" / "adapters"
INSTALLED_ADAPTER_PROFILE_DIR = Path(sys.prefix) / "share" / "eprs" / "adapters"
ADAPTER_PROFILE_DIR = (
    REPOSITORY_ADAPTER_PROFILE_DIR
    if REPOSITORY_ADAPTER_PROFILE_DIR.is_dir()
    else INSTALLED_ADAPTER_PROFILE_DIR
)
REPOSITORY_LOCAL_ADAPTER_PROFILE_DIR = REPOSITORY_LOCAL_CONFIG_DIR / "adapters"
SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
AUTOMATION_KINDS = {"cli", "gui", "hybrid"}
MAX_PROFILES = 128
MAX_HANDOFFS = 32
MAX_ITEMS = 32


def _text(record: dict, key: str, label: str, maximum: int = 4096) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"software adapter {label} requires non-empty {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"software adapter {label} {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _slug(record: dict, key: str, label: str) -> str:
    value = _text(record, key, label, 256)
    if not SLUG.fullmatch(value):
        raise ValueError(f"software adapter {label} {key} must be a portable slug")
    return value


def _text_list(
    value: object,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = MAX_ITEMS,
) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(
            f"software adapter {label} must contain {minimum} to {maximum} text items"
        )
    result: list[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"software adapter {label} item {index} must be non-empty text")
        clean = item.strip()
        if len(clean.encode("utf-8")) > 4096:
            raise ValueError(f"software adapter {label} item {index} exceeds 4096 UTF-8 bytes")
        if clean in result:
            raise ValueError(f"software adapter {label} contains a duplicate item")
        result.append(clean)
    return result


def _capabilities(value: object, label: str) -> list[str]:
    values = _text_list(value, label)
    if not all(SLUG.fullmatch(item) for item in values):
        raise ValueError(f"software adapter {label} must contain portable capability slugs")
    return values


def _normalize_handoff(value: object, profile_id: str, number: int) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"software adapter {profile_id} handoff {number} must be an object")
    allowed = {
        "id", "label", "intent", "capabilities", "automation",
        "requires_user_operation", "inputs", "outputs", "steps", "verification",
    }
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(
            f"software adapter {profile_id} handoff {number} has unknown fields: "
            f"{', '.join(unexpected)}"
        )
    handoff_id = _slug(value, "id", f"{profile_id} handoff {number}")
    automation = value.get("automation")
    if automation not in AUTOMATION_KINDS:
        raise ValueError(
            f"software adapter {profile_id} handoff {handoff_id} automation must be "
            "cli, gui, or hybrid"
        )
    user_operation = value.get("requires_user_operation")
    if not isinstance(user_operation, bool):
        raise ValueError(
            f"software adapter {profile_id} handoff {handoff_id} "
            "requires_user_operation must be boolean"
        )
    return {
        "id": handoff_id,
        "label": _text(value, "label", f"{profile_id} handoff {handoff_id}", 1024),
        "intent": _text(value, "intent", f"{profile_id} handoff {handoff_id}"),
        "capabilities": _capabilities(
            value.get("capabilities"), f"{profile_id} handoff {handoff_id} capabilities"
        ),
        "automation": automation,
        "requires_user_operation": user_operation,
        "inputs": _text_list(value.get("inputs"), f"{profile_id} handoff {handoff_id} inputs"),
        "outputs": _text_list(
            value.get("outputs"), f"{profile_id} handoff {handoff_id} outputs"
        ),
        "steps": _text_list(value.get("steps"), f"{profile_id} handoff {handoff_id} steps"),
        "verification": _text_list(
            value.get("verification"),
            f"{profile_id} handoff {handoff_id} verification",
        ),
    }


def _normalize_profile(value: object, source: Path, providers: dict[str, dict]) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"software adapter profile must be an object: {source}")
    allowed = {
        "schema", "id", "label", "summary", "provider", "capabilities",
        "handoffs", "safety",
    }
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(
            f"software adapter profile {source.name} has unknown fields: {', '.join(unexpected)}"
        )
    if value.get("schema") != ADAPTER_PROFILE_SCHEMA:
        raise ValueError(f"unsupported software adapter schema in {source}")
    profile_id = _slug(value, "id", source.name)
    provider_id = _slug(value, "provider", profile_id)
    provider = providers.get(provider_id)
    if provider is None:
        raise ValueError(
            f"software adapter {profile_id} references unknown toolchain provider: {provider_id}"
        )
    capabilities = _capabilities(value.get("capabilities"), f"{profile_id} capabilities")
    unknown = sorted(set(capabilities) - set(provider.get("capabilities", [])))
    if unknown:
        raise ValueError(
            f"software adapter {profile_id} claims capabilities not declared by {provider_id}: "
            f"{', '.join(unknown)}"
        )
    handoff_values = value.get("handoffs")
    if not isinstance(handoff_values, list) or not 1 <= len(handoff_values) <= MAX_HANDOFFS:
        raise ValueError(
            f"software adapter {profile_id} requires 1 to {MAX_HANDOFFS} handoffs"
        )
    handoffs = [
        _normalize_handoff(item, profile_id, index)
        for index, item in enumerate(handoff_values, start=1)
    ]
    handoff_ids = [item["id"] for item in handoffs]
    if len(handoff_ids) != len(set(handoff_ids)):
        raise ValueError(f"software adapter {profile_id} handoff ids must be unique")
    for handoff in handoffs:
        unsupported = sorted(set(handoff["capabilities"]) - set(capabilities))
        if unsupported:
            raise ValueError(
                f"software adapter {profile_id} handoff {handoff['id']} references profile-"
                f"unsupported capabilities: {', '.join(unsupported)}"
            )
    safety = value.get("safety")
    if not isinstance(safety, dict) or set(safety) != {"preserve", "avoid"}:
        raise ValueError(
            f"software adapter {profile_id} safety must contain exactly preserve and avoid"
        )
    return {
        "schema": ADAPTER_PROFILE_SCHEMA,
        "id": profile_id,
        "label": _text(value, "label", profile_id, 1024),
        "summary": _text(value, "summary", profile_id),
        "provider": provider_id,
        "capabilities": capabilities,
        "handoffs": handoffs,
        "safety": {
            "preserve": _text_list(safety.get("preserve"), f"{profile_id} safety preserve"),
            "avoid": _text_list(safety.get("avoid"), f"{profile_id} safety avoid"),
        },
    }


def load_adapter_profiles(
    directory: str | Path = ADAPTER_PROFILE_DIR,
    *,
    toolchain: str | Path = TOOLCHAIN_PATH,
    additional_directories: list[str | Path] | None = None,
    toolchain_extensions: list[str | Path] | None = None,
) -> list[dict]:
    """Load shared plus additive private profiles and validate provider contracts."""
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(root)
    if additional_directories is None:
        extra_roots = (
            [REPOSITORY_LOCAL_ADAPTER_PROFILE_DIR]
            if root.resolve() == Path(ADAPTER_PROFILE_DIR).resolve()
            and REPOSITORY_LOCAL_ADAPTER_PROFILE_DIR.is_dir()
            else []
        )
    else:
        if not isinstance(additional_directories, list):
            raise ValueError("additional adapter profile directories must be a list")
        extra_roots = [Path(value).expanduser() for value in additional_directories]
    roots = [root.resolve()]
    for extra_root in extra_roots:
        resolved = extra_root.resolve()
        if not resolved.is_dir():
            raise FileNotFoundError(resolved)
        if resolved in roots:
            raise ValueError(f"duplicate adapter profile directory: {resolved}")
        roots.append(resolved)
    paths = sorted(
        path
        for profile_root in roots
        for path in profile_root.glob("*.json")
        if path.is_file()
    )
    if not paths:
        raise ValueError(f"software adapter directory contains no JSON profiles: {root}")
    if len(paths) > MAX_PROFILES:
        raise ValueError(f"software adapter directory exceeds {MAX_PROFILES} profiles")
    registry = load_toolchain(toolchain, extensions=toolchain_extensions)
    providers = {record["id"]: record for record in registry["tools"]}
    profiles = []
    for path in paths:
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid software adapter JSON: {path}: {exc.msg}") from exc
        profiles.append(_normalize_profile(value, path, providers))
    ids = [profile["id"] for profile in profiles]
    if len(ids) != len(set(ids)):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        raise ValueError(f"duplicate software adapter ids: {', '.join(duplicates)}")
    return profiles


def _provider_status(tool_report: dict) -> dict:
    return {
        "id": tool_report["id"],
        "label": tool_report["label"],
        "kind": tool_report["kind"],
        "applicable": tool_report["applicable"],
        "available": tool_report["available"],
        "versions": tool_report["versions"],
        "install_hint": tool_report["install_hint"],
    }


def adapter_catalog(
    directory: str | Path = ADAPTER_PROFILE_DIR,
    *,
    toolchain: str | Path = TOOLCHAIN_PATH,
    available_only: bool = False,
    capabilities: list[str] | None = None,
    workflows: list[str] | None = None,
    additional_directories: list[str | Path] | None = None,
    toolchain_extensions: list[str | Path] | None = None,
    tool_report: dict | None = None,
) -> dict:
    """Match validated profiles to detected providers without running or enabling them."""
    profiles = load_adapter_profiles(
        directory,
        toolchain=toolchain,
        additional_directories=additional_directories,
        toolchain_extensions=toolchain_extensions,
    )
    report = (
        tool_report
        if tool_report is not None
        else doctor(toolchain, extensions=toolchain_extensions)
    )
    if not isinstance(report, dict) or report.get("schema") != "eprs.doctor/v1":
        raise ValueError("software adapter catalog requires an eprs.doctor/v1 report")
    provider_reports = {record["id"]: record for record in report["tools"]}
    declared_capabilities = set(report["capabilities"])
    requested_capabilities: list[str] = []
    for value in capabilities or []:
        clean = value.strip() if isinstance(value, str) else ""
        if not clean:
            raise ValueError("software adapter capability filters cannot be blank")
        if clean not in declared_capabilities:
            raise ValueError(f"unknown software adapter capability: {clean}")
        if clean not in requested_capabilities:
            requested_capabilities.append(clean)
    workflow_map = {item["id"]: item for item in report["workflow_catalog"]}
    requested_workflows: list[str] = []
    workflow_capabilities: list[str] = []
    for value in workflows or []:
        clean = value.strip() if isinstance(value, str) else ""
        if not clean:
            raise ValueError("software adapter workflow filters cannot be blank")
        workflow = workflow_map.get(clean)
        if workflow is None:
            raise ValueError(f"unknown software adapter workflow: {clean}")
        if clean not in requested_workflows:
            requested_workflows.append(clean)
        for capability in workflow["capabilities"]:
            if capability not in workflow_capabilities:
                workflow_capabilities.append(capability)
    matches = []
    for profile in profiles:
        provider = provider_reports.get(profile["provider"])
        if provider is None:
            raise ValueError(
                f"software adapter provider is absent from doctor: {profile['provider']}"
            )
        profile_capabilities = set(profile["capabilities"])
        if available_only and provider["available"] is not True:
            continue
        if requested_capabilities and not set(requested_capabilities).issubset(
            profile_capabilities
        ):
            continue
        matched_workflow_capabilities = sorted(
            profile_capabilities.intersection(workflow_capabilities)
        )
        if requested_workflows and not matched_workflow_capabilities:
            continue
        matches.append({
            "id": profile["id"],
            "label": profile["label"],
            "summary": profile["summary"],
            "provider": _provider_status(provider),
            "capabilities": profile["capabilities"],
            "matched_workflow_capabilities": matched_workflow_capabilities,
            "handoffs": [
                {
                    "id": handoff["id"],
                    "label": handoff["label"],
                    "capabilities": handoff["capabilities"],
                    "automation": handoff["automation"],
                    "requires_user_operation": handoff["requires_user_operation"],
                }
                for handoff in profile["handoffs"]
            ],
        })
    return {
        "schema": ADAPTER_CATALOG_SCHEMA,
        "filters": {
            "available_only": available_only,
            "capabilities": requested_capabilities,
            "workflows": requested_workflows,
        },
        "profiles": matches,
        "profiles_total": len(matches),
        "authority": {
            "software_installed": False,
            "application_started": False,
            "control_enabled": False,
            "media_changed": False,
        },
    }


def adapter_fit(
    required_capabilities: list[str],
    *,
    directory: str | Path = ADAPTER_PROFILE_DIR,
    toolchain: str | Path = TOOLCHAIN_PATH,
    additional_directories: list[str | Path] | None = None,
    toolchain_extensions: list[str | Path] | None = None,
    tool_report: dict | None = None,
) -> dict:
    """Report declared capability readiness and all matching guides without ranking them."""
    if not isinstance(required_capabilities, list):
        raise ValueError("software adapter fit capabilities must be a list")
    requested: list[str] = []
    for value in required_capabilities:
        if (
            not isinstance(value, str)
            or not SLUG.fullmatch(value)
            or len(value) > 200
        ):
            raise ValueError(
                "software adapter fit capabilities must contain portable capability slugs"
            )
        if value in requested:
            raise ValueError("software adapter fit capabilities must not contain duplicates")
        requested.append(value)
    if len(requested) > 64:
        raise ValueError("software adapter fit capabilities exceeds 64 items")

    report = (
        tool_report
        if tool_report is not None
        else doctor(toolchain, extensions=toolchain_extensions)
    )
    if not isinstance(report, dict) or report.get("schema") != "eprs.doctor/v1":
        raise ValueError("software adapter fit requires an eprs.doctor/v1 report")
    declared = report.get("capabilities")
    if not isinstance(declared, dict):
        raise ValueError("software adapter fit requires doctor capability results")

    available = [item for item in requested if declared.get(item) is True]
    missing = [item for item in requested if item in declared and declared.get(item) is not True]
    unknown = [item for item in requested if item not in declared]
    profiles = load_adapter_profiles(
        directory,
        toolchain=toolchain,
        additional_directories=additional_directories,
        toolchain_extensions=toolchain_extensions,
    )
    providers = {record["id"]: record for record in report.get("tools", [])}
    matches = []
    guided: set[str] = set()
    for profile in profiles:
        matched = [item for item in requested if item in profile["capabilities"]]
        if not matched:
            continue
        provider = providers.get(profile["provider"])
        if provider is None:
            raise ValueError(
                f"software adapter provider is absent from doctor: {profile['provider']}"
            )
        handoffs = []
        for handoff in profile["handoffs"]:
            handoff_matches = [
                item for item in requested if item in handoff["capabilities"]
            ]
            if not handoff_matches:
                continue
            guided.update(handoff_matches)
            handoffs.append({
                "id": handoff["id"],
                "label": handoff["label"],
                "matched_capabilities": handoff_matches,
                "automation": handoff["automation"],
                "requires_user_operation": handoff["requires_user_operation"],
            })
        matches.append({
            "id": profile["id"],
            "label": profile["label"],
            "provider": {
                "id": provider["id"],
                "label": provider["label"],
                "applicable": provider["applicable"],
                "available": provider["available"],
            },
            "matched_capabilities": matched,
            "handoffs": handoffs,
        })
    uncovered = [item for item in requested if item not in guided]
    next_actions = [
        f"Declare a provider for unknown capability `{item}` before dispatching this step."
        for item in unknown
    ]
    next_actions.extend(
        f"Install or configure an applicable provider for missing capability `{item}`."
        for item in missing
    )
    next_actions.extend(
        f"No adapter handoff guide covers `{item}`; proceed only with explicit instructions "
        "and preserve the same authority boundary."
        for item in uncovered
        if item not in unknown and item not in missing
    )
    return {
        "schema": ADAPTER_FIT_SCHEMA,
        "requested_capabilities": requested,
        "available_capabilities": available,
        "missing_capabilities": missing,
        "unknown_capabilities": unknown,
        "ready": not missing and not unknown,
        "matching_adapters": matches,
        "guidance_uncovered_capabilities": uncovered,
        "guidance_complete": not uncovered,
        "next_actions": next_actions,
        "authority": {
            "software_installed": False,
            "application_started": False,
            "control_enabled": False,
            "media_changed": False,
            "creative_approval": False,
            "upload_authorized": False,
            "publication_authorized": False,
        },
    }


def adapter_guide(
    adapter_id: str,
    *,
    handoff_id: str | None = None,
    directory: str | Path = ADAPTER_PROFILE_DIR,
    toolchain: str | Path = TOOLCHAIN_PATH,
    additional_directories: list[str | Path] | None = None,
    toolchain_extensions: list[str | Path] | None = None,
    tool_report: dict | None = None,
) -> dict:
    """Return one complete, provider-aware handoff guide without executing it."""
    profiles = load_adapter_profiles(
        directory,
        toolchain=toolchain,
        additional_directories=additional_directories,
        toolchain_extensions=toolchain_extensions,
    )
    profile_map = {profile["id"]: profile for profile in profiles}
    profile = profile_map.get(adapter_id)
    if profile is None:
        raise ValueError(
            f"unknown software adapter: {adapter_id}; available adapters: "
            f"{', '.join(profile_map)}"
        )
    report = (
        tool_report
        if tool_report is not None
        else doctor(toolchain, extensions=toolchain_extensions)
    )
    if not isinstance(report, dict) or report.get("schema") != "eprs.doctor/v1":
        raise ValueError("software adapter guide requires an eprs.doctor/v1 report")
    provider_report = next(
        (record for record in report["tools"] if record["id"] == profile["provider"]),
        None,
    )
    if provider_report is None:
        raise ValueError(f"software adapter provider is absent from doctor: {profile['provider']}")
    handoffs = profile["handoffs"]
    if handoff_id is not None:
        handoffs = [item for item in handoffs if item["id"] == handoff_id]
        if not handoffs:
            raise ValueError(
                f"unknown {profile['id']} handoff: {handoff_id}; available handoffs: "
                f"{', '.join(item['id'] for item in profile['handoffs'])}"
            )
    provider = _provider_status(provider_report)
    next_actions = []
    if provider["applicable"] is not True:
        next_actions.append("This provider is not declared applicable on the current platform.")
    elif provider["available"] is not True:
        next_actions.append(
            provider["install_hint"]
            or "Install or configure the provider explicitly before using this guide."
        )
    if any(item["requires_user_operation"] for item in handoffs):
        next_actions.append(
            "One or more handoffs require a person to operate or review the application."
        )
    return {
        "schema": ADAPTER_GUIDE_SCHEMA,
        "adapter": {
            **profile,
            "handoffs": handoffs,
        },
        "provider": provider,
        "next_actions": next_actions,
        "authority": {
            "software_installed": False,
            "application_started": False,
            "control_enabled": False,
            "media_changed": False,
        },
    }
