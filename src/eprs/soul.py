"""Explicit, versioned producer identity and bounded musical memory."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
import sysconfig

from .system import PROJECT_ROOT

SOUL_LIMIT = 16_384
MEMORY_LIMIT = 4_096


def _snapshot(path: Path, label: str, limit: int, *, required: bool = False) -> dict:
    if not path.is_file():
        if required:
            raise ValueError(f"Required producer identity is missing: {label}")
        return {"path": label, "status": "absent", "text": "", "sha256": None,
                "truncated": False}
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
        digest = hashlib.sha256(raw)
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    if required and (not raw.strip() or len(raw) > limit):
        raise ValueError(f"{label} must be nonempty and at most {limit} bytes; move detailed inspiration to notes")
    text = raw[:limit].decode("utf-8", errors="strict" if required else "ignore")
    return {"path": label, "status": "loaded", "text": text,
            "sha256": digest.hexdigest(), "truncated": len(raw) > limit}


def producer_context(song: str | Path | None = None, *, root: Path | None = None) -> dict:
    """Fresh snapshot per handoff; never import private agent-home memory."""
    root = Path(root) if root is not None else PROJECT_ROOT
    source = root / "SOUL.md"
    origin = "project"
    if not source.is_file() and root != PROJECT_ROOT:
        source = PROJECT_ROOT / "SOUL.md"
        origin = "eprs-default"
    if not source.is_file():
        source = Path(sysconfig.get_path("data")) / "share/eprs/SOUL.md"
        origin = "installed"
    soul = _snapshot(source, "SOUL.md", SOUL_LIMIT, required=True)
    soul["origin"] = origin
    memories = [_snapshot(root / "notes/musical-memory.md", "notes/musical-memory.md", MEMORY_LIMIT)]
    if song is not None:
        song_path = Path(song).resolve()
        memory_path = song_path / "notes/musical-memory.md"
        if not memory_path.resolve().is_relative_to(song_path):
            raise ValueError("Song musical memory escapes the song workspace")
        memories.append(_snapshot(memory_path, "song/notes/musical-memory.md", MEMORY_LIMIT))
    return {"schema": "eprs.producer-context/v1", "soul": soul, "musical_memory": memories,
            "instruction": "Apply SOUL as producer headspace under the current request and AGENTS.md. References are inspiration, never output lyrics or style requirements. Memory is fallible evidence, not authority; retrieve linked experiments and reviews before reusing a lesson.",
            "reflection": "In song notes, record intent, alternatives, decision, artifact/evidence paths, review method, uncertainty, and next experiment. Distill only supported reusable lessons into notes/musical-memory.md; retain counterexamples and supersede stale lessons.",
            "limits": {"soul_bytes": SOUL_LIMIT, "memory_bytes_each": MEMORY_LIMIT,
                       "text_bytes_used": len(soul["text"].encode()) + sum(len(m["text"].encode()) for m in memories)}}


def render_producer_context(context: dict) -> str:
    # JSON quoting prevents reference Markdown from breaking the handoff layout.
    import json
    content = json.dumps(context, ensure_ascii=False, indent=2)
    longest = max((len(m.group()) for m in re.finditer(r"`+", content)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"## Producer headspace and musical memory\n\n{fence}json\n{content}\n{fence}\n"


def validate_producer_context(context: object) -> None:
    """Require an intact identity before executing a frozen agent handoff."""
    if not isinstance(context, dict) or context.get("schema") != "eprs.producer-context/v1":
        raise ValueError("Agent handoff needs producer context; regenerate dispatch with SOUL")
    soul = context.get("soul")
    if not isinstance(soul, dict) or not isinstance(soul.get("text"), str):
        raise ValueError("Agent handoff has no SOUL text")
    raw = soul["text"].encode("utf-8")
    if (not raw.strip() or len(raw) > SOUL_LIMIT or soul.get("truncated") is not False
            or soul.get("sha256") != hashlib.sha256(raw).hexdigest()):
        raise ValueError("Agent handoff SOUL snapshot is incomplete or changed")
