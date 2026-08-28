"""Validate portable frontier-research scouting packets.

EPRS does not browse or decide whether a scientific claim is true. An external
adapter can freeze a dated set of research leads, then this module checks that
each lead carries provenance, uncertainty, a falsifiable capability test, and
one bounded creative consequence.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .system import slugify


FRONTIER_SCHEMA = "eprs.frontier-watch/v1"
CLAIM_STAGES = {
    "lead",
    "reported",
    "preprint",
    "peer-reviewed",
    "replicated",
    "independently-validated",
}


def _text(value: object, label: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"frontier {label} is required")
    result = value.strip()
    if len(result) > maximum:
        raise ValueError(f"frontier {label} is limited to {maximum} characters")
    return result


def _optional_text(value: object, label: str, *, maximum: int = 4096) -> str:
    if value in (None, ""):
        return ""
    return _text(value, label, maximum=maximum)


def _list(value: object, label: str, *, maximum: int = 20, required: bool = True) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or len(value) > maximum:
        requirement = "at least one" if required else "at most"
        raise ValueError(f"frontier {label} must contain {requirement} item(s)")
    return [_text(item, f"{label} item", maximum=1000) for item in value]


def _ids(value: object, label: str, known: set[str], *, required: bool = True) -> list[str]:
    values = _list(value, label, required=required)
    identifiers = [slugify(item) for item in values]
    if any(not item for item in identifiers):
        raise ValueError(f"frontier {label} contains an invalid id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"frontier {label} contains duplicate ids")
    unknown = set(identifiers) - known
    if unknown:
        raise ValueError(f"frontier {label} references unknown ids: {', '.join(sorted(unknown))}")
    return identifiers


def _sources(value: object) -> tuple[list[dict], set[str]]:
    if not isinstance(value, list) or not value or len(value) > 100:
        raise ValueError("frontier sources must contain 1 to 100 items")
    identifiers: set[str] = set()
    records = []
    for index, source in enumerate(value, start=1):
        if not isinstance(source, dict):
            raise ValueError(f"frontier source {index} must be an object")
        declared_id = _text(source.get("id"), f"source {index} id", maximum=200)
        source_id = slugify(declared_id)
        if not source_id or source_id in identifiers:
            raise ValueError(f"frontier source id is empty or duplicated: {declared_id}")
        identifiers.add(source_id)
        kind = _text(source.get("kind"), f"source {source_id} kind", maximum=100)
        locator = _text(source.get("locator"), f"source {source_id} locator")
        parsed = urlparse(locator)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"frontier source {source_id} requires an http(s) locator")
        records.append({
            "id": source_id,
            "declared_id": declared_id,
            "kind": kind,
            "title": _text(source.get("title"), f"source {source_id} title", maximum=1000),
            "locator": locator,
            "accessed_at": _text(source.get("accessed_at"), f"source {source_id} accessed_at", maximum=200),
            "rights_note": _text(source.get("rights_note"), f"source {source_id} rights_note"),
            "note": _optional_text(source.get("note"), f"source {source_id} note"),
        })
    return records, identifiers


def _test(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"frontier {label} must be an object")
    return {
        "task": _text(value.get("task"), f"{label} task"),
        "oracle": _text(value.get("oracle"), f"{label} oracle"),
        "constraints": _list(value.get("constraints"), f"{label} constraints"),
        "artifact": _text(value.get("artifact"), f"{label} artifact"),
    }


def _optional_block(value: object, label: str, fields: tuple[str, ...]) -> dict[str, str]:
    """Normalize optional v1 collaboration metadata without breaking old packets."""
    if value in (None, ""):
        return {field: "" for field in fields}
    if not isinstance(value, dict):
        raise ValueError(f"frontier {label} must be an object")
    return {
        field: _text(value.get(field), f"{label} {field}")
        for field in fields
    }


def _empirical_boundary(value: object, label: str) -> dict[str, str]:
    fields = ("mode", "what_compute_can_test", "what_requires_reality")
    result = _optional_block(value, label, fields)
    if not result["mode"]:
        result["mode"] = "unspecified"
    if result["mode"] not in {"compute-closed", "data-constrained", "mixed", "unspecified"}:
        raise ValueError(
            f"frontier {label} mode must be compute-closed, data-constrained, mixed, or unspecified"
        )
    return result


def _candidate(value: object, index: int, source_ids: set[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"frontier candidate {index} must be an object")
    declared_id = _text(value.get("id"), f"candidate {index} id", maximum=200)
    candidate_id = slugify(declared_id)
    if not candidate_id:
        raise ValueError(f"frontier candidate {index} id is invalid")
    status = value.get("status")
    if not isinstance(status, dict):
        raise ValueError(f"frontier candidate {candidate_id} status must be an object")
    stage = status.get("stage")
    if stage not in CLAIM_STAGES:
        raise ValueError(f"frontier candidate {candidate_id} status stage is invalid")
    return {
        "id": candidate_id,
        "declared_id": declared_id,
        "domain": _text(value.get("domain"), f"candidate {candidate_id} domain", maximum=200),
        "title": _text(value.get("title"), f"candidate {candidate_id} title", maximum=1000),
        "question": _text(value.get("question"), f"candidate {candidate_id} question"),
        "claim": _text(value.get("claim"), f"candidate {candidate_id} claim"),
        "human_direction": _optional_block(
            value.get("human_direction"),
            f"candidate {candidate_id} human_direction",
            ("thought_experiment", "cross_domain_bridge", "steering_question", "why_this_might_be_wrong"),
        ),
        "formal_pressure": _optional_block(
            value.get("formal_pressure"),
            f"candidate {candidate_id} formal_pressure",
            ("translation", "consequence_space", "counterexample_search", "oracle_scope"),
        ),
        "empirical_boundary": _empirical_boundary(
            value.get("empirical_boundary"),
            f"candidate {candidate_id} empirical_boundary",
        ),
        "source_ids": _ids(value.get("source_ids"), f"candidate {candidate_id} source_ids", source_ids),
        "status": {
            "stage": stage,
            "confidence": _text(status.get("confidence"), f"candidate {candidate_id} confidence", maximum=1000),
            "independent_check": _optional_text(
                status.get("independent_check"),
                f"candidate {candidate_id} independent_check",
            ),
        },
        "mechanism": _text(value.get("mechanism"), f"candidate {candidate_id} mechanism"),
        "bottleneck": _text(value.get("bottleneck"), f"candidate {candidate_id} bottleneck"),
        "unknowns": _list(value.get("unknowns"), f"candidate {candidate_id} unknowns"),
        "capability_test": _test(value.get("capability_test"), f"candidate {candidate_id} capability_test"),
        "creative_test": _test(value.get("creative_test"), f"candidate {candidate_id} creative_test"),
        "next_action": _text(value.get("next_action"), f"candidate {candidate_id} next_action"),
    }


def validate_frontier_watch(spec: str | Path | dict) -> tuple[Path | None, dict]:
    """Validate and normalize one external, dated frontier-watch packet."""
    path: Path | None = None
    if isinstance(spec, (str, Path)):
        path = Path(spec).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid frontier JSON: {path}: {exc.msg}") from exc
    else:
        payload = spec
    if not isinstance(payload, dict):
        raise ValueError("frontier watch must be a JSON object")
    if payload.get("schema") != FRONTIER_SCHEMA:
        raise ValueError(f"unsupported frontier schema: {payload.get('schema')}")
    sources, source_ids = _sources(payload.get("sources"))
    candidates_value = payload.get("candidates")
    if not isinstance(candidates_value, list) or not candidates_value or len(candidates_value) > 20:
        raise ValueError("frontier candidates must contain 1 to 20 items")
    candidates = []
    candidate_ids: set[str] = set()
    for index, value in enumerate(candidates_value, start=1):
        candidate = _candidate(value, index, source_ids)
        candidate_id = _text(candidate.get("id"), f"candidate {index} id", maximum=200)
        if candidate_id in candidate_ids:
            raise ValueError(f"frontier candidate id is duplicated: {candidate_id}")
        candidate_ids.add(candidate_id)
        candidates.append(candidate)
    selection = payload.get("selection")
    if not isinstance(selection, dict):
        raise ValueError("frontier selection must be an object")
    privacy = payload.get("privacy")
    if not isinstance(privacy, dict):
        raise ValueError("frontier privacy must be an object")
    normalized = {
        "schema": FRONTIER_SCHEMA,
        "date": _text(payload.get("date"), "date", maximum=40),
        "question": _text(payload.get("question"), "question"),
        "sources": sources,
        "candidates": candidates,
        "selection": {
            "mode": _text(selection.get("mode"), "selection mode", maximum=100),
            "method": _text(selection.get("method"), "selection method", maximum=1000),
            "selected_candidate_ids": _ids(
                selection.get("selected_candidate_ids"),
                "selection selected_candidate_ids",
                candidate_ids,
            ),
            "rule": _text(selection.get("rule"), "selection rule"),
        },
        "privacy": {
            "source_policy": _text(privacy.get("source_policy"), "privacy source_policy"),
            "public_metadata": _text(privacy.get("public_metadata"), "privacy public_metadata"),
        },
    }
    return path, normalized


def load_frontier_watch(spec: str | Path) -> tuple[Path, dict]:
    """Load and verify one frontier-watch file."""
    path, record = validate_frontier_watch(spec)
    assert path is not None
    return path, record
