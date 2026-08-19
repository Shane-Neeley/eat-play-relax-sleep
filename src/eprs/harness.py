"""One-command, agent-led song starts with explicit provenance and replayable entropy.

The harness is deliberately a small orchestration layer over the existing EPRS
records.  It does not pretend that a generated sketch is a finished mix: it
captures the request, queues bounded agent work, renders one audible test, and
leaves a compact handoff at the song root.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import secrets

from .beat import Beat, dumps, load, mutate, parse
from .frontdoor import expose_current_media
from .production_map import write_production_map
from .request import (
    DEFAULT_RIGHTS_NOTE,
    capture_production_request,
    load_production_request,
)
from .system import (
    create_experiment,
    load_song_manifest,
    new_song,
    probe,
    record_experiment_result,
    sha256,
    slugify,
    utc_now,
)
from .visualize import svg
from .visuals import compile_prompt, render_visual
from .work import create_work_item


HARNESS_SCHEMA = "eprs.song-run/v1"
NOVELTY_MAX_ATTEMPTS = 1_024


_BEAT_STUDIES = (
    """title \"Pocket Study\"
tempo 94
meter 4/4
resolution 16
bars 8
swing 0.54
seed 1

track kick  | X... ..x. .... x... | X... .... ..x. x... | ; gain=0.78 humanize_ms=5
track snare | .... X... .... X... | .... X.g. .... X... | ; gain=0.58 humanize_ms=8
track hat   | x.x. x.x. x.x. x.x. | x.x. x.xo x.x. xxx. | ; gain=0.22 pan=0.18 humanize_ms=4
track clap  | .... x... .... x... | .... x... .... x... | ; gain=0.18 pan=-0.22 humanize_ms=10
notes bass  | C2 . . . C2 . G1 . Bb1 . . . G1 . . . | ; voice=bass gain=0.34 length=1.5 pan=-0.08
""",
    """title \"Window Engine\"
tempo 112
meter 5/4
resolution 16
bars 6
swing 0.50
seed 1

track kick   | X... ..x. X... .... x... | ; gain=0.76
track snare  | .... .... X... .... X... | ; gain=0.56 humanize_ms=3
track hat    | x.x. x.x. x.x. x.x. x.x. | ; gain=0.20 pan=0.20
track shaker | .x.x .x.x .x.x .x.x .x.x | ; gain=0.12 pan=-0.25 humanize_ms=7
track tom    | .... .... .... x... ..g. | ; gain=0.24 pan=-0.12
notes bass   | D2 . . D2 . . A1 . C2 . . . A1 . . . G1 . . . | ; voice=bass gain=0.30 length=1.2
""",
    """title \"Sleep Circuit\"
tempo 72
meter 4/4
resolution 16
bars 8
swing 0.62
seed 1

track kick  | X... .... .... ..x. | X... .... .g.. .... | ; gain=0.68
track snare | .... .... X... .... | .... .... X... ..g. | ; gain=0.44 humanize_ms=12
track hat   | x... ..g. x... .... | x... .... x... ..g. | ; gain=0.16 pan=0.26 humanize_ms=9
notes bass  | A1 . . . . . E2 . G2 . . . E2 . . . | ; voice=bass gain=0.26 length=3.2 pan=-0.12
notes glow  | A3+C4+E4 . . . . . . . G3+B3+D4 . . . E3+A3+C4 . . . | ; voice=lead gain=0.12 length=5 pan=0.22
""",
    """title \"Field Signal\"
tempo 104
meter 6/8
resolution 12
bars 8
swing 0.50
seed 1

track kick   | X.. ... ... | X.. ..x ... | ; gain=0.70
track stick  | ... x.. ... | ... ..x ... | ; gain=0.16 pan=-0.12 humanize_ms=8
track shaker | x.x x.x x.x | x.x x.x x.x | ; gain=0.14 pan=0.24 humanize_ms=5
notes call   | D4 . . F4 . . A4 . . | D4 . . G4 . . A4 . . | ; voice=pluck gain=0.15 length=1.1 pan=0.16
notes answer | . . . A3 . . G3 . . | . . . F3 . . D3 . . | ; voice=lead gain=0.13 length=1.4 pan=-0.18
""",
    """title \"String Spark\"
tempo 108
meter 4/4
resolution 16
bars 8
swing 0.52
seed 1

