"""Reusable provenance for artifacts derived from one completed work run."""

from __future__ import annotations

from pathlib import Path

from .system import load_song_manifest, sha256
from .work import load_work_item


COMPLETED_WORK_ORIGIN_SCHEMA = "eprs.completed-work-origin/v1"


def _result_records(song: Path, item_path: Path, results: object, artifact: str) -> list[dict]:
    if not isinstance(results, dict) or not results:
        raise ValueError(f"{artifact} work run requires frozen results")
    records = []
    for result_id, result in sorted(results.items()):
        result_path = (
            (item_path.parent / result.get("path", "")).resolve()
            if isinstance(result, dict)
            else None
        )
        try:
            if result_path is None:
                raise ValueError
            result_path.relative_to(item_path.parent.resolve())
        except ValueError as exc:
            raise ValueError(f"{artifact} work result has an unsafe path: {result_id}") from exc
        if not result_path.is_file() or result.get("sha256") != sha256(result_path):
            raise ValueError(f"{artifact} work result is missing or changed: {result_id}")
        records.append({
            "id": result_id,
            "role": result.get("role"),
            "path": str(result_path.relative_to(song.resolve())),
            "sha256": result["sha256"],
        })
    return records


def capture_completed_work_origin(
    value: object,
    song: str | Path,
    artifact: str,
) -> dict | None:
    """Snapshot one completed run without coupling it to future recurring runs."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{artifact} work must be an object")
    item_value = value.get("item")
    run_number = value.get("run")
    if not isinstance(item_value, str) or not item_value:
        raise ValueError(f"{artifact} work requires item")
    if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
        raise ValueError(f"{artifact} work requires a positive run number")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    item_path, item = load_work_item(song_path, item_value)
    run = next((record for record in item["runs"] if record.get("number") == run_number), None)
    if run is None or run.get("status") != "completed":
        raise ValueError(f"{artifact} work run must be completed")
    return {
        "schema": COMPLETED_WORK_ORIGIN_SCHEMA,
        "item_id": item["id"],
        "item_path": str(item_path.resolve().relative_to(song_path)),
        "title": item["title"],
        "kind": item["kind"],
        "prompt": item["prompt"],
        "references": item["references"],
        "plan_origin": item.get("origin"),
        **({
            "request_origin": item["request_origin"],
        } if "request_origin" in item else {}),
        "run_number": run_number,
        "agent": run.get("agent"),
        "completed_at": run.get("completed_at"),
        "summary": run.get("summary"),
        "decision": run.get("decision"),
        "results": _result_records(song_path, item_path, run.get("results"), artifact),
    }


def verify_completed_work_origin(
    song: str | Path,
    origin: object,
    artifact: str,
) -> dict:
    """Verify the selected run while allowing unrelated later recurring runs."""
    if not isinstance(origin, dict) or origin.get("schema") != COMPLETED_WORK_ORIGIN_SCHEMA:
        raise ValueError(f"{artifact} work origin is invalid")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    item_path, item = load_work_item(song_path, origin.get("item_path", ""))
    if any(
        origin.get(key) != item.get(item_key)
        for key, item_key in (
            ("item_id", "id"),
            ("title", "title"),
            ("kind", "kind"),
            ("prompt", "prompt"),
            ("references", "references"),
            ("plan_origin", "origin"),
            ("request_origin", "request_origin"),
        )
    ):
        raise ValueError(f"{artifact} work origin request is missing or changed")
    run_number = origin.get("run_number")
    if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
        raise ValueError(f"{artifact} work origin run is invalid")
    run = next((record for record in item["runs"] if record.get("number") == run_number), None)
    if run is None or run.get("status") != "completed":
        raise ValueError(f"{artifact} work origin run is missing or changed")
    for key in ("agent", "completed_at", "summary", "decision"):
        if origin.get(key) != run.get(key):
            raise ValueError(f"{artifact} work origin run is missing or changed")
    try:
        expected_results = _result_records(song_path, item_path, run.get("results"), artifact)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"{artifact} work origin result is missing or changed") from exc
    if origin.get("results") != expected_results:
        raise ValueError(f"{artifact} work origin result is missing or changed")
    return origin
