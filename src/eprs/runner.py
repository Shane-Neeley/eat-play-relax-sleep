"""OS-isolated execution for explicit packet/response agent profiles."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import string
import subprocess
import threading
import time
from typing import BinaryIO

from .dispatch import (
    DISPATCH_SCHEMA,
    accept_agent_response,
    initialize_agent_response,
)
from .system import load_song_manifest, sha256, slugify, utc_now
from .work import load_work_item, release_work_item


PROFILE_SCHEMA = "eprs.runner-profile/v1"
RECEIPT_SCHEMA = "eprs.agent-runner-execution/v1"
PROTOCOL = "eprs.packet-response-files/v1"
ALLOWED_PLACEHOLDERS = {"packet", "response", "workspace"}
MAX_ARGUMENTS = 64
MAX_ARGUMENT_BYTES = 4096
MAX_LOG_BYTES_LIMIT = 10 * 1024 * 1024


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: str | Path, label: str) -> tuple[Path, dict, str]:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    payload = resolved.read_bytes()
    try:
        record = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"invalid {label} encoding: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {label} JSON: {resolved}: {exc.msg}") from exc
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be a JSON object")
    return resolved, record, hashlib.sha256(payload).hexdigest()


def _number(
    record: dict,
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = record.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not minimum <= float(value) <= maximum
    ):
        raise ValueError(
            f"runner profile {key} must be from {minimum:g} to {maximum:g}"
        )
    return float(value)


def load_runner_profile(profile: str | Path) -> tuple[Path, dict, str]:
    """Validate a portable, shell-free runner profile."""
    path, record, digest = _load_json(profile, "runner profile")
    if record.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"runner profile schema must be {PROFILE_SCHEMA}")
    declared_id = record.get("id")
    if (
        not isinstance(declared_id, str)
        or not declared_id.strip()
        or slugify(declared_id) != declared_id
    ):
        raise ValueError("runner profile id must be a portable slug")
    label = record.get("label")
    if not isinstance(label, str) or not label.strip() or len(label) > 512:
        raise ValueError("runner profile requires a bounded label")
    if record.get("protocol") != PROTOCOL:
        raise ValueError(f"runner profile protocol must be {PROTOCOL}")
    executable = record.get("executable")
    if (
        not isinstance(executable, str)
        or not executable.strip()
        or len(executable.encode("utf-8")) > 2048
        or "{" in executable
        or "}" in executable
    ):
        raise ValueError("runner profile executable must be a literal command or path")
    arguments = record.get("arguments")
    if (
        not isinstance(arguments, list)
        or not arguments
        or len(arguments) > MAX_ARGUMENTS
        or not all(
            isinstance(value, str)
            and len(value.encode("utf-8")) <= MAX_ARGUMENT_BYTES
            for value in arguments
        )
    ):
        raise ValueError("runner profile arguments must be a bounded non-empty string list")
    fields: set[str] = set()
    formatter = string.Formatter()
    for argument in arguments:
        try:
            parsed = list(formatter.parse(argument))
        except ValueError as exc:
            raise ValueError("runner profile has invalid argument placeholders") from exc
        for _, field, _, _ in parsed:
            if field is not None:
                fields.add(field)
    unknown = sorted(fields - ALLOWED_PLACEHOLDERS)
    if unknown:
        raise ValueError(f"runner profile has unknown placeholders: {', '.join(unknown)}")
    if not {"packet", "response"}.issubset(fields):
        raise ValueError("runner profile arguments must include {packet} and {response}")
    if record.get("isolation") != "auto":
        raise ValueError("runner profile isolation must be auto")
    if record.get("network_mode") != "deny":
        raise ValueError("runner profile network_mode must be deny")
    timeout = _number(record, "timeout_seconds", 900, 0.1, 86_400)
    grace = _number(record, "terminate_grace_seconds", 3, 0.1, 60)
    max_log = record.get("max_log_bytes", 1_048_576)
    if (
        isinstance(max_log, bool)
        or not isinstance(max_log, int)
        or not 1_024 <= max_log <= MAX_LOG_BYTES_LIMIT
    ):
        raise ValueError(
            f"runner profile max_log_bytes must be from 1024 to {MAX_LOG_BYTES_LIMIT}"
        )
    return path, {
        **record,
        "label": label.strip(),
        "executable": executable.strip(),
        "timeout_seconds": timeout,
        "terminate_grace_seconds": grace,
        "max_log_bytes": max_log,
    }, digest


def _resolved_executable(value: str) -> Path:
    requested = Path(value)
    located = (
        requested.resolve()
        if requested.is_absolute() or "/" in value
        else Path(shutil.which(value) or "")
    )
    if not str(located) or not located.is_file() or not os.access(located, os.X_OK):
        raise FileNotFoundError(f"runner executable is unavailable or not executable: {value}")
    return located.resolve()


def _escape_sbpl(value: Path) -> str:
    return str(value.resolve()).replace("\\", "\\\\").replace('"', '\\"')


def _macos_policy(workspace: Path) -> str:
    return (
        "(version 1)\n"
        "(allow default)\n"
        "(deny network*)\n"
        "(deny file-write*)\n"
        f'(allow file-write* (subpath "{_escape_sbpl(workspace)}"))\n'
        '(allow file-write-data (literal "/dev/null"))\n'
    )


def _isolation_provider(system_name: str | None = None) -> tuple[str, str]:
    system = system_name or platform.system()
    if system == "Darwin":
        executable = shutil.which("sandbox-exec")
        if not executable:
            raise RuntimeError("macOS sandbox-exec is required for agent runner isolation")
        return "macos-sandbox-exec", executable
    if system == "Linux":
        executable = shutil.which("bwrap")
        if not executable:
            raise RuntimeError("Linux bubblewrap (bwrap) is required for agent runner isolation")
        return "linux-bubblewrap", executable
    raise RuntimeError(f"agent runner isolation is unsupported on {system}")


def _sandbox_command(
    workspace: Path,
    command: list[str],
    *,
    system_name: str | None = None,
) -> tuple[str, list[str], Path | None]:
    """Return a mandatory network-off, workspace-write-only OS sandbox command."""
    system = system_name or platform.system()
    provider, executable = _isolation_provider(system)
    if system == "Darwin":
        policy_path = workspace.parent / "sandbox.sb"
        policy_path.write_text(_macos_policy(workspace), encoding="utf-8")
        return provider, [executable, "-f", str(policy_path), *command], policy_path
    if system == "Linux":
        return (
            provider,
            [
                executable,
                "--die-with-parent",
                "--new-session",
                "--unshare-net",
                "--ro-bind", "/", "/",
                "--bind", str(workspace), str(workspace),
                "--chdir", str(workspace),
                *command,
            ],
            None,
        )
    raise AssertionError(f"unhandled isolation provider for {system}")


def _raw_snapshot(song: Path) -> dict:
    root = song / "recordings" / "raw"
    records: list[tuple[str, str]] = []
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            records.append((str(path.relative_to(song)), sha256(path)))
    digest = hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {"file_count": len(records), "aggregate_sha256": digest, "files": records}


def _raw_integrity(before: dict, after: dict) -> dict:
    before_map = dict(before["files"])
    after_map = dict(after["files"])
    paths = sorted(set(before_map) | set(after_map))
    changed = [path for path in paths if before_map.get(path) != after_map.get(path)]
    return {
        "before_file_count": before["file_count"],
        "after_file_count": after["file_count"],
        "before_aggregate_sha256": before["aggregate_sha256"],
        "after_aggregate_sha256": after["aggregate_sha256"],
        "unchanged": not changed,
        "changed_paths": changed,
    }


def _capture_stream(
    stream: BinaryIO,
    destination: Path,
    maximum: int,
    result: dict,
) -> None:
    total = 0
    kept = 0
    with destination.open("wb") as output:
        while True:
            chunk = stream.read(65_536)
            if not chunk:
                break
            total += len(chunk)
            if kept < maximum:
                payload = chunk[: maximum - kept]
                output.write(payload)
                kept += len(payload)
    result.update({"bytes_seen": total, "bytes_kept": kept, "truncated": total > kept})


def _active_process_group_members(process_group: int) -> list[dict] | None:
    """Return non-zombie group members, or None when ps cannot verify them."""
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,pgid=,state="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    members: list[dict] = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            pid = int(fields[0])
            group = int(fields[1])
        except ValueError:
            continue
        state = fields[2]
        if group == process_group and not state.startswith("Z"):
            members.append({"pid": pid, "state": state})
    return members


def _group_has_active_members(process_group: int) -> bool:
    members = _active_process_group_members(process_group)
    if members is not None:
        return bool(members)
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    return True


def _terminate_group(pid: int, grace_seconds: float) -> dict:
    record = {"signal": None, "kill_signal": None, "cleanup_verified": True}
    if not _group_has_active_members(pid):
        return record
    try:
        os.killpg(pid, 0)
    except PermissionError:
        record["cleanup_verified"] = False
        return record
    record["signal"] = "SIGTERM"
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return record
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _group_has_active_members(pid):
            return record
        time.sleep(0.02)
    record["kill_signal"] = "SIGKILL"
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return record
    deadline = time.monotonic() + max(0.5, grace_seconds)
    while time.monotonic() < deadline:
        if not _group_has_active_members(pid):
            return record
        time.sleep(0.02)
    record["cleanup_verified"] = False
    return record


def _unique_run_directory(song: Path, profile_id: str, packet_digest: str) -> Path:
    timestamp = utc_now().replace("-", "").replace(":", "").replace("Z", "Z")
    root = song / "notes" / "runner-runs" / profile_id
    root.mkdir(parents=True, exist_ok=True)
    base = f"{timestamp}-{packet_digest[:10]}"
    destination = root / base
    suffix = 2
    while destination.exists():
        destination = root / f"{base}-{suffix}"
        suffix += 1
    destination.mkdir()
    return destination


def _receipt_path(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    path = (
        requested.resolve()
        if requested.is_absolute() or requested.exists()
        else (song / requested).resolve()
    )
    if path.is_dir():
        path = path / "runner.json"
    try:
        path.relative_to((song / "notes" / "runner-runs").resolve())
    except ValueError as exc:
        raise ValueError("runner receipt must stay inside notes/runner-runs") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _song_file(song: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"runner receipt {label} path is invalid")
    path = (song / value).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"runner receipt {label} path escapes the song") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def verify_runner_receipt(
    song: str | Path,
    receipt: str | Path,
    *,
    verify_artifacts: bool = True,
) -> tuple[Path, dict]:
    """Verify a runner receipt and its frozen packet/profile/log evidence."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _receipt_path(song_path, receipt)
    _, record, _ = _load_json(path, "runner receipt")
    if record.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("unsupported runner receipt schema")
    status = record.get("status")
    if status not in {"running", "completed", "failed"}:
        raise ValueError("runner receipt status is invalid")
    isolation = record.get("isolation")
    if (
        not isinstance(isolation, dict)
        or isolation.get("provider") not in {
            "macos-sandbox-exec", "linux-bubblewrap"
        }
        or isolation.get("network_mode") != "deny"
        or isolation.get("network_hard_denied") is not True
        or isolation.get("host_write_scope") != "runner workspace only"
    ):
        raise ValueError("runner receipt isolation evidence is invalid")
    for label, section in (
        ("profile", record.get("profile")),
        ("packet", record.get("dispatch")),
    ):
        if not isinstance(section, dict):
            raise ValueError(f"runner receipt {label} evidence is invalid")
        path_key = "path" if label == "profile" else "packet_path"
        digest_key = "sha256" if label == "profile" else "packet_sha256"
        artifact = _song_file(song_path, section.get(path_key), label)
        expected = section.get(digest_key)
        if (
            not isinstance(expected, str)
            or len(expected) != 64
            or verify_artifacts and sha256(artifact) != expected
        ):
            raise ValueError(f"runner receipt {label} checksum is invalid")
    process = record.get("process")
    raw = record.get("raw_integrity")
    response = record.get("response")
    if not all(isinstance(value, dict) for value in (process, raw, response)):
        raise ValueError("runner receipt process, raw, or response evidence is invalid")
    if status != "running":
        termination = process.get("termination")
        if not isinstance(termination, dict) or termination.get("cleanup_verified") is not True:
            raise ValueError("runner receipt process cleanup is unverified")
        if raw.get("unchanged") is not True:
            raise ValueError("runner receipt does not prove immutable raw integrity")
        logs = record.get("logs")
        if not isinstance(logs, dict) or set(logs) != {"stdout", "stderr"}:
            raise ValueError("runner receipt logs are invalid")
        for label, log in logs.items():
            if not isinstance(log, dict):
                raise ValueError(f"runner receipt {label} log is invalid")
            artifact = _song_file(song_path, log.get("path"), f"{label} log")
            expected = log.get("sha256")
            if verify_artifacts and expected != sha256(artifact):
                raise ValueError(f"runner receipt {label} log checksum has changed")
    if status == "completed":
        if response.get("accepted") is not True or not isinstance(
            response.get("acceptance_path"), str
        ):
            raise ValueError("completed runner receipt lacks accepted response evidence")
        response_path = _song_file(song_path, response.get("path"), "response")
        response_digest = response.get("sha256")
        if (
            not isinstance(response_digest, str)
            or len(response_digest) != 64
            or (verify_artifacts and sha256(response_path) != response_digest)
        ):
            raise ValueError("runner receipt response checksum is invalid")
        acceptance = (song_path / response["acceptance_path"]).resolve()
        try:
            acceptance.relative_to(song_path)
        except ValueError as exc:
            raise ValueError("runner receipt acceptance path escapes the song") from exc
        if not acceptance.is_file():
            raise FileNotFoundError(acceptance)
    if status == "failed" and response.get("accepted") is not False:
        raise ValueError("failed runner receipt cannot claim response acceptance")
    return path, record