track kick | X... .... ..x. .... | X... .... ...x .... | ; gain=0.68
track stick | .... x... .... x... | .... x... ..g. x... | ; gain=0.18 pan=-0.14 humanize_ms=6
track hat  | ..x. ..x. ..x. ..x. | ..x. .x.. ..x. .x.. | ; gain=0.13 pan=0.22
notes pluck | E3 . G3 . B3 . G3 . D3 . F#3 . A3 . F#3 . | ; voice=pluck gain=0.18 length=0.8 pan=0.12
notes bass  | E2 . . . . . B1 . D2 . . . A1 . . . | ; voice=bass gain=0.27 length=1.2 pan=-0.16
""",
    """title \"Four On The Floor\"
tempo 124
meter 4/4
resolution 16
bars 8
swing 0.50
seed 1

track kick  | X... X... X... X... | X... X... X... X... | ; gain=0.76
track clap  | .... X... .... X... | .... X... .... X... | ; gain=0.26 pan=-0.08
track hat   | ..x. ..x. ..x. ..x. | ..x. ..x. .x.. ..x. | ; gain=0.14 pan=0.20
track shaker | .x.x .x.x .x.x .x.x | .x.x .x.x x.x. .x.x | ; gain=0.10 pan=-0.24 humanize_ms=3
notes bass  | C2 . C2 . G1 . C2 . C2 . C2 . G1 . Bb1 . | ; voice=bass gain=0.30 length=0.85
""",
    """title \"Voice Room\"
tempo 86
meter 3/4
resolution 12
bars 8
swing 0.56
seed 1

