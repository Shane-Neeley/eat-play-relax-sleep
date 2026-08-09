"""Performance-aware take comparison without automatic ranking."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

from .rhythm import (
    ALGORITHM as ONSET_ALGORITHM,
    MAX_ANALYSIS_SECONDS,
    _decode_region,
    _detect_events,
    _frame_features,
    _percentile,
    _timing_observation,
)
from .system import load_song_manifest, probe, sha256, slugify, utc_now


COMPARE_SCHEMA = "eprs.performance-compare/v1"
REPORT_SCHEMA = "eprs.performance-comparison/v1"
ALGORITHM = "eprs-performance-evidence/v1"
REVIEW_DECISIONS = {"keep", "alternate", "stop"}


def _number(record: dict, key: str, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"comparison take {key} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"comparison take {key} must be finite")
    return result


def _source(song: Path, value: object, take_id: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"comparison take {take_id} requires a path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError(f"comparison take {take_id} path must be relative to the song")
    source = (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"comparison take {take_id} path escapes the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def _phrase_shape(levels: list[float]) -> dict:
    if not levels:
        return {"quarter_levels_dbfs": [], "relative_profile_db": [], "shape_hint": "unavailable"}
    quarters = []
    for index in range(4):
        start = round(index * len(levels) / 4)
        end = round((index + 1) * len(levels) / 4)
        section = levels[start:end] or levels[-1:]
        quarters.append(statistics.median(section))
    center = statistics.median(quarters)
    relative = [value - center for value in quarters]
    span = max(relative) - min(relative)
    if span < 3:
        hint = "broadly even envelope"
    elif relative[-1] - relative[0] >= 4:
        hint = "grows toward the ending"
    elif relative[0] - relative[-1] >= 4:
        hint = "settles toward the ending"
    elif max(relative[1:3]) >= max(relative[0], relative[-1]) + 3:
        hint = "swells through the middle"
    else:
        hint = "changing or multi-part envelope"
    return {
        "quarter_levels_dbfs": [round(value, 2) for value in quarters],
        "relative_profile_db": [round(value, 2) for value in relative],
        "shape_hint": hint,
    }


def _take(song: Path, record: object, identifiers: set[str], sensitivity: float, min_gap_ms: float) -> dict:
    if not isinstance(record, dict):
        raise ValueError("each comparison take must be an object")
    declared_id = record.get("id")
    if not isinstance(declared_id, str) or not declared_id.strip():
        raise ValueError("each comparison take requires an id")
    take_id = slugify(declared_id)
    if not take_id or take_id in identifiers:
        raise ValueError(f"comparison take id is empty or duplicated: {declared_id}")
    identifiers.add(take_id)
    role = record.get("role", declared_id)
    note = record.get("player_note", "")
    if not isinstance(role, str) or not role.strip() or not isinstance(note, str):
        raise ValueError(f"comparison take {take_id} role and player_note must be text")
    source = _source(song, record.get("path"), take_id)
    media_probe = probe(source)
    stream = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    if stream is None:
        raise ValueError(f"comparison take {take_id} has no audio stream")
    source_duration = float(media_probe.get("format", {}).get("duration") or 0)
    if source_duration <= 0:
        raise ValueError(f"comparison take {take_id} duration is unavailable")
    start = _number(record, "start_seconds", 0)
    duration_value = record.get("duration_seconds")
    duration = source_duration - start if duration_value is None else _number(record, "duration_seconds")
    if start < 0 or duration <= 0 or start >= source_duration or start + duration > source_duration + 0.01:
        raise ValueError(f"comparison take {take_id} listening region exceeds its source")
    if duration > MAX_ANALYSIS_SECONDS:
        raise ValueError(f"comparison take {take_id} exceeds the {MAX_ANALYSIS_SECONDS}-second analysis limit")
    digest = sha256(source)
    samples = _decode_region(source, start, duration)
    levels, _, _ = _frame_features(samples)
    onset_note = None
    try:
        events, thresholds = _detect_events(samples, start, sensitivity, min_gap_ms)
    except ValueError as exc:
        events = []
        thresholds = None
        onset_note = str(exc)
    timing = _timing_observation(events)
    timbre_counts = {
        hint: sum(1 for event in events if event["timbre_hint"] == hint)
        for hint in ("lower/rounder", "brighter/noisier", "mixed/uncertain")
    }
    return {
        "id": take_id,
        "declared_id": declared_id.strip(),
        "role": role.strip(),
        "player_note": note.strip(),
        "source": {
            "path": str(source.relative_to(song.resolve())),
            "sha256": digest,
            "probe": media_probe,
        },
        "region": {"start_seconds": start, "duration_seconds": duration},
        "level_evidence": {
            "quiet_frame_level_dbfs": round(_percentile(levels, 0.2), 2),
            "median_frame_level_dbfs": round(_percentile(levels, 0.5), 2),
            "strong_frame_level_dbfs": round(_percentile(levels, 0.95), 2),
            "frame_level_spread_db": round(_percentile(levels, 0.95) - _percentile(levels, 0.2), 2),
        },
        "phrase_shape": _phrase_shape(levels),
        "attack_evidence": {
            "event_count": len(events),
            "events": events,
            "timing": timing,
            "timbre_hint_counts": timbre_counts,
            "thresholds": thresholds,
            "note": onset_note,
        },
    }


def _contrasts(takes: list[dict]) -> list[dict]:
    result = []
    for left, right in itertools.combinations(takes, 2):
        left_spacing = left["attack_evidence"]["timing"]["median_interval_seconds"]
        right_spacing = right["attack_evidence"]["timing"]["median_interval_seconds"]
        result.append({
            "takes": [left["id"], right["id"]],
            "right_minus_left": {
                "duration_seconds": round(right["region"]["duration_seconds"] - left["region"]["duration_seconds"], 6),
                "median_frame_level_db": round(
                    right["level_evidence"]["median_frame_level_dbfs"]
                    - left["level_evidence"]["median_frame_level_dbfs"], 2,
                ),
                "attack_count": right["attack_evidence"]["event_count"] - left["attack_evidence"]["event_count"],
                "median_attack_spacing_ms": None if left_spacing is None or right_spacing is None else round((right_spacing - left_spacing) * 1000, 2),
            },
            "phrase_shape_hints": [left["phrase_shape"]["shape_hint"], right["phrase_shape"]["shape_hint"]],
        })
    return result


def compare_performances(spec: str | Path, song: str | Path) -> tuple[Path, dict]:
    """Create a non-ranking evidence report and counterbalanced listening worksheet."""
    song_path = Path(song)
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid performance comparison JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != COMPARE_SCHEMA:
        raise ValueError(f"unsupported performance comparison schema: {score.get('schema')}")
    title = score.get("title")
    intent = score.get("intent")
    questions = score.get("listening_questions")
    if not isinstance(title, str) or not title.strip() or not isinstance(intent, str) or not intent.strip():
        raise ValueError("performance comparison requires title and player-facing intent")
    if not isinstance(questions, list) or not questions or not all(isinstance(item, str) and item.strip() for item in questions):
        raise ValueError("performance comparison requires non-empty listening_questions")
    analysis = score.get("analysis", {})
    if not isinstance(analysis, dict):
        raise ValueError("performance comparison analysis must be an object")
    sensitivity = _number(analysis, "sensitivity", 0.5)
    min_gap_ms = _number(analysis, "min_gap_ms", 150)
    if not 0 <= sensitivity <= 1 or not 30 <= min_gap_ms <= 1000:
        raise ValueError("performance comparison sensitivity or min_gap_ms is out of range")
    take_values = score.get("takes")
    if not isinstance(take_values, list) or not 2 <= len(take_values) <= 12:
        raise ValueError("performance comparison requires between 2 and 12 takes")
    identifiers: set[str] = set()
    takes = [_take(song_path, record, identifiers, sensitivity, min_gap_ms) for record in take_values]
    recipe = {
        "schema": COMPARE_SCHEMA,
        "title": title.strip(),
        "intent": intent.strip(),
        "listening_questions": [item.strip() for item in questions],
        "analysis": {"algorithm": ALGORITHM, "onset_algorithm": ONSET_ALGORITHM, "sensitivity": sensitivity, "min_gap_ms": min_gap_ms},
        "takes": [{
            "id": take["id"], "role": take["role"], "player_note": take["player_note"],
            "path": take["source"]["path"], "sha256": take["source"]["sha256"],
            **take["region"],
        } for take in takes],
    }
    comparison_id = hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("performance comparison title must contain a letter or number")
    destination_dir = song_path / "notes" / "comparisons" / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{comparison_id[:10]}-{title_slug}.json"
    if destination.exists():
        existing = json.loads(destination.read_text())
        if existing.get("comparison_id") == comparison_id:
            return destination, existing
        raise FileExistsError(f"performance comparison destination has different provenance: {destination}")
    take_ids = [take["id"] for take in takes]
    report = {
        "schema": REPORT_SCHEMA,
        "comparison_id": comparison_id,
        "created_at": utc_now(),
        "title": title.strip(),
        "intent": intent.strip(),
        "listening_questions": recipe["listening_questions"],
        "recipe": recipe,
        "takes": takes,
        "contrasts": _contrasts(takes),
        "audition": {
            "orders": [take_ids, list(reversed(take_ids))],
            "instruction": "Alternate which take starts, compare at a sensible matched listening level, answer each listening question, and preserve more than one take when the differences are musically useful.",
        },
        "interpretation_limits": {
            "automatic_winner": False,
            "waveform_alignment": False,
            "timing_error_assumed": False,
            "level_is_quality": False,
            "phrase_shape_is_inference": True,
            "instruction": "Measurements locate differences; listening notes decide what serves the song.",
        },
        "reviews": {take_id: {"decision": "not recorded", "listening_notes": []} for take_id in take_ids},
        "review_state": "pending",
    }
    temporary = destination.with_name(f".{destination.name}.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete performance comparison exists: {temporary}")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.rename(destination)
    return destination, report


def review_comparison(song: str | Path, comparison: str | Path, take_id: str, decision: str, note: str) -> Path:
    """Record a take-specific listening decision without changing any audio."""
    song_path = Path(song)
    load_song_manifest(song_path)
    requested = Path(comparison)
    path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        path.relative_to((song_path / "notes" / "comparisons").resolve())
    except ValueError as exc:
        raise ValueError("performance comparison must be inside notes/comparisons") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    report = json.loads(path.read_text())
    if report.get("schema") != REPORT_SCHEMA:
        raise ValueError("unsupported performance comparison report")
    for take in report.get("takes", []):
        source = take.get("source", {}) if isinstance(take, dict) else {}
        source_path = song_path / source.get("path", "")
        try:
            source_path.resolve().relative_to(song_path.resolve())
        except ValueError as exc:
            raise ValueError("performance comparison has an unsafe source path") from exc
        if not source_path.is_file() or sha256(source_path) != source.get("sha256"):
            raise ValueError("performance comparison source is missing or changed")
    clean_id = slugify(take_id)
    reviews = report.get("reviews")
    if not isinstance(reviews, dict) or clean_id not in reviews:
        raise ValueError(f"unknown comparison take: {take_id}")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("comparison decision must be keep, alternate, or stop")
    listening_note = note.strip()
    if not listening_note:
        raise ValueError("comparison review requires a listening note")
    review = reviews[clean_id]
    notes = review.get("listening_notes")
    if not isinstance(notes, list):
        raise ValueError("comparison listening_notes must be a list")
    if not any(item.get("note") == listening_note and item.get("decision") == decision for item in notes if isinstance(item, dict)):
        notes.append({"reviewed_at": utc_now(), "decision": decision, "note": listening_note})
    review["decision"] = decision
    report["review_state"] = "complete" if (
        len(reviews) == len(report.get("takes", []))
        and all(isinstance(item, dict) and item.get("decision") in REVIEW_DECISIONS for item in reviews.values())
    ) else "pending"
    temporary = path.with_name(f".{path.name}.review.partial")
    if temporary.exists():
        raise FileExistsError(f"incomplete performance comparison review exists: {temporary}")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)
    return path
