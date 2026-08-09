"""Source-bound lyric variants with explicit, non-destructive review history."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import shutil

from .system import load_song_manifest, sha256, slugify, utc_now
from .work_origin import capture_completed_work_origin, verify_completed_work_origin


LYRICS_SPEC_SCHEMA = "eprs.lyrics/v1"
LYRICS_SCHEMA = "eprs.lyric-development/v1"
DECISIONS = {"keep", "alternate", "stop"}


@contextmanager
def _review_lock(path: Path):
    lock = path.parent / ".lyrics-review.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(
            f"Lyrics review is locked by another process: {lock}. "
            "Inspect the record before removing a stale lock left by a confirmed crash."
        ) from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} created_at={utc_now()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _text(record: dict, key: str, *, required: bool = True, maximum: int = 8192) -> str:
    value = record.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"lyrics require {key}")
    clean = value.strip()
    if len(clean) > maximum:
        raise ValueError(f"lyrics {key} is limited to {maximum} characters")
    return clean


def _text_list(
    record: dict,
    key: str,
    *,
    required: bool = False,
    maximum_items: int = 100,
    maximum_chars: int = 8192,
) -> list[str]:
    values = record.get(key, [])
    if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
        raise ValueError(f"lyrics {key} must be a list of non-empty strings")
    if required and not values:
        raise ValueError(f"lyrics {key} requires at least one item")
    if len(values) > maximum_items or any(len(value.strip()) > maximum_chars for value in values):
        raise ValueError(f"lyrics {key} exceeds its size limit")
    return [value.strip() for value in values]


def _identifier(value: object, label: str, identifiers: set[str]) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError(f"lyrics {label} requires an id of at most 200 characters")
    identifier = slugify(value.strip())
    if not identifier or identifier in identifiers:
        raise ValueError(f"lyrics {label} id is empty or duplicated: {value}")
    identifiers.add(identifier)
    return identifier


def _source_path(value: object, song: Path, spec: Path, source_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"lyrics source {source_id} requires path")
    requested = Path(value)
    candidates = [requested] if requested.is_absolute() else [song / requested, spec.parent / requested]
    source = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
    if source is None:
        raise FileNotFoundError(candidates[0])
    return source


def _sources(values: object, song: Path, spec: Path) -> list[dict]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 100:
        raise ValueError("lyrics sources must be a list of at most 100 items")
    identifiers: set[str] = set()
    records = []
    raw_root = (song / "recordings" / "raw").resolve()
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"lyrics source {index} must be an object")
        source_id = _identifier(value.get("id"), "source", identifiers)
        source = _source_path(value.get("path"), song, spec, source_id)
        try:
            relative = source.relative_to(raw_root)
        except ValueError:
            relative = None
        records.append({
            "id": source_id,
            "role": _text(value, "role", maximum=1000),
            "note": _text(value, "note", required=False),
            "rights_note": _text(value, "rights_note"),
            "source": source,
            "sha256": sha256(source),
            "original_name": source.name,
            "storage": "song-reference" if relative is not None else "lyric-record-copy",
            "song_path": str(source.relative_to(song.resolve())) if relative is not None else None,
        })
    return records


def _source_ids(value: object, variant_id: str, known: set[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"lyrics variant {variant_id} source_ids must be a list")
    ids = [slugify(item.strip()) for item in value]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"lyrics variant {variant_id} source_ids are invalid or duplicated")
    unknown = set(ids) - known
    if unknown:
        raise ValueError(
            f"lyrics variant {variant_id} references unknown sources: {', '.join(sorted(unknown))}"
        )
    return ids


def _variants(values: object, source_ids: set[str]) -> list[dict]:
    if not isinstance(values, list) or not values or len(values) > 100:
        raise ValueError("lyrics variants must contain 1 to 100 items")
    identifiers: set[str] = set()
    variants = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            raise ValueError(f"lyrics variant {index} must be an object")
        variant_id = _identifier(value.get("id"), "variant", identifiers)
        variants.append({
            "id": variant_id,
            "role": _text(value, "role", maximum=1000),
            "text": _text(value, "text", maximum=50_000),
            "intent": _text(value, "intent"),
            "source_ids": _source_ids(value.get("source_ids", []), variant_id, source_ids),
            "singability_note": _text(value, "singability_note"),
            "unresolved": _text_list(
                value, "unresolved", maximum_items=50, maximum_chars=2048
            ),
        })
    return variants


def create_lyric_development(spec: str | Path, song: str | Path) -> Path:
    """Freeze lyric sources and alternatives without selecting a winner."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec).resolve()
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lyrics JSON: {spec_path}: {exc.msg}") from exc
    if not isinstance(score, dict):
        raise ValueError("lyrics spec must be a JSON object")
    if score.get("schema") != LYRICS_SPEC_SCHEMA:
        raise ValueError(f"unsupported lyrics schema: {score.get('schema')}")
    sources = _sources(score.get("sources"), song_path, spec_path)
    work_origin = capture_completed_work_origin(score.get("work"), song_path, "lyrics")
    if not sources and work_origin is None:
        raise ValueError("lyrics require at least one source or a completed work origin")
    recipe_sources = [
        {key: value for key, value in source.items() if key != "source"}
        for source in sources
    ]
    recipe = {
        "schema": LYRICS_SPEC_SCHEMA,
        "title": _text(score, "title", maximum=200),
        "intent": _text(score, "intent"),
        "language": _text(score, "language", maximum=200),
        "voice_note": _text(score, "voice_note"),
        "preserve": _text_list(score, "preserve", required=True),
        "avoid": _text_list(score, "avoid", required=True),
        "work_origin": work_origin,
        "sources": recipe_sources,
        "variants": _variants(score.get("variants"), {source["id"] for source in sources}),
    }
    development_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    slug = slugify(recipe["title"])
    if not slug:
        raise ValueError("lyrics title must contain a letter or number")
    destination = song_path / "notes" / "lyrics" / f"{slug}-{development_id[:10]}"
    manifest_path = destination / "lyrics.json"
    if destination.exists():
        _, existing = verify_lyric_development(song_path, manifest_path)
        if existing.get("development_id") == development_id:
            return manifest_path
        raise FileExistsError(f"lyrics destination has different provenance: {destination}")
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete lyrics record exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        source_records = {}
        for source, recipe_source in zip(sources, recipe_sources):
            record = dict(recipe_source)
            if source["storage"] == "song-reference":
                record["base"] = "song"
                record["path"] = source["song_path"]
            else:
                evidence = temporary / "sources"
                evidence.mkdir(exist_ok=True)
                copy = evidence / f"{source['id']}-{source['original_name']}"
                shutil.copy2(source["source"], copy)
                if sha256(copy) != source["sha256"]:
                    raise RuntimeError(f"lyrics source changed while being frozen: {source['source']}")
                record["base"] = "lyrics"
                record["path"] = str(copy.relative_to(temporary))
            source_records[source["id"]] = record
        manifest = {
            "schema": LYRICS_SCHEMA,
            "development_id": development_id,
            "created_at": utc_now(),
            "recipe": recipe,
            "sources": source_records,
            "reviews": {
                variant["id"]: {"decision": "not-reviewed", "listening_notes": []}
                for variant in recipe["variants"]
            },
            "review_state": "pending",
            "authority": {
                "statement": "This record preserves private lyric alternatives. It does not grant rights, select a final lyric, replace a singer's phrasing, or authorize sharing or publication.",
            },
        }
        (temporary / "lyrics.json").write_text(json.dumps(manifest, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest_path


def resolve_lyric_development(song: str | Path, value: str | Path) -> Path:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    root = (song_path / "notes" / "lyrics").resolve()
    requested = Path(value)
    if requested.is_absolute() or "/" in str(value):
        candidate = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
        if candidate.is_dir():
            candidate = candidate / "lyrics.json"
    else:
        candidate = (root / str(value) / "lyrics.json").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("lyrics record must be inside the song notes/lyrics directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def _resolved_source(song: Path, path: Path, record: object, source_id: str) -> Path:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise ValueError(f"lyrics source record is invalid: {source_id}")
    base = song if record.get("base") == "song" else path.parent if record.get("base") == "lyrics" else None
    if base is None:
        raise ValueError(f"lyrics source has an unsupported base: {source_id}")
    source = (base / record["path"]).resolve()
    try:
        source.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"lyrics source has an unsafe path: {source_id}") from exc
    if not source.is_file() or record.get("sha256") != sha256(source):
        raise ValueError(f"lyrics source is missing or changed: {source_id}")
    return source


def verify_lyric_development(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    song_path = Path(song).resolve()
    path = resolve_lyric_development(song_path, value)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid lyrics record: {path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != LYRICS_SCHEMA:
        raise ValueError("unsupported lyrics record schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != LYRICS_SPEC_SCHEMA:
        raise ValueError("lyrics recipe is invalid")
    expected_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("development_id") != expected_id or not path.parent.name.endswith(expected_id[:10]):
        raise ValueError("lyrics id does not match its normalized recipe")
    for key in ("title", "intent", "language", "voice_note"):
        _text(recipe, key, maximum=200 if key in {"title", "language"} else 8192)
    _text_list(recipe, "preserve", required=True)
    _text_list(recipe, "avoid", required=True)
    recipe_sources = recipe.get("sources")
    sources = record.get("sources")
    if not isinstance(recipe_sources, list) or not isinstance(sources, dict):
        raise ValueError("lyrics sources are invalid")
    source_ids = {source.get("id") for source in recipe_sources if isinstance(source, dict)}
    if len(source_ids) != len(recipe_sources) or None in source_ids or set(sources) != source_ids:
        raise ValueError("lyrics source ids are inconsistent")
    for recipe_source in recipe_sources:
        source_id = recipe_source["id"]
        source = sources[source_id]
        if not isinstance(source, dict) or any(source.get(key) != value for key, value in recipe_source.items()):
            raise ValueError(f"lyrics source metadata changed: {source_id}")
        _resolved_source(song_path, path, source, source_id)
    variants = _variants(recipe.get("variants"), source_ids)
    if variants != recipe.get("variants"):
        raise ValueError("lyrics variants are not normalized")
    if not sources and recipe.get("work_origin") is None:
        raise ValueError("lyrics require sources or a work origin")
    origin = recipe.get("work_origin")
    if origin is not None:
        verify_completed_work_origin(song_path, origin, "lyrics")
    reviews = record.get("reviews")
    variant_ids = {variant["id"] for variant in variants}
    if not isinstance(reviews, dict) or set(reviews) != variant_ids:
        raise ValueError("lyrics reviews are inconsistent")
    for variant_id, review in reviews.items():
        if not isinstance(review, dict) or review.get("decision") not in {*DECISIONS, "not-reviewed"}:
            raise ValueError(f"lyrics review is invalid: {variant_id}")
        notes = review.get("listening_notes")
        if not isinstance(notes, list) or not all(
            isinstance(note, dict)
            and note.get("decision") in DECISIONS
            and isinstance(note.get("note"), str)
            and bool(note["note"].strip())
            for note in notes
        ):
            raise ValueError(f"lyrics listening notes are invalid: {variant_id}")
        if notes and notes[-1]["decision"] != review["decision"]:
            raise ValueError(f"lyrics review decision does not match its latest note: {variant_id}")
        if not notes and review["decision"] != "not-reviewed":
            raise ValueError(f"lyrics review decision has no note: {variant_id}")
    expected_state = "complete" if all(review["decision"] != "not-reviewed" for review in reviews.values()) else "pending"
    if record.get("review_state") != expected_state:
        raise ValueError("lyrics review state is inconsistent")
    return path, record


def load_lyric_development(song: str | Path, value: str | Path) -> tuple[Path, dict]:
    return verify_lyric_development(song, value)


def review_lyric_variant(
    song: str | Path,
    value: str | Path,
    variant: str,
    decision: str,
    listening_note: str,
) -> Path:
    if decision not in DECISIONS:
        raise ValueError("lyrics decision must be keep, alternate, or stop")
    clean_note = listening_note.strip()
    if not clean_note:
        raise ValueError("lyrics review requires a listening or reading note")
    variant_id = slugify(variant)
    path = resolve_lyric_development(song, value)
    with _review_lock(path):
        path, record = verify_lyric_development(song, path)
        if variant_id not in record["reviews"]:
            raise ValueError(f"lyrics record has no variant: {variant_id}")
        review = record["reviews"][variant_id]
        if review["listening_notes"]:
            latest = review["listening_notes"][-1]
            if latest["decision"] == decision and latest["note"] == clean_note:
                return path
        review["decision"] = decision
        review["listening_notes"].append({
            "recorded_at": utc_now(),
            "decision": decision,
            "note": clean_note,
        })
        record["review_state"] = (
            "complete"
            if all(value["decision"] != "not-reviewed" for value in record["reviews"].values())
            else "pending"
        )
        temporary = path.with_name(f".{path.name}.partial")
        if temporary.exists():
            raise FileExistsError(f"incomplete lyrics review update exists: {temporary}")
        temporary.write_text(json.dumps(record, indent=2) + "\n")
        os.replace(temporary, path)
        verify_lyric_development(song, path)
    return path