track kick | X.. ... ... | X.. ... ..g | ; gain=0.60
track stick | ... x.. ... | ... ..x ... | ; gain=0.12 pan=0.24 humanize_ms=10
notes bed | C3+E3+G3 . . . . . . . . . | A2+C3+E3 . . . . . . . . . | ; voice=lead gain=0.10 length=3.4 pan=-0.08
notes answer | . . . G4 . . A4 . . . E4 . | . . . E4 . . G4 . . . C5 . | ; voice=pluck gain=0.12 length=1.2 pan=0.18
""",
)


def _require_text(value: str | None, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()


def _unique_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    suffix = 2
    while candidate.exists():
        candidate = parent / f"{name}-{suffix}"
        suffix += 1
    return candidate


def _relative(song: Path, path: Path) -> str:
    return str(path.resolve().relative_to(song.resolve()))


def _short_title(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ").strip()


def _starter_beat(title: str, prompt: str, seed: int):
    """Choose and gently mutate a study so the first sketch has a pocket."""
    lowered = prompt.casefold()
    if any(word in lowered for word in ("sleep", "ambient", "drift", "quiet", "slow")):
        study_index = 2
    elif any(word in lowered for word in ("animal", "bird", "frog", "cricket", "cicada", "wildlife", "field recording", "organism")):
        study_index = 3
    elif any(word in lowered for word in ("voice", "vocal", "singer", "singing", "spoken", "speech", "choir")):
        study_index = 6
    elif any(word in lowered for word in ("guitar", "string", "pluck", "ukulele", "marimba", "instrument")):
        study_index = 4
    elif any(word in lowered for word in ("dance", "club", "house", "techno", "four on the floor")):
        study_index = 5
    elif any(word in lowered for word in ("odd", "five", "uneven", "crooked", "broken")):
        study_index = 1
    else:
        study_index = random.Random(seed).randrange(len(_BEAT_STUDIES))

    beat = parse(_BEAT_STUDIES[study_index])
    variation = mutate(beat, seed ^ 0xA5A5_5A5A, amount=0.14)
    rng = random.Random(seed ^ 0x51_7E_11)
    if any(word in lowered for word in ("fast", "dance", "club", "push", "bright")):
        tempo = rng.randint(116, 132)
    elif any(word in lowered for word in ("sleep", "ambient", "drift", "quiet", "slow")):
        tempo = rng.randint(66, 82)
    else:
        tempo = round(variation.tempo + rng.randint(-5, 5))
    if variation.meter == (5, 4):
        tempo = max(78, min(132, tempo))
    else:
        tempo = max(60, min(132, tempo))
    swing = variation.swing
    if "straight" in lowered:
        swing = 0.5
    elif "swing" in lowered or "shuffle" in lowered:
        swing = round(rng.uniform(0.57, 0.68), 3)
    variation.title = f"{_short_title(title)} · agent sketch"
    variation.tempo = tempo
    variation.swing = swing
    variation.seed = seed
    return variation


def _beat_creative_fingerprint(beat) -> str:
    """Hash audible BeatScript choices while excluding labels and replay seed."""
    payload = {
        # BeatScript parses a serialized whole-number tempo as a float. Keep
        # the fingerprint stable across the in-memory -> file -> parser round
        # trip so prior artifacts can actually block a duplicate structure.
        "tempo": float(beat.tempo),
        "meter": list(beat.meter),
        "resolution": beat.resolution,
        "bars": beat.bars,
        "swing": beat.swing,
        "tracks": [{
            "name": track.name,
            "kind": track.kind,
            "steps": track.steps,
            "options": track.options,
        } for track in beat.tracks],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _prior_starter_fingerprints(song: Path) -> set[str]:
    fingerprints: set[str] = set()
    for run_path in (song / "notes" / "runs").glob("*/run.json"):
        try:
            record = json.loads(run_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("schema") != HARNESS_SCHEMA:
            continue
        beat_value = record.get("paths", {}).get("beat")
        if isinstance(beat_value, str):
            beat_path = (song / beat_value).resolve()
            try:
                beat_path.relative_to(song.resolve())
                fingerprints.add(_beat_creative_fingerprint(load(beat_path)))
                continue
            except (FileNotFoundError, ValueError):
                pass
        randomness = record.get("randomness")
        stored = randomness.get("creative_fingerprint") if isinstance(randomness, dict) else None
        if isinstance(stored, str) and len(stored) == 64:
            fingerprints.add(stored)
    return fingerprints


def _choose_starter(
    song: Path,
    title: str,
    prompt: str,
    seed: int | None,
) -> tuple[int, Beat, str, dict]:
    if seed is not None:
        chosen_seed = int(seed)
        beat = _starter_beat(title, prompt, chosen_seed)
        return chosen_seed, beat, _beat_creative_fingerprint(beat), {
            "enforced": False,
            "scope": "explicit seed replay may intentionally match prior song artifacts",
            "collision_rejections": 0,
        }
    prior = _prior_starter_fingerprints(song)
    for attempt in range(1, NOVELTY_MAX_ATTEMPTS + 1):
        chosen_seed = secrets.randbits(63)
        beat = _starter_beat(title, prompt, chosen_seed)
        fingerprint = _beat_creative_fingerprint(beat)
        if fingerprint not in prior:
            return chosen_seed, beat, fingerprint, {
                "enforced": True,
                "scope": "song-local BeatScript musical structure excluding title and seed",
                "prior_fingerprints_checked": len(prior),
                "collision_rejections": attempt - 1,
                "maximum_attempts": NOVELTY_MAX_ATTEMPTS,
            }
    raise RuntimeError(
        f"could not find a new starter structure after {NOVELTY_MAX_ATTEMPTS} entropy draws"
    )


def _agent_brief(
    title: str,
    prompt: str,
    seed: int,
    references: list[str],
    preserve: list[str],
    avoid: list[str],
    has_supplied_recordings: bool,
    prompt_routes: list[dict] | None = None,
) -> str:
    lines = [
        "---",
        "schema: eprs.agent-song-brief/v1",
        f"title: {_short_title(title)}",
        "status: starter-preview",
        f"seed: {seed}",
        "---",
        "",
        "# Agent handoff",
        "",
        f"{prompt}",
        "",
        "## Operating contract",
        "",
        "This is a generated starting point, not approval to publish. Preserve raw recordings, keep processing reversible, and make one audible hypothesis at a time.",
        "Fresh runs use new entropy. Pass the seed back to `make-song --song ... --seed ...` when an exact replay is needed.",
        "",
        "## Preserve",
        "",
    ]
    lines.extend(f"- {item}" for item in (preserve or ["human timing, breath, room, and deliberate roughness"]))
    lines.extend(["", "## Avoid", ""])
    lines.extend(f"- {item}" for item in (avoid or ["automatic tuning, denoising, loudness chasing, and generic replacement parts"]))
    if references:
        lines.extend(["", "## References and leads", ""])
        lines.extend(f"- {item}" for item in references)
    if prompt_routes:
        lines.extend(["", "## Prompt routes", ""])
        for route in prompt_routes:
            if not isinstance(route, dict):
                continue
            label = route.get("label", route.get("id", "route"))
            first_action = route.get("first_action", "inspect the route before acting")
            tools = route.get("optional_tools", [])
            tool_text = f"; optional tools: {', '.join(tools)}" if tools else ""
            lines.append(f"- **{label}**: {first_action}{tool_text}")
    lines.extend([
        "",
        "## First listen",
        "",
        "Listen end to end for the pocket, the answer between phrases, the amount of negative space, and whether the source material still has a place to become the emotional foreground.",
        "",
    ])
    if has_supplied_recordings:
        lines.extend([
            "",
            "## Source-use warning",
            "",
            "The starter audio is a synthetic control and does not contain the supplied recordings. Inspect and audition those request-bound sources before claiming that the song uses them.",
        ])
    return "\n".join(lines)


def _now_markdown(song: Path, manifest: dict) -> str:
    paths = manifest["paths"]
    visual = paths.get("visual_preview")
    visual_line = f"- Visual preview: `{visual}`\n" if visual else "- Visual preview: not rendered (run `eprs visual-render` after installing visual dependencies)\n"
    map_value = paths.get("production_map_svg") or paths.get("production_map_dot")
    map_line = f"- Production map: `{map_value}`\n" if map_value else ""
    source_warning = (
        "\n> Source-use warning: the starter is a synthetic control. It does not yet contain the supplied recordings.\n"
        if manifest["starter"]["supplied_recordings_used"] is False
        and manifest["inputs"]["recordings"]
        else ""
    )
    novelty = manifest["randomness"].get("novelty", {})
    novelty_line = (
        f"- Novelty: checked `{novelty.get('prior_fingerprints_checked', 0)}` prior "
        f"musical structure(s); rejected `{novelty.get('collision_rejections', 0)}` collision(s)\n"
        if novelty.get("enforced") else
        "- Novelty: explicit seed replay; matching a prior artifact is allowed\n"
    )
    routes = manifest.get("input_routes", {})
    prompt_routes = routes.get("prompt", []) if isinstance(routes, dict) else []
    provided_routes = routes.get("provided", []) if isinstance(routes, dict) else []
    reference_routes = routes.get("references", []) if isinstance(routes, dict) else []
    prompt_lines = [
        f"- **{item.get('label', item.get('id', 'route'))}**: {item.get('first_action', '')}"
        for item in prompt_routes if isinstance(item, dict)
    ]
    routing_lines = [
        f"- **{item['role']}** (`{item['family']}`): {item['first_action']}"
        for item in provided_routes if isinstance(item, dict)
    ]
    routing_lines.extend(
        f"- **Reference** (`{item['family']}`): {item['first_action']} — `{item['reference']}`"
        for item in reference_routes if isinstance(item, dict)
    )
    if not routing_lines:
        routing_lines = ["- No files or research leads were supplied in this run."]
    routing_text = "\n".join(routing_lines)
    prompt_text = "\n".join(prompt_lines) or "- Open-ended creative direction; choose one smallest experiment."
    return f"""<!-- eprs.now/v1 -->
