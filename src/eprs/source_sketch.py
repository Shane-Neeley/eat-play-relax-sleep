"""Seeded, reversible first arrangements made from captured recordings."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random
import secrets

from .beat import load as load_beat
from .frontdoor import expose_current_media
from .mix import render_mix, verify_mix_provenance
from .musical_observation import verify_musical_observation
from .production_map import write_production_map
from .request import load_production_request
from .system import load_song_manifest, probe, sha256, slugify, utc_now
from .visuals import compile_prompt, render_visual


SOURCE_SKETCH_SCHEMA = "eprs.source-sketch/v1"
RUN_SCHEMA = "eprs.song-run/v1"
NOW_MARKER = "<!-- eprs.now/v1 -->"
ARRANGEMENT_SHAPES = {"one-pass", "call-response", "loop"}
DEFAULT_SHAPE = "one-pass"
NOVELTY_MAX_ATTEMPTS = 1_024


ROLE_WORDS = {
    "rhythm": ("beat", "drum", "kick", "snare", "clap", "percussion", "boom", "rhythm"),
    "vocal": ("voice", "voices", "vocal", "sing", "choir", "family", "chant", "lyric"),
    "bass": ("bass", "sub", "low end"),
    "harmonic": ("guitar", "piano", "keys", "chord", "synth", "organ", "ukulele", "banjo"),
}


def _inside(song: Path, value: str | Path, label: str) -> Path:
    requested = Path(value)
    path = requested.resolve() if requested.is_absolute() else (song / requested).resolve()
    try:
        path.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError(f"source sketch {label} must stay inside the song workspace") from exc
    return path


def _load_run(song: Path, value: str | Path | None) -> tuple[Path, dict]:
    if value is None:
        latest = load_song_manifest(song).get("latest_run")
        if not isinstance(latest, dict) or not isinstance(latest.get("path"), str):
            raise ValueError("song has no agent-led run; create one with make-song first")
        path = _inside(song, latest["path"], "run")
    else:
        requested = Path(value)
        direct = _inside(song, requested, "run")
        by_id = song / "notes" / "runs" / str(value) / "run.json"
        path = direct if direct.is_file() else by_id.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid song-run JSON: {path}: {exc.msg}") from exc
    if record.get("schema") != RUN_SCHEMA:
        raise ValueError(f"unsupported song-run schema: {record.get('schema')}")
    return path, record


def _classify(item: dict) -> str:
    words = " ".join(str(item.get(key, "")) for key in ("role", "kind", "note")).casefold()
    for group in ("rhythm", "vocal", "bass", "harmonic"):
        if any(word in words for word in ROLE_WORDS[group]):
            return group
    return "texture"


def _audio_duration(path: Path, label: str) -> tuple[float, dict]:
    media_probe = probe(path)
    stream = next(
        (item for item in media_probe.get("streams", []) if item.get("codec_type") == "audio"),
        None,
    )
    if stream is None:
        raise ValueError(f"source sketch recording has no audio stream: {label}")
    value = media_probe.get("format", {}).get("duration")
    try:
        duration = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"source sketch recording duration is unavailable: {label}") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"source sketch recording duration is invalid: {label}")
    return duration, media_probe


def _bar_seconds(beat_path: Path) -> float:
    beat = load_beat(beat_path)
    numerator, denominator = beat.meter
    return numerator * (60.0 / beat.tempo) * (4.0 / denominator)


def _start_bars(group: str, rng: random.Random) -> int:
    choices = {
        "rhythm": (0, 0, 1),
        "bass": (0, 1, 2),
        "harmonic": (0, 1, 2),
        "vocal": (2, 3, 4),
        "texture": (1, 2, 3),
    }
    return rng.choice(choices[group])


def _base_gain(group: str) -> float:
    return {
        "rhythm": -10.0,
        "vocal": -8.0,
        "bass": -12.0,
        "harmonic": -10.0,
        "texture": -13.0,
    }[group]


def _pan_width(group: str) -> float:
    return {
        "rhythm": 0.12,
        "vocal": 0.08,
        "bass": 0.03,
        "harmonic": 0.28,
        "texture": 0.38,
    }[group]


def _player_intent(
    group: str,
    role: str,
    start_bars: int,
    *,
    shape: str,
    turns: int,
    stride_bars: int | None,
    relationship_role: str,
) -> str:
    entrance = "from the downbeat" if start_bars == 0 else f"after {start_bars} bar{'s' if start_bars != 1 else ''}"
    statements = {
        "rhythm": f"Let {role} act as performed timekeeping {entrance}; keep its push, drag, accents, and gaps rather than forcing it to the grid.",
        "vocal": f"Let {role} answer {entrance}; preserve breath, overlap, pitch, laughter, and room sound without tuning or tightening.",
        "bass": f"Let {role} enter {entrance} as low support; keep its original envelope and timing without replacement or side-chain processing.",
        "harmonic": f"Let {role} open space {entrance}; preserve the attack, drift, decay, and any useful rough edge.",
        "texture": f"Let {role} color the room {entrance}; leave its internal timing and noise intact and hear whether it belongs.",
    }
    if shape == "call-response":
        return (
            f"Treat {role} as the {relationship_role}. {statements[group]} Make {turns} "
            "clearly separated conversational turn(s); "
            "the score may audition the opening phrase twice but must not tune, tighten, or warp it."
        )
    if shape == "loop":
        return (
            f"{statements[group]} Repeat the complete captured phrase every {stride_bars} "
            f"bar{'s' if stride_bars != 1 else ''} for {turns} occurrence(s), preserving its "
            "performed length and any gap before the next entrance without time-stretching."
        )
    return statements[group]


def _arrangement_placements(
    shape: str,
    group: str,
    duration: float,
    seconds_per_bar: float,
    horizon_seconds: float | None,
    rng: random.Random,
    relationship_role: str,
    conversation_start_bars: int | None,
) -> tuple[list[dict], int | None]:
    """Choose explicit source occurrences without altering the source clock."""
    if shape == "one-pass":
        starts = [_start_bars(group, rng)]
        maximum_duration = duration
        stride_bars = None
        clip_to_horizon = True
    elif shape == "call-response":
        if conversation_start_bars is None:
            raise ValueError("call-response placement needs an explicit turn start")
        base = conversation_start_bars
        starts = [base, base + 4]
        maximum_duration = min(duration, 2 * seconds_per_bar)
        stride_bars = 4
        clip_to_horizon = False
    else:
        first = _start_bars(group, rng)
        stride_bars = max(1, math.ceil(duration / seconds_per_bar))
        limit = horizon_seconds if horizon_seconds is not None else 8 * seconds_per_bar
        starts = []
        current = first
        while (
            current * seconds_per_bar + duration <= limit + 0.01
            and len(starts) < 8
        ):
            starts.append(current)
            current += stride_bars
        if not starts:
            starts = [first]
        maximum_duration = duration
        clip_to_horizon = False

    placements: list[dict] = []
    for bars in starts:
        start = round(bars * seconds_per_bar, 6)
        if (
            clip_to_horizon
            and horizon_seconds is not None
            and start >= max(0.0, horizon_seconds - 0.05)
        ):
            continue
        available = maximum_duration
        if clip_to_horizon and horizon_seconds is not None:
            available = min(available, horizon_seconds - start)
        if available <= 0:
            continue
        placements.append({
            "start_bars": bars,
            "start_seconds": start,
            "duration_seconds": round(available, 6),
            "truncated_for_sketch": available < duration - 0.01,
        })
    if not placements:
        available = (
            duration
            if not clip_to_horizon or horizon_seconds is None
            else min(duration, horizon_seconds)
        )
        placements.append({
            "start_bars": 0,
            "start_seconds": 0.0,
            "duration_seconds": round(available, 6),
            "truncated_for_sketch": available < duration - 0.01,
        })
    return placements, stride_bars


def _source_creative_fingerprint(
    shape: str,
    bed_sha256: str | None,
    source_plans: list[dict],
) -> str:
    """Hash audible arrangement choices while excluding labels and replay seed."""
    payload = {
        "shape": shape,
        "bed_sha256": bed_sha256,
        "sources": [{
            "sha256": source.get("sha256"),
            "relationship_role": source.get("relationship_role"),
            "placements": [
                {
                    **{
                        key: placement.get(key) for key in (
                            "start_seconds", "duration_seconds", "gain_db",
                            "pan",
                        )
                    },
                    **(
                        {"source_start_seconds": placement.get("source_start_seconds")}
                        if placement.get("source_start_seconds") not in {None, 0}
                        else {}
                    ),
                }
                for placement in source.get("placements", [source.get("placement")])
            if isinstance(placement, dict)],
        } for source in source_plans],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _prior_source_fingerprints(song: Path) -> set[str]:
    fingerprints: set[str] = set()
    for path in (song / "notes" / "source-sketches").glob("*/*/source-sketch.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("schema") != SOURCE_SKETCH_SCHEMA:
            continue
        randomness = record.get("randomness")
        stored = randomness.get("creative_fingerprint") if isinstance(randomness, dict) else None
        arrangement = record.get("arrangement")
        sources = record.get("sources")
        if (
            isinstance(stored, str) and len(stored) == 64
            and isinstance(arrangement, dict)
            and arrangement.get("shape") in ARRANGEMENT_SHAPES
            and isinstance(sources, list)
            and stored == _source_creative_fingerprint(
                arrangement["shape"], arrangement.get("bed_sha256"), sources
            )
        ):
            fingerprints.add(stored)
    return fingerprints


def _prepare_source_inputs(song: Path, recordings: list[dict]) -> list[dict]:
    """Validate and probe immutable media once, outside novelty retries."""
    prepared: list[dict] = []
    for index, item in enumerate(recordings, start=1):
        role = str(
            item.get("role") or item.get("declared_id") or f"recording {index}"
        ).strip()
        source = _inside(song, item.get("path", ""), role)
        source_digest = sha256(source) if source.is_file() else None
        if source_digest is None or item.get("sha256") != source_digest:
            raise ValueError(f"captured recording is missing or changed: {role}")
        duration, media_probe = _audio_duration(source, role)
        prepared.append({
            "role": role,
            "classification": _classify(item),
            "path": str(source.relative_to(song)),
            "sha256": source_digest,
            "duration_seconds": duration,
            "probe": media_probe,
            "rights_note": item.get("rights_note"),
        })
    return prepared


def _phrase_selection_pool(regions: list[dict]) -> tuple[list[dict], dict]:
    """Prefer substantial regions while retaining short-idea fallback."""
    if not regions:
        raise ValueError("musical observation has no phrase region to arrange")
    maximum_phrase_duration = max(item["duration_seconds"] for item in regions)
    minimum_phrase_duration = round(
        max(0.2, min(1.0, maximum_phrase_duration * 0.25)), 6
    )
    phrase_pool = [
        item for item in regions
        if item["duration_seconds"] >= minimum_phrase_duration
    ]
    fallback_used = not phrase_pool
    if fallback_used:
        phrase_pool = regions
    return phrase_pool, {
        "rule": (
            "all measured regions because none reached the preferred duration"
            if fallback_used else
            "regions at least max(0.2 seconds, min(1 second, one quarter of the longest region))"
        ),
        "preferred_minimum_duration_seconds": minimum_phrase_duration,
        "fallback_used": fallback_used,
        "phrase_ids": [item["id"] for item in phrase_pool],
    }


def _bind_musical_observations(
    song: Path,
    prepared_sources: list[dict],
    values: list[str | Path],
) -> list[dict]:
    """Bind each explicit observation to one already-hashed captured source."""
    bindings: list[dict] = []
    seen_paths: set[Path] = set()
    for value in values:
        path, report = verify_musical_observation(
            song, value, verify_checksum=False
        )
        if path in seen_paths:
            raise ValueError(f"duplicate source-sketch musical observation: {path}")
        seen_paths.add(path)
        source_digest = report["source"]["sha256"]
        observed_source_path = report["source"]["path"]
        matches = [
            item for item in prepared_sources
            if item["sha256"] == source_digest and item["path"] == observed_source_path
        ]
        if len(matches) != 1:
            raise ValueError(
                "source-sketch musical observation must describe exactly one captured recording"
            )
        source = matches[0]
        if source.get("_musical_observation") is not None:
            raise ValueError(
                f"source sketch accepts only one musical observation per recording: {source['role']}"
            )
        regions = report["phrase_observation"]["regions"]
        if not regions:
            raise ValueError(
                f"musical observation has no phrase region to arrange: {path.relative_to(song)}"
            )
        phrase_pool, selection_pool = _phrase_selection_pool(regions)
        binding = {
            "path": str(path.relative_to(song)),
            "sha256": sha256(path),
            "analysis_id": report["analysis_id"],
            "result_id": report["result_id"],
            "source_sha256": source_digest,
            "role": report["role"],
        }
        source["_musical_observation"] = {
            "binding": binding,
            "phrases": regions,
            "phrase_pool": phrase_pool,
            "selection_pool": selection_pool,
            "pitch_candidates": report["pitch_observation"]["candidates"],
            "tempo_candidates": report["pulse_observation"]["tempo_candidates"],
        }
        bindings.append(binding)
    return sorted(bindings, key=lambda item: (item["source_sha256"], item["path"]))


def _build_source_plan(
    song: Path,
    prepared_sources: list[dict],
    shape: str,
    seed: int,
    seconds_per_bar: float,
    bed_path: Path,
    bed_duration: float | None,
    include_bed: bool,
) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed ^ 0x53_4F_55_52_43_45)
    phrase_rng = random.Random(seed ^ 0x50_48_52_41_53_45)
    caller_index = min(
        range(len(prepared_sources)),
        key=lambda index: ({
            "rhythm": 0, "harmonic": 1, "bass": 2, "texture": 3, "vocal": 4,
        }[prepared_sources[index]["classification"]], index),
    )
    conversation_call_bar = rng.choice((0, 1)) if shape == "call-response" else None
    shared_attenuation = 3.0 * math.log2(max(1, len(prepared_sources)))
    source_plans: list[dict] = []
    tracks: list[dict] = []
    if include_bed:
        tracks.append({
            "id": "synthetic-pocket",
            "role": "quiet synthetic pocket",
            "intent": "Stay underneath the supplied performances as a timing and low-frequency question, not as a replacement band.",
            "path": str(bed_path.relative_to(song)),
            "start_seconds": 0,
            "source_start_seconds": 0,
            "duration_seconds": bed_duration,
            "gain_db": -18.0,
            "pan": 0,
            "fade_in_ms": 0,
            "fade_out_ms": 0,
        })

    for index, item in enumerate(prepared_sources, start=1):
        role = item["role"]
        observation = item.get("_musical_observation")
        selected_phrase = (
            phrase_rng.choice(observation["phrase_pool"]) if observation else None
        )
        source_start_seconds = selected_phrase["start_seconds"] if selected_phrase else 0.0
        duration = (
            selected_phrase["duration_seconds"]
            if selected_phrase else item["duration_seconds"]
        )
        group = item["classification"]
        relationship_role = (
            "call" if shape == "call-response" and index - 1 == caller_index
            else "answer" if shape == "call-response"
            else "ostinato" if shape == "loop"
            else "single-pass"
        )
        gain = round(_base_gain(group) - shared_attenuation + rng.uniform(-0.75, 0.0), 3)
        pan = round(rng.uniform(-_pan_width(group), _pan_width(group)), 3)
        placements, stride_bars = _arrangement_placements(
            shape, group, duration, seconds_per_bar, bed_duration, rng,
            relationship_role,
            (
                conversation_call_bar
                if relationship_role == "call"
                else conversation_call_bar + 2
                if relationship_role == "answer" and conversation_call_bar is not None
                else None
            ),
        )
        player_intent = _player_intent(
            group,
            role,
            placements[0]["start_bars"],
            shape=shape,
            turns=len(placements),
            stride_bars=stride_bars,
            relationship_role=relationship_role,
        )
        if observation and selected_phrase:
            pitch_names = [
                item["nearest_note_name"]
                for item in observation["pitch_candidates"][:4]
            ]
            pulse_values = [item["bpm"] for item in observation["tempo_candidates"]]
            player_intent += (
                f" This pass explicitly uses observed phrase {selected_phrase['id']} "
                f"({selected_phrase['start_seconds']:g}s–{selected_phrase['end_seconds']:g}s) "
                "as an unchanged boundary."
            )
            if pitch_names:
                player_intent += (
                    f" Hear {', '.join(pitch_names)} only as periodicity leads; no key or chord was inferred."
                )
            if pulse_values:
                player_intent += (
                    " Keep the pulse open among "
                    + ", ".join(f"{value:g} BPM" for value in pulse_values)
                    + "; no tempo or meter was selected."
                )
        source_id = slugify(role) or f"recording-{index}"
        if any(source_plan.get("id") == source_id for source_plan in source_plans):
            source_id = f"{source_id}-{index}"
        source_path = item["path"]
        placement_records = []
        for occurrence, placement in enumerate(placements, start=1):
            track_id = source_id if len(placements) == 1 else f"{source_id}-turn-{occurrence}"
            tracks.append({
                "id": track_id,
                "role": role,
                "intent": player_intent,
                "path": source_path,
                "start_seconds": placement["start_seconds"],
                "source_start_seconds": source_start_seconds,
                "duration_seconds": placement["duration_seconds"],
                "gain_db": gain,
                "pan": pan,
                "fade_in_ms": 0,
                "fade_out_ms": 20 if placement["truncated_for_sketch"] else 0,
            })
            placement_records.append({
                **placement,
                "track_id": track_id,
                "source_start_seconds": source_start_seconds,
                "gain_db": gain,
                "pan": pan,
            })
        source_plans.append({
            "id": source_id,
            "role": role,
            "classification": group,
            "relationship_role": relationship_role,
            "path": source_path,
            "sha256": item["sha256"],
            "probe": item["probe"],
            "rights_note": item.get("rights_note"),
            "player_intent": player_intent,
            "musical_observation": (
                {
                    **observation["binding"],
                    "selected_phrase": selected_phrase,
                    "selection_pool": observation["selection_pool"],
                    "pitch_candidates": observation["pitch_candidates"][:4],
                    "tempo_candidates": observation["tempo_candidates"],
                    "interpretation": {
                        "key_selected": False,
                        "chord_selected": False,
                        "tempo_selected": False,
                        "meter_selected": False,
                    },
                }
                if observation else None
            ),
            "placement": placement_records[0],
            "placements": placement_records,
        })
    return source_plans, tracks


def _write_exact_json(path: Path, value: dict, label: str) -> None:
    content = json.dumps(value, indent=2) + "\n"
    if path.exists():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"{label} exists with different content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _now_markdown(song: Path, record: dict) -> str:
    paths = record["paths"]
    source_lines = "\n".join(
        f"- **{item['role']}** ({len(item.get('placements', [item.get('placement')]))} "
        f"occurrence(s)): {item['player_intent']}"
        for item in record["sources"]
    )
    watch = f"- Watch: `{paths['visual_preview']}`\n" if paths.get("visual_preview") else "- Watch: no source-synced visual rendered for this pass\n"
    map_value = paths.get("production_map_svg") or paths.get("production_map_dot")
    novelty = record["randomness"].get("novelty", {})
    novelty_line = (
        f"- Novelty: checked `{novelty.get('prior_fingerprints_checked', 0)}` prior "
        f"source arrangement(s); rejected `{novelty.get('collision_rejections', 0)}` collision(s)\n"
        if novelty.get("enforced") else
        "- Novelty: explicit seed replay; matching a prior artifact is allowed\n"
    )
    return f"""{NOW_MARKER}
