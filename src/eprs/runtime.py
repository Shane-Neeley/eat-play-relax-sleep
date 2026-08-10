"""Read-only runtime and render-performance diagnostics."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess

from .system import PROJECT_ROOT, load_song_manifest, utc_now


PERFORMANCE_SCHEMA = "eprs.performance/v1"


def _elapsed_seconds(value: str) -> int:
    """Parse the portable [[dd-]hh:]mm:ss shape emitted by ps."""
    days = 0
    clock = value.strip()
    if "-" in clock:
        day_value, clock = clock.split("-", 1)
        days = int(day_value)
    parts = [int(item) for item in clock.split(":")]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    else:
        raise ValueError(f"unsupported process elapsed time: {value}")
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds


def _process_kind(command: str) -> str | None:
    if "/notes/runner-runs/" in command or "\\notes\\runner-runs\\" in command:
        return "eprs-agent-runner"
    root = str(PROJECT_ROOT.resolve())
    if root not in command:
        return None
    if ".remotion/chrome-headless-shell" in command:
        return "remotion-chromium"
    if "node_modules/.bin/remotion" in command or "remotion render" in command:
        return "remotion-cli"
    if "scripts/eprs" in command and "visual-render" in command:
        return "eprs-visual-render"
    return None


def _processes(ps_output: str, stale_seconds: int) -> list[dict]:
    records: list[dict] = []
    for line in ps_output.splitlines():
        fields = line.strip().split(None, 7)
        if len(fields) != 8:
            continue
        pid, ppid, elapsed, state, cpu, memory, rss, command = fields
        kind = _process_kind(command)
        if kind is None:
            continue
        try:
            age = _elapsed_seconds(elapsed)
            record = {
                "pid": int(pid),
                "ppid": int(ppid),
                "kind": kind,
                "elapsed": elapsed,
                "elapsed_seconds": age,
                "state": state,
                "cpu_percent": float(cpu),
                "memory_percent": float(memory),
                "resident_mb": round(int(rss) / 1024, 2),
            }
        except ValueError:
            continue
        record["orphaned"] = record["ppid"] == 1 and kind == "remotion-chromium"
        record["stale"] = record["orphaned"] and age >= stale_seconds
        records.append(record)
    return sorted(records, key=lambda item: (not item["stale"], -item["elapsed_seconds"], item["pid"]))


def _visual_timings(song: Path, limit: int = 20) -> tuple[list[dict], list[str]]:
    timings: list[dict] = []
    errors: list[str] = []
    candidates = sorted(
        song.rglob("*.mp4.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )[:limit]
    for path in candidates:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(song)}: {exc}")
            continue
        if record.get("schema") != "eprs.visual-render/v1":
            continue
        performance = record.get("performance")
        duration = record.get("duration_seconds")
        elapsed = performance.get("elapsed_seconds") if isinstance(performance, dict) else None
        ratio = None
        if (
            isinstance(duration, (int, float)) and not isinstance(duration, bool)
            and isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool)
            and math.isfinite(float(duration)) and math.isfinite(float(elapsed))
            and duration > 0
        ):
            ratio = round(float(elapsed) / float(duration), 3)
        timings.append({
            "path": str(path.relative_to(song)),
            "rendered_at": record.get("rendered_at"),
            "quality": record.get("quality"),
            "media_seconds": duration,
            "elapsed_seconds": elapsed,
            "render_to_media_ratio": ratio,
            "concurrency": performance.get("concurrency") if isinstance(performance, dict) else None,
            "timeout_seconds": performance.get("timeout_seconds") if isinstance(performance, dict) else None,
        })
    return timings, errors


def _runner_timings(song: Path, limit: int = 20) -> tuple[list[dict], list[str]]:
    """Summarize preserved runner receipts without touching live processes."""
    timings: list[dict] = []
    errors: list[str] = []
    root = song / "notes" / "runner-runs"
    if not root.is_dir():
        return timings, errors
    candidates = sorted(
        root.glob("*/*/runner.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )[:limit]
    for path in candidates:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(song)}: {exc}")
            continue
        if record.get("schema") != "eprs.agent-runner-execution/v1":
            errors.append(f"{path.relative_to(song)}: unsupported runner receipt schema")
            continue
        process = record.get("process", {})
        isolation = record.get("isolation", {})
        logs = record.get("logs", {})
        timings.append({
            "path": str(path.relative_to(song)),
            "status": record.get("status"),
            "profile": record.get("profile", {}).get("id"),
            "agent": record.get("dispatch", {}).get("agent"),
            "work_item": record.get("dispatch", {}).get("work_item"),
            "started_at": process.get("started_at"),
            "ended_at": process.get("ended_at"),
            "elapsed_seconds": process.get("elapsed_seconds"),
            "pid": process.get("pid"),
            "exit_code": process.get("exit_code"),
            "timed_out": process.get("timed_out"),
            "cleanup_verified": (
                process.get("termination", {}).get("cleanup_verified")
                if isinstance(process.get("termination"), dict) else None
            ),
            "isolation_provider": isolation.get("provider"),
            "network_hard_denied": isolation.get("network_hard_denied"),
            "raw_unchanged": record.get("raw_integrity", {}).get("unchanged"),
            "stdout_truncated": logs.get("stdout", {}).get("truncated"),
            "stderr_truncated": logs.get("stderr", {}).get("truncated"),
            "response_accepted": record.get("response", {}).get("accepted"),
        })
    return timings, errors


def performance_report(
    song: str | Path | None = None,
    *,
    stale_seconds: int = 900,
    ps_output: str | None = None,
) -> dict:
    """Report EPRS-owned workers and recent render timings without changing state."""
    if isinstance(stale_seconds, bool) or not isinstance(stale_seconds, int) or stale_seconds < 1:
        raise ValueError("performance stale_seconds must be a positive integer")
    if ps_output is None:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,etime=,state=,%cpu=,%mem=,rss=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "could not inspect processes")
        ps_output = completed.stdout
    processes = _processes(ps_output, stale_seconds)
    stale = [item for item in processes if item["stale"]]
    orphaned = [item for item in processes if item["orphaned"]]
    active = [item for item in processes if not item["orphaned"]]
    timings: list[dict] = []
    runner_timings: list[dict] = []
    timing_errors: list[str] = []
    song_value = None
    if song is not None:
        song_path = Path(song).resolve()
        load_song_manifest(song_path)
        song_value = str(song_path)
        timings, timing_errors = _visual_timings(song_path)
        runner_timings, runner_errors = _runner_timings(song_path)
        timing_errors.extend(runner_errors)
    return {
        "schema": PERFORMANCE_SCHEMA,
        "generated_at": utc_now(),
        "read_only": True,
        "song": song_value,
        "thresholds": {"stale_worker_seconds": stale_seconds},
        "summary": {
            "status": "attention" if stale else "healthy",
            "matching_processes": len(processes),
            "active_processes": len(active),
            "orphaned_browser_roots": len(orphaned),
            "stale_browser_roots": len(stale),
            "resident_mb": round(sum(item["resident_mb"] for item in processes), 2),
        },
        "processes": processes,
        "recent_visual_renders": timings,
        "recent_agent_runs": runner_timings,
        "errors": timing_errors,
        "guidance": (
            "Stale EPRS Remotion browser roots need explicit review; this report never stops them."
            if stale else
            "No stale EPRS Remotion browser roots were detected."
        ),
    }


def format_performance_report(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"Performance: {summary['status']}",
        (
            f"Processes: {summary['active_processes']} active, "
            f"{summary['orphaned_browser_roots']} orphaned browser root(s), "
            f"{summary['resident_mb']:g} MiB resident"
        ),
    ]
    for process in report["processes"]:
        label = "STALE" if process["stale"] else "orphan" if process["orphaned"] else "active"
        lines.append(
            f"- {label}: PID {process['pid']} {process['kind']} · "
            f"{process['elapsed']} · CPU {process['cpu_percent']:g}% · "
            f"{process['resident_mb']:g} MiB"
        )
    renders = report.get("recent_visual_renders", [])
    if renders:
        lines.append(f"Recent visual renders: {len(renders)}")
        for render in renders[:5]:
            elapsed = render.get("elapsed_seconds")
            media = render.get("media_seconds")
            media_label = f"{media}s" if media is not None else "unknown duration"
            timing_label = (
                f"{elapsed}s render / {media_label} media"
                if elapsed is not None else
                f"timing unavailable (legacy) / {media_label} media"
            )
            lines.append(
                f"- {render['path']}: {timing_label} · {render.get('quality')}"
            )
    agent_runs = report.get("recent_agent_runs", [])
    if agent_runs:
        lines.append(f"Recent agent runs: {len(agent_runs)}")
        for run in agent_runs[:5]:
            elapsed = run.get("elapsed_seconds")
            elapsed_label = f"{elapsed:g}s" if isinstance(elapsed, (int, float)) else "running"
            lines.append(
                f"- {run['path']}: {run.get('status')} · {elapsed_label} · "
                f"{run.get('isolation_provider')} · network denied"
            )
    lines.append(report["guidance"])
    return "\n".join(lines)
