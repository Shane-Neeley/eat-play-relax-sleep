"""Small, inspectable production maps for one agent-led song run."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlsplit

from .request import load_production_request
from .system import load_song_manifest, sha256


MAP_SCHEMA = "eprs.production-map/v1"
RUN_SCHEMA = "eprs.song-run/v1"
DOT_MARKER = "// eprs.production-map/v1"


def _inside(song: Path, value: str | Path, label: str) -> Path:
    requested = Path(value)
    path = requested.resolve() if requested.is_absolute() else (song / requested).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"production map {label} must stay inside the song workspace") from exc
    return path


def _load_run(song: Path, value: str | Path | None) -> tuple[Path, dict]:
    if value is None:
        latest = load_song_manifest(song).get("latest_run")
        if not isinstance(latest, dict) or not isinstance(latest.get("path"), str):
            raise ValueError("song has no latest agent-led run to map")
        run_path = _inside(song, latest["path"], "run")
    else:
        requested = Path(value)
        candidates = [
            _inside(song, requested, "run"),
            song / "notes" / "runs" / str(value) / "run.json",
        ]
        run_path = next((candidate.resolve() for candidate in candidates if candidate.is_file()), candidates[0])
    if not run_path.is_file():
        raise FileNotFoundError(run_path)
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid song-run JSON: {run_path}: {exc.msg}") from exc
    if run.get("schema") != RUN_SCHEMA:
        raise ValueError(f"unsupported song-run schema: {run.get('schema')}")
    return run_path, run


def _q(value: object) -> str:
    """Return a DOT-safe quoted scalar."""
    return json.dumps(str(value), ensure_ascii=False)


def _short(value: object, maximum: int = 72) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= maximum else text[: maximum - 1] + "…"


def _reference(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        tail = parsed.path.rstrip("/").split("/")[-1]
        return _short(f"{parsed.netloc}/{tail}" if tail else parsed.netloc, 64)
    return _short(value, 64)


def _node(identifier: str, label: str, group: str) -> str:
    colors = {
        "intent": ("#ffcc66", "#3a2b12"),
        "source": ("#8bd5ca", "#12332f"),
        "agent": ("#c6a0f6", "#2c1e40"),
        "editable": ("#91d7e3", "#15313a"),
        "media": ("#a6da95", "#1d351c"),
        "visual": ("#f5bde6", "#3a2035"),
        "handoff": ("#f0c6c6", "#3b2424"),
        "evidence": ("#b8c0e0", "#252a3b"),
    }
    border, fill = colors[group]
    return (
        f"  {identifier} [label={_q(label)}, color={_q(border)}, "
        f"fillcolor={_q(fill)}, group={_q(group)}];"
    )


def _edge(source: str, target: str, label: str = "") -> str:
    suffix = f" [label={_q(label)}]" if label else ""
    return f"  {source} -> {target}{suffix};"


def production_map_dot(song: str | Path, run: str | Path | None = None) -> tuple[Path, str]:
    """Build renderer-independent DOT for one run without touching the workspace."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    run_path, record = _load_run(song_path, run)
    paths = record.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("song run paths must be an object")

    request_path = paths.get("request")
    request = {}
    if isinstance(request_path, str):
        _, request = load_production_request(song_path, request_path)

    title = _short(record.get("title", song_path.name), 80)
    prompt = _short(record.get("prompt", "creative prompt"), 100)
    seed = record.get("randomness", {}).get("seed", "unknown")
    lines = [
        DOT_MARKER,
        "digraph eprs_production_map {",
        "  graph [rankdir=LR, bgcolor=\"#0f1117\", fontcolor=\"#cad3f5\", "
        f"fontname=\"Helvetica\", labelloc=\"t\", label={_q(title + ' · production map')}, "
        "id=\"eprs-production-map-v1\", pad=\"0.35\", nodesep=\"0.35\", ranksep=\"0.55\"];",
        "  node [shape=box, style=\"rounded,filled\", fontname=\"Helvetica\", "
        "fontcolor=\"#f5f5f5\", fontsize=10, margin=\"0.14,0.10\"] ;",
        "  edge [color=\"#6e738d\", fontcolor=\"#a5adcb\", fontname=\"Helvetica\", "
        "fontsize=8, arrowsize=0.7];",
        _node("prompt", f"PROMPT\\n{prompt}", "intent"),
        _node("request", f"CAPTURED REQUEST\\n{request_path or 'unavailable'}", "intent"),
        _node("agent_work", f"QUEUED AGENT PLAN\\n{paths.get('agent_work', 'unavailable')}", "agent"),
        _node("brief", f"AGENT BRIEF\\n{paths.get('brief', 'unavailable')}", "agent"),
        _node("beat", f"EDITABLE BEATSCRIPT\\n{paths.get('beat', 'unavailable')}\\nseed {seed}", "editable"),
        _node("visual_score", f"EDITABLE VISUAL SCORE\\n{paths.get('visual_score', 'unavailable')}\\nseed {seed}", "editable"),
        _node("experiment", f"FROZEN EXPERIMENT\\n{paths.get('experiment', 'unavailable')}", "evidence"),
        _node("audio", f"STARTER AUDIO\\n{paths.get('audio_preview', 'unavailable')}", "media"),
        _node("rhythm", f"RHYTHM MAP\\n{paths.get('rhythm_map', 'unavailable')}", "visual"),
        _node("run", f"RUN MANIFEST\\n{run_path.relative_to(song_path)}", "evidence"),
        _node("now", "SHALLOW HANDOFF\\nNOW.md + _CHANGE_ME.md", "handoff"),
        _node("listen", "LISTEN NOW\\n_LISTEN.wav", "handoff"),
    ]

    provided = request.get("provided", {}) if isinstance(request, dict) else {}
    if isinstance(provided, dict):
        for index, item in enumerate(provided.values(), start=1):
            if not isinstance(item, dict):
                continue
            node_id = f"input_{index}"
            handling = item.get("handling", "supplied input")
            location = item.get("path", "path unavailable")
            label = f"{_short(item.get('role', 'supplied input'), 48).upper()}\\n{handling}\\n{_short(location, 64)}"
            lines.extend([_node(node_id, label, "source"), _edge(node_id, "request", "captured")])

    references = request.get("references", []) if isinstance(request, dict) else []
    if isinstance(references, list):
        for index, value in enumerate(references, start=1):
            if not isinstance(value, str):
                continue
            node_id = f"reference_{index}"
            lines.extend([
                _node(node_id, f"RESEARCH LEAD\\n{_reference(value)}", "source"),
                _edge(node_id, "request", "declared"),
                _edge(node_id, "agent_work", "research before use"),
            ])

    lines.extend([
        _edge("prompt", "request", "preserved"),
        _edge("request", "agent_work", "bounds"),
        _edge("request", "brief", "informs"),
        _edge("brief", "experiment", "intent"),
        _edge("beat", "experiment", "frozen input"),
        _edge("visual_score", "experiment", "frozen input"),
        _edge("beat", "audio", "renders"),
        _edge("beat", "rhythm", "draws"),
        _edge("experiment", "audio", "records"),
    ])
    if isinstance(paths.get("visual_preview"), str):
        lines.extend([
            _node("video", f"VISUAL PREVIEW\\n{paths['visual_preview']}", "visual"),
            _node("watch", "WATCH NOW\\n_WATCH.mp4", "handoff"),
            _edge("audio", "video", "reacts to"),
            _edge("visual_score", "video", "drives"),
            _edge("video", "watch", "points to"),
            _edge("video", "run", "checksummed"),
        ])
    lines.extend([
        _edge("request", "run", "links"),
        _edge("agent_work", "run", "links"),
        _edge("experiment", "run", "links"),
        _edge("audio", "run", "checksummed"),
        _edge("rhythm", "run", "checksummed"),
        _edge("run", "now", "summarized by"),
        _edge("audio", "listen", "points to"),
        _edge("listen", "now", "review here"),
        "}",
        "",
    ])
    return run_path, "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    if path.exists():
        if not path.is_file() or not path.read_text(encoding="utf-8").startswith(DOT_MARKER):
            raise FileExistsError(f"refusing to replace non-EPRS production map: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def write_production_map(
    song: str | Path,
    run: str | Path | None = None,
    *,
    out: str | Path | None = None,
    render_svg: bool = True,
) -> dict:
    """Write DOT and optionally render SVG with Graphviz when it is available."""
    song_path = Path(song).resolve()
    run_path, dot = production_map_dot(song_path, run)
    dot_path = (
        _inside(song_path, out, "output")
        if out is not None
        else run_path.parent / "production-map.dot"
    )
    if dot_path.suffix.lower() != ".dot":
        raise ValueError("production map output must use the .dot extension")
    _write_text(dot_path, dot)

    result = {
        "schema": MAP_SCHEMA,
        "run": str(run_path.relative_to(song_path)),
        "dot": {
            "path": str(dot_path.relative_to(song_path)),
            "sha256": sha256(dot_path),
        },
        "svg": None,
        "renderer": {"status": "disabled", "tool": None},
    }
    if not render_svg:
        return result
    executable = shutil.which("dot")
    if executable is None:
        result["renderer"] = {
            "status": "skipped",
            "tool": "Graphviz dot",
            "reason": "dot command is not installed; the portable DOT map is still complete",
        }
        return result

    svg_path = dot_path.with_suffix(".svg")
    if svg_path.exists():
        if not svg_path.is_file() or b"eprs-production-map-v1" not in svg_path.read_bytes()[:65536]:
            raise FileExistsError(f"refusing to replace non-EPRS production map: {svg_path}")
    temporary = svg_path.with_name(f".{svg_path.name}.partial")
    completed = subprocess.run(
        [executable, "-Tsvg", str(dot_path), "-o", str(temporary)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        detail = (completed.stderr or completed.stdout).strip()
        result["renderer"] = {
            "status": "failed",
            "tool": "Graphviz dot",
            "reason": detail or f"dot exited {completed.returncode}",
        }
        return result
    temporary.replace(svg_path)
    result["svg"] = {
        "path": str(svg_path.relative_to(song_path)),
        "sha256": sha256(svg_path),
    }
    result["renderer"] = {"status": "rendered", "tool": "Graphviz dot"}
    return result