def _release_failure(song: Path, contract: dict, reason: str) -> tuple[str | None, str | None]:
    note = f"Agent runner failed: {' '.join(reason.split())}"[:2_000]
    try:
        path = release_work_item(
            song,
            contract.get("work_item", ""),
            contract.get("agent", ""),
            note,
        )
        return str(path.resolve().relative_to(song.resolve())), None
    except Exception as exc:  # The receipt must preserve a failed release attempt.
        return None, f"{type(exc).__name__}: {exc}"


def run_agent_profile(
    song: str | Path,
    profile: str | Path,
    packet: str | Path,
) -> tuple[Path, dict]:
    """Execute one ready packet in a mandatory OS sandbox and preserve a receipt."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    profile_path, profile_record, profile_digest = load_runner_profile(profile)
    packet_path, packet_record, packet_digest = _load_json(packet, "agent dispatch packet")
    if packet_record.get("schema") != DISPATCH_SCHEMA or packet_record.get("status") != "ready":
        raise ValueError("agent runner requires a ready dispatch packet")
    contract = packet_record.get("response_contract")
    if not isinstance(contract, dict):
        raise ValueError("agent runner packet has no response contract")
    work_path_value = contract.get("work", {}).get("path")
    if not isinstance(work_path_value, str):
        raise ValueError("agent runner packet work path is invalid")
    work_path = (song_path / work_path_value).resolve()
    try:
        work_path.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("agent runner packet work path escapes the song") from exc
    if not work_path.is_file() or sha256(work_path) != contract.get("work", {}).get("sha256"):
        raise ValueError("agent runner packet work item is missing or changed")
    _, work_record = load_work_item(song_path, work_path)
    current = work_record.get("runs", [])[-1]
    if (
        work_record.get("status") != "in_progress"
        or current.get("number") != contract.get("run_number")
        or current.get("agent") != contract.get("agent")
    ):
        raise ValueError("agent runner packet no longer owns the current work run")
    executable = _resolved_executable(profile_record["executable"])
    _isolation_provider()

    run_directory = _unique_run_directory(song_path, profile_record["id"], packet_digest)
    workspace = run_directory / "workspace"
    workspace.mkdir()
    (workspace / "tmp").mkdir()
    (workspace / "cache").mkdir()
    frozen_profile = run_directory / "profile.json"
    shutil.copyfile(profile_path, frozen_profile)
    frozen_packet = workspace / "packet.json"
    shutil.copyfile(packet_path, frozen_packet)
    if sha256(frozen_packet) != packet_digest:
        raise RuntimeError("agent runner packet changed while it was being staged")
    response = initialize_agent_response(frozen_packet, workspace / "response.json")
    placeholders = {
        "packet": str(frozen_packet),
        "response": str(response),
        "workspace": str(workspace),
    }
    arguments = [value.format(**placeholders) for value in profile_record["arguments"]]
    command = [str(executable), *arguments]
    provider, sandboxed_command, policy_path = _sandbox_command(workspace, command)
    raw_before = _raw_snapshot(song_path)
    receipt_path = run_directory / "runner.json"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "id": run_directory.name,
        "status": "running",
        "created_at": utc_now(),
        "profile": {
            "id": profile_record["id"],
            "path": str(frozen_profile.relative_to(song_path)),
            "sha256": profile_digest,
            "protocol": profile_record["protocol"],
        },
        "dispatch": {
            "work_item": contract.get("work_item"),
            "run_number": contract.get("run_number"),
            "agent": contract.get("agent"),
            "packet_path": str(frozen_packet.relative_to(song_path)),
            "packet_sha256": packet_digest,
        },
        "isolation": {
            "provider": provider,
            "network_mode": "deny",
            "network_hard_denied": True,
            "host_write_scope": "runner workspace only",
            "workspace": str(workspace.relative_to(song_path)),
            "policy_path": str(policy_path.relative_to(song_path)) if policy_path else None,
        },
        "limits": {
            "timeout_seconds": profile_record["timeout_seconds"],
            "terminate_grace_seconds": profile_record["terminate_grace_seconds"],
            "max_log_bytes_per_stream": profile_record["max_log_bytes"],
        },
        "process": {
            "command": sandboxed_command,
            "started_at": None,
            "ended_at": None,
            "elapsed_seconds": None,
            "pid": None,
            "process_group": None,
            "exit_code": None,
            "timed_out": False,
            "termination": None,
        },
        "raw_integrity": {
            "before_file_count": raw_before["file_count"],
            "before_aggregate_sha256": raw_before["aggregate_sha256"],
            "unchanged": None,
        },
        "logs": {},
        "response": {
            "path": str(response.relative_to(song_path)),
            "accepted": False,
            "acceptance_path": None,
            "error": None,
        },
        "release": {"path": None, "error": None},
        "authority": {
            "statement": "Execution receipt only; it does not prove listening, creative approval, consent, rights, release, upload, or publication.",
            "remote_changes_authorized": False,
            "upload_publish_or_send_authorized": False,
        },
    }
    _atomic_json(receipt_path, receipt)

    stdout_path = workspace / "stdout.log"
    stderr_path = workspace / "stderr.log"
    stdout_path.touch()
    stderr_path.touch()
    stdout_result: dict = {}
    stderr_result: dict = {}
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    failure: str | None = None
    timed_out = False
    termination: dict | None = {
        "signal": None,
        "kill_signal": None,
        "cleanup_verified": True,
    }
    try:
        child_environment = dict(os.environ)
        child_environment.update({
            "EPRS_RUNNER_PACKET": str(frozen_packet),
            "EPRS_RUNNER_RESPONSE": str(response),
            "EPRS_RUNNER_WORKSPACE": str(workspace),
            "EPRS_RUNNER_NETWORK_MODE": "deny",
            "TMPDIR": str(workspace / "tmp"),
            "XDG_CACHE_HOME": str(workspace / "cache"),
            "PYTHONPYCACHEPREFIX": str(workspace / "cache" / "python"),
            "NPM_CONFIG_CACHE": str(workspace / "cache" / "npm"),
        })
        process = subprocess.Popen(
            sandboxed_command,
            cwd=workspace,
            env=child_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        receipt["process"].update({
            "started_at": utc_now(),
            "pid": process.pid,
            "process_group": process.pid,
        })
        _atomic_json(receipt_path, receipt)
        stdout_thread = threading.Thread(
            target=_capture_stream,
            args=(process.stdout, stdout_path, profile_record["max_log_bytes"], stdout_result),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=_capture_stream,
            args=(process.stderr, stderr_path, profile_record["max_log_bytes"], stderr_result),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        try:
            process.wait(timeout=profile_record["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            termination = _terminate_group(
                process.pid, profile_record["terminate_grace_seconds"]
            )
            process.wait(timeout=max(1.0, profile_record["terminate_grace_seconds"] + 1))
        else:
            # Reap background descendants even after a cooperative parent exits.
            termination = _terminate_group(
                process.pid, profile_record["terminate_grace_seconds"]
            )
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            failure = "runner log capture did not finish"
        if timed_out:
            failure = f"runner exceeded {profile_record['timeout_seconds']:g} seconds"
        elif process.returncode != 0:
            failure = f"runner exited with code {process.returncode}"
        if termination and not termination.get("cleanup_verified"):
            failure = "runner process-group cleanup could not be verified"
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if process is not None:
            termination = _terminate_group(
                process.pid, profile_record["terminate_grace_seconds"]
            )

    raw_after = _raw_snapshot(song_path)
    raw_integrity = _raw_integrity(raw_before, raw_after)
    if not raw_integrity["unchanged"]:
        failure = "immutable raw recording bytes changed during runner execution"
    elapsed = round(time.monotonic() - started, 3)
    receipt["process"].update({
        "ended_at": utc_now(),
        "elapsed_seconds": elapsed,
        "exit_code": process.returncode if process is not None else None,
        "timed_out": timed_out,
        "termination": termination,
    })
    receipt["raw_integrity"] = raw_integrity
    for label, path, capture in (
        ("stdout", stdout_path, stdout_result),
        ("stderr", stderr_path, stderr_result),
    ):
        receipt["logs"][label] = {
            "path": str(path.relative_to(song_path)),
            "sha256": sha256(path) if path.is_file() else None,
            **capture,
        }

    if failure is None:
        try:
            accepted_path = accept_agent_response(song_path, frozen_packet, response)
            receipt["response"].update({
                "accepted": True,
                "acceptance_path": str(accepted_path.resolve().relative_to(song_path)),
                "sha256": sha256(response),
            })
            receipt["status"] = "completed"
        except Exception as exc:
            failure = f"response acceptance failed: {type(exc).__name__}: {exc}"

    if failure is not None:
        receipt["status"] = "failed"
        receipt["response"]["error"] = failure
        release_path, release_error = _release_failure(song_path, contract, failure)
        receipt["release"] = {"path": release_path, "error": release_error}
    receipt["completed_at"] = utc_now()
    _atomic_json(receipt_path, receipt)
    return receipt_path, receipt