# Current song run

This file is the shallow entry point for the latest agent-led run. The generated sketch is intentionally not a release or a listening approval.
{source_warning}

- Song: `{manifest['title']}`
- Run: `{manifest['id']}`
- Seed: `{manifest['randomness']['seed']}` ({manifest['randomness']['mode']})
{novelty_line}- Request: `{paths['request']}`
- Agent work: `{paths['agent_work']}`
- Starter BeatScript: `{paths['beat']}`
- Starter audio: `{paths['audio_preview']}`
- Rhythm map: `{paths['rhythm_map']}`
{visual_line}{map_line}- Run manifest: `{paths['run_manifest']}`

## Input routing

### Prompt routes

{prompt_text}

### Supplied files and references

{routing_text}

These are inspectable first-action suggestions, not processing, browsing, sampling, approval, or publication authority. Read the exact request rights notes before acting.

## Next move

1. Listen to the starter audio and decide keep/change/stop.
2. Inspect the bounded handoff with `./scripts/eprs context {song} --request {paths['request']} --verify --format markdown`.
3. Let an agent claim the queued planning work with `./scripts/eprs dispatch next --song {song} --agent <agent-name>`.
4. For a fresh variation, rerun `make-song` without `--seed`. For an exact replay, pass seed `{manifest['randomness']['seed']}`.

