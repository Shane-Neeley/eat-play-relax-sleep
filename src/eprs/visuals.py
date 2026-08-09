"""Prompt-score compilation and deterministic Remotion rendering orchestration."""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess

from .system import sha256, slugify, utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
VISUALS_ROOT = REPO_ROOT / "visuals"

PALETTES = {
    "neon": ["#ff7657", "#62c6cf", "#f2bd63", "#efe6d8"],
    "cold": ["#8be9c7", "#68a8ff", "#b8c0ff", "#e7edf8"],
    "warm": ["#ff6b35", "#f7c59f", "#efefd0", "#d6a2ad"],
    "acid": ["#ff8066", "#7f5af0", "#d7ff72", "#f3eadc"],
    "mono": ["#f5f2ea", "#a9afb9", "#565d69", "#ffffff"],
}


def compile_prompt(prompt: str, title: str, seed: int = 1) -> dict:
    """Compile a free prompt into a conservative visual score agents can refine."""
    lowered = prompt.lower()
    if any(word in lowered for word in ("constellation", "star", "nodes", "circuit")):
        world = "constellation"
    elif any(word in lowered for word in (
        "ribbon", "liquid", "tape", "wave", "flow", "family", "voice", "voices",
        "guitar", "breath", "organic", "hand-played",
    )):
        world = "ribbons"
    else:
        world = "portal"
    palette_name = next((name for name in PALETTES if name in lowered), "neon")
    speed = 0.72
    if any(word in lowered for word in ("slow", "patient", "drift", "sleep")):
        speed = 0.34
    elif any(word in lowered for word in ("fast", "frantic", "strobe", "frenetic")):
        speed = 1.25
    turbulence = 0.7 if any(word in lowered for word in ("rough", "broken", "noisy", "chaos")) else 0.42
    bass = 1.35 if any(word in lowered for word in ("bass", "kick", "sub")) else 1.0
    mids = 1.2 if any(word in lowered for word in ("guitar", "voice", "midrange", "tape")) else 0.8
    highs = 1.1 if any(word in lowered for word in ("spark", "hat", "shimmer", "dust")) else 0.68
    show_typography = not any(
        phrase in lowered
        for phrase in ("no text", "without text", "no title", "instrumental visual only")
    )
    return {
        "schema": "eprs.visual/v1", "title": title,
        "subtitle": "EAT · PLAY · RELAX · SLEEP", "prompt": prompt,
        "world": world, "seed": seed, "palette": PALETTES[palette_name],
        "background": "#080a0f",
        "motion": {"speed": speed, "feedback": 0.58, "rotation": 0.34, "turbulence": turbulence},
        "reactivity": {"bass": bass, "mids": mids, "highs": highs},
        "texture": {"grain": 0.2 if turbulence > 0.5 else 0.14, "scanlines": 0.1, "bloom": 0.72},
        "typography": {"show": show_typography, "position": "center"},
        "avoid": ["faces", "stock footage", "generic AI imagery", "literal equalizer bars", "constant motion"],
    }


def write_prompt_score(prompt: str, title: str, seed: int, output: str | Path) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(compile_prompt(prompt, title, seed), indent=2) + "\n")
    return destination


def validate_spec(candidate: dict) -> dict:
    if candidate.get("schema") != "eprs.visual/v1":
        raise ValueError("visual score must use schema eprs.visual/v1")
    if candidate.get("world") not in {"portal", "ribbons", "constellation"}:
        raise ValueError("visual world must be portal, ribbons, or constellation")
    palette = candidate.get("palette")
    if not isinstance(palette, list) or len(palette) != 4 or not all(isinstance(color, str) and color.startswith("#") for color in palette):
        raise ValueError("visual palette must contain four hex colors")
    if not isinstance(candidate.get("seed"), int):
        raise ValueError("visual seed must be an integer")
    return candidate


def _duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("FFprobe is required to determine visual duration")
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip())
    return float(completed.stdout.strip())


def render_visual(spec_path: str | Path, audio_path: str | Path, output: str | Path,
                  seconds: float | None = None, quality: str = "draft") -> tuple[Path, Path]:
    if quality not in {"draft", "full"}:
        raise ValueError("visual quality must be draft or full")
    spec_file, audio_file = Path(spec_path).resolve(), Path(audio_path).resolve()
    if not spec_file.is_file():
        raise FileNotFoundError(spec_file)
    if not audio_file.is_file():
        raise FileNotFoundError(audio_file)
    spec = validate_spec(json.loads(spec_file.read_text()))
    duration = _duration(audio_file)
    if seconds is not None:
        if seconds <= 0:
            raise ValueError("visual preview seconds must be positive")
        duration = min(duration, seconds)
    fps = 30
    duration_frames = max(1, math.ceil(duration * fps))
    media_dir = VISUALS_ROOT / "public" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    audio_hash = sha256(audio_file)
    cached_audio = media_dir / f"{audio_hash[:16]}{audio_file.suffix.lower()}"
    if not cached_audio.exists():
        shutil.copy2(audio_file, cached_audio)
    props = {"audioFile": f"media/{cached_audio.name}", "durationInFrames": duration_frames, "spec": spec}
    build_dir = REPO_ROOT / "build" / "visuals"
    build_dir.mkdir(parents=True, exist_ok=True)
    name = slugify(spec.get("title", spec_file.stem))
    props_file = build_dir / f"{name}-{audio_hash[:8]}.props.json"
    props_file.write_text(json.dumps(props, indent=2) + "\n")
    remotion = VISUALS_ROOT / "node_modules" / ".bin" / "remotion"
    if not remotion.is_file():
        raise RuntimeError("visual dependencies are not installed; run 'make visuals-install'")
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(remotion), "render", "src/index.ts", "PromptVisual", str(destination),
        f"--props={props_file}", "--codec=h264", "--pixel-format=yuv420p",
        "--color-space=bt709", "--audio-codec=aac", "--audio-bitrate=320k",
        "--sample-rate=48000", "--gop=15", "--x264-preset=medium",
        f"--crf={'23' if quality == 'draft' else '17'}", "--concurrency=4",
    ]
    if quality == "draft":
        command.append("--scale=0.5")
    else:
        command.append("--image-format=png")
    completed = subprocess.run(command, cwd=VISUALS_ROOT, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-5000:] or completed.stdout[-5000:])
    provenance = destination.with_suffix(destination.suffix + ".json")
    provenance.write_text(json.dumps({
        "schema": "eprs.visual-render/v1", "rendered_at": utc_now(),
        "output": destination.name, "output_sha256": sha256(destination),
        "visual_score": spec_file.name, "visual_score_sha256": sha256(spec_file),
        "audio": audio_file.name, "audio_sha256": audio_hash,
        "duration_seconds": duration, "duration_frames": duration_frames, "fps": fps,
        "quality": quality, "renderer": "Remotion 4.0.504 + custom EPRS SVG engine",
    }, indent=2) + "\n")
    return destination, provenance
