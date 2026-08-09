"""Request-bound, non-executing production plans for people and agents."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil

from .request import load_production_request
from .system import load_song_manifest, sha256, slugify, utc_now


PLAN_SPEC_SCHEMA_V1 = "eprs.production-plan/v1"
PLAN_SPEC_SCHEMA_V2 = "eprs.production-plan/v2"
PLAN_SCHEMA_V1 = "eprs.production-plan-record/v1"
PLAN_SCHEMA_V2 = "eprs.production-plan-record/v2"
# Compatibility aliases for callers that construct the original contract.
PLAN_SPEC_SCHEMA = PLAN_SPEC_SCHEMA_V1
PLAN_SCHEMA = PLAN_SCHEMA_V1
PLAN_RECORD_BY_SPEC = {
    PLAN_SPEC_SCHEMA_V1: PLAN_SCHEMA_V1,
    PLAN_SPEC_SCHEMA_V2: PLAN_SCHEMA_V2,
}
CAPABILITY_ID = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
GATES = {
    "user-direction",
    "performer-consent",
    "source-rights",
    "listening-decision",
    "technical-verification",
    "upload-authorization",
    "publication-authorization",
}


def _text(
    record: dict,
    key: str,
    *,
    required: bool = True,
    maximum: int = 8192,
) -> str:
    value = record.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"production plan requires {key}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"production plan {key} is limited to {maximum} characters")
    return clean


def _text_list(
    record: dict,
    key: str,
    *,
    required: bool = False,
    maximum_items: int = 100,
    maximum_chars: int = 8192,
) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"production plan {key} must be a list of non-empty strings")
    if required and not value:
        raise ValueError(f"production plan {key} requires at least one item")
    if len(value) > maximum_items or any(len(item.strip()) > maximum_chars for item in value):
        raise ValueError(f"production plan {key} exceeds its size limit")
    return [item.strip() for item in value]


def _ids(value: object, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"production plan {label} must be a list of ids")
    if not allow_empty and not value:
        raise ValueError(f"production plan {label} requires at least one id")
    identifiers = [slugify(item.strip()) for item in value]
    if any(not item or len(item) > 200 for item in identifiers):
        raise ValueError(f"production plan {label} contains an invalid id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"production plan {label} must not contain duplicate ids")
    return identifiers


def _request_evidence(song: Path, value: object) -> tuple[dict, dict]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("production plan requires request")
    path, request = load_production_request(song, value.strip())
    return {
        "id": request["id"],
        "path": str(path.resolve().relative_to(song.resolve())),
        "sha256": sha256(path),
        "title": request.get("title"),
    }, request


def _capability_ids(value: object, step_id: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(
            f"production plan step {step_id} required_capabilities must be a list"
        )
    if len(value) > 64:
        raise ValueError(
            f"production plan step {step_id} required_capabilities exceeds 64 items"
        )
    capabilities: list[str] = []
    for capability in value:
        if (
            not isinstance(capability, str)
            or not CAPABILITY_ID.fullmatch(capability)
            or len(capability) > 200
        ):
            raise ValueError(
                f"production plan step {step_id} required_capabilities must contain "
                "portable capability slugs"
            )
        if capability in capabilities:
            raise ValueError(
                f"production plan step {step_id} required_capabilities must not contain duplicates"
            )
        capabilities.append(capability)
    return capabilities


def _result_role_ids(value: object, step_id: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(
            f"production plan step {step_id} required_result_roles must be a non-empty list"
        )
    if len(value) > 64:
        raise ValueError(
            f"production plan step {step_id} required_result_roles exceeds 64 items"
        )
    roles: list[str] = []
    for role in value:
        if (
            not isinstance(role, str)
            or not CAPABILITY_ID.fullmatch(role)
            or len(role) > 200
        ):
            raise ValueError(
                f"production plan step {step_id} required_result_roles must contain "
                "portable result-role slugs"
            )
        if role in roles:
            raise ValueError(
                f"production plan step {step_id} required_result_roles must not contain duplicates"
            )
        roles.append(role)
    return roles


def _steps(values: object, provided_ids: set[str], schema: str) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 100:
        raise ValueError("production plan steps must contain 1 to 100 items")
    identifiers: set[str] = set()
    steps = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"production plan step {index} must be an object")
        declared_id = _text(value, "id", maximum=200)
        step_id = slugify(declared_id)
        if not step_id or step_id in identifiers:
            raise ValueError(f"production plan step id is empty or duplicated: {declared_id}")
        identifiers.add(step_id)
        uses = _ids(value.get("uses", []), f"step {step_id} uses")
        unknown_inputs = set(uses) - provided_ids
        if unknown_inputs:
            raise ValueError(
                f"production plan step {step_id} uses unknown request inputs: "
                f"{', '.join(sorted(unknown_inputs))}"
            )
        gates = value.get("gates", [])
        if not isinstance(gates, list) or not all(isinstance(gate, str) for gate in gates):
            raise ValueError(f"production plan step {step_id} gates must be a list")
        if len(gates) != len(set(gates)) or set(gates) - GATES:
            raise ValueError(f"production plan step {step_id} has duplicate or unsupported gates")
        if schema == PLAN_SPEC_SCHEMA_V1:
            for field in ("required_capabilities", "required_result_roles"):
                if field in value:
                    raise ValueError(
                        f"production plan step {step_id} {field} requires "
                        f"{PLAN_SPEC_SCHEMA_V2}"
                    )
        step = {
            "id": step_id,
            "kind": _text(value, "kind", maximum=200),
            "intent": _text(value, "intent"),
            "depends_on": _ids(value.get("depends_on", []), f"step {step_id} depends_on"),
            "uses": uses,
            "smallest_action": _text(value, "smallest_action"),
            "outputs": _text_list(
                value, "outputs", required=True, maximum_items=20, maximum_chars=1000
            ),
            "done_when": _text_list(
                value, "done_when", required=True, maximum_items=20, maximum_chars=2048
            ),
            "listening_question": _text(value, "listening_question", required=False),
            "gates": gates,
        }
        if schema == PLAN_SPEC_SCHEMA_V2:
            if "required_capabilities" not in value:
                raise ValueError(
                    f"production plan step {step_id} requires required_capabilities"
                )
            step["required_capabilities"] = _capability_ids(
                value.get("required_capabilities"), step_id
            )
            if "required_result_roles" in value:
                step["required_result_roles"] = _result_role_ids(
                    value.get("required_result_roles"), step_id
                )
        steps.append(step)
    known = {step["id"] for step in steps}
    for step in steps:
        unknown = set(step["depends_on"]) - known
        if unknown:
            raise ValueError(
                f"production plan step {step['id']} depends on unknown steps: "
                f"{', '.join(sorted(unknown))}"
            )
        if step["id"] in step["depends_on"]:
            raise ValueError(f"production plan step {step['id']} cannot depend on itself")

    # Validate the dependency graph without imposing declaration order.
    pending = {step["id"]: set(step["depends_on"]) for step in steps}
    resolved: set[str] = set()
    while pending:
        ready = sorted(step_id for step_id, dependencies in pending.items() if dependencies <= resolved)
        if not ready:
            raise ValueError("production plan step dependencies contain a cycle")
        for step_id in ready:
            resolved.add(step_id)
            del pending[step_id]
    return steps


def _supersedes(song: Path, value: object, request_id: str) -> dict | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("production plan supersedes must be an id or path")
    path, record = load_production_plan(song, value)
    if record["recipe"]["request"]["id"] != request_id:
        raise ValueError("production plan can supersede only a plan for the same request")
    return {
        "plan_id": record["plan_id"],
        "path": str(path.resolve().relative_to(song.resolve())),
        "sha256": sha256(path),
    }


def create_production_plan(spec: str | Path, song: str | Path) -> Path:
    """Freeze an inspectable plan without executing or authorizing any step."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid production plan JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict):
        raise ValueError("production plan spec must be a JSON object")
    recipe_schema = score.get("schema")
    if recipe_schema not in PLAN_RECORD_BY_SPEC:
        raise ValueError(f"unsupported production plan schema: {score.get('schema')}")
    request_evidence, request = _request_evidence(song_path, score.get("request"))
    steps = _steps(score.get("steps"), set(request.get("provided", {})), recipe_schema)
    recipe = {
        "schema": recipe_schema,
        "title": _text(score, "title", maximum=200),
        "request": request_evidence,
        "supersedes": _supersedes(song_path, score.get("supersedes"), request["id"]),
        "north_star": _text(score, "north_star"),
        "assumptions": _text_list(score, "assumptions"),
        "open_questions": _text_list(score, "open_questions"),
        "steps": steps,
    }
    plan_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    slug = slugify(recipe["title"])
    if not slug:
        raise ValueError("production plan title must contain a letter or number")
    destination = song_path / "notes" / "plans" / f"{slug}-{plan_id[:10]}"
    manifest_path = destination / "plan.json"
    if destination.exists():
        _, existing = verify_production_plan(song_path, manifest_path)
        if existing.get("plan_id") == plan_id:
            return manifest_path
        raise FileExistsError(f"production plan destination has different provenance: {destination}")
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete production plan exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        manifest = {
            "schema": PLAN_RECORD_BY_SPEC[recipe_schema],
            "plan_id": plan_id,
            "created_at": utc_now(),
            "recipe": recipe,
            "entry_steps": [step["id"] for step in steps if not step["depends_on"]],
            "authority": {
                "statement": "This plan describes possible local work. It does not execute a step, satisfy a gate, or authorize browsing, recording, processing, sending, uploading, or publishing.",
            },
        }
        (temporary / "plan.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest_path


def resolve_production_plan(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = (song_path / "notes" / "plans").resolve()
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
        if candidate.is_dir():
            candidate = candidate / "plan.json"
    else:
        candidate = (root / str(value) / "plan.json").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("production plan must be inside the song notes/plans directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_production_plan(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    path = resolve_production_plan(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid production plan record: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") not in PLAN_RECORD_BY_SPEC.values():
        raise ValueError("unsupported production plan record schema")
    recipe = record.get("recipe")
    recipe_schema = recipe.get("schema") if isinstance(recipe, dict) else None
    if (
        recipe_schema not in PLAN_RECORD_BY_SPEC
        or PLAN_RECORD_BY_SPEC[recipe_schema] != record.get("schema")
    ):
        raise ValueError("production plan recipe is invalid")
    request_evidence = recipe.get("request")
    if not isinstance(request_evidence, dict):
        raise ValueError("production plan request evidence is invalid")
    request_path, request = load_production_request(song_path, request_evidence.get("path", ""))
    if (
        request_evidence.get("id") != request.get("id")
        or request_evidence.get("sha256") != sha256(request_path)
        or request_evidence.get("title") != request.get("title")
    ):
        raise ValueError("production plan request evidence is missing or changed")
    steps = _steps(recipe.get("steps"), set(request.get("provided", {})), recipe_schema)
    if steps != recipe.get("steps"):
        raise ValueError("production plan steps are not normalized")
    for key in ("title", "north_star"):
        _text(recipe, key, maximum=200 if key == "title" else 8192)
    _text_list(recipe, "assumptions")
    _text_list(recipe, "open_questions")
    supersedes = recipe.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, dict):
            raise ValueError("production plan supersedes evidence is invalid")
        previous_path, previous = load_production_plan(song_path, supersedes.get("path", ""))
        if (
            previous.get("plan_id") != supersedes.get("plan_id")
            or sha256(previous_path) != supersedes.get("sha256")
            or previous["recipe"]["request"]["id"] != request["id"]
        ):
            raise ValueError("production plan superseded evidence is missing or changed")
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("plan_id") != expected_id or not path.parent.name.endswith(expected_id[:10]):
        raise ValueError("production plan id does not match its normalized recipe")
    entry = [step["id"] for step in steps if not step["depends_on"]]
    if record.get("entry_steps") != entry:
        raise ValueError("production plan entry steps are inconsistent")
    return path, record


def load_production_plan(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    return verify_production_plan(song, value)