The harness never uploads or publishes. Promotion to a master, video approval, FINAL packaging, and platform publication remain separate gates.
"""


def create_song_run(
    title: str | None,
    prompt: str,
    *,
    root: str | Path = "songs",
    song: str | Path | None = None,
    seed: int | None = None,
    recordings: list[tuple[str, str | Path]] | None = None,
    evidence: list[tuple[str, str | Path]] | None = None,
    references: list[str] | None = None,
    preserve: list[str] | None = None,
    avoid: list[str] | None = None,
    questions: list[str] | None = None,
    rights_note: str = DEFAULT_RIGHTS_NOTE,
    render_visual_preview: bool = True,
    visual_seconds: float = 8.0,
) -> tuple[Path, dict]:
    """Create one inspectable song run and return its run manifest.

    The default seed comes from OS entropy. An explicit seed is the escape hatch
    for exact diagnostic replay, so novelty and debuggability can coexist.
    """
    prompt = _require_text(prompt, "prompt")
    references = list(references or [])
    preserve = list(preserve or [])
    avoid = list(avoid or [])
    questions = list(questions or [])
    if visual_seconds <= 0:
        raise ValueError("visual_seconds must be positive")
    if song is None:
        title = _require_text(title, "title")
        song_path = new_song(root, title).resolve()
        run_title = title
    else:
        song_path = Path(song).resolve()
        song_manifest = load_song_manifest(song_path)
        run_title = (title or song_manifest.get("title") or song_path.name).strip()
        if not run_title:
            raise ValueError("existing song has no usable title")
    seed_was_supplied = seed is not None
    run_seed, beat, creative_fingerprint, novelty = _choose_starter(
        song_path, run_title, prompt, seed
    )
    slug = slugify(run_title) or "song"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{slug}-{run_seed:x}"[:180]
    run_dir = _unique_path(song_path / "notes" / "runs", run_id)
    run_dir.mkdir(parents=True, exist_ok=False)

    request_path = capture_production_request(
        song_path,
        f"{run_title} intake",
        prompt,
        preserve=preserve,
        avoid=avoid,
        questions=questions,
        deliverables=["Seeded audio sketch", "Audio-reactive visual preview", "Agent-ready next steps"],
        references=references,
        recordings=recordings,
        evidence=evidence,
        rights_note=rights_note,
    )
    request_record = load_production_request(song_path, request_path)[1]
    provided_records = list(request_record.get("provided", {}).values())
    recording_count = sum(item.get("handling") == "immutable-recording" for item in provided_records)
    evidence_count = sum(item.get("handling") == "frozen-evidence" for item in provided_records)
    work_path = create_work_item(song_path, None, None, None, request=request_path)

    # Include the run id in editable filenames so an exact replay never
    # overwrites a previous source or a user's later hand edit.
    file_key = run_dir.name
    code_path = song_path / "code" / f"{file_key}.beat"
    visual_score_path = song_path / "visuals" / f"{file_key}.json"
    brief_path = song_path / "code" / f"{file_key}.md"
    code_path.write_text(dumps(beat), encoding="utf-8")
    brief_path.write_text(
        _agent_brief(
            run_title, prompt, run_seed, references, preserve, avoid,
            has_supplied_recordings=bool(recording_count),
            prompt_routes=request_record.get("input_routes", {}).get("prompt", []),
        ),
        encoding="utf-8",
    )
    visual_score = compile_prompt(
        f"{prompt}. Preserve a little human asymmetry and negative space; seed {run_seed}.",
        run_title,
        run_seed,
    )
    visual_score["avoid"] = sorted(set(visual_score["avoid"] + avoid))
    visual_score_path.write_text(json.dumps(visual_score, indent=2) + "\n", encoding="utf-8")

    experiment = create_experiment(
        song_path,
        code_path,
        brief_path,
        "Does this first seeded sketch leave a useful pocket for the supplied idea?",
        run_seed,
        sources=[("visual score", visual_score_path)],
    )
    audio_path = experiment / "starter-audio.wav"
    from .audio import render
    render(load(code_path), audio_path)
    record_experiment_result(
        experiment,
        audio_path,
        "Technical render completed; no creative listening decision was inferred.",
    )
    rhythm_map = run_dir / "rhythm-map.svg"
    svg(load(code_path), rhythm_map)

    visual_preview: Path | None = None
    visual_error: str | None = None
    if render_visual_preview:
        visual_preview = run_dir / "visual-preview.mp4"
        try:
            render_visual(visual_score_path, audio_path, visual_preview, seconds=visual_seconds, quality="draft")
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            visual_error = str(exc)
            visual_preview = None

    paths = {
        "request": _relative(song_path, request_path),
        "agent_work": _relative(song_path, work_path),
        "beat": _relative(song_path, code_path),
        "brief": _relative(song_path, brief_path),
        "visual_score": _relative(song_path, visual_score_path),
        "experiment": _relative(song_path, experiment),
        "audio_preview": _relative(song_path, audio_path),
        "rhythm_map": _relative(song_path, rhythm_map),
    }
    if visual_preview is not None:
        paths["visual_preview"] = _relative(song_path, visual_preview)
    run_manifest_path = run_dir / "run.json"
    paths["run_manifest"] = _relative(song_path, run_manifest_path)
    manifest = {
        "schema": HARNESS_SCHEMA,
        "id": run_dir.name,
        "created_at": utc_now(),
        "title": run_title,
        "prompt": prompt,
        "request_id": request_record["id"],
        "randomness": {
            "mode": "explicit-replay" if seed_was_supplied else "fresh-entropy",
            "seed": run_seed,
            "source": "caller" if seed_was_supplied else "OS entropy via secrets.randbits",
            "creative_fingerprint": creative_fingerprint,
            "novelty": novelty,
            "replay_command": f"./scripts/eprs make-song --song {song_path} --prompt {prompt!r} --seed {run_seed}",
        },
        "status": "starter-preview",
        "inputs": {
            "recordings": recording_count,
            "evidence": evidence_count,
            "references": len(references),
        },
        "input_routes": request_record.get("input_routes", {
            "provided": [], "references": [],
            "authority": "No routing metadata was recorded.",
        }),
        "starter": {
            "purpose": "synthetic diagnostic control, not a source-aware arrangement",
            "supplied_recordings_used": False,
            "creative_approval": False,
        },
        "paths": paths,
        "outputs": {
            "audio": {"sha256": sha256(audio_path), "probe": probe(audio_path)},
            "beat": {"sha256": sha256(code_path)},
            "visual_score": {"sha256": sha256(visual_score_path)},
            "rhythm_map": {"sha256": sha256(rhythm_map)},
            "visual_preview": (
                {"sha256": sha256(visual_preview), "probe": probe(visual_preview)}
                if visual_preview is not None else {"status": "skipped", "reason": visual_error or "disabled"}
            ),
        },
        "next": [
            "Listen to the full starter audio before making a creative decision.",
            "Audition and develop supplied recordings separately; the synthetic starter does not contain them.",
            "Inspect the request and claim the queued planning work with a bounded agent context.",
            "Keep raw recordings immutable and confirm participant rights before any public release.",
        ],
    }
    run_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    production_map = write_production_map(song_path, run_manifest_path)
    paths["production_map_dot"] = production_map["dot"]["path"]
    if production_map["svg"] is not None:
        paths["production_map_svg"] = production_map["svg"]["path"]
    manifest["outputs"]["production_map"] = production_map
    run_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (song_path / "NOW.md").write_text(_now_markdown(song_path, manifest), encoding="utf-8")
    expose_current_media(
        song_path,
        audio_path,
        video=visual_preview,
        label=f"{run_title} — generated starter run {manifest['id']}",
        status="diagnostic",
        note=(
            "Synthetic starter does not contain supplied recordings."
            if recording_count else "Synthetic starter awaiting a complete listen."
        ),
    )

    song_manifest_path = song_path / "song.json"
    song_manifest = load_song_manifest(song_path)
    song_manifest["status"] = "prototype"
    song_manifest["latest_run"] = {
        "id": manifest["id"],
        "path": paths["run_manifest"],
        "seed": run_seed,
        "created_at": manifest["created_at"],
    }
    song_manifest["harness"] = {
        "schema": HARNESS_SCHEMA,
        "fresh_entropy_by_default": True,
        "fresh_artifact_novelty_check": True,
    }
    song_manifest_path.write_text(json.dumps(song_manifest, indent=2) + "\n", encoding="utf-8")
    return run_manifest_path, manifest
