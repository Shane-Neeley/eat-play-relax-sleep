"""Auditable acceptance of agent-authored production plans."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .plan import (
    PLAN_SPEC_SCHEMA_V2,
    create_production_plan,
    load_production_plan,
)
from .request import load_production_request
from .system import load_song_manifest, sha256, slugify, utc_now
from .work import load_work_item
from .work_origin import capture_completed_work_origin, verify_completed_work_origin


PLAN_ACCEPTANCE_SCHEMA = "eprs.production-plan-acceptance/v1"
PLAN_ACCEPTANCE_LIST_SCHEMA = "eprs.production-plan-acceptance-list/v1"


def _acceptance_id(recipe: dict) -> str:
    return hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _authority() -> dict:
    return {
        "statement": (
            "This receipt proves which completed local work result was validated as a "
            "production plan. It does not execute the plan, satisfy a gate, or authorize "
            "browsing, recording, processing, sending, uploading, or publishing."
        ),
        "gates_verified": False,
        "plan_executed": False,
        "upload_authorized": False,
        "publication_authorized": False,
    }


def resolve_plan_acceptance(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = (song_path / "notes" / "plans").resolve()
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    else:
        matches = sorted(root.glob(f"*/acceptances/{value}.json"))
        if len(matches) > 1:
            raise ValueError(f"production plan acceptance id is ambiguous: {value}")
        candidate = matches[0].resolve() if matches else root / str(value)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("production plan acceptance must be inside song notes/plans") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_plan_acceptance(
    song: str | Path,
    value: str | Path,
) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    path = resolve_plan_acceptance(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid production plan acceptance JSON: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != PLAN_ACCEPTANCE_SCHEMA:
        raise ValueError("unsupported production plan acceptance schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or record.get("acceptance_id") != _acceptance_id(recipe):
        raise ValueError("production plan acceptance id does not match its recipe")
    if path.stem != record["acceptance_id"] or path.parent.name != "acceptances":
        raise ValueError("production plan acceptance path does not match its id")

    plan_evidence = recipe.get("plan")
    if not isinstance(plan_evidence, dict):
        raise ValueError("production plan acceptance plan evidence is invalid")
    plan_path, plan = load_production_plan(song_path, plan_evidence.get("path", ""))
    if (
        plan.get("plan_id") != plan_evidence.get("id")
        or plan.get("schema") != plan_evidence.get("schema")
        or plan["recipe"].get("title") != plan_evidence.get("title")
        or plan["recipe"].get("request") != plan_evidence.get("request")
        or sha256(plan_path) != plan_evidence.get("sha256")
    ):
        raise ValueError("production plan acceptance plan evidence is missing or changed")

    work_origin = verify_completed_work_origin(
        song_path, recipe.get("work"), "production plan acceptance"
    )
    if work_origin.get("decision") != "complete":
        raise ValueError("production plan acceptance work decision must be complete")
    request_origin = work_origin.get("request_origin")
    plan_request = plan["recipe"]["request"]
    if (
        not isinstance(request_origin, dict)
        or request_origin.get("request_id") != plan_request.get("id")
        or request_origin.get("request_path") != plan_request.get("path")
        or request_origin.get("request_sha256") != plan_request.get("sha256")
    ):
        raise ValueError("production plan acceptance request origin does not match the plan")

    selected = recipe.get("selected_result")
    results = work_origin.get("results")
    if (
        not isinstance(selected, dict)
        or not isinstance(results, list)
        or selected not in results
    ):
        raise ValueError("production plan acceptance selected result is invalid")
    if record.get("authority") != _authority():
        raise ValueError("production plan acceptance authority is invalid")
    return path, record


def accept_plan_work_result(
    song: str | Path,
    work: str | Path,
    *,
    run_number: int | None = None,
    result_id: str | None = None,
) -> tuple[Path, dict]:
    """Validate one completed request-origin result as v2 plan and freeze provenance."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    item_path, item = load_work_item(song_path, work)
    if not isinstance(item.get("request_origin"), dict):
        raise ValueError("production plan acceptance requires request-origin work")
    completed = [run for run in item["runs"] if run.get("status") == "completed"]
    if run_number is None:
        if not completed:
            raise ValueError("production plan acceptance requires a completed work run")
        run = completed[-1]
    else:
        if isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1:
            raise ValueError("production plan acceptance run must be a positive integer")
        run = next((entry for entry in completed if entry.get("number") == run_number), None)
        if run is None:
            raise ValueError(f"production plan acceptance has no completed run {run_number}")
    if run.get("decision") != "complete":
        raise ValueError("production plan acceptance work decision must be complete")

    results = run.get("results")
    if not isinstance(results, dict) or not results:
        raise ValueError("production plan acceptance work run requires frozen results")
    if result_id is None:
        if len(results) != 1:
            raise ValueError(
                "production plan acceptance requires --result when the run has multiple results: "
                f"{', '.join(sorted(results))}"
            )
        selected_id = next(iter(results))
    else:
        if not isinstance(result_id, str) or not slugify(result_id):
            raise ValueError("production plan acceptance result must contain a valid id")
        selected_id = slugify(result_id)
    if selected_id not in results:
        raise ValueError(
            f"production plan acceptance has no result {selected_id}; available: "
            f"{', '.join(sorted(results))}"
        )

    work_origin = capture_completed_work_origin(
        {"item": item["id"], "run": run["number"]},
        song_path,
        "production plan acceptance",
    )
    selected = next(
        result for result in work_origin["results"] if result["id"] == selected_id
    )
    result_path = (song_path / selected["path"]).resolve()
    try:
        score = json.loads(result_path.read_text())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("production plan acceptance result must be valid UTF-8 JSON") from exc
    if not isinstance(score, dict) or score.get("schema") != PLAN_SPEC_SCHEMA_V2:
        raise ValueError(
            f"production plan acceptance result must use {PLAN_SPEC_SCHEMA_V2}"
        )
    request_path, request = load_production_request(song_path, score.get("request", ""))
    request_origin = item["request_origin"]
    if (
        request.get("id") != request_origin.get("request_id")
        or str(request_path.resolve().relative_to(song_path))
        != request_origin.get("request_path")
        or sha256(request_path) != request_origin.get("request_sha256")
    ):
        raise ValueError("agent-authored plan does not target its work item's captured request")

    plan_path = create_production_plan(result_path, song_path)
    _, plan = load_production_plan(song_path, plan_path)
    recipe = {
        "plan": {
            "id": plan["plan_id"],
            "path": str(plan_path.resolve().relative_to(song_path)),
            "sha256": sha256(plan_path),
            "schema": plan["schema"],
            "title": plan["recipe"]["title"],
            "request": plan["recipe"]["request"],
        },
        "work": work_origin,
        "selected_result": selected,
    }
    acceptance_id = _acceptance_id(recipe)
    acceptance_dir = plan_path.parent / "acceptances"
    acceptance_dir.mkdir(exist_ok=True)
    destination = acceptance_dir / f"{acceptance_id}.json"
    if destination.exists():
        return verify_plan_acceptance(song_path, destination)
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete production plan acceptance exists: {temporary}")
    manifest = {
        "schema": PLAN_ACCEPTANCE_SCHEMA,
        "acceptance_id": acceptance_id,
        "created_at": utc_now(),
        "recipe": recipe,
        "authority": _authority(),
    }
    try:
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return verify_plan_acceptance(song_path, destination)


