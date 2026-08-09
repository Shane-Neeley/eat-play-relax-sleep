"""Song-scoped agent work requests and recurring automation runs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil

from .plan import PLAN_SPEC_SCHEMA_V2, load_production_plan
from .request import load_production_request
from .system import create_experiment, load_song_manifest, sha256, slugify, utc_now


WORK_SCHEMA = "eprs.work-item/v1"
WORK_LIST_SCHEMA = "eprs.work-list/v1"
WORK_CLAIM_SCHEMA = "eprs.work-claim/v1"
CADENCES = {"once", "daily", "weekly"}
DECISIONS = {"complete", "needs-followup", "stop"}
PLAN_STEP_ORIGIN_SCHEMA_V1 = "eprs.production-plan-step-origin/v1"
PLAN_STEP_ORIGIN_SCHEMA_V2 = "eprs.production-plan-step-origin/v2"
PLAN_STEP_ORIGIN_SCHEMA = PLAN_STEP_ORIGIN_SCHEMA_V1
REQUEST_WORK_ORIGIN_SCHEMA = "eprs.production-request-work-origin/v1"
WORK_RESULT_CONTRACT_SCHEMA = "eprs.work-result-contract/v1"
RESULT_ROLE_ID = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def _parse_moment(value: str, label: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO 8601 date-time with a timezone") from exc
    if moment.tzinfo is None:
        raise ValueError(f"{label} must include a timezone, such as Z or -07:00")
    return moment.astimezone(timezone.utc)


def _format_moment(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"Incomplete work-item update already exists: {temporary}")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


@contextmanager
def _exclusive_lock(lock: Path, label: str):
    """Create one local lock that is never cleared speculatively."""
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(
            f"{label} is locked by another process: {lock}. "
            "If a process crashed, inspect the item before removing the stale lock."
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} created_at={utc_now()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


@contextmanager
def _item_lock(path: Path):
    """Prevent two local agents from mutating one work item concurrently."""
    with _exclusive_lock(path.parent / ".work.lock", "Work item"):
        yield


def _unique_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name}-{number}"
        number += 1
    return candidate


def _freeze_source(song: Path, item_dir: Path, role: str, source: str | Path) -> dict:
    source_path = Path(source).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    digest = sha256(source_path)
    raw_root = (song / "recordings" / "raw").resolve()
    try:
        relative = source_path.relative_to(raw_root)
    except ValueError:
        relative = None
    if relative is not None:
        return {
            "role": role,
            "path": str(source_path.relative_to(song.resolve())),
            "base": "song",
            "storage": "song-reference",
            "original_name": source_path.name,
            "sha256": digest,
        }
    inputs = item_dir / "inputs"
    inputs.mkdir(exist_ok=True)
    role_id = slugify(role)
    destination = inputs / f"{role_id}-{source_path.name}"
    if destination.exists() and sha256(destination) != digest:
        destination = inputs / f"{role_id}-{digest[:10]}-{source_path.name}"
    if not destination.exists():
        shutil.copy2(source_path, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"work source changed while it was being frozen: {source_path}")
    return {
        "role": role,
        "path": str(destination.relative_to(item_dir)),
        "base": "work-item",
        "storage": "work-item-copy",
        "original_name": source_path.name,
        "sha256": digest,
    }


def _validated_sources(sources: list[tuple[str, str | Path]] | None) -> list[tuple[str, Path]]:
    validated: list[tuple[str, Path]] = []
    ids: set[str] = set()
    for role, source in sources or []:
        role_id = slugify(role)
        if not role_id:
            raise ValueError("work source role must contain at least one letter or number")
        if role_id in ids:
            raise ValueError(f"duplicate work source role: {role}")
        source_path = Path(source).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        ids.add(role_id)
        validated.append((role, source_path))
    return validated


def _validated_result_roles(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    if len(value) > 64:
        raise ValueError(f"{label} exceeds 64 items")
    roles: list[str] = []
    for role in value:
        if (
            not isinstance(role, str)
            or not RESULT_ROLE_ID.fullmatch(role)
            or len(role) > 200
        ):
            raise ValueError(f"{label} must contain portable result-role slugs")
        if role in roles:
            raise ValueError(f"{label} must not contain duplicates")
        roles.append(role)
    return roles


def _result_contract(required_roles: object) -> dict | None:
    roles = _validated_result_roles(required_roles, "work required result roles")
    if not roles:
        return None
    return {
        "schema": WORK_RESULT_CONTRACT_SCHEMA,
        "required_roles": roles,
        "allow_additional": True,
        "applies_to_decision": "complete",
    }


def _request_source(
    song: Path,
    request_path: Path,
    record: object,
    source_id: str,
    *,
    label: str,
) -> Path:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise ValueError(f"{label} input is invalid: {source_id}")
    base_name = record.get("base")
    base = song if base_name == "song" else request_path.parent if base_name == "request" else None
    if base is None:
        raise ValueError(f"{label} input has an unsupported base: {source_id}")
    source = (base / record["path"]).resolve()
    try:
        source.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} input has an unsafe path: {source_id}") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    if record.get("sha256") != sha256(source):
        raise ValueError(f"{label} input checksum has changed: {source_id}")
    return source


def _plan_step_origin(
    song: Path,
    plan: str | Path | None,
    plan_step: str | None,
) -> tuple[dict | None, list[tuple[str, str, Path]], dict | None]:
    if (plan is None) != (plan_step is None):
        raise ValueError("work plan and plan_step must be supplied together")
    if plan is None:
        return None, [], None
    clean_step = slugify(plan_step.strip()) if isinstance(plan_step, str) else ""
    if not clean_step:
        raise ValueError("work plan_step must contain at least one letter or number")
    plan_path, plan_record = load_production_plan(song, plan)
    step = next(
        (record for record in plan_record["recipe"]["steps"] if record.get("id") == clean_step),
        None,
    )
    if step is None:
        raise ValueError(f"production plan has no step: {clean_step}")
    request_path, request = load_production_request(song, plan_record["recipe"]["request"]["path"])
    plan_sources = []
    for source_id in step["uses"]:
        record = request["provided"].get(source_id)
        source = _request_source(
            song,
            request_path,
            record,
            source_id,
            label="production plan request",
        )
        plan_sources.append((source_id, record["role"], source))
    origin = {
        "schema": (
            PLAN_STEP_ORIGIN_SCHEMA_V2
            if plan_record["recipe"]["schema"] == PLAN_SPEC_SCHEMA_V2
            else PLAN_STEP_ORIGIN_SCHEMA_V1
        ),
        "plan_id": plan_record["plan_id"],
        "plan_path": str(plan_path.resolve().relative_to(song.resolve())),
        "plan_sha256": sha256(plan_path),
        "request": plan_record["recipe"]["request"],
        "step": step,
        "source_map": {source_id: source_id for source_id in step["uses"]},
    }
    return origin, plan_sources, step


def _request_work_origin(
    song: Path,
    request: str | Path | None,
) -> tuple[dict | None, list[tuple[str, str, Path]], dict | None]:
    if request is None:
        return None, [], None
    request_path, record = load_production_request(song, request)
    request_sources = []
    for source_id, source_record in record["provided"].items():
        source = _request_source(
            song,
            request_path,
            source_record,
            source_id,
            label="captured production request",
        )
        request_sources.append((source_id, source_record["role"], source))
    origin = {
        "schema": REQUEST_WORK_ORIGIN_SCHEMA,
        "request_id": record["id"],
        "request_path": str(request_path.resolve().relative_to(song.resolve())),
        "request_sha256": sha256(request_path),
        "source_map": {source_id: source_id for source_id in record["provided"]},
    }
    return origin, request_sources, record


def _default_request_prompt(request: dict) -> str:
    return (
        f"Author an eprs.production-plan/v2 for captured request {request['id']}. "
        "Read its exact prompt, intended experience, preserve/avoid constraints, open "
        "questions, deliverables, references, supplied evidence, and rights notes. Keep "
        "the creative path open; declare only justified dependencies, smallest actions, "
        "evidence conditions, listening questions, gates, exact required capability "
        "slugs, and exact required result-role slugs. Return the plan specification as "
        "frozen result evidence under role production-plan. Do not execute "
        "the plan, process media, browse, upload, publish, or infer consent or approval."
    )


def _default_plan_prompt(step: dict) -> str:
    outputs = "; ".join(step["outputs"])
    done_when = "; ".join(step["done_when"])
    gates = ", ".join(step["gates"]) or "none declared"
    listening = step["listening_question"] or "No listening question declared for this step."
    capability_statement = ""
    if "required_capabilities" in step:
        capabilities = ", ".join(step["required_capabilities"]) or "none declared"
        capability_statement = f" Required software capabilities: {capabilities}."
    result_statement = ""
    if "required_result_roles" in step:
        roles = ", ".join(step["required_result_roles"])
        result_statement = f" Required result roles for decision complete: {roles}."
    return (
        f"Execute only production-plan step {step['id']}. Intent: {step['intent']} "
        f"Smallest action: {step['smallest_action']} Outputs: {outputs}. "
        f"Done only when: {done_when}. Listening question: {listening}"
        f"{capability_statement}{result_statement} "
        f"Gates to verify separately: {gates}. This work item does not satisfy those gates."
    )


def create_work_item(
    song: str | Path,
    title: str | None,
    kind: str | None,
    prompt: str | None,
    *,
    priority: int = 50,
    cadence: str = "once",
    due_at: str | None = None,
    references: list[str] | None = None,
    sources: list[tuple[str, str | Path]] | None = None,
    request: str | Path | None = None,
    plan: str | Path | None = None,
    plan_step: str | None = None,
    required_result_roles: list[str] | None = None,
) -> Path:
    """Create a queued request with frozen local inputs and explicit recurrence."""
    song_path = Path(song)
    load_song_manifest(song_path)
    if request is not None and (plan is not None or plan_step is not None):
        raise ValueError("work request origin cannot be combined with a production-plan step")
    origin, plan_sources, step = _plan_step_origin(song_path.resolve(), plan, plan_step)
    request_origin, request_sources, request_record = _request_work_origin(
        song_path.resolve(), request
    )
    clean_title = title.strip() if isinstance(title, str) else ""
    clean_kind = kind.strip() if isinstance(kind, str) else ""
    clean_prompt = prompt.strip() if isinstance(prompt, str) else ""
    uses_request_planning_defaults = (
        request_record is not None and not clean_title and not clean_kind and not clean_prompt
    )
    if step is not None:
        clean_title = clean_title or f"Plan step: {step['id']}"
        clean_kind = clean_kind or step["kind"]
        clean_prompt = clean_prompt or _default_plan_prompt(step)
    elif request_record is not None:
        clean_title = clean_title or f"Plan request: {request_record['title']}"
        clean_kind = clean_kind or "production planning"
        clean_prompt = clean_prompt or _default_request_prompt(request_record)
    if not clean_title or not slugify(clean_title):
        raise ValueError("work title must contain at least one letter or number")
    if not clean_kind or not slugify(clean_kind):
        raise ValueError("work kind must contain at least one letter or number")
    if not clean_prompt:
        raise ValueError("work prompt is required")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ValueError("work priority must be an integer from 0 to 100")
    if cadence not in CADENCES:
        raise ValueError(f"work cadence must be one of: {', '.join(sorted(CADENCES))}")
    clean_references = []
    for reference in references or []:
        value = reference.strip()
        if not value:
            raise ValueError("work references cannot be blank")
        clean_references.append(value)
    validated_sources = _validated_sources(sources)
    declared_roles = list(required_result_roles or [])
    if step is not None and "required_result_roles" in step:
        plan_roles = step["required_result_roles"]
        if declared_roles and declared_roles != plan_roles:
            raise ValueError(
                "work required result roles must exactly match the production-plan step"
            )
        declared_roles = plan_roles
    elif uses_request_planning_defaults and not declared_roles:
        declared_roles = ["production-plan"]
    result_contract = _result_contract(declared_roles)
    created = utc_now()
    due = _format_moment(_parse_moment(due_at, "work due_at")) if due_at else created
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    item_id = f"{stamp}-{slugify(clean_title)}"
    item_dir = _unique_path(song_path / "notes" / "work", item_id)
    temporary = item_dir.with_name(f".{item_dir.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"Incomplete work-item creation already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        frozen_sources = {}
        inherited_sources = [*plan_sources, *request_sources]
        for source_id, role, source in inherited_sources:
            frozen_sources[source_id] = _freeze_source(song_path, temporary, role, source)
        for role, source in validated_sources:
            source_id = slugify(role)
            if source_id in frozen_sources:
                raise ValueError(f"work source role conflicts with an inherited input: {role}")
            frozen_sources[source_id] = _freeze_source(song_path, temporary, role, source)
        item = {
            "schema": WORK_SCHEMA,
            "id": item_dir.name,
            "created_at": created,
            "updated_at": created,
            "title": clean_title,
            "kind": clean_kind,
            "prompt": clean_prompt,
            "origin": origin,
            **({"request_origin": request_origin} if request_origin is not None else {}),
            **({"result_contract": result_contract} if result_contract is not None else {}),
            "priority": priority,
            "status": "queued",
            "schedule": {"cadence": cadence, "next_due_at": due},
            "references": clean_references,
            "sources": frozen_sources,
            "runs": [{
                "number": 1,
                "status": "queued",
                "queued_at": created,
                "due_at": due,
                "agent": None,
                "claims": [],
                "results": [],
            }],
        }
        _atomic_json(temporary / "work.json", item)
        temporary.rename(item_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return item_dir / "work.json"


def _work_root(song: Path) -> Path:
    return song / "notes" / "work"


@contextmanager
def work_queue_transaction(song: str | Path):
    """Serialize a queue mutation that may create a new work item."""
    song_path = Path(song)
    load_song_manifest(song_path)
    root = _work_root(song_path)
    root.mkdir(parents=True, exist_ok=True)
    with _exclusive_lock(root / ".queue.lock", "Work queue"):
        yield root


def resolve_work_item(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
        if candidate.is_dir():
            candidate = candidate / "work.json"
    elif requested.exists():
        candidate = requested.resolve()
        if candidate.is_dir():
            candidate = candidate / "work.json"
    elif "/" in str(value):
        candidate = (song_path / requested).resolve()
        if candidate.is_dir():
            candidate = candidate / "work.json"
    else:
        candidate = (_work_root(song_path) / str(value) / "work.json").resolve()
    try:
        candidate.relative_to(_work_root(song_path).resolve())
    except ValueError as exc:
        raise ValueError("work item must be inside the song notes/work directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def load_work_item(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    path = resolve_work_item(song, value)
    try:
        item = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid work item JSON: {path}: {exc.msg}") from exc
    if item.get("schema") != WORK_SCHEMA:
        raise ValueError("unsupported work item schema")
    if item.get("id") != path.parent.name:
        raise ValueError("work item id does not match its directory")
    for field in ("title", "kind", "prompt"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(f"work item requires a non-empty {field}")
    priority = item.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ValueError("work item priority must be an integer from 0 to 100")
    state = item.get("status")
    if state not in {"queued", "in_progress", "completed", "stopped"}:
        raise ValueError("work item has an unsupported status")
    schedule = item.get("schedule")
    if not isinstance(schedule, dict) or schedule.get("cadence") not in CADENCES:
        raise ValueError("work item has an invalid schedule")
    if not isinstance(item.get("sources"), dict) or not isinstance(item.get("references"), list):
        raise ValueError("work item sources and references must be collections")
    origin = item.get("origin")
    request_origin = item.get("request_origin")
    if origin is not None and request_origin is not None:
        raise ValueError("work item cannot have both plan and request origins")
    if origin is not None:
        if not isinstance(origin, dict) or origin.get("schema") not in {
            PLAN_STEP_ORIGIN_SCHEMA_V1, PLAN_STEP_ORIGIN_SCHEMA_V2
        }:
            raise ValueError("work item has an unsupported origin")
        plan_path, plan = load_production_plan(Path(song), origin.get("plan_path", ""))
        expected_origin_schema = (
            PLAN_STEP_ORIGIN_SCHEMA_V2
            if plan["recipe"]["schema"] == PLAN_SPEC_SCHEMA_V2
            else PLAN_STEP_ORIGIN_SCHEMA_V1
        )
        if origin.get("schema") != expected_origin_schema:
            raise ValueError("work item origin schema does not match its production plan")
        step = origin.get("step")
        live_step = next(
            (
                record for record in plan["recipe"]["steps"]
                if isinstance(step, dict) and record.get("id") == step.get("id")
            ),
            None,
        )
        if (
            plan.get("plan_id") != origin.get("plan_id")
            or sha256(plan_path) != origin.get("plan_sha256")
            or plan["recipe"]["request"] != origin.get("request")
            or live_step != step
        ):
            raise ValueError("work item production-plan origin is missing or changed")
        source_map = origin.get("source_map")
        if (
            not isinstance(source_map, dict)
            or set(source_map) != set(step.get("uses", []))
            or any(source_map.get(source_id) not in item["sources"] for source_id in source_map)
        ):
            raise ValueError("work item production-plan source map is invalid")
    if request_origin is not None:
        if (
            not isinstance(request_origin, dict)
            or request_origin.get("schema") != REQUEST_WORK_ORIGIN_SCHEMA
        ):
            raise ValueError("work item has an unsupported production-request origin")
        request_path, request_record = load_production_request(
            Path(song), request_origin.get("request_path", "")
        )
        if (
            request_record.get("id") != request_origin.get("request_id")
            or sha256(request_path) != request_origin.get("request_sha256")
        ):
            raise ValueError("work item production-request origin is missing or changed")
        source_map = request_origin.get("source_map")
        expected_source_map = {
            source_id: source_id for source_id in request_record.get("provided", {})
        }
        if (
            not isinstance(source_map, dict)
            or source_map != expected_source_map
            or any(source_id not in item["sources"] for source_id in source_map)
        ):
            raise ValueError("work item production-request source map is invalid")
    result_contract = item.get("result_contract")
    required_roles: list[str] | None = None
    if result_contract is not None:
        if (
            not isinstance(result_contract, dict)
            or result_contract.get("schema") != WORK_RESULT_CONTRACT_SCHEMA
            or result_contract.get("allow_additional") is not True
            or result_contract.get("applies_to_decision") != "complete"
        ):
            raise ValueError("work item has an invalid result contract")
        required_roles = _validated_result_roles(
            result_contract.get("required_roles"), "work result contract required_roles"
        )
        if not required_roles:
            raise ValueError("work result contract requires at least one role")
    if origin is not None:
        step_roles = origin.get("step", {}).get("required_result_roles")
        if step_roles is not None and required_roles != step_roles:
            raise ValueError(
                "work item result contract does not match its production-plan step"
            )
    runs = item.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("work item requires at least one run")
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict) or run.get("number") != index:
            raise ValueError("work item run numbers must be consecutive")
        run_state = run.get("status")
        if run_state not in {"queued", "in_progress", "completed"}:
            raise ValueError(f"work item run {index} has an unsupported status")
        due_at = run.get("due_at")
        if not isinstance(due_at, str):
            raise ValueError(f"work item run {index} requires a due time")
        _parse_moment(due_at, f"work item run {index} due_at")
        if index < len(runs) and run_state != "completed":
            raise ValueError("only the current work-item run may be unfinished")
        if run_state == "completed":
            if run.get("decision") not in DECISIONS or not isinstance(run.get("summary"), str):
                raise ValueError(f"completed work-item run {index} requires a decision and summary")
            if not isinstance(run.get("results"), dict) or not run["results"]:
                raise ValueError(f"completed work-item run {index} requires frozen results")
            if run.get("decision") == "complete" and result_contract is not None:
                missing = set(result_contract["required_roles"]) - set(run["results"])
                if missing:
                    raise ValueError(
                        f"completed work-item run {index} is missing required result roles: "
                        f"{', '.join(sorted(missing))}"
                    )
        claims = run.get("claims")
        if claims is not None:
            if not isinstance(claims, list) or not all(isinstance(claim, dict) for claim in claims):
                raise ValueError(f"work item run {index} has invalid claim history")
            open_claims = [
                claim for claim in claims
                if claim.get("released_at") is None and claim.get("completed_at") is None
            ]
            if run_state == "in_progress":
                if len(open_claims) != 1 or open_claims[0].get("agent") != run.get("agent"):
                    raise ValueError(f"work item run {index} claim history does not match its owner")
            elif open_claims:
                raise ValueError(f"work item run {index} has an open claim while not in progress")
    expected_current = "completed" if state in {"completed", "stopped"} else state
    if runs[-1].get("status") != expected_current:
        raise ValueError("work item status does not match its current run")
    return path, item


def list_work_items(
    song: str | Path,
    *,
    due_only: bool = False,
    status: str | None = None,
    now: str | None = None,
) -> dict:
    """Return a compact automation-friendly view ordered by due time and priority."""
    song_path = Path(song)
    load_song_manifest(song_path)
    moment = _parse_moment(now, "work list now") if now else datetime.now(timezone.utc)
    summaries: list[dict] = []
    errors: list[dict] = []
    root = _work_root(song_path)
    if root.is_dir():
        for item_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            try:
                path, item = load_work_item(song_path, item_dir.name)
            except (FileNotFoundError, ValueError) as exc:
                errors.append({"id": item_dir.name, "error": str(exc)})
                continue
            current = item["runs"][-1]
            due_value = current.get("due_at")
            try:
                is_due = (
                    item.get("status") == "queued"
                    and isinstance(due_value, str)
                    and _parse_moment(due_value, "work run due_at") <= moment
                )
            except ValueError as exc:
                errors.append({"id": item_dir.name, "error": str(exc)})
                continue
            if due_only and not is_due:
                continue
            if status is not None and item.get("status") != status:
                continue
            summaries.append({
                "id": item["id"],
                "path": str(path.resolve().relative_to(song_path.resolve())),
                "title": item.get("title"),
                "kind": item.get("kind"),
                "priority": item.get("priority"),
                "status": item.get("status"),
                "cadence": item.get("schedule", {}).get("cadence"),
                "due_at": due_value,
                "due": is_due,
                "run_number": current.get("number"),
                "agent": current.get("agent"),
                "plan_origin": {
                    "plan_id": item["origin"].get("plan_id"),
                    "step_id": item["origin"].get("step", {}).get("id"),
                    **({
                        "required_capabilities": item["origin"]["step"][
                            "required_capabilities"
                        ],
                    } if "required_capabilities" in item["origin"].get("step", {}) else {}),
                } if isinstance(item.get("origin"), dict) else None,
                **({
                    "request_origin": {
                        "request_id": item["request_origin"].get("request_id"),
                        "request_path": item["request_origin"].get("request_path"),
                    },
                } if isinstance(item.get("request_origin"), dict) else {}),
                **({
                    "result_contract": item["result_contract"],
                } if "result_contract" in item else {}),
            })
    summaries.sort(key=lambda entry: (entry.get("due_at") or "", -(entry.get("priority") or 0), entry["id"]))
    return {
        "schema": WORK_LIST_SCHEMA,
        "generated_at": _format_moment(moment),
        "due_only": due_only,
        "status_filter": status,
        "items": summaries,
        "errors": errors,
    }


def start_work_item(song: str | Path, value: str | Path, agent: str) -> Path:
    """Claim the current queued run for one named person or agent."""
    clean_agent = agent.strip()
    if not clean_agent:
        raise ValueError("work start requires an agent name")
    path = resolve_work_item(song, value)
    with _item_lock(path):
        _, item = load_work_item(song, path)
        current = item["runs"][-1]
        if item.get("status") == "in_progress":
            if current.get("agent") == clean_agent:
                return path
            raise ValueError(f"work item is already claimed by {current.get('agent') or 'another agent'}")
        if item.get("status") != "queued" or current.get("status") != "queued":
            raise ValueError("only a queued work item can be started")
        started = utc_now()
        claims = current.setdefault("claims", [])
        if not isinstance(claims, list):
            raise ValueError("work item claim history must be a list")
        claims.append({
            "agent": clean_agent,
            "claimed_at": started,
            "released_at": None,
            "release_note": None,
            "completed_at": None,
        })
        current["status"] = "in_progress"
        current["started_at"] = started
        current["agent"] = clean_agent
        item["status"] = "in_progress"
        item["updated_at"] = started
        _atomic_json(path, item)
    return path


def release_work_item(
    song: str | Path,
    value: str | Path,
    agent: str,
    note: str,
) -> Path:
    """Return an owned run to the queue while preserving its claim attempt."""
    clean_agent = agent.strip()
    clean_note = note.strip()
    if not clean_agent:
        raise ValueError("work release requires an agent name")
    if not clean_note:
        raise ValueError("work release requires a reason")
    path = resolve_work_item(song, value)
    with _item_lock(path):
        _, item = load_work_item(song, path)
        current = item["runs"][-1]
        claims = current.setdefault("claims", [])
        if not isinstance(claims, list):
            raise ValueError("work item claim history must be a list")
        if item.get("status") == "queued" and claims:
            latest = claims[-1]
            if (
                latest.get("agent") == clean_agent
                and latest.get("released_at") is not None
                and latest.get("release_note") == clean_note
            ):
                return path
        if item.get("status") != "in_progress" or current.get("status") != "in_progress":
            raise ValueError("only an in-progress work item can be released")
        if current.get("agent") != clean_agent:
            raise ValueError(f"work item is owned by {current.get('agent') or 'another agent'}")
        if not claims:  # Compatibility with work items claimed before claim history existed.
            claims.append({
                "agent": clean_agent,
                "claimed_at": current.get("started_at"),
                "released_at": None,
                "release_note": None,
                "completed_at": None,
            })
        open_claim = next(
            (
                claim for claim in reversed(claims)
                if claim.get("agent") == clean_agent
                and claim.get("released_at") is None
                and claim.get("completed_at") is None
            ),
            None,
        )
        if open_claim is None:
            raise ValueError("work item has no open claim for this agent")
        released = utc_now()
        open_claim["released_at"] = released
        open_claim["release_note"] = clean_note
        current["status"] = "queued"
        current["agent"] = None
        current["last_released_at"] = released
        current["last_release_note"] = clean_note
        item["status"] = "queued"
        item["updated_at"] = released
        _atomic_json(path, item)
    return path


def claim_next_work_item(
    song: str | Path,
    agent: str,
    *,
    kind: str | None = None,
    now: str | None = None,
) -> dict:
    """Atomically select and claim the first due item visible to this queue."""
    clean_agent = agent.strip()
    if not clean_agent:
        raise ValueError("work claim-next requires an agent name")
    clean_kind = kind.strip() if isinstance(kind, str) else None
    if clean_kind == "":
        raise ValueError("work claim-next kind cannot be blank")
    song_path = Path(song)
    load_song_manifest(song_path)
    root = _work_root(song_path)
    if not root.is_dir():
        empty = list_work_items(song_path, due_only=True, now=now)
        return {
            "schema": WORK_CLAIM_SCHEMA,
            "generated_at": empty["generated_at"],
            "agent": clean_agent,
            "kind_filter": clean_kind,
            "claimed": None,
            "errors": empty["errors"],
        }
    with _exclusive_lock(root / ".queue.lock", "Work queue"):
        due = list_work_items(song_path, due_only=True, now=now)
        errors = list(due["errors"])
        candidates = [
            entry for entry in due["items"]
            if clean_kind is None or str(entry.get("kind", "")).casefold() == clean_kind.casefold()
        ]
        for entry in candidates:
            try:
                path = start_work_item(song_path, entry["id"], clean_agent)
            except (FileExistsError, ValueError) as exc:
                errors.append({"id": entry["id"], "error": str(exc)})
                continue
            claimed = {
                **entry,
                "path": str(path.resolve().relative_to(song_path.resolve())),
                "status": "in_progress",
                "agent": clean_agent,
            }
            return {
                "schema": WORK_CLAIM_SCHEMA,
                "generated_at": due["generated_at"],
                "agent": clean_agent,
                "kind_filter": clean_kind,
                "claimed": claimed,
                "errors": errors,
            }
        return {
            "schema": WORK_CLAIM_SCHEMA,
            "generated_at": due["generated_at"],
            "agent": clean_agent,
            "kind_filter": clean_kind,
            "claimed": None,
            "errors": errors,
        }


def _next_due(previous_due: str, cadence: str, completed: datetime) -> str:
    previous = _parse_moment(previous_due, "work run due_at")
    interval = timedelta(days=1 if cadence == "daily" else 7)
    elapsed = max(timedelta(0), completed - previous)
    steps = int(elapsed // interval) + 1
    return _format_moment(previous + steps * interval)


def finish_work_item(
    song: str | Path,
    value: str | Path,
    summary: str,
    decision: str,
    results: list[tuple[str, str | Path]],
) -> Path:
    """Freeze run results, record an outcome, and requeue recurring work."""
    clean_summary = summary.strip()
    if not clean_summary:
        raise ValueError("work finish requires a summary")
    if decision not in DECISIONS:
        raise ValueError(f"work decision must be one of: {', '.join(sorted(DECISIONS))}")
    validated_results = _validated_sources(results)
    if not validated_results:
        raise ValueError("work finish requires at least one role-labeled result")
    song_path = Path(song)
    path = resolve_work_item(song_path, value)
    with _item_lock(path):
        _, item = load_work_item(song_path, path)
        current = item["runs"][-1]
        if item.get("status") != "in_progress" or current.get("status") != "in_progress":
            raise ValueError("work item must be started before it can be finished")
        if decision == "complete" and isinstance(item.get("result_contract"), dict):
            returned_roles = {slugify(role) for role, _ in validated_results}
            missing = set(item["result_contract"]["required_roles"]) - returned_roles
            if missing:
                raise ValueError(
                    "work finish decision complete is missing required result roles: "
                    f"{', '.join(sorted(missing))}"
                )
        completed = datetime.now(timezone.utc)
        completed_at = _format_moment(completed)
        run_dir = path.parent / "runs" / f"{current['number']:04d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        result_records = {}
        for role, source in validated_results:
            role_id = slugify(role)
            digest = sha256(source)
            destination = run_dir / f"{role_id}-{source.name}"
            if destination.exists() and sha256(destination) != digest:
                destination = run_dir / f"{role_id}-{digest[:10]}-{source.name}"
            if not destination.exists():
                shutil.copy2(source, destination)
            if sha256(destination) != digest:
                raise RuntimeError(f"work result changed while it was being frozen: {source}")
            result_records[role_id] = {
                "role": role,
                "path": str(destination.relative_to(path.parent)),
                "original_name": source.name,
                "sha256": digest,
            }
        current["status"] = "completed"
        current["completed_at"] = completed_at
        current["summary"] = clean_summary
        current["decision"] = decision
        current["results"] = result_records
        claims = current.get("claims")
        if claims is None and current.get("agent"):
            claims = [{
                "agent": current["agent"],
                "claimed_at": current.get("started_at"),
                "released_at": None,
                "release_note": None,
                "completed_at": completed_at,
            }]
            current["claims"] = claims
        elif isinstance(claims, list):
            open_claim = next(
                (
                    claim for claim in reversed(claims)
                    if claim.get("agent") == current.get("agent")
                    and claim.get("released_at") is None
                    and claim.get("completed_at") is None
                ),
                None,
            )
            if open_claim is not None:
                open_claim["completed_at"] = completed_at
        cadence = item.get("schedule", {}).get("cadence", "once")
        if decision == "stop" or (cadence == "once" and decision == "complete"):
            item["status"] = "stopped" if decision == "stop" else "completed"
            item["schedule"]["next_due_at"] = None
        else:
            next_due = completed_at
            if decision == "complete" and cadence in {"daily", "weekly"}:
                next_due = _next_due(current["due_at"], cadence, completed)
            item["status"] = "queued"
            item["schedule"]["next_due_at"] = next_due
            item["runs"].append({
                "number": current["number"] + 1,
                "status": "queued",
                "queued_at": completed_at,
                "due_at": next_due,
                "agent": None,
                "claims": [],
                "results": [],
            })
        item["updated_at"] = completed_at
        _atomic_json(path, item)
    return path


def _resolved_evidence(song: Path, item_path: Path, record: object, label: str) -> Path:
    if not isinstance(record, dict):
        raise ValueError(f"{label} has an invalid evidence record")
    value = record.get("path")
    base_name = record.get("base")
    if base_name == "song":
        base = song
    elif base_name == "work-item":
        base = item_path.parent
    elif base_name is None:  # Completed run results are always work-item-relative.
        base = item_path.parent
    else:
        raise ValueError(f"{label} has an unsupported evidence base")
    candidate = base / value if isinstance(value, str) else None
    try:
        if candidate is None:
            raise ValueError
        candidate.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} has an unsafe evidence path") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"{label} evidence is missing: {candidate}")
    if record.get("sha256") != sha256(candidate):
        raise ValueError(f"{label} evidence checksum has changed")
    return candidate


def promote_work_run(
    song: str | Path,
    value: str | Path,
    hypothesis: str,
    *,
    seed: int = 1,
    run_number: int | None = None,
    beat: str | Path | None = None,
    brief: str | Path | None = None,
    sources: list[tuple[str, str | Path]] | None = None,
) -> Path:
    """Freeze one completed work run and its evidence into a new experiment."""
    clean_hypothesis = hypothesis.strip()
    if not clean_hypothesis:
        raise ValueError("work promotion requires a musical hypothesis")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("work promotion seed must be an integer")
    if run_number is not None and (
        isinstance(run_number, bool) or not isinstance(run_number, int) or run_number < 1
    ):
        raise ValueError("work promotion run must be a positive integer")
    song_path = Path(song)
    item_path = resolve_work_item(song_path, value)
    with _item_lock(item_path):
        _, item = load_work_item(song_path, item_path)
        completed_runs = [run for run in item["runs"] if run.get("status") == "completed"]
        if not completed_runs:
            raise ValueError("work promotion requires a completed run")
        if run_number is None:
            selected_run = completed_runs[-1]
        else:
            selected_run = next(
                (run for run in completed_runs if run.get("number") == run_number),
                None,
            )
            if selected_run is None:
                raise ValueError(f"work item has no completed run {run_number}")

        promotion_sources: list[tuple[str, str | Path]] = [("work request", item_path)]
        source_input_ids: list[str] = []
        for source_id, source_record in item["sources"].items():
            role = source_record.get("role", source_id)
            promoted_role = f"work source: {role}"
            evidence = _resolved_evidence(
                song_path,
                item_path,
                source_record,
                f"work source {source_id}",
            )
            promotion_sources.append((promoted_role, evidence))
            source_input_ids.append(slugify(promoted_role))

        result_input_ids: list[str] = []
        for result_id, result_record in selected_run["results"].items():
            role = result_record.get("role", result_id)
            promoted_role = f"work result: {role}"
            evidence = _resolved_evidence(
                song_path,
                item_path,
                result_record,
                f"work result {result_id}",
            )
            promotion_sources.append((promoted_role, evidence))
            result_input_ids.append(slugify(promoted_role))

        promotion_sources.extend(sources or [])
        origin = {
            "schema": "eprs.work-run-origin/v1",
            "work_item_id": item["id"],
            "run_number": selected_run["number"],
            "run_decision": selected_run["decision"],
            "work_item_snapshot_input": "work-request",
            "work_source_inputs": source_input_ids,
            "work_result_inputs": result_input_ids,
        }
        return create_experiment(
            song_path,
            beat,
            brief,
            clean_hypothesis,
            seed,
            promotion_sources,
            origin,
        )
