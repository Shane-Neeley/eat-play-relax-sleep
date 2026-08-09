"""Source-attributed research records for agent-led musical development."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse

from .system import load_song_manifest, sha256, slugify, utc_now
from .work_origin import capture_completed_work_origin, verify_completed_work_origin


RESEARCH_SPEC_SCHEMA = "eprs.research/v1"
RESEARCH_SCHEMA = "eprs.research-record/v1"
FINDING_KINDS = {"observation", "interpretation", "open-question"}
CONFIDENCE = {"direct", "supported", "tentative", "unknown"}


def _text(record: dict, key: str, *, required: bool = True, maximum: int = 8192) -> str:
    value = record.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"research requires {key}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"research {key} is limited to {maximum} characters")
    return clean


def _identifier(value: object, label: str, identifiers: set[str]) -> tuple[str, str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"research {label} requires an id")
    declared = value.strip()
    if len(declared) > 200:
        raise ValueError(f"research {label} id is limited to 200 characters")
    identifier = slugify(declared)
    if not identifier or identifier in identifiers:
        raise ValueError(f"research {label} id is empty or duplicated: {declared}")
    identifiers.add(identifier)
    return identifier, declared


def _evidence_path(value: object, song: Path, spec: Path, source_id: str) -> Path | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"research source {source_id} evidence_path must be text")
    requested = Path(value)
    candidates = [requested] if requested.is_absolute() else [song / requested, spec.parent / requested]
    source = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
    if source is None:
        raise FileNotFoundError(candidates[0])
    return source


def _sources(values: object, song: Path, spec: Path) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 100:
        raise ValueError("research sources must contain 1 to 100 items")
    identifiers: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"research source {index} must be an object")
        source_id, declared_id = _identifier(value.get("id"), "source", identifiers)
        kind = _text(value, "kind", maximum=100)
        locator = _text(value, "locator")
        if kind.casefold() in {"web", "youtube"}:
            parsed = urlparse(locator)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"research source {source_id} requires an http(s) locator")
            if kind.casefold() == "youtube":
                host = parsed.netloc.casefold().split(":", 1)[0]
                if not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")):
                    raise ValueError(f"research source {source_id} is labeled YouTube but has a non-YouTube locator")
        evidence = _evidence_path(value.get("evidence_path"), song, spec, source_id)
        if kind.casefold() in {"local", "local-file"} and evidence is None:
            raise ValueError(f"research source {source_id} requires frozen local evidence")
        records.append({
            "id": source_id,
            "declared_id": declared_id,
            "kind": kind,
            "title": _text(value, "title", maximum=1000),
            "creator": _text(value, "creator", required=False, maximum=1000),
            "locator": locator,
            "published_at": _text(value, "published_at", required=False, maximum=200),
            "accessed_at": _text(value, "accessed_at", maximum=200),
            "rights_note": _text(value, "rights_note"),
            "note": _text(value, "note", required=False),
            "evidence": evidence,
            "evidence_sha256": sha256(evidence) if evidence else None,
            "evidence_original_name": evidence.name if evidence else None,
        })
    return records


def _id_references(value: object, label: str, known: set[str], *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"research {label} must be a list of ids")
    identifiers = [slugify(item) for item in value]
    if (not allow_empty and not identifiers) or any(not item for item in identifiers):
        raise ValueError(f"research {label} must contain valid ids")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"research {label} must not contain duplicates")
    unknown = set(identifiers) - known
    if unknown:
        raise ValueError(f"research {label} references unknown ids: {', '.join(sorted(unknown))}")
    return identifiers


def _findings(values: object, source_ids: set[str]) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 200:
        raise ValueError("research findings must contain 1 to 200 items")
    identifiers: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"research finding {index} must be an object")
        finding_id, declared_id = _identifier(value.get("id"), "finding", identifiers)
        kind = value.get("kind")
        if kind not in FINDING_KINDS:
            raise ValueError(f"research finding {finding_id} kind must be observation, interpretation, or open-question")
        confidence = value.get("confidence")
        if confidence not in CONFIDENCE:
            raise ValueError(f"research finding {finding_id} confidence is invalid")
        cited = _id_references(
            value.get("source_ids", []),
            f"finding {finding_id} source_ids",
            source_ids,
            allow_empty=kind == "open-question",
        )
        records.append({
            "id": finding_id,
            "declared_id": declared_id,
            "kind": kind,
            "statement": _text(value, "statement"),
            "source_ids": cited,
            "confidence": confidence,
            "musical_consequence": _text(value, "musical_consequence"),
            "copying_boundary": _text(value, "copying_boundary"),
        })
    return records


def _experiments(values: object, finding_ids: set[str]) -> list[dict]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 100:
        raise ValueError("research experiments must be a list of at most 100 items")
    identifiers: set[str] = set()
    records = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"research experiment {index} must be an object")
        experiment_id, declared_id = _identifier(value.get("id"), "experiment", identifiers)
        records.append({
            "id": experiment_id,
            "declared_id": declared_id,
            "finding_ids": _id_references(
                value.get("finding_ids", []),
                f"experiment {experiment_id} finding_ids",
                finding_ids,
                allow_empty=False,
            ),
            "hypothesis": _text(value, "hypothesis"),
            "smallest_test": _text(value, "smallest_test"),
            "listening_question": _text(value, "listening_question"),
        })
    return records


def create_research_record(spec: str | Path, song: str | Path) -> Path:
    """Freeze attributed research without browsing or downloading sources."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid research JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict):
        raise ValueError("research spec must be a JSON object")
    if score.get("schema") != RESEARCH_SPEC_SCHEMA:
        raise ValueError(f"unsupported research schema: {score.get('schema')}")
    title = _text(score, "title", maximum=200)
    sources = _sources(score.get("sources"), song_path, spec_path)
    findings = _findings(score.get("findings"), {record["id"] for record in sources})
    experiments = _experiments(score.get("experiments"), {record["id"] for record in findings})
    work_origin = capture_completed_work_origin(score.get("work"), song_path, "research")
    recipe_sources = [{key: value for key, value in record.items() if key != "evidence"} for record in sources]
    recipe = {
        "schema": RESEARCH_SPEC_SCHEMA,
        "title": title,
        "question": _text(score, "question"),
        "musical_purpose": _text(score, "musical_purpose"),
        "researched_at": _text(score, "researched_at", maximum=200),
        "work_origin": work_origin,
        "sources": recipe_sources,
        "findings": findings,
        "experiments": experiments,
    }
    research_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("research title must contain a letter or number")
    destination = song_path / "notes" / "research" / f"{title_slug}-{research_id[:10]}"
    manifest_path = destination / "research.json"
    if destination.exists():
        _, existing = verify_research_record(song_path, manifest_path)
        if existing.get("research_id") == research_id:
            return manifest_path
        raise FileExistsError(f"research destination has different provenance: {destination}")
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete research record exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        source_records = {}
        for source, recipe_source in zip(sources, recipe_sources):
            record = dict(recipe_source)
            evidence = source["evidence"]
            if evidence:
                if sha256(evidence) != source["evidence_sha256"]:
                    raise RuntimeError(f"research evidence changed during intake: {evidence}")
                evidence_dir = temporary / "evidence"
                evidence_dir.mkdir(exist_ok=True)
                copy = evidence_dir / f"{source['id']}-{evidence.name}"
                shutil.copy2(evidence, copy)
                if sha256(copy) != source["evidence_sha256"]:
                    raise RuntimeError(f"research evidence changed while being frozen: {evidence}")
                record["evidence_path"] = str(copy.relative_to(temporary))
                record["evidence_sha256"] = sha256(copy)
            else:
                record["evidence_path"] = None
            source_records[source["id"]] = record
        manifest = {
            "schema": RESEARCH_SCHEMA,
            "research_id": research_id,
            "created_at": utc_now(),
            "recipe": recipe,
            "sources": source_records,
            "authority": {
                "statement": "This is attributed research evidence, not authority to browse, copy a reference, process media, or publish anything.",
            },
        }
        (temporary / "research.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest_path


def resolve_research_record(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = (song_path / "notes" / "research").resolve()
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
        if candidate.is_dir():
            candidate = candidate / "research.json"
    else:
        candidate = (root / str(value) / "research.json").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("research record must be inside the song notes/research directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_research_record(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    path = resolve_research_record(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid research record: {path}: {exc.msg}") from exc
    if not isinstance(record, dict):
        raise ValueError("research record must be a JSON object")
    if record.get("schema") != RESEARCH_SCHEMA:
        raise ValueError("unsupported research record schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != RESEARCH_SPEC_SCHEMA:
        raise ValueError("research recipe is invalid")
    for key in ("title", "question", "musical_purpose", "researched_at"):
        _text(recipe, key, maximum=200 if key in {"title", "researched_at"} else 8192)
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("research_id") != expected_id or not path.parent.name.endswith(expected_id[:10]):
        raise ValueError("research id does not match its normalized recipe")
    recipe_sources = recipe.get("sources")
    sources = record.get("sources")
    if not isinstance(recipe_sources, list) or not isinstance(sources, dict):
        raise ValueError("research sources are invalid")
    if not 1 <= len(recipe_sources) <= 100:
        raise ValueError("research recipe sources are invalid")
    expected_source_ids: set[str] = set()
    for source in recipe_sources:
        if not isinstance(source, dict):
            raise ValueError("research recipe source must be an object")
        source_id = source.get("id")
        if (
            not isinstance(source_id, str)
            or not source_id
            or slugify(source_id) != source_id
            or source_id in expected_source_ids
        ):
            raise ValueError("research recipe source ids are invalid")
        expected_source_ids.add(source_id)
        for key in ("kind", "title", "locator", "accessed_at", "rights_note"):
            _text(source, key)
        kind = source["kind"].casefold()
        if kind in {"web", "youtube"}:
            parsed = urlparse(source["locator"])
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"research source {source_id} requires an http(s) locator")
            if kind == "youtube":
                host = parsed.netloc.casefold().split(":", 1)[0]
                if not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")):
                    raise ValueError(f"research source {source_id} is labeled YouTube but has a non-YouTube locator")
        digest = source.get("evidence_sha256")
        if digest is not None and (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"research source {source_id} has an invalid evidence checksum")
        if kind in {"local", "local-file"} and digest is None:
            raise ValueError(f"research source {source_id} requires frozen local evidence")
    if set(sources) != expected_source_ids:
        raise ValueError("research source ids are inconsistent")
    for recipe_source in recipe_sources:
        source_id = recipe_source["id"]
        source = sources[source_id]
        if not isinstance(source, dict):
            raise ValueError(f"research source record is invalid: {source_id}")
        for key, value in recipe_source.items():
            if source.get(key) != value:
                raise ValueError(f"research source metadata changed: {source_id}")
        evidence_value = source.get("evidence_path")
        expected_digest = recipe_source.get("evidence_sha256")
        if expected_digest is None:
            if evidence_value is not None:
                raise ValueError(f"research source has unexpected evidence: {source_id}")
            continue
        evidence = (path.parent / evidence_value).resolve() if isinstance(evidence_value, str) else None
        try:
            if evidence is None:
                raise ValueError
            evidence.relative_to(path.parent.resolve())
        except ValueError as exc:
            raise ValueError(f"research source has unsafe evidence: {source_id}") from exc
        if not evidence.is_file() or sha256(evidence) != expected_digest:
            raise ValueError(f"research source evidence is missing or changed: {source_id}")
    _findings(recipe.get("findings"), expected_source_ids)
    finding_ids = {finding["id"] for finding in recipe["findings"]}
    _experiments(recipe.get("experiments"), finding_ids)
    origin = recipe.get("work_origin")
    if origin is not None:
        verify_completed_work_origin(song_path, origin, "research")
    return path, record


def load_research_record(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    return verify_research_record(song, value)