def list_plan_acceptances(
    song: str | Path,
    plan: str | Path,
    *,
    verify: bool = True,
) -> dict:
    song_path = Path(song).resolve()
    plan_path, plan_record = load_production_plan(song_path, plan)
    root = plan_path.parent / "acceptances"
    items = []
    errors = []
    for path in sorted(root.glob("*.json")) if root.is_dir() else []:
        try:
            if verify:
                _, record = verify_plan_acceptance(song_path, path)
            else:
                record = json.loads(path.read_text())
                if (
                    not isinstance(record, dict)
                    or record.get("schema") != PLAN_ACCEPTANCE_SCHEMA
                ):
                    raise ValueError("unsupported schema")
            work = record.get("recipe", {}).get("work", {})
            selected = record.get("recipe", {}).get("selected_result", {})
            items.append({
                "id": record.get("acceptance_id"),
                "path": str(path.resolve().relative_to(song_path)),
                "created_at": record.get("created_at"),
                "work_item_id": work.get("item_id"),
                "run_number": work.get("run_number"),
                "agent": work.get("agent"),
                "result_id": selected.get("id"),
                "result_role": selected.get("role"),
            })
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            errors.append({
                "path": str(path.resolve().relative_to(song_path)),
                "error": str(exc),
            })
    return {
        "schema": PLAN_ACCEPTANCE_LIST_SCHEMA,
        "plan_id": plan_record["plan_id"],
        "items": items,
        "errors": errors,
    }
