"""Authored drummer-facing interpretations of performed rhythm observations."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import wave

from .audio import SAMPLE_RATE, render
from .beat import Beat, Track, dumps, load, validate
from .rhythm import verify_rhythm_observation
from .system import load_song_manifest, sha256, slugify, utc_now


GROOVE_SCHEMA = "eprs.groove/v1"
GROOVE_DEVELOPMENT_SCHEMA = "eprs.groove-development/v1"
REVIEW_DECISIONS = {"keep", "change", "stop"}
DISPOSITIONS = {"pattern", "pickup", "omit"}
KINDS = {"kick", "snare", "clap", "hat", "shaker", "stick", "tom", "perc", "ride", "crash"}
RESOLUTIONS = {4, 8, 12, 16, 24, 32}
MAX_VOICES = 24
MAX_EVENTS = 256
MAX_ALTERNATIVES = 12
PLAYER_FIELDS = (
    "meter_and_tempo",
    "subdivision_and_feel",
    "backbeat_or_answer",
    "bass_drum_or_low_voice",
    "timekeeping_voice",
    "dynamics",
    "orchestration",
    "phrase_shape",
    "pocket",
    "listening_question",
)


@contextmanager
def _review_lock(path: Path):
    lock = path.parent / ".groove-review.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f"groove review is locked by another process: {lock}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} created_at={utc_now()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def _text(record: dict, key: str, label: str, maximum: int = 4096) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"groove {label} requires {key}")
    clean = value.strip()
    if len(clean.encode("utf-8")) > maximum:
        raise ValueError(f"groove {label} {key} exceeds {maximum} UTF-8 bytes")
    return clean


def _text_list(value: object, label: str, *, maximum: int = 32) -> list[str]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise ValueError(f"groove {label} must contain 1 to {maximum} text items")
    result = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"groove {label} item {index} must be non-empty text")
        clean = item.strip()
        if len(clean.encode("utf-8")) > 2048:
            raise ValueError(f"groove {label} item {index} is too long")
        result.append(clean)
    return result


def _number(
    record: dict,
    key: str,
    label: str,
    minimum: float,
    maximum: float,
    *,
    default: float | None = None,
) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"groove {label} {key} must be a number")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"groove {label} {key} must be between {minimum:g} and {maximum:g}")
    return number


def _integer(record: dict, key: str, label: str, minimum: int, maximum: int) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"groove {label} {key} must be an integer from {minimum} to {maximum}")
    return value


def _resolve_spec(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _player_brief(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("groove player_brief must be an object")
    result = {key: _text(value, key, "player_brief") for key in PLAYER_FIELDS}
    result["preserve"] = _text_list(value.get("preserve"), "player_brief preserve")
    result["avoid"] = _text_list(value.get("avoid"), "player_brief avoid")
    return result


def _pattern(value: object, expected_steps: int, voice_id: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"groove voice {voice_id} requires pattern")
    compact = "".join(character for character in value if not character.isspace() and character != "|")
    invalid = sorted(set(compact) - set(".xXgo-"))
    if invalid:
        raise ValueError(f"groove voice {voice_id} pattern has invalid symbols: {''.join(invalid)}")
    steps = list(compact.replace("-", "."))
    if len(steps) != expected_steps:
        raise ValueError(
            f"groove voice {voice_id} pattern must contain exactly {expected_steps} steps"
        )
    return steps


def _prototype(value: object) -> tuple[dict, Beat, dict[str, dict]]:
    if not isinstance(value, dict):
        raise ValueError("groove prototype must be an object")
    tempo = _number(value, "tempo", "prototype", 20, 400)
    meter = value.get("meter")
    if (
        not isinstance(meter, dict)
        or isinstance(meter.get("numerator"), bool)
        or not isinstance(meter.get("numerator"), int)
        or not 1 <= meter["numerator"] <= 32
        or meter.get("denominator") not in {1, 2, 4, 8, 16}
    ):
        raise ValueError("groove prototype meter requires a positive numerator and power-of-two denominator")
    resolution = value.get("resolution")
    if resolution not in RESOLUTIONS:
        raise ValueError("groove prototype resolution is unsupported")
    bars = _integer(value, "bars", "prototype", 1, 64)
    swing = _number(value, "swing", "prototype", 0.5, 0.75)
    seed = value.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not -(2**31) <= seed < 2**31:
        raise ValueError("groove prototype seed must be a 32-bit integer")
    steps_per_bar = round(resolution * meter["numerator"] / meter["denominator"])
    total_steps = steps_per_bar * bars
    voices_value = value.get("voices")
    if not isinstance(voices_value, list) or not voices_value or len(voices_value) > MAX_VOICES:
        raise ValueError(f"groove prototype requires 1 to {MAX_VOICES} voices")
    voices = []
    voice_map: dict[str, dict] = {}
    tracks = []
    for index, voice_value in enumerate(voices_value, start=1):
        if not isinstance(voice_value, dict):
            raise ValueError(f"groove voice {index} must be an object")
        declared_id = _text(voice_value, "id", f"voice {index}", 256)
        voice_id = slugify(declared_id)
        if not voice_id or voice_id in voice_map:
            raise ValueError(f"groove voice id is invalid or duplicated: {declared_id}")
        kind = _text(voice_value, "kind", f"voice {voice_id}", 64).lower()
        if kind not in KINDS:
            raise ValueError(f"groove voice {voice_id} kind is unsupported: {kind}")
        steps = _pattern(voice_value.get("pattern"), total_steps, voice_id)
        gain = _number(voice_value, "gain", f"voice {voice_id}", 0, 1, default=0.5)
        pan = _number(voice_value, "pan", f"voice {voice_id}", -1, 1, default=0)
        offset_ms = _number(
            voice_value, "offset_ms", f"voice {voice_id}", -250, 250, default=0
        )
        humanize_ms = _number(
            voice_value, "humanize_ms", f"voice {voice_id}", 0, 100, default=0
        )
        record = {
            "id": voice_id,
            "declared_id": declared_id,
            "kind": kind,
            "role": _text(voice_value, "role", f"voice {voice_id}", 1024),
            "player_instruction": _text(
                voice_value, "player_instruction", f"voice {voice_id}"
            ),
            "pattern": "".join(steps),
            "gain": gain,
            "pan": pan,
            "offset_ms": offset_ms,
            "humanize_ms": humanize_ms,
        }
        voice_map[voice_id] = {**record, "steps": steps}
        voices.append(record)
        tracks.append(Track(
            name=voice_id,
            kind=kind,
            steps=steps,
            options={
                "gain": f"{gain:g}",
                "pan": f"{pan:g}",
                "offset_ms": f"{offset_ms:g}",
                "humanize_ms": f"{humanize_ms:g}",
            },
        ))
    beat = Beat(
        title="Groove prototype",
        tempo=tempo,
        meter=(meter["numerator"], meter["denominator"]),
        resolution=resolution,
        bars=bars,
        swing=swing,
        seed=seed,
        tracks=tracks,
    )
    validate(beat)
    anchor_event_id = _integer(value, "anchor_event_id", "prototype", 1, MAX_EVENTS)
    normalized = {
        "tempo": tempo,
        "meter": {"numerator": meter["numerator"], "denominator": meter["denominator"]},
        "resolution": resolution,
        "bars": bars,
        "swing": swing,
        "seed": seed,
        "anchor_event_id": anchor_event_id,
        "voices": voices,
    }
    return normalized, beat, voice_map


def _grid_time(beat: Beat, absolute_step: int, offset_ms: float) -> float:
    value = absolute_step * beat.seconds_per_step
    if absolute_step % 2 == 1:
        value += (beat.swing - 0.5) * 2 * beat.seconds_per_step
    return value + offset_ms / 1000


def _interpret_events(
    value: object,
    events: list[dict],
    prototype: dict,
    beat: Beat,
    voices: dict[str, dict],
) -> list[dict]:
    if not isinstance(value, list) or len(value) != len(events) or len(value) > MAX_EVENTS:
        raise ValueError("groove event_interpretations must cover every observed event exactly once")
    event_map = {event["id"]: event for event in events}
    normalized = []
    seen_events: set[int] = set()
    used_positions: set[tuple[str, int]] = set()
    steps_per_bar = beat.steps_per_bar
    anchor_id = prototype["anchor_event_id"]
    preliminary = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"groove event interpretation {index} must be an object")
        event_id = _integer(item, "event_id", f"event interpretation {index}", 1, MAX_EVENTS)
        if event_id not in event_map or event_id in seen_events:
            raise ValueError(f"groove event interpretation is missing, unknown, or duplicated: {event_id}")
        seen_events.add(event_id)
        disposition = _text(item, "disposition", f"event {event_id}", 32).lower()
        if disposition not in DISPOSITIONS:
            raise ValueError(f"groove event {event_id} disposition is unsupported")
        record = {
            "event_id": event_id,
            "disposition": disposition,
            "count": _text(item, "count", f"event {event_id}", 128),
            "interpretation": _text(item, "interpretation", f"event {event_id}"),
            "timing_intent": _text(item, "timing_intent", f"event {event_id}"),
            "performed_event_time_seconds": event_map[event_id]["time_seconds"],
        }
        if disposition == "pattern":
            declared_voice = _text(item, "voice", f"event {event_id}", 256)
            voice_id = slugify(declared_voice)
            if voice_id not in voices:
                raise ValueError(f"groove event {event_id} references unknown voice: {declared_voice}")
            bar = _integer(item, "bar", f"event {event_id}", 1, beat.bars)
            step = _integer(item, "step", f"event {event_id}", 0, steps_per_bar - 1)
            absolute_step = (bar - 1) * steps_per_bar + step
            position = (voice_id, absolute_step)
            if position in used_positions:
                raise ValueError(f"groove events cannot share voice/grid position: {voice_id} bar {bar} step {step}")
            used_positions.add(position)
            if voices[voice_id]["steps"][absolute_step] == ".":
                raise ValueError(f"groove event {event_id} maps to a rest in voice {voice_id}")
            record.update({
                "voice": voice_id,
                "bar": bar,
                "step": step,
                "absolute_step": absolute_step,
            })
        preliminary.append(record)
    if seen_events != set(event_map):
        raise ValueError("groove event_interpretations do not cover the observation")
    anchor = next((item for item in preliminary if item["event_id"] == anchor_id), None)
    if anchor is None or anchor["disposition"] != "pattern":
        raise ValueError("groove prototype anchor_event_id must map to a pattern hit")
    anchor_grid = _grid_time(
        beat, anchor["absolute_step"], voices[anchor["voice"]]["offset_ms"]
    )
    anchor_performed = event_map[anchor_id]["time_seconds"]
    for record in preliminary:
        performed_relative = record["performed_event_time_seconds"] - anchor_performed
        record["performed_relative_to_anchor_ms"] = round(performed_relative * 1000, 3)
        if record["disposition"] == "pattern":
            nominal_grid = _grid_time(
                beat,
                record["absolute_step"],
                voices[record["voice"]]["offset_ms"],
            )
            grid_relative = nominal_grid - anchor_grid
            record["nominal_grid_relative_to_anchor_ms"] = round(grid_relative * 1000, 3)
            record["performed_minus_nominal_grid_ms"] = round(
                (performed_relative - grid_relative) * 1000, 3
            )
        normalized.append(record)
    return normalized


def _alternatives(value: object) -> list[dict]:
    if not isinstance(value, list) or not value or len(value) > MAX_ALTERNATIVES:
        raise ValueError(f"groove alternatives must contain 1 to {MAX_ALTERNATIVES} records")
    result = []
    names: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"groove alternative {index} must be an object")
        name = _text(item, "name", f"alternative {index}", 512)
        name_id = slugify(name)
        if not name_id or name_id in names:
            raise ValueError(f"groove alternative name is invalid or duplicated: {name}")
        names.add(name_id)
        result.append({
            "id": name_id,
            "name": name,
            "description": _text(item, "description", f"alternative {name_id}"),
        })
    return result


def _beat_text(title: str, observation_path: str, brief: dict, beat: Beat) -> str:
    beat.title = title
    comments = [
        f"# Player idea: {brief['subdivision_and_feel']}",
        f"# Pocket: {brief['pocket']}",
        f"# Phrase: {brief['phrase_shape']}",
        f"# Source rhythm observation: {observation_path}",
        "# This is one explicit grid interpretation, not a transcription or correction of the performance.",
    ]
    for track in beat.tracks:
        instruction = next(
            voice["player_instruction"]
            for voice in brief["voices"]
            if voice["id"] == track.name
        )
        comments.append(f"# {track.name}: {instruction}")
    return "\n".join(comments) + "\n" + dumps(beat)


def _resolve_groove(song: Path, value: str | Path) -> Path:
    requested = Path(value)
    if requested.is_absolute():
        candidate = requested.resolve()
    elif requested.exists():
        candidate = requested.resolve()
    elif "/" in str(value):
        candidate = (song / requested).resolve()
    else:
        matches = sorted((song / "notes" / "grooves").rglob(str(value)))
        if len(matches) != 1:
            raise FileNotFoundError(f"groove must resolve uniquely inside notes/grooves: {value}")
        candidate = matches[0].resolve()
    if candidate.is_dir():
        candidate = candidate / "groove.json"
    try:
        candidate.relative_to((song / "notes" / "grooves").resolve())
    except ValueError as exc:
        raise ValueError("groove must be inside the song notes/grooves directory") from exc
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def verify_groove_development(
    song: str | Path,
    groove: str | Path,
    *,
    require_approval: bool = False,
) -> tuple[Path, dict]:
    """Verify a groove interpretation, source observation, prototype, and review gate."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    path = _resolve_groove(song_path, groove)
    try:
        record = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid groove development JSON: {path}: {exc.msg}") from exc
    if record.get("schema") != GROOVE_DEVELOPMENT_SCHEMA:
        raise ValueError("unsupported groove development schema")
    recipe = record.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != GROOVE_SCHEMA:
        raise ValueError("groove development recipe is invalid")
    groove_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if record.get("groove_id") != groove_id or path.parent.name != groove_id[:10]:
        raise ValueError("groove development id does not match its recipe or directory")
    observation = recipe.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("groove observation binding is invalid")
    observation_path, observation_report = verify_rhythm_observation(
        song_path, observation.get("path", ""), verify_checksum=True
    )
    if (
        observation.get("sha256") != sha256(observation_path)
        or observation.get("analysis_id") != observation_report.get("analysis_id")
        or observation.get("result_id") != observation_report.get("result_id")
        or observation.get("schema") != observation_report.get("schema")
        or observation.get("source") != {
            "path": observation_report["source"]["path"],
            "sha256": observation_report["source"]["sha256"],
        }
    ):
        raise ValueError("groove observation binding is missing or changed")
    try:
        title = _text(recipe, "title", "persisted recipe", 1024)
        intent = _text(recipe, "intent", "persisted recipe")
        normalized_brief = _player_brief(recipe.get("player_brief"))
        normalized_prototype, expected_beat, expected_voices = _prototype(
            recipe.get("prototype")
        )
        expected_beat.title = title
        normalized_events = _interpret_events(
            recipe.get("event_interpretations"),
            observation_report["events"],
            normalized_prototype,
            expected_beat,
            expected_voices,
        )
        normalized_alternatives = _alternatives(recipe.get("alternatives"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"groove persisted recipe is invalid: {exc}") from exc
    if (
        record.get("title") != title
        or record.get("intent") != intent
        or recipe.get("player_brief") != normalized_brief
        or recipe.get("prototype") != normalized_prototype
        or recipe.get("event_interpretations") != normalized_events
        or recipe.get("alternatives") != normalized_alternatives
    ):
        raise ValueError("groove persisted recipe is inconsistent or not normalized")
    outputs = record.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("groove outputs are invalid")
    beat_record = outputs.get("beatscript")
    audio_record = outputs.get("audio_prototype")
    if not isinstance(beat_record, dict) or not isinstance(audio_record, dict):
        raise ValueError("groove output records are invalid")
    for label, output in (("BeatScript", beat_record), ("audio prototype", audio_record)):
        value = output.get("path")
        if not isinstance(value, str) or Path(value).is_absolute():
            raise ValueError(f"groove {label} path is invalid")
        output_path = (song_path / value).resolve()
        try:
            output_path.relative_to(path.parent)
        except ValueError as exc:
            raise ValueError(f"groove {label} escapes its development directory") from exc
        if not output_path.is_file() or output.get("sha256") != sha256(output_path):
            raise ValueError(f"groove {label} is missing or changed")
    if (
        beat_record.get("path") != str((path.parent / "prototype.beat").relative_to(song_path))
        or audio_record.get("path") != str((path.parent / "prototype.wav").relative_to(song_path))
        or audio_record.get("format") != {
            "sample_rate": SAMPLE_RATE,
            "channels": 2,
            "sample_width_bits": 16,
            "synthesized": True,
        }
    ):
        raise ValueError("groove output declarations are inconsistent")
    beat_path = song_path / beat_record["path"]
    beat = load(beat_path)
    prototype = recipe.get("prototype")
    if not isinstance(prototype, dict) or (
        beat.tempo != prototype.get("tempo")
        or beat.meter != (
            prototype.get("meter", {}).get("numerator"),
            prototype.get("meter", {}).get("denominator"),
        )
        or beat.resolution != prototype.get("resolution")
        or beat.bars != prototype.get("bars")
        or beat.swing != prototype.get("swing")
        or beat.seed != prototype.get("seed")
    ):
        raise ValueError("groove BeatScript no longer matches its prototype recipe")
    expected_text = _beat_text(
        title,
        observation["path"],
        {**normalized_brief, "voices": normalized_prototype["voices"]},
        expected_beat,
    )
    if beat_path.read_text() != expected_text:
        raise ValueError("groove BeatScript content is inconsistent with its recipe")
    with wave.open(str(song_path / audio_record["path"]), "rb") as wav:
        if (
            wav.getframerate() != SAMPLE_RATE
            or wav.getnchannels() != 2
            or wav.getsampwidth() != 2
            or wav.getnframes() <= 0
        ):
            raise ValueError("groove audio prototype format is invalid")
        actual_duration = wav.getnframes() / wav.getframerate()
        if abs(actual_duration - (beat.duration + 1.4)) > 1 / SAMPLE_RATE:
            raise ValueError("groove audio prototype duration is invalid")
    interpretation = record.get("interpretation_limits")
    if not isinstance(interpretation, dict) or any(
        interpretation.get(key) is not expected
        for key, expected in {
            "source_audio_modified": False,
            "automatic_role_assignment": False,
            "automatic_quantization": False,
            "prototype_grid_quantized": True,
            "prototype_is_one_authored_interpretation": True,
            "performed_grid_offsets_preserved_as_evidence": True,
        }.items()
    ):
        raise ValueError("groove interpretation limits are invalid")
    expected_warnings = [
        "The WAV is a synthesized BeatScript audition of one explicit interpretation; it is not a transcription, replacement, or processed copy of the performed beat idea.",
        "Per-event performed-minus-grid offsets are evidence only; the prototype applies only declared voice-wide offset, swing, and seeded humanize controls.",
        "The lightweight prototype renderer may lower an overloaded synthetic sum for safe integer output; do not treat its level as a mix decision.",
    ]
    if any(voice["humanize_ms"] for voice in normalized_prototype["voices"]):
        expected_warnings.append(
            "Seeded prototype humanize is an authored audition control, not a reconstruction of the performer's microtiming."
        )
    if record.get("warnings") != expected_warnings:
        raise ValueError("groove warnings are invalid")
    authority = record.get("authority")
    if not isinstance(authority, dict) or any(
        authority.get(key) is not False
        for key in (
            "creative_approval_inferred", "final_promotion",
            "upload_authorized", "publication_authorized",
        )
    ):
        raise ValueError("groove authority record is invalid")
    review = record.get("review")
    notes = review.get("listening_notes") if isinstance(review, dict) else None
    if not isinstance(review, dict) or not isinstance(notes, list):
        raise ValueError("groove review record is invalid")
    decision = review.get("decision")
    if decision not in {"not recorded by renderer", *REVIEW_DECISIONS}:
        raise ValueError("groove review decision is invalid")
    for index, note in enumerate(notes, start=1):
        if (
            not isinstance(note, dict)
            or note.get("decision") not in REVIEW_DECISIONS
            or not isinstance(note.get("note"), str)
            or not note["note"].strip()
            or not isinstance(note.get("reviewed_at"), str)
            or not note["reviewed_at"]
        ):
            raise ValueError(f"groove listening note {index} is invalid")
    if require_approval:
        has_keep = any(
            isinstance(note, dict)
            and note.get("decision") == "keep"
            and isinstance(note.get("note"), str)
            and bool(note["note"].strip())
            for note in notes
        )
        if review.get("decision") != "keep" or not has_keep:
            raise ValueError("groove requires a complete-listen keep decision")
    return path, record


def create_groove_development(spec: str | Path, song: str | Path) -> tuple[Path, dict]:
    """Create one explicit, auditionable grid interpretation of a rhythm observation."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = _resolve_spec(spec)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid groove JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != GROOVE_SCHEMA:
        raise ValueError(f"unsupported groove schema: {score.get('schema')}")
    title = _text(score, "title", "spec", 1024)
    intent = _text(score, "intent", "spec")
    observation_path, observation = verify_rhythm_observation(
        song_path, score.get("observation", ""), verify_checksum=True
    )
    if not isinstance(observation.get("result_id"), str):
        raise ValueError(
            "groove development requires a result-bound rhythm observation; re-observe legacy v1 evidence"
        )
    brief = _player_brief(score.get("player_brief"))
    prototype, beat, voices = _prototype(score.get("prototype"))
    beat.title = title
    assignments = _interpret_events(
        score.get("event_interpretations"),
        observation["events"],
        prototype,
        beat,
        voices,
    )
    alternatives = _alternatives(score.get("alternatives"))
    observation_record = {
        "path": str(observation_path.relative_to(song_path)),
        "sha256": sha256(observation_path),
        "analysis_id": observation["analysis_id"],
        "result_id": observation["result_id"],
        "schema": observation["schema"],
        "source": {
            "path": observation["source"]["path"],
            "sha256": observation["source"]["sha256"],
        },
    }
    recipe = {
        "schema": GROOVE_SCHEMA,
        "title": title,
        "intent": intent,
        "observation": observation_record,
        "player_brief": brief,
        "prototype": prototype,
        "event_interpretations": assignments,
        "alternatives": alternatives,
    }
    groove_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    title_slug = slugify(title)
    if not title_slug:
        raise ValueError("groove title must contain at least one letter or number")
    parent = song_path / "notes" / "grooves" / title_slug
    destination = parent / groove_id[:10]
    manifest = destination / "groove.json"
    if destination.exists():
        verified_path, existing = verify_groove_development(song_path, destination)
        if existing.get("groove_id") != groove_id:
            raise FileExistsError(f"groove destination has different provenance: {destination}")
        return verified_path, existing
    parent.mkdir(parents=True, exist_ok=True)
    temporary = parent / f".{groove_id[:10]}.partial"
    if temporary.exists():
        raise FileExistsError(f"incomplete groove development exists: {temporary}")
    temporary.mkdir()
    try:
        beat_name = "prototype.beat"
        audio_name = "prototype.wav"
        beat_path = temporary / beat_name
        brief_with_voices = {**brief, "voices": prototype["voices"]}
        beat_path.write_text(_beat_text(
            title,
            observation_record["path"],
            brief_with_voices,
            beat,
        ))
        parsed = load(beat_path)
        audio_path = temporary / audio_name
        render(parsed, audio_path)
        warnings = [
            "The WAV is a synthesized BeatScript audition of one explicit interpretation; it is not a transcription, replacement, or processed copy of the performed beat idea.",
            "Per-event performed-minus-grid offsets are evidence only; the prototype applies only declared voice-wide offset, swing, and seeded humanize controls.",
            "The lightweight prototype renderer may lower an overloaded synthetic sum for safe integer output; do not treat its level as a mix decision.",
        ]
        if any(voice["humanize_ms"] for voice in prototype["voices"]):
            warnings.append(
                "Seeded prototype humanize is an authored audition control, not a reconstruction of the performer's microtiming."
            )
        record = {
            "schema": GROOVE_DEVELOPMENT_SCHEMA,
            "groove_id": groove_id,
            "created_at": utc_now(),
            "title": title,
            "intent": intent,
            "recipe": recipe,
            "outputs": {
                "beatscript": {
                    "path": str((destination / beat_name).relative_to(song_path)),
                    "sha256": sha256(beat_path),
                },
                "audio_prototype": {
                    "path": str((destination / audio_name).relative_to(song_path)),
                    "sha256": sha256(audio_path),
                    "format": {
                        "sample_rate": SAMPLE_RATE,
                        "channels": 2,
                        "sample_width_bits": 16,
                        "synthesized": True,
                    },
                },
            },
            "interpretation_limits": {
                "source_audio_modified": False,
                "automatic_role_assignment": False,
                "automatic_quantization": False,
                "prototype_grid_quantized": True,
                "prototype_is_one_authored_interpretation": True,
                "performed_grid_offsets_preserved_as_evidence": True,
            },
            "warnings": warnings,
            "review": {
                "decision": "not recorded by renderer",
                "listening_notes": [],
            },
            "authority": {
                "creative_approval_inferred": False,
                "final_promotion": False,
                "upload_authorized": False,
                "publication_authorized": False,
            },
        }
        (temporary / "groove.json").write_text(json.dumps(record, indent=2) + "\n")
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return verify_groove_development(song_path, manifest)


def review_groove(
    song: str | Path,
    groove: str | Path,
    listening_note: str,
    decision: str,
) -> Path:
    """Append a listening decision without changing the interpretation or audio."""
    note = listening_note.strip()
    if not note:
        raise ValueError("groove review requires a listening note")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("groove review decision must be keep, change, or stop")
    path, _ = verify_groove_development(song, groove)
    with _review_lock(path):
        path, record = verify_groove_development(song, path)
        review = record["review"]
        notes = review["listening_notes"]
        duplicate = any(
            isinstance(item, dict) and item.get("decision") == decision and item.get("note") == note
            for item in notes
        )
        if duplicate and review.get("decision") == decision:
            return path
        if not duplicate:
            notes.append({"reviewed_at": utc_now(), "decision": decision, "note": note})
        review["decision"] = decision
        temporary = path.with_name(f".{path.name}.review.partial")
        try:
            with temporary.open("x") as output:
                output.write(json.dumps(record, indent=2) + "\n")
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return path