# Current source-aware sketch

This is a reversible diagnostic arrangement using the supplied recordings. It is not a mix approval, master, rights clearance, or publication authorization.

- Listen: `{paths['mix']}`
{watch}- Seed: `{record['randomness']['seed']}` ({record['randomness']['mode']})
{novelty_line}- Arrangement shape: `{record.get('arrangement', {}).get('shape', DEFAULT_SHAPE)}`
- Mix score: `{paths['mix_score']}`
- Source-sketch record: `{paths['source_sketch']}`
- Production map: `{map_value}`

## What this pass is trying

{record['intent']}

{source_lines}

No source was normalized, tuned, quantized, denoised, compressed, limited, or time-stretched. Explicit occurrences, placement, conservative balance, and short truncation fades are the only authored moves.

## Next move

1. Listen end to end and say what locks, fights, disappears, or deserves more room.
2. Record keep/change/stop with `./scripts/eprs mix-review {paths['mix']} --song {song} --listening-note "..." --decision <keep|change|stop>`.
3. Ask an agent for a new source sketch without `--seed` for a fresh interpretation, or replay seed `{record['randomness']['seed']}` exactly.
"""


def _replace_now(song: Path, content: str) -> None:
    path = song / "NOW.md"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not (existing.startswith(NOW_MARKER) or existing.startswith("# Current song run")):
            raise FileExistsError(f"refusing to replace user-authored NOW.md: {path}")
    temporary = song / ".NOW.md.partial"
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _existing_sketch(song: Path, manifest_path: Path, expected_id: str) -> dict | None:
    if not manifest_path.is_file():
        return None
    try:
        record = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid source-sketch JSON: {manifest_path}: {exc.msg}") from exc
    if record.get("schema") != SOURCE_SKETCH_SCHEMA or record.get("id") != expected_id:
        raise FileExistsError(f"source-sketch destination has different provenance: {manifest_path}")
    mix_path = _inside(song, record.get("paths", {}).get("mix", ""), "existing mix")
    verify_mix_provenance(song, mix_path)
    score_path = _inside(song, record.get("paths", {}).get("mix_score", ""), "existing score")
    if not score_path.is_file() or record.get("outputs", {}).get("mix_score_sha256") != sha256(score_path):
        raise ValueError("existing source-sketch score is missing or changed")
    return record


def verify_source_sketch(
    song: str | Path,
    item: str | Path,
) -> tuple[Path, dict]:
    """Verify a source sketch, its immutable inputs, score, mix, and optional picture."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(item)
    path = (
        requested.resolve()
        if requested.is_absolute() or requested.exists()
        else (song_path / requested).resolve()
    )
    if path.is_dir():
        path = path / "source-sketch.json"
    try:
        path.relative_to((song_path / "notes" / "source-sketches").resolve())
    except ValueError as exc:
        raise ValueError("source sketch must stay inside notes/source-sketches") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid source-sketch JSON: {path}: {exc.msg}") from exc
    if record.get("schema") != SOURCE_SKETCH_SCHEMA:
        raise ValueError("unsupported source-sketch schema")
    if not isinstance(record.get("id"), str) or len(record["id"]) != 64:
        raise ValueError("source-sketch id is invalid")
    for label in ("run", "request"):
        binding = record.get(label)
        value = binding.get("path") if isinstance(binding, dict) else None
        source = _inside(song_path, value or "", label)
        if not source.is_file() or binding.get("sha256") != sha256(source):
            raise ValueError(f"source-sketch {label} is missing or changed")
    sources = record.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("source-sketch sources are invalid")
    for source in sources:
        value = source.get("path") if isinstance(source, dict) else None
        source_path = _inside(song_path, value or "", "recording")
        if not source_path.is_file() or source.get("sha256") != sha256(source_path):
            raise ValueError("source-sketch recording is missing or changed")
    observation_records = record.get("musical_observations", [])
    if not isinstance(observation_records, list):
        raise ValueError("source-sketch musical observations are invalid")
    observations_by_path: dict[str, dict] = {}
    for binding in observation_records:
        value = binding.get("path") if isinstance(binding, dict) else None
        if not isinstance(value, str) or value in observations_by_path:
            raise ValueError("source-sketch musical observation binding is invalid")
        observation_path, observation = verify_musical_observation(song_path, value)
        if any(binding.get(key) != expected for key, expected in {
            "sha256": sha256(observation_path),
            "analysis_id": observation.get("analysis_id"),
            "result_id": observation.get("result_id"),
            "source_sha256": observation.get("source", {}).get("sha256"),
            "role": observation.get("role"),
        }.items()):
            raise ValueError("source-sketch musical observation binding has drifted")
        observations_by_path[value] = observation
    used_observation_paths: set[str] = set()
    for source in sources:
        binding = source.get("musical_observation")
        if binding is None:
            continue
        value = binding.get("path") if isinstance(binding, dict) else None
        observation = observations_by_path.get(value)
        if observation is None or binding.get("source_sha256") != source.get("sha256"):
            raise ValueError("source-sketch source observation binding is invalid")
        top_binding = next(
            item for item in observation_records if item.get("path") == value
        )
        if any(binding.get(key) != top_binding.get(key) for key in (
            "path", "sha256", "analysis_id", "result_id", "source_sha256", "role"
        )):
            raise ValueError("source-sketch source observation identity has drifted")
        selected = binding.get("selected_phrase")
        if selected not in observation["phrase_observation"]["regions"]:
            raise ValueError("source-sketch selected phrase is not in its observation")
        regions = observation["phrase_observation"]["regions"]
        phrase_pool, expected_pool = _phrase_selection_pool(regions)
        if binding.get("selection_pool") != expected_pool or selected not in phrase_pool:
            raise ValueError("source-sketch selected phrase is outside its declared pool")
        if (
            binding.get("pitch_candidates")
            != observation["pitch_observation"]["candidates"][:4]
            or binding.get("tempo_candidates")
            != observation["pulse_observation"]["tempo_candidates"]
        ):
            raise ValueError("source-sketch observation candidates have drifted")
        interpretation = binding.get("interpretation")
        if not isinstance(interpretation, dict) or any(
            interpretation.get(key) is not False for key in (
                "key_selected", "chord_selected", "tempo_selected", "meter_selected"
            )
        ):
            raise ValueError("source-sketch observation interpretation is invalid")
        used_observation_paths.add(value)
    if used_observation_paths != set(observations_by_path):
        raise ValueError("source-sketch has an unused musical observation binding")
    arrangement = record.get("arrangement")
    shape = DEFAULT_SHAPE
    if arrangement is not None:
        if not isinstance(arrangement, dict) or arrangement.get("shape") not in ARRANGEMENT_SHAPES:
            raise ValueError("source-sketch arrangement is invalid")
        if arrangement.get("source_clock_preserved") is not True:
            raise ValueError("source-sketch source-clock contract is invalid")
        shape = arrangement["shape"]
    paths = record.get("paths")
    outputs = record.get("outputs")
    if not isinstance(paths, dict) or not isinstance(outputs, dict):
        raise ValueError("source-sketch paths or outputs are invalid")
    score = _inside(song_path, paths.get("mix_score", ""), "mix score")
    if not score.is_file() or outputs.get("mix_score_sha256") != sha256(score):
        raise ValueError("source-sketch mix score is missing or changed")
    try:
        score_record = json.loads(score.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid source-sketch mix score: {score}: {exc.msg}") from exc
    score_binding = score_record.get("source_sketch")
    if (
        not isinstance(score_binding, dict)
        or score_binding.get("shape", DEFAULT_SHAPE) != shape
    ):
        raise ValueError("source-sketch arrangement does not match its mix score")
    if score_binding.get("musical_observations", []) != observation_records:
        raise ValueError("source-sketch observations do not match its mix score")
    evidence_paths = {
        item.get("path") for item in score_record.get("evidence", [])
        if isinstance(item, dict)
    }
    if not set(observations_by_path).issubset(evidence_paths):
        raise ValueError("source-sketch mix score is missing musical observation evidence")
    mix_tracks = score_record.get("tracks")
    if not isinstance(mix_tracks, list):
        raise ValueError("source-sketch mix-score tracks are invalid")
    tracks_by_id = {
        item.get("id"): item for item in mix_tracks
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    occurrence_count = 0
    for source in sources:
        placements = source.get("placements")
        if placements is None:
            placements = [source.get("placement")]
        if not isinstance(placements, list) or not placements:
            raise ValueError("source-sketch source placements are invalid")
        occurrence_count += len(placements)
        for placement in placements:
            if not isinstance(placement, dict):
                raise ValueError("source-sketch source placement is invalid")
            track_id = placement.get("track_id")
            if track_id is None:
                continue
            track = tracks_by_id.get(track_id)
            if not isinstance(track, dict) or any(
                track.get(key) != expected for key, expected in {
                    "path": source.get("path"),
                    "start_seconds": placement.get("start_seconds"),
                    "source_start_seconds": placement.get("source_start_seconds", 0),
                    "duration_seconds": placement.get("duration_seconds"),
                    "gain_db": placement.get("gain_db"),
                    "pan": placement.get("pan"),
                }.items()
            ):
                raise ValueError("source-sketch placement does not match its mix-score track")
    if arrangement is not None and arrangement.get("occurrences") != occurrence_count:
        raise ValueError("source-sketch occurrence count is invalid")
    bed_track = tracks_by_id.get("synthetic-pocket")
    bed_digest = None
    if isinstance(bed_track, dict):
        bed_path = _inside(song_path, bed_track.get("path", ""), "starter bed")
        if not bed_path.is_file():
            raise ValueError("source-sketch starter bed is missing")
        bed_digest = sha256(bed_path)
    if (
        arrangement is not None
        and "bed_sha256" in arrangement
        and arrangement.get("bed_sha256") != bed_digest
    ):
        raise ValueError("source-sketch starter-bed fingerprint input is invalid")
    expected_fingerprint = _source_creative_fingerprint(shape, bed_digest, sources)
    randomness = record.get("randomness")
    stored_fingerprint = (
        randomness.get("creative_fingerprint") if isinstance(randomness, dict) else None
    )
    if stored_fingerprint is not None and stored_fingerprint != expected_fingerprint:
        raise ValueError("source-sketch creative fingerprint is invalid")
    if stored_fingerprint is not None:
        novelty = randomness.get("novelty")
        if not isinstance(novelty, dict) or not isinstance(novelty.get("enforced"), bool):
            raise ValueError("source-sketch novelty evidence is invalid")
    mix = _inside(song_path, paths.get("mix", ""), "mix")
    verify_mix_provenance(song_path, mix)
    mix_output = outputs.get("mix")
    if not isinstance(mix_output, dict) or mix_output.get("sha256") != sha256(mix):
        raise ValueError("source-sketch mix is missing or changed")
    visual_score = _inside(song_path, paths.get("visual_score", ""), "visual score")
    if not visual_score.is_file() or outputs.get("visual_score_sha256") != sha256(visual_score):
        raise ValueError("source-sketch visual score is missing or changed")
    visual = outputs.get("visual_preview")
    if not isinstance(visual, dict) or visual.get("status") not in {"rendered", "skipped"}:
        raise ValueError("source-sketch visual output is invalid")
    if visual.get("status") == "rendered":
        video = _inside(song_path, paths.get("visual_preview", ""), "visual preview")
        provenance = _inside(song_path, paths.get("visual_provenance", ""), "visual provenance")
        if not video.is_file() or visual.get("sha256") != sha256(video):
            raise ValueError("source-sketch visual preview is missing or changed")
        if not provenance.is_file() or visual.get("provenance_sha256") != sha256(provenance):
            raise ValueError("source-sketch visual provenance is missing or changed")
    render = record.get("render")
    if not isinstance(render, dict) or any(render.get(key) is not False for key in (
        "automatic_normalization", "compression", "limiting", "time_stretch",
        "pitch_correction", "quantization",
    )):
        raise ValueError("source-sketch preservation contract is invalid")
    return path, record


def create_source_sketch(
    song: str | Path,
    intent: str,
    *,
    run: str | Path | None = None,
    seed: int | None = None,
    include_bed: bool = True,
    shape: str = DEFAULT_SHAPE,
    render_visual_preview: bool = True,
    visual_seconds: float = 8.0,
    observations: list[str | Path] | None = None,
) -> tuple[Path, dict]:
    """Render one fresh, source-aware diagnostic arrangement from a captured request."""
    clean_intent = intent.strip() if isinstance(intent, str) else ""
    if not clean_intent:
        raise ValueError("source sketch requires player-facing intent")
    if visual_seconds <= 0:
        raise ValueError("source sketch visual_seconds must be positive")
    if shape not in ARRANGEMENT_SHAPES:
        raise ValueError("source sketch shape must be one-pass, call-response, or loop")
    song_path = Path(song).resolve()
    song_manifest = load_song_manifest(song_path)
    run_path, run_record = _load_run(song_path, run)
    paths = run_record.get("paths")
    if not isinstance(paths, dict) or not isinstance(paths.get("request"), str):
        raise ValueError("song run does not link a captured request")
    request_path, request = load_production_request(song_path, paths["request"])
    provided = request.get("provided")
    if not isinstance(provided, dict):
        raise ValueError("captured request provided sources are invalid")
    recordings = [
        item for item in provided.values()
        if isinstance(item, dict) and item.get("handling") == "immutable-recording"
    ]
    if not recordings:
        raise ValueError("source sketch needs at least one captured recording")
    if shape == "call-response" and len(recordings) < 2:
        raise ValueError("call-response source sketch needs at least two captured recordings")

    seed_was_supplied = seed is not None
    beat_path = _inside(song_path, paths.get("beat", ""), "BeatScript")
    if not beat_path.is_file():
        raise FileNotFoundError(beat_path)
    seconds_per_bar = _bar_seconds(beat_path)
    bed_path = _inside(song_path, paths.get("audio_preview", ""), "starter bed")
    if include_bed and not bed_path.is_file():
        raise FileNotFoundError(bed_path)
    bed_duration = _audio_duration(bed_path, "starter bed")[0] if include_bed else None
    bed_sha256 = sha256(bed_path) if include_bed else None
    prepared_sources = _prepare_source_inputs(song_path, recordings)
    observation_bindings = _bind_musical_observations(
        song_path, prepared_sources, list(observations or [])
    )
    if seed_was_supplied:
        sketch_seed = int(seed)
        source_plans, tracks = _build_source_plan(
            song_path, prepared_sources, shape, sketch_seed, seconds_per_bar,
            bed_path, bed_duration, include_bed,
        )
        creative_fingerprint = _source_creative_fingerprint(
            shape, bed_sha256, source_plans
        )
        novelty = {
            "enforced": False,
            "scope": "explicit seed replay may intentionally match prior song artifacts",
            "collision_rejections": 0,
        }
    else:
        prior_fingerprints = _prior_source_fingerprints(song_path)
        for attempt in range(1, NOVELTY_MAX_ATTEMPTS + 1):
            sketch_seed = secrets.randbits(63)
            source_plans, tracks = _build_source_plan(
                song_path, prepared_sources, shape, sketch_seed, seconds_per_bar,
                bed_path, bed_duration, include_bed,
            )
            creative_fingerprint = _source_creative_fingerprint(
                shape, bed_sha256, source_plans
            )
            if creative_fingerprint not in prior_fingerprints:
                novelty = {
                    "enforced": True,
                    "scope": "song-local source checksums, bed, shape, occurrence timing, duration, gain, and pan",
                    "prior_fingerprints_checked": len(prior_fingerprints),
                    "collision_rejections": attempt - 1,
                    "maximum_attempts": NOVELTY_MAX_ATTEMPTS,
                }
                break
        else:
            raise RuntimeError(
                f"could not find a new source arrangement after {NOVELTY_MAX_ATTEMPTS} entropy draws"
            )

    plan = {
        "run_path": str(run_path.relative_to(song_path)),
        "run_sha256": sha256(run_path),
        "request_path": str(request_path.relative_to(song_path)),
        "request_sha256": sha256(request_path),
        "intent": clean_intent,
        "seed": sketch_seed,
        "include_bed": include_bed,
        "shape": shape,
        "seconds_per_bar": seconds_per_bar,
        "tracks": tracks,
        "musical_observations": observation_bindings,
    }
    sketch_id = hashlib.sha256(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    run_key = run_record.get("id") or run_path.parent.name
    score_path = song_path / "code" / f"{run_key}-source-sketch-{sketch_id[:10]}.json"
    mix_score = {
        "schema": "eprs.mix/v1",
        "title": f"{run_record.get('title', song_manifest.get('title', song_path.name))} source sketch {sketch_id[:6]}",
        "intent": clean_intent,
        "output": {"sample_rate": int(song_manifest.get("sample_rate", 48_000))},
        "evidence": [{
            "id": "captured-request",
            "role": "source-sketch intent and supplied recordings",
            "path": str(request_path.relative_to(song_path)),
            "use": "Bind every placement to the exact captured prompt, roles, preserve/avoid notes, references, and rights context.",
        }] + [
            {
                "id": f"musical-observation-{index}",
                "role": f"arrangement-facing observation for {binding['role']}",
                "path": binding["path"],
                "use": "Bind the selected unchanged phrase boundary and retain pitch/pulse ambiguity without automatic correction.",
            }
            for index, binding in enumerate(observation_bindings, start=1)
        ],
        "tracks": tracks,
        "source_sketch": {
            "seed": sketch_seed,
            "run": str(run_path.relative_to(song_path)),
            "shape": shape,
            "randomness": "role-aware occurrences plus conservative no-boost gain and pan variation",
            "musical_observations": observation_bindings,
        },
    }
    _write_exact_json(score_path, mix_score, "source-sketch mix score")
    destination, sidecar = render_mix(score_path, song_path)

    sketch_dir = song_path / "notes" / "source-sketches" / run_key / sketch_id[:12]
    manifest_path = sketch_dir / "source-sketch.json"
    existing = _existing_sketch(song_path, manifest_path, sketch_id)
    if existing is not None:
        video_value = existing.get("paths", {}).get("visual_preview")
        video_path = _inside(song_path, video_value, "existing visual") if isinstance(video_value, str) else None
        expose_current_media(
            song_path,
            destination,
            video=video_path,
            label=f"{run_record.get('title', song_path.name)} — source-aware sketch {sketch_id[:8]}",
            status="diagnostic",
            note="Uses captured recordings without tuning, quantization, normalization, compression, limiting, or time-stretching.",
        )
        _replace_now(song_path, _now_markdown(song_path, existing))
        return manifest_path, existing

    visual_score_path = song_path / "visuals" / f"{run_key}-source-sketch-{sketch_id[:10]}.json"
    visual_score = compile_prompt(
        f"{run_record.get('prompt', '')}. {clean_intent}. React to the supplied performances and leave negative space.",
        f"{run_record.get('title', song_path.name)} source sketch",
        sketch_seed,
    )
    original_visual = paths.get("visual_score")
    if isinstance(original_visual, str):
        original_path = _inside(song_path, original_visual, "original visual score")
        if original_path.is_file():
            try:
                original = json.loads(original_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                original = {}
            original_avoid = original.get("avoid", []) if isinstance(original, dict) else []
            if isinstance(original_avoid, list):
                visual_score["avoid"] = sorted(set(visual_score["avoid"] + [
                    item for item in original_avoid if isinstance(item, str)
                ]))
    _write_exact_json(visual_score_path, visual_score, "source-sketch visual score")

    visual_path: Path | None = None
    visual_provenance: Path | None = None
    visual_error: str | None = None
    if render_visual_preview:
        visual_path = sketch_dir / "visual-preview.mp4"
        try:
            visual_path, visual_provenance = render_visual(
                visual_score_path,
                destination,
                visual_path,
                seconds=visual_seconds,
                quality="draft",
            )
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            visual_error = str(exc)
            visual_path = None
            visual_provenance = None

    relative_manifest = str(manifest_path.relative_to(song_path))
    record = {
        "schema": SOURCE_SKETCH_SCHEMA,
        "id": sketch_id,
        "created_at": utc_now(),
        "status": "diagnostic-source-arrangement",
        "title": run_record.get("title", song_manifest.get("title", song_path.name)),
        "intent": clean_intent,
        "arrangement": {
            "shape": shape,
            "bed_sha256": bed_sha256,
            "occurrences": sum(len(item["placements"]) for item in source_plans),
            "source_clock_preserved": True,
            "repetition_is_explicit": shape in {"call-response", "loop"},
            "excerpting_is_explicit": shape == "call-response",
        },
        "randomness": {
            "mode": "explicit-replay" if seed_was_supplied else "fresh-entropy",
            "seed": sketch_seed,
            "source": "caller" if seed_was_supplied else "OS entropy via secrets.randbits",
            "creative_fingerprint": creative_fingerprint,
            "novelty": novelty,
            "choices": "explicit arrangement shape, role-aware occurrences, conservative no-boost gain variation, and narrow pan variation",
        },
        "run": {"path": plan["run_path"], "sha256": plan["run_sha256"]},
        "request": {"path": plan["request_path"], "sha256": plan["request_sha256"]},
        "musical_observations": observation_bindings,
        "sources": source_plans,
        "paths": {
            "source_sketch": relative_manifest,
            "mix_score": str(score_path.relative_to(song_path)),
            "mix": str(destination.relative_to(song_path)),
            "mix_provenance": str(sidecar.relative_to(song_path)),
            "visual_score": str(visual_score_path.relative_to(song_path)),
        },
        "outputs": {
            "mix_score_sha256": sha256(score_path),
            "mix": {"sha256": sha256(destination), "probe": probe(destination)},
            "visual_score_sha256": sha256(visual_score_path),
            "visual_preview": (
                {
                    "status": "rendered",
                    "sha256": sha256(visual_path),
                    "probe": probe(visual_path),
                    "provenance_path": str(visual_provenance.relative_to(song_path)),
                    "provenance_sha256": sha256(visual_provenance),
                }
                if visual_path is not None and visual_provenance is not None
                else {"status": "skipped", "reason": visual_error or "disabled"}
            ),
        },
        "render": {
            "automatic_normalization": False,
            "compression": False,
            "limiting": False,
            "time_stretch": False,
            "pitch_correction": False,
            "quantization": False,
        },
        "review": {"decision": "not recorded by renderer", "required": True},
        "authority": {
            "statement": "This is a diagnostic arrangement, not approval of the mix, rights, master, visual, release, upload, or publication."
        },
    }
    if visual_path is not None:
        record["paths"]["visual_preview"] = str(visual_path.relative_to(song_path))
        record["paths"]["visual_provenance"] = str(visual_provenance.relative_to(song_path))
    _write_exact_json(manifest_path, record, "source-sketch manifest")

    latest = load_song_manifest(song_path)
    latest["latest_source_sketch"] = {
        "id": sketch_id,
        "path": relative_manifest,
        "seed": sketch_seed,
        "created_at": record["created_at"],
    }
    (song_path / "song.json").write_text(
        json.dumps(latest, indent=2) + "\n", encoding="utf-8"
    )
    production_map = write_production_map(song_path, run_path)
    record["paths"]["production_map_dot"] = production_map["dot"]["path"]
    if production_map["svg"] is not None:
        record["paths"]["production_map_svg"] = production_map["svg"]["path"]
    manifest_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    expose_current_media(
        song_path,
        destination,
        video=visual_path,
        label=f"{record['title']} — source-aware sketch {sketch_id[:8]}",
        status="diagnostic",
        note="Uses captured recordings without tuning, quantization, normalization, compression, limiting, or time-stretching.",
    )
    _replace_now(song_path, _now_markdown(song_path, record))
    return manifest_path, record
