"""Read-only production-plan progress derived from verified work decisions."""

from __future__ import annotations

from pathlib import Path

from .plan import load_production_plan
from .system import load_song_manifest, slugify, utc_now
from .work import (
    create_work_item,
    list_work_items,
    load_work_item,
    work_queue_transaction,
)


PROGRESS_SCHEMA = "eprs.production-plan-progress/v1"
QUEUE_SCHEMA = "eprs.production-plan-queue/v1"


def _linked_work_state(items: list[dict]) -> str:
    """Derive conservatively: active work overrides an older completion."""
    states = {item["status"] for item in items}
    if "in_progress" in states:
        return "in_progress"
    if "queued" in states:
        return "queued"
    if "completed" in states:
        return "complete"
    if "stopped" in states:
        return "stopped"
    return "not_started"


def production_plan_progress(song: str | Path, value: str | Path) -> dict:
    """Project immutable plan + work history; never infer approval-gate state."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    plan_path, plan = load_production_plan(song_path, value)
    plan_id = plan["plan_id"]
    work_report = list_work_items(song_path)
    linked: dict[str, list[dict]] = {}
    for summary in work_report["items"]:
        origin = summary.get("plan_origin")
        if not isinstance(origin, dict) or origin.get("plan_id") != plan_id:
            continue
        item_path, item = load_work_item(song_path, summary["path"])
        step_id = origin.get("step_id")
        if not isinstance(step_id, str):
            continue
        current = item["runs"][-1]
        title = item["title"]
        linked.setdefault(step_id, []).append({
            "id": item["id"],
            "path": str(item_path.resolve().relative_to(song_path)),
            "title": title[:512],
            "title_truncated": len(title) > 512,
            "status": item["status"],
            "run_number": current["number"],
            "run_status": current["status"],
            "decision": current.get("decision"),
            "due_at": current.get("due_at"),
            "agent": current.get("agent"),
            "completed_at": current.get("completed_at"),
        })

    steps = []
    work_states = {}
    for step in plan["recipe"]["steps"]:
        items = sorted(linked.get(step["id"], []), key=lambda item: item["id"])
        work_state = _linked_work_state(items)
        work_states[step["id"]] = work_state
        steps.append({
            "id": step["id"],
            "kind": step["kind"],
            "intent": step["intent"],
            "depends_on": step["depends_on"],
            "work_state": work_state,
            "work_items": items,
            "declared_gates": step["gates"],
            "gates_verified": False,
        })

    actionable = []
    blocked = []
    active = []
    complete = []
    stopped = []
    for step in steps:
        dependencies_complete = all(
            work_states.get(dependency) == "complete" for dependency in step["depends_on"]
        )
        step["dependencies_complete"] = dependencies_complete
        state = step["work_state"]
        if state == "complete":
            step["dependency_state"] = "complete"
            complete.append(step["id"])
        elif state == "stopped":
            step["dependency_state"] = "stopped"
            stopped.append(step["id"])
        elif state == "in_progress":
            step["dependency_state"] = "active"
            active.append(step["id"])
        elif dependencies_complete:
            step["dependency_state"] = "actionable"
            actionable.append(step["id"])
            if state == "queued":
                active.append(step["id"])
        else:
            step["dependency_state"] = "blocked"
            blocked.append(step["id"])

    if len(complete) == len(steps):
        overall = "complete"
    elif active or complete:
        overall = "in_progress"
    elif stopped and not actionable:
        overall = "stopped"
    else:
        overall = "not_started"
    gates = sorted({gate for step in steps for gate in step["declared_gates"]})
    queueable = [
        step["id"] for step in steps
        if step["dependency_state"] == "actionable"
        and step["work_state"] == "not_started"
    ]
    return {
        "schema": PROGRESS_SCHEMA,
        "generated_at": utc_now(),
        "plan": {
            "id": plan_id,
            "path": str(plan_path.resolve().relative_to(song_path)),
            "title": plan["recipe"]["title"],
            "request": plan["recipe"]["request"],
        },
        "state": overall,
        "steps": steps,
        "summary": {
            "total": len(steps),
            "complete": len(complete),
            "active": len(active),
            "actionable": len(actionable),
            "queueable": len(queueable),
            "blocked": len(blocked),
            "stopped": len(stopped),
        },
        "complete_steps": complete,
        "active_steps": active,
        "actionable_steps": actionable,
        "queueable_steps": queueable,
        "blocked_steps": blocked,
        "stopped_steps": stopped,
        "declared_gates": gates,
        "gates_verified": False,
        "errors": work_report["errors"],
        "authority": {
            "statement": "Progress is derived only from verified plan-linked work decisions. It does not satisfy or infer user direction, consent, rights, listening, technical, upload, or publication gates.",
        },
    }


def _queue_step_summary(step: dict) -> dict:
    return {
        "id": step["id"],
        "kind": step["kind"],
        "intent": step["intent"],
        "work_state": step["work_state"],
        "dependency_state": step["dependency_state"],
        "depends_on": step["depends_on"],
        "declared_gates": step["declared_gates"],
        "gates_verified": False,
    }


def queue_next_plan_step(
    song: str | Path,
    value: str | Path,
    *,
    step_id: str | None = None,
    priority: int = 50,
    due_at: str | None = None,
) -> dict:
    """Queue one unstarted dependency-ready step without executing or approving it."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    plan_path, plan = load_production_plan(song_path, value)
    if step_id is not None and not isinstance(step_id, str):
        raise ValueError("plan queue-next step must be a string")
    requested_step = slugify(step_id.strip()) if isinstance(step_id, str) else None
    if isinstance(step_id, str) and not requested_step:
        raise ValueError("plan queue-next step must contain at least one letter or number")
    if requested_step is not None and not any(
        step["id"] == requested_step for step in plan["recipe"]["steps"]
    ):
        raise ValueError(f"production plan has no step: {requested_step}")

    with work_queue_transaction(song_path):
        progress = production_plan_progress(song_path, plan_path)
        if progress["errors"]:
            invalid = ", ".join(error.get("id", "unknown") for error in progress["errors"])
            raise ValueError(
                f"plan queue-next refuses an invalid work queue; inspect: {invalid}"
            )
        steps = progress["steps"]
        if requested_step is not None:
            selected = next(step for step in steps if step["id"] == requested_step)
            eligible = (
                selected["dependency_state"] == "actionable"
                and selected["work_state"] == "not_started"
            )
            candidates = [selected] if eligible else []
        else:
            queueable = set(progress["queueable_steps"])
            candidates = [step for step in steps if step["id"] in queueable]
            selected = candidates[0] if candidates else None

        base = {
            "schema": QUEUE_SCHEMA,
            "generated_at": utc_now(),
            "plan": progress["plan"],
            "requested_step": requested_step,
            "gates_verified": False,
            "authority": {
                "statement": (
                    "This transaction prepares one local work request only. It does not execute "
                    "the step or verify user direction, consent, rights, listening, technical, "
                    "upload, or publication gates."
                ),
            },
        }
        if not candidates:
            return {
                **base,
                "status": "idle",
                "reason": (
                    "requested-step-not-unstarted-and-actionable"
                    if requested_step is not None
                    else "no-unstarted-actionable-step"
                ),
                "selected_step": _queue_step_summary(selected) if selected else None,
                "work": None,
                "actionable_steps": progress["actionable_steps"],
            }

        item_path = create_work_item(
            song_path,
            None,
            None,
            None,
            priority=priority,
            due_at=due_at,
            plan=plan_path,
            plan_step=selected["id"],
        )
        _, item = load_work_item(song_path, item_path)
        current = item["runs"][-1]
        return {
            **base,
            "status": "queued",
            "reason": None,
            "selected_step": _queue_step_summary(selected),
            "work": {
                "id": item["id"],
                "path": str(item_path.resolve().relative_to(song_path)),
                "title": item["title"],
                "kind": item["kind"],
                "priority": item["priority"],
                "status": item["status"],
                "run_number": current["number"],
                "due_at": current["due_at"],
            },
            "actionable_steps": progress["actionable_steps"],
        }
