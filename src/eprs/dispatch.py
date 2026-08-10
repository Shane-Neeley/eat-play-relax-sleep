"""Safe queue dispatch preparation for external agent runners."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .context import build_agent_context
from .system import load_song_manifest, sha256, slugify, utc_now
from .work import (
    DECISIONS,
    claim_next_work_item,
    finish_work_item,
    load_work_item,
    release_work_item,
)


DISPATCH_SCHEMA = "eprs.agent-dispatch/v1"
AGENT_RESPONSE_SCHEMA = "eprs.agent-response/v1"
MAX_RELEASE_REASON_CHARS = 2_000
MAX_RESPONSE_RESULTS = 100
MAX_RESPONSE_COMMANDS = 100
RESERVED_RESPONSE_ROLES = {"agent-dispatch-packet", "agent-response"}


def _release_reason(prefix: str, details: str) -> str:
    clean = " ".join(details.split())
    reason = f"Agent dispatch preparation failed: {prefix}"
    if clean:
        reason += f": {clean}"
    return reason[:MAX_RELEASE_REASON_CHARS]


def _response_contract(
    song: Path, item_path: Path, item: dict, run_number: int, agent: str
) -> dict:
    result_contract = item.get("result_contract")
    required_roles = (
        list(result_contract.get("required_roles", []))
        if isinstance(result_contract, dict)
        else []
    )
    return {
        "work_item": item["id"],
        "run_number": run_number,
        "agent": agent,
        "work": {
            "path": str(item_path.resolve().relative_to(song.resolve())),
            "sha256": sha256(item_path),
        },
        "agent_response": {
            "schema": AGENT_RESPONSE_SCHEMA,
            "bind_packet_with": "dispatch.packet_sha256",
            "reserved_result_roles": sorted(RESERVED_RESPONSE_ROLES),
            "accepted_by": "dispatch accept",
        },
        "finish": {
            "command": "work finish",
            "required": ["structured agent response", "summary", "decision", "declared action report"],
            "decisions": ["complete", "needs-followup", "stop"],
            "required_result_roles": required_roles,
            "required_result_roles_apply_to_decision": "complete",
            "additional_result_roles_allowed": True,
        },
        "release": {
            "command": "work release",
            "required": ["same agent name", "non-empty reason"],
        },
        "song": str(song),
    }


def _authority(allow_network_research: bool) -> dict:
    does_not_authorize = [
        "uploading, publishing, sending, or remote control",
        "remote mutation",
        "audio processing not explicitly requested by the work item",
        "creative approval, consent, rights, listening, technical, upload, or publication gates",
    ]
    if not allow_network_research:
        does_not_authorize.insert(0, "network access or browsing")
    return {
        "statement": (
            "This bundle claims and prepares one bounded task; it does not launch an agent. "
            + (
                "The caller explicitly permits read-only network research for this claimed task only."
                if allow_network_research else
                "It does not expand the current user's authorization."
            )
        ),
        "permissions": {
            "network_research": allow_network_research,
            "song_local_result_writes": True,
            "raw_recording_writes": False,
            "remote_state_changes": False,
            "upload_publish_or_send": False,
        },
        "does_not_authorize": does_not_authorize,
        "raw_recordings_immutable": True,
    }


def dispatch_next_work(
    song: str | Path,
    agent: str,
    *,
    kind: str | None = None,
    now: str | None = None,
    max_text_bytes: int = 65_536,
    allow_network_research: bool = False,
    toolchain_extensions: list[str | Path] | None = None,
    adapter_profile_directories: list[str | Path] | None = None,
) -> dict:
    """Claim due work and return verified context, or release a failed preparation."""
    song_path = Path(song)
    load_song_manifest(song_path)
    claim = claim_next_work_item(song_path, agent, kind=kind, now=now)
    claimed = claim["claimed"]
    base = {
        "schema": DISPATCH_SCHEMA,
        "generated_at": utc_now(),
        "agent": claim["agent"],
        "kind_filter": claim["kind_filter"],
        "authority": _authority(allow_network_research),
        "claim": claim,
    }
    if claimed is None:
        return {
            **base,
            "status": "idle",
            "context": None,
            "release": None,
            "response_contract": None,
        }

    item_id = claimed["id"]
    run_number = claimed["run_number"]
    try:
        context = build_agent_context(
            song_path,
            purpose=f"Execute only claimed work item {item_id}, run {run_number}.",
            work=item_id,
            work_run=run_number,
            verify=True,
            max_text_bytes=max_text_bytes,
            toolchain_extensions=toolchain_extensions,
            adapter_profile_directories=adapter_profile_directories,
        )
        attention = context.get("attention")
        if not isinstance(attention, list):
            raise ValueError("verified agent context has an invalid attention field")
        fit = context.get("adapter_fit")
        if fit is not None:
            if not isinstance(fit, dict) or not isinstance(fit.get("ready"), bool):
                raise ValueError("verified agent context has an invalid adapter fit")
            if not fit["ready"]:
                unavailable = [
                    *fit.get("missing_capabilities", []),
                    *fit.get("unknown_capabilities", []),
                ]
                reason = _release_reason(
                    "required software capabilities unavailable",
                    ", ".join(map(str, unavailable)),
                )
                release_work_item(song_path, item_id, claim["agent"], reason)
                _, released_item = load_work_item(song_path, item_id)
                return {
                    **base,
                    "status": "released",
                    "context": context,
                    "release": {
                        "reason": reason,
                        "work_status": released_item["status"],
                        "run_number": run_number,
                    },
                    "response_contract": None,
                }
        if attention:
            reason = _release_reason("verified context requires attention", "; ".join(map(str, attention)))
            release_work_item(song_path, item_id, claim["agent"], reason)
            _, released_item = load_work_item(song_path, item_id)
            return {
                **base,
                "status": "released",
                "context": context,
                "release": {
                    "reason": reason,
                    "work_status": released_item["status"],
                    "run_number": run_number,
                },
                "response_contract": None,
            }
    except Exception as exc:
        reason = _release_reason(type(exc).__name__, str(exc))
        try:
            release_work_item(song_path, item_id, claim["agent"], reason)
            _, released_item = load_work_item(song_path, item_id)
        except Exception as release_exc:
            raise RuntimeError(
                f"dispatch preparation failed for {item_id}, and its claim could not be released: "
                f"{release_exc}"
            ) from release_exc
        return {
            **base,
            "status": "released",
            "context": None,
            "release": {
                "reason": reason,
                "work_status": released_item["status"],
                "run_number": run_number,
            },
            "response_contract": None,
        }

    return {
        **base,
        "status": "ready",
        "context": context,
        "release": None,
        "response_contract": _response_contract(
            song_path,
            *load_work_item(song_path, item_id),
            run_number,
            claim["agent"],
        ),
    }


def write_dispatch_packet(bundle: dict, destination: str | Path) -> Path:
    """Write one ready dispatch bundle without overwriting an existing packet."""
    if not isinstance(bundle, dict) or bundle.get("schema") != DISPATCH_SCHEMA:
        raise ValueError("dispatch packet requires an eprs.agent-dispatch/v1 bundle")
    if bundle.get("status") != "ready":
        raise ValueError("only a ready dispatch can be written as an agent packet")
    return _write_new_json(destination, bundle, "agent dispatch packet")


def _write_new_json(destination: str | Path, value: dict, label: str) -> Path:
    path = Path(destination).resolve()
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {label}: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete {label} already exists: {temporary}")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _load_json_object(path: str | Path, label: str) -> tuple[Path, dict, str]:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    try:
        content = resolved.read_bytes()
        value = json.loads(content.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid {label} encoding: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {label} JSON: {resolved}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return resolved, value, hashlib.sha256(content).hexdigest()


def _required_bool(record: dict, key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"agent response actions.{key} must be true or false")
    return value


def initialize_agent_response(
    packet: str | Path,
    destination: str | Path,
) -> Path:
    """Create a bound response skeleton from one exact ready packet."""
    _, packet_record, packet_digest = _load_json_object(
        packet, "agent dispatch packet"
    )
    if packet_record.get("schema") != DISPATCH_SCHEMA or packet_record.get("status") != "ready":
        raise ValueError("agent dispatch packet must be a ready eprs.agent-dispatch/v1 bundle")
    contract = packet_record.get("response_contract")
    if not isinstance(contract, dict):
        raise ValueError("agent dispatch packet has no response contract")
    if (
        not isinstance(contract.get("work_item"), str)
        or not contract["work_item"]
        or isinstance(contract.get("run_number"), bool)
        or not isinstance(contract.get("run_number"), int)
        or contract["run_number"] < 1
        or not isinstance(contract.get("agent"), str)
        or not contract["agent"].strip()
    ):
        raise ValueError("agent dispatch packet has invalid work, run, or agent coordinates")
    response = {
        "schema": AGENT_RESPONSE_SCHEMA,
        "dispatch": {
            "packet_sha256": packet_digest,
            "work_item": contract.get("work_item"),
            "run_number": contract.get("run_number"),
            "agent": contract.get("agent"),
        },
        "summary": "REPLACE: state what was actually done and what remains unresolved",
        "decision": "needs-followup",
        "actions": {
            "network_accessed": False,
            "raw_recordings_modified": False,
            "remote_state_changed": False,
            "uploaded_published_or_sent": False,
            "local_audio_processed": False,
            "listening_performed": False,
            "commands_run": [],
        },
        "results": [],
    }
    return _write_new_json(destination, response, "agent response")


def accept_agent_response(
    song: str | Path,
    packet: str | Path,
    response: str | Path,
) -> Path:
    """Validate one exact runner response and freeze both sides into its work run."""
    song_path = Path(song)
    load_song_manifest(song_path)
    packet_path, packet_record, packet_digest = _load_json_object(
        packet, "agent dispatch packet"
    )
    if packet_record.get("schema") != DISPATCH_SCHEMA or packet_record.get("status") != "ready":
        raise ValueError("agent dispatch packet must be a ready eprs.agent-dispatch/v1 bundle")
    contract = packet_record.get("response_contract")
    if not isinstance(contract, dict):
        raise ValueError("agent dispatch packet has no response contract")
    if (
        not isinstance(contract.get("work_item"), str)
        or not contract["work_item"]
        or isinstance(contract.get("run_number"), bool)
        or not isinstance(contract.get("run_number"), int)
        or contract["run_number"] < 1
        or not isinstance(contract.get("agent"), str)
        or not contract["agent"].strip()
    ):
        raise ValueError("agent dispatch packet has invalid work, run, or agent coordinates")
    agent_response_contract = contract.get("agent_response")
    if (
        not isinstance(agent_response_contract, dict)
        or agent_response_contract.get("schema") != AGENT_RESPONSE_SCHEMA
    ):
        raise ValueError("agent dispatch packet has an invalid response schema contract")
    work = contract.get("work")
    if (
        not isinstance(work, dict)
        or not isinstance(work.get("sha256"), str)
        or len(work["sha256"]) != 64
    ):
        raise ValueError("agent dispatch packet has an invalid work binding")

    response_path, response_record, response_digest = _load_json_object(
        response, "agent response"
    )
    if response_record.get("schema") != AGENT_RESPONSE_SCHEMA:
        raise ValueError(f"agent response schema must be {AGENT_RESPONSE_SCHEMA}")
    binding = response_record.get("dispatch")
    if not isinstance(binding, dict):
        raise ValueError("agent response requires a dispatch binding")
    expected_binding = {
        "packet_sha256": packet_digest,
        "work_item": contract.get("work_item"),
        "run_number": contract.get("run_number"),
        "agent": contract.get("agent"),
    }
    if any(binding.get(key) != value for key, value in expected_binding.items()):
        raise ValueError("agent response does not match its exact packet, work item, run, and agent")
    claim_record = packet_record.get("claim")
    claimed = claim_record.get("claimed") if isinstance(claim_record, dict) else None
    if (
        not isinstance(claimed, dict)
        or claimed.get("id") != contract.get("work_item")
        or claimed.get("run_number") != contract.get("run_number")
        or claimed.get("agent") != contract.get("agent")
    ):
        raise ValueError("agent dispatch claim does not match its response contract")

    summary = response_record.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 8_192:
        raise ValueError("agent response summary must be 1 to 8192 characters")
    if summary.strip().startswith("REPLACE:"):
        raise ValueError("agent response summary placeholder must be replaced")
    decision = response_record.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"agent response decision must be one of: {', '.join(sorted(DECISIONS))}")
    actions = response_record.get("actions")
    if not isinstance(actions, dict):
        raise ValueError("agent response requires a declared action report")
    network_accessed = _required_bool(actions, "network_accessed")
    raw_modified = _required_bool(actions, "raw_recordings_modified")
    remote_changed = _required_bool(actions, "remote_state_changed")
    uploaded = _required_bool(actions, "uploaded_published_or_sent")
    _required_bool(actions, "local_audio_processed")
    _required_bool(actions, "listening_performed")
    commands = actions.get("commands_run")
    if (
        not isinstance(commands, list)
        or len(commands) > MAX_RESPONSE_COMMANDS
        or not all(isinstance(command, str) and 0 < len(command) <= 2_048 for command in commands)
    ):
        raise ValueError("agent response actions.commands_run must be at most 100 bounded strings")
    authority = packet_record.get("authority")
    permissions = authority.get("permissions", {}) if isinstance(authority, dict) else {}
    permissions = permissions if isinstance(permissions, dict) else {}
    if network_accessed and permissions.get("network_research") is not True:
        raise ValueError("agent response reports network access that its packet did not permit")
    if raw_modified:
        raise ValueError("agent response cannot accept modification of immutable raw recordings")
    if remote_changed or uploaded:
        raise ValueError("agent response cannot accept remote changes, uploads, publication, or sending")

    result_values = response_record.get("results", [])
    if not isinstance(result_values, list) or len(result_values) > MAX_RESPONSE_RESULTS:
        raise ValueError("agent response results must be a list of at most 100 role/path records")
    results: list[tuple[str, Path]] = [
        ("agent-dispatch-packet", packet_path),
        ("agent-response", response_path),
    ]
    seen_roles = set(RESERVED_RESPONSE_ROLES)
    for index, value in enumerate(result_values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"agent response result {index} must be an object")
        role = value.get("role")
        path_value = value.get("path")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"agent response result {index} requires a role")
        role_id = slugify(role)
        if not role_id or role_id in seen_roles:
            raise ValueError(f"agent response result role is empty, reserved, or duplicated: {role}")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"agent response result {index} requires a path")
        source = Path(path_value)
        source = source.resolve() if source.is_absolute() else (response_path.parent / source).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        if source in {packet_path, response_path}:
            raise ValueError("agent response packet files use reserved result roles")
        seen_roles.add(role_id)
        results.append((role.strip(), source))

    expected_result_sha256 = {
        slugify(role): (
            packet_digest if slugify(role) == "agent-dispatch-packet"
            else response_digest if slugify(role) == "agent-response"
            else sha256(path)
        )
        for role, path in results
    }

    return finish_work_item(
        song_path,
        contract.get("work_item", ""),
        summary.strip(),
        decision,
        results,
        expected_agent=contract.get("agent"),
        expected_run=contract.get("run_number"),
        expected_work_sha256=work["sha256"],
        expected_result_sha256=expected_result_sha256,
    )
