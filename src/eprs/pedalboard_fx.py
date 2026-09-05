"""Pinned, declarative Spotify Pedalboard rendering for EPRS working stems."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any

from .evidence import bind_song_evidence, verify_evidence_bindings
from .system import analyze, load_song_manifest, probe, sha256, slugify, utc_now


PEDALBOARD_SCHEMA = "eprs.pedalboard/v1"
PEDALBOARD_RENDER_SCHEMA = "eprs.pedalboard-render/v1"
OUTPUT_CODEC = "pcm_f32le"
REVIEW_DECISIONS = {"keep", "change", "stop"}
SOURCE_REPOSITORY = "https://github.com/spotify/pedalboard"
SOURCE_REVISION = "a3f824ff3026eac6f409b538a5df1d10f46eba32"
MAX_DEPTH = 4
MAX_PLUGINS = 64


def _number(record: dict, key: str, low: float, high: float, default: float | None = None) -> float:
    value = record.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Pedalboard parameter {key} must be a number")
    number = float(value)
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"Pedalboard parameter {key} must be between {low:g} and {high:g}")
    return number


def _require_backend() -> tuple[Any, Any, Any]:
    try:
        import numpy as np
        import pedalboard
        from pedalboard.io import AudioFile
    except ImportError as exc:  # pragma: no cover - depends on optional wheel
        raise RuntimeError(
            "Pedalboard is not installed; run `make pedalboard-install` or "
            "`uv sync --extra pedalboard` in the EPRS checkout"
        ) from exc
    return pedalboard, AudioFile, np


def _normalize_plugin(value: object, sample_rate: int, depth: int, path: str) -> dict:
    if depth > MAX_DEPTH:
        raise ValueError(f"Pedalboard plugin nesting exceeds {MAX_DEPTH} levels at {path}")
    if not isinstance(value, dict):
        raise ValueError(f"Pedalboard plugin {path} must be an object")
    raw_type = value.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise ValueError(f"Pedalboard plugin {path} requires a type")
    kind = raw_type.strip().lower().replace("-", "_")
    aliases = {"hpf": "highpass_filter", "lpf": "lowpass_filter", "parallel": "mix"}
    kind = aliases.get(kind, kind)
    normalized: dict[str, Any] = {"type": kind}
    nyquist = min(40_000.0, sample_rate * 0.49)
    if kind in {"chain", "mix"}:
        if kind == "chain":
            children = value.get("plugins")
            if not isinstance(children, list) or not children:
                raise ValueError(f"Pedalboard chain {path} requires at least one plugin")
            normalized["plugins"] = [
                _normalize_plugin(child, sample_rate, depth + 1, f"{path}.plugins[{index}]")
                for index, child in enumerate(children)
            ]
        else:
            branches = value.get("branches")
            if not isinstance(branches, list) or not branches or len(branches) > 8:
                raise ValueError(f"Pedalboard mix {path} requires 1 to 8 branches")
            normalized["branches"] = []
            for branch_index, branch in enumerate(branches):
                if not isinstance(branch, list) or not branch:
                    raise ValueError(f"Pedalboard mix branch {path}[{branch_index}] is empty")
                normalized["branches"].append([
                    _normalize_plugin(item, sample_rate, depth + 1, f"{path}.branches[{branch_index}][{index}]")
                    for index, item in enumerate(branch)
                ])
        return normalized

    if kind in {"gain", "distortion", "clipping", "bitcrush", "pitch_shift"}:
        fields = {
            "gain": ("gain_db", -90, 36, 1),
            "distortion": ("drive_db", 0, 100, 25),
            "clipping": ("threshold_db", -36, 0, -6),
            "bitcrush": ("bit_depth", 0, 32, 8),
            "pitch_shift": ("semitones", -72, 72, 0),
        }
        key, low, high, default = fields[kind]
        normalized[key] = _number(value, key, low, high, default)
        return normalized

    if kind in {"compressor", "noise_gate"}:
        normalized.update({
            "threshold_db": _number(value, "threshold_db", -100, 0, -18 if kind == "compressor" else -80),
            "ratio": _number(value, "ratio", 1, 100, 4 if kind == "compressor" else 10),
            "attack_ms": _number(value, "attack_ms", 0.01, 2000, 20),
            "release_ms": _number(value, "release_ms", 0.01, 9000, 250),
        })
        return normalized

    if kind in {"highpass_filter", "lowpass_filter"}:
        normalized["cutoff_frequency_hz"] = _number(
            value, "cutoff_frequency_hz", 10, nyquist, 50 if kind == "highpass_filter" else min(18_000, nyquist)
        )
        return normalized

    if kind == "ladder_filter":
        mode = value.get("mode", "LPF24")
        if not isinstance(mode, str) or mode not in {"LPF12", "HPF12", "BPF12", "LPF24", "HPF24", "BPF24"}:
            raise ValueError("Pedalboard ladder_filter mode is invalid")
        normalized.update({
            "mode": mode,
            "cutoff_hz": _number(value, "cutoff_hz", 10, nyquist, 800),
            "resonance": _number(value, "resonance", 0, 1, 0.2),
            "drive": _number(value, "drive", 0, 10, 1),
        })
        return normalized

    if kind in {"chorus", "phaser"}:
        normalized.update({
            "rate_hz": _number(value, "rate_hz", 0, 100, 0.8 if kind == "chorus" else 0.35),
            "depth": _number(value, "depth", 0, 1, 0.25 if kind == "chorus" else 0.5),
            "feedback": _number(value, "feedback", -1, 1, 0),
            "mix": _number(value, "mix", 0, 1, 0.5),
        })
        if kind == "chorus":
            normalized["centre_delay_ms"] = _number(value, "centre_delay_ms", 0, 100, 7)
        else:
            normalized["centre_frequency_hz"] = _number(value, "centre_frequency_hz", 10, nyquist, 1300)
        return normalized

    if kind == "delay":
        normalized.update({
            "delay_seconds": _number(value, "delay_seconds", 0, 30, 0.25),
            "feedback": _number(value, "feedback", 0, 0.99, 0.25),
            "mix": _number(value, "mix", 0, 1, 0.35),
        })
        return normalized

    if kind == "reverb":
        normalized.update({
            "room_size": _number(value, "room_size", 0, 1, 0.5),
            "damping": _number(value, "damping", 0, 1, 0.5),
            "wet_level": _number(value, "wet_level", 0, 1, 0.33),
            "dry_level": _number(value, "dry_level", 0, 1, 0.4),
            "width": _number(value, "width", 0, 1, 1),
            "freeze_mode": _number(value, "freeze_mode", 0, 1, 0),
        })
        return normalized

    if kind in {"limiter", "invert"}:
        if kind == "limiter":
            normalized.update({
                "threshold_db": _number(value, "threshold_db", -30, 0, -1),
                "release_ms": _number(value, "release_ms", 0.01, 9000, 100),
            })
        return normalized
    raise ValueError(f"unsupported Pedalboard plugin type: {kind}")


def _instantiate_plugin(spec: dict, pedalboard: Any) -> Any:
    kind = spec["type"]
    if kind == "chain":
        return pedalboard.Pedalboard([_instantiate_plugin(item, pedalboard) for item in spec["plugins"]])
    if kind == "mix":
        branches = [
            pedalboard.Pedalboard([_instantiate_plugin(item, pedalboard) for item in branch])
            for branch in spec["branches"]
        ]
        return pedalboard.Mix(branches)
    if kind == "gain":
        return pedalboard.Gain(gain_db=spec["gain_db"])
    if kind == "distortion":
        return pedalboard.Distortion(drive_db=spec["drive_db"])
    if kind == "clipping":
        return pedalboard.Clipping(threshold_db=spec["threshold_db"])
    if kind == "bitcrush":
        return pedalboard.Bitcrush(bit_depth=spec["bit_depth"])
    if kind == "pitch_shift":
        return pedalboard.PitchShift(semitones=spec["semitones"])
    if kind in {"compressor", "noise_gate"}:
        klass = pedalboard.Compressor if kind == "compressor" else pedalboard.NoiseGate
        return klass(
            threshold_db=spec["threshold_db"], ratio=spec["ratio"],
            attack_ms=spec["attack_ms"], release_ms=spec["release_ms"],
        )
    if kind == "highpass_filter":
        return pedalboard.HighpassFilter(cutoff_frequency_hz=spec["cutoff_frequency_hz"])
    if kind == "lowpass_filter":
        return pedalboard.LowpassFilter(cutoff_frequency_hz=spec["cutoff_frequency_hz"])
    if kind == "ladder_filter":
        return pedalboard.LadderFilter(
            mode=getattr(pedalboard.LadderFilter.Mode, spec["mode"]),
            cutoff_hz=spec["cutoff_hz"], resonance=spec["resonance"], drive=spec["drive"],
        )
    if kind == "chorus":
        return pedalboard.Chorus(
            rate_hz=spec["rate_hz"], depth=spec["depth"], centre_delay_ms=spec["centre_delay_ms"],
            feedback=spec["feedback"], mix=spec["mix"],
        )
    if kind == "phaser":
        return pedalboard.Phaser(
            rate_hz=spec["rate_hz"], depth=spec["depth"], centre_frequency_hz=spec["centre_frequency_hz"],
            feedback=spec["feedback"], mix=spec["mix"],
        )
    if kind == "delay":
        return pedalboard.Delay(
            delay_seconds=spec["delay_seconds"], feedback=spec["feedback"], mix=spec["mix"],
        )
    if kind == "reverb":
        return pedalboard.Reverb(
            room_size=spec["room_size"], damping=spec["damping"], wet_level=spec["wet_level"],
            dry_level=spec["dry_level"], width=spec["width"], freeze_mode=spec["freeze_mode"],
        )
    if kind == "limiter":
        return pedalboard.Limiter(threshold_db=spec["threshold_db"], release_ms=spec["release_ms"])
    if kind == "invert":
        return pedalboard.Invert()
    raise ValueError(f"unsupported normalized Pedalboard plugin type: {kind}")


def _source(song: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Pedalboard recipe requires a source path")
    requested = Path(value)
    if requested.is_absolute():
        raise ValueError("Pedalboard source path must be relative to the song")
    source = (song / requested).resolve()
    try:
        source.relative_to(song.resolve())
    except ValueError as exc:
        raise ValueError("Pedalboard source path escapes the song workspace") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def _stem_path(song: Path, value: str) -> Path:
    requested = Path(value)
    stem_path = requested.resolve() if requested.is_absolute() else (song / requested).resolve()
    try:
        stem_path.relative_to((song / "stems").resolve())
    except ValueError as exc:
        raise ValueError("Pedalboard stem must be inside the song stems directory") from exc
    return stem_path


def verify_pedalboard_provenance(song: str | Path, stem: str | Path) -> tuple[Path, Path, dict]:
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    stem_path = _stem_path(song_path, str(stem))
    if not stem_path.is_file():
        raise FileNotFoundError(stem_path)
    sidecar = stem_path.with_suffix(stem_path.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"Pedalboard provenance sidecar not found: {sidecar}")
    try:
        metadata = json.loads(sidecar.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Pedalboard provenance JSON: {sidecar}: {exc.msg}") from exc
    if metadata.get("schema") != PEDALBOARD_RENDER_SCHEMA:
        raise ValueError("unsupported Pedalboard provenance schema")
    recipe = metadata.get("recipe")
    if not isinstance(recipe, dict) or recipe.get("schema") != PEDALBOARD_SCHEMA:
        raise ValueError("Pedalboard provenance has an invalid recipe")
    expected_recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if metadata.get("recipe_id") != expected_recipe_id:
        raise ValueError("Pedalboard recipe id does not match its recipe")
    verify_evidence_bindings(song_path, recipe.get("evidence", []), "Pedalboard stem")
    output = metadata.get("output")
    if not isinstance(output, dict) or output.get("path") != str(stem_path.relative_to(song_path)):
        raise ValueError("Pedalboard provenance has an invalid output path")
    if output.get("sha256") != sha256(stem_path):
        raise ValueError("Pedalboard output checksum has changed")
    source = metadata.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        raise ValueError("Pedalboard provenance has an invalid source")
    source_path = _source(song_path, source["path"])
    if source.get("sha256") != sha256(source_path):
        raise ValueError("Pedalboard source is missing or changed")
    return stem_path, sidecar, metadata


def review_pedalboard(
    song: str | Path, stem: str | Path, listening_note: str, decision: str
) -> Path:
    note = listening_note.strip()
    if not note:
        raise ValueError("Pedalboard review requires a listening note")
    if decision not in REVIEW_DECISIONS:
        raise ValueError("Pedalboard review decision must be keep, change, or stop")
    _, sidecar, metadata = verify_pedalboard_provenance(song, stem)
    review = metadata.setdefault("review", {})
    notes = review.setdefault("listening_notes", [])
    if not isinstance(notes, list):
        raise ValueError("Pedalboard listening_notes must be a list")
    if not any(isinstance(record, dict) and record.get("note") == note and record.get("decision") == decision for record in notes):
        notes.append({"reviewed_at": utc_now(), "note": note, "decision": decision})
    review["decision"] = decision
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return sidecar


def render_pedalboard(spec: str | Path, song: str | Path) -> tuple[Path, Path]:
    pedalboard, AudioFile, np = _require_backend()
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    spec_path = Path(spec)
    if not spec_path.is_file():
        raise FileNotFoundError(spec_path)
    try:
        score = json.loads(spec_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Pedalboard JSON: {spec_path}: {exc.msg}") from exc
    if score.get("schema") != PEDALBOARD_SCHEMA:
        raise ValueError(f"unsupported Pedalboard schema: {score.get('schema')}")
    title = score.get("title")
    role = score.get("role")
    intent = score.get("intent")
    for name, value in (("title", title), ("role", role), ("intent", intent)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Pedalboard recipe requires {name}")
    title_slug = slugify(title)
    role_slug = slugify(role)
    if not title_slug or not role_slug:
        raise ValueError("Pedalboard title and role must contain a letter or number")
    source_path = _source(song_path, score.get("source"))
    source_probe = probe(source_path)
    audio_stream = next((stream for stream in source_probe.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if audio_stream is None:
        raise ValueError("Pedalboard source has no audio stream")
    sample_rate = int(audio_stream.get("sample_rate") or 0)
    channels = int(audio_stream.get("channels") or 0)
    source_duration = float(source_probe.get("format", {}).get("duration") or 0)
    if not 8_000 <= sample_rate <= 192_000 or channels not in {1, 2} or source_duration <= 0:
        raise ValueError("Pedalboard v1 requires mono/stereo audio with known rate and duration")
    buffer_size_value = score.get("buffer_size", 16_384)
    if isinstance(buffer_size_value, bool) or not isinstance(buffer_size_value, int) or not 128 <= buffer_size_value <= 262_144:
        raise ValueError("Pedalboard buffer_size must be an integer between 128 and 262144")
    tail_seconds = _number(score, "tail_seconds", 0, 10, 0)
    plugins_value = score.get("plugins")
    if not isinstance(plugins_value, list) or not plugins_value:
        raise ValueError("Pedalboard recipe requires at least one plugin")
    if len(plugins_value) > MAX_PLUGINS:
        raise ValueError(f"Pedalboard recipe supports at most {MAX_PLUGINS} top-level plugins")
    plugins = [_normalize_plugin(value, sample_rate, 0, f"plugins[{index}]") for index, value in enumerate(plugins_value)]
    evidence = bind_song_evidence(song_path, score.get("evidence"), "Pedalboard")
    source_relative = str(source_path.relative_to(song_path))
    recipe = {
        "schema": PEDALBOARD_SCHEMA,
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "source_path": source_relative,
        "source_sha256": sha256(source_path),
        "sample_rate": sample_rate,
        "channels": channels,
        "buffer_size": buffer_size_value,
        "tail_seconds": tail_seconds,
        "output_codec": OUTPUT_CODEC,
        "evidence": evidence,
        "plugins": plugins,
    }
    recipe_id = hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    destination_dir = song_path / "stems" / role_slug / title_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{recipe_id[:10]}-{title_slug}.wav"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists():
        if not sidecar.is_file():
            raise FileExistsError(f"Pedalboard stem exists without provenance: {destination}")
        existing = json.loads(sidecar.read_text())
        if existing.get("recipe_id") == recipe_id and existing.get("output", {}).get("sha256") == sha256(destination):
            return destination, sidecar
        raise FileExistsError(f"Pedalboard destination exists with different provenance: {destination}")
    temporary = destination_dir / f".{recipe_id[:10]}-{title_slug}.partial.wav"
    if temporary.exists():
        raise FileExistsError(f"Incomplete Pedalboard render already exists: {temporary}")
    board = pedalboard.Pedalboard([_instantiate_plugin(plugin, pedalboard) for plugin in plugins])
    started = time.perf_counter()
    try:
        with AudioFile(str(source_path)) as reader:
            with AudioFile(
                str(temporary), "w", samplerate=reader.samplerate,
                num_channels=reader.num_channels, bit_depth=32,
            ) as writer:
                first = True
                while reader.tell() < reader.frames:
                    chunk = reader.read(min(buffer_size_value, reader.frames - reader.tell()))
                    if chunk.shape[1] == 0:
                        break
                    effected = board.process(chunk, sample_rate=reader.samplerate, buffer_size=buffer_size_value, reset=first)
                    writer.write(effected)
                    first = False
                tail_frames = round(tail_seconds * reader.samplerate)
                for start in range(0, tail_frames, buffer_size_value):
                    count = min(buffer_size_value, tail_frames - start)
                    silence = np.zeros((reader.num_channels, count), dtype=np.float32)
                    writer.write(board.process(silence, sample_rate=reader.samplerate, buffer_size=buffer_size_value, reset=False))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    if sha256(source_path) != recipe["source_sha256"]:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Pedalboard source changed during rendering")
    try:
        verify_evidence_bindings(song_path, evidence, "Pedalboard render")
    except (FileNotFoundError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Pedalboard evidence changed during rendering: {exc}") from exc
    output_probe = probe(temporary)
    output_stream = next((stream for stream in output_probe.get("streams", []) if stream.get("codec_type") == "audio"), {})
    actual_duration = float(output_probe.get("format", {}).get("duration") or 0)
    expected_duration = source_duration + tail_seconds
    verification = {
        "float32_pcm": output_stream.get("codec_name") == OUTPUT_CODEC,
        "sample_rate_preserved": output_stream.get("sample_rate") == str(sample_rate),
        "channels_preserved": output_stream.get("channels") == channels,
        "duration_expected": abs(actual_duration - expected_duration) <= max(0.05, expected_duration * 0.002),
    }
    failed = [name for name, passed in verification.items() if not passed]
    if failed:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Pedalboard render failed verification: {', '.join(failed)}")
    output_analysis = analyze(temporary)
    output_analysis.pop("path", None)
    warnings = [
        "This is a float working stem; use EPRS master v1 for the final 24-bit lossless export and peak ceiling.",
        "Pedalboard native processing is deterministic for this recipe; no external VST3 or Audio Unit state is included.",
    ]
    temporary.rename(destination)
    metadata = {
        "schema": PEDALBOARD_RENDER_SCHEMA,
        "recipe_id": recipe_id,
        "rendered_at": utc_now(),
        "title": title.strip(),
        "role": role.strip(),
        "intent": intent.strip(),
        "pedalboard": {
            "package": "pedalboard",
            "version": getattr(pedalboard, "__version__", "0.9.24"),
            "repository": SOURCE_REPOSITORY,
            "revision": SOURCE_REVISION,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
        },
        "recipe": recipe,
        "source": {"path": source_relative, "sha256": recipe["source_sha256"], "probe": source_probe},
        "output": {
            "path": str(destination.relative_to(song_path)),
            "sha256": sha256(destination),
            "probe": output_probe,
            "analysis": output_analysis,
        },
        "verification": verification,
        "warnings": warnings,
        "review": {"decision": "not recorded by renderer", "listening_notes": []},
    }
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n")
    return destination, sidecar
