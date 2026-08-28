"""Prompt-score compilation and deterministic Remotion rendering orchestration."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

from .inaturalist_photo import verify_inaturalist_photo
from .system import sha256, slugify, utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
VISUALS_ROOT = REPO_ROOT / "visuals"
DEFAULT_RENDER_TIMEOUT_SECONDS = 1_800.0
RENDER_CONCURRENCY = 4

PALETTES = {
    "neon": ["#ff7657", "#62c6cf", "#f2bd63", "#efe6d8"],
    "cold": ["#8be9c7", "#68a8ff", "#b8c0ff", "#e7edf8"],
    "warm": ["#ff6b35", "#f7c59f", "#efefd0", "#d6a2ad"],
    "acid": ["#ff8066", "#7f5af0", "#d7ff72", "#f3eadc"],
    "mono": ["#f5f2ea", "#a9afb9", "#565d69", "#ffffff"],
    "field": ["#b7d66d", "#5c8f73", "#263d3a", "#f2d49b"],
    "dusk": ["#f09ac2", "#8e7dbe", "#27334d", "#f6d6a8"],
    "meadow": ["#f6c85f", "#8ecf76", "#f17f75", "#2b6864"],
}


def compile_prompt(prompt: str, title: str, seed: int = 1) -> dict:
    """Compile a free prompt into a conservative visual score agents can refine."""
    lowered = prompt.lower()
    if any(word in lowered for word in ("meadow", "grass", "sunlit", "sunny", "wildflower", "firefly", "cricket")):
        world = "meadow"
    elif any(word in lowered for word in ("constellation", "star", "nodes", "circuit")):
        world = "constellation"
    elif any(word in lowered for word in ("animal", "bird", "frog", "cricket", "cicada", "wildlife", "field recording", "organism", "nature")):
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
    score = {
        "schema": "eprs.visual/v1", "title": title,
        "subtitle": "EAT · PLAY · RELAX · SLEEP", "prompt": prompt,
        "world": world, "seed": seed, "palette": PALETTES[palette_name],
        "background": "#dce9bd" if world == "meadow" else "#080a0f",
        "motion": {"speed": speed, "feedback": 0.58, "rotation": 0.34, "turbulence": turbulence},
        "reactivity": {"bass": bass, "mids": mids, "highs": highs},
        "texture": {"grain": 0.2 if turbulence > 0.5 else 0.14, "scanlines": 0.1, "bloom": 0.72},
        "typography": {"show": show_typography, "position": "center"},
        "avoid": ["faces", "stock footage", "generic AI imagery", "literal equalizer bars", "constant motion"],
    }
    if any(word in lowered for word in ("cricket", "chirp", "firefly", "meadow pulse")):
        score["motif"] = "cricket-pulse"
    elif any(word in lowered for word in ("animal", "bird", "frog", "cicada", "wildlife", "field recording", "organism")):
        score["motif"] = "rare-signal-atlas"
    elif any(word in lowered for word in ("paper", "notebook", "score", "lyric sheet")):
        score["motif"] = "paper-score"
    elif any(word in lowered for word in ("cloud", "mist", "vapor", "haze")):
        score["motif"] = "cloud-braid"
    elif any(word in lowered for word in ("screenprint", "poster", "ink", "print")):
        score["motif"] = "screenprint-count"
    elif "pull me in" in lowered or "pull-in" in lowered or "invitation" in lowered:
        score["motif"] = "pull-me-in"
    elif any(word in lowered for word in ("jamaica", "jamaican", "reggae", "dancehall")):
        score["motif"] = "jamaica-reggae"
    return score


def write_prompt_score(prompt: str, title: str, seed: int, output: str | Path) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(compile_prompt(prompt, title, seed), indent=2) + "\n")
    return destination


def validate_spec(candidate: dict) -> dict:
    if candidate.get("schema") != "eprs.visual/v1":
        raise ValueError("visual score must use schema eprs.visual/v1")
    if candidate.get("world") not in {"portal", "ribbons", "constellation", "meadow"}:
        raise ValueError("visual world must be portal, ribbons, constellation, or meadow")
    if candidate.get("motif") not in {None, "octopus-ink", "pillow-fight", "pull-me-in", "jamaica-reggae", "paper-score", "rare-signal-atlas", "five-pane-door", "magnetic-dust", "cloud-braid", "screenprint-count", "squirrel-pines", "cricket-pulse", "eclipse-shadow", "paper-pond"}:
        raise ValueError("visual motif is not supported by the renderer")
    cards = candidate.get("cards")
    if cards is not None:
        valid_cards = (
            isinstance(cards, list)
            and len(cards) <= 8
            and all(
                isinstance(card, dict)
                and all(isinstance(card.get(field), str) and card[field].strip() for field in ("label", "region", "note"))
                and ("accent" not in card or isinstance(card["accent"], str))
                for card in cards
            )
        )
        if not valid_cards:
            raise ValueError("visual cards must contain at most eight labeled region and note records")
    photographs = candidate.get("photographs")
    if photographs is not None:
        valid_photographs = (
            isinstance(photographs, list)
            and len(photographs) <= 4
            and all(
                isinstance(photo, dict)
                and isinstance(photo.get("path"), str)
                and bool(photo["path"].strip())
                and not Path(photo["path"]).is_absolute()
                and (
                    "opacity" not in photo
                    or (
                        isinstance(photo["opacity"], (int, float))
                        and not isinstance(photo["opacity"], bool)
                        and math.isfinite(photo["opacity"])
                        and 0.05 <= photo["opacity"] <= 0.85
                    )
                )
                and photo.get("treatment", "soft-light") in {"soft-light", "screen", "normal"}
                for photo in photographs
            )
        )
        if not valid_photographs:
            raise ValueError(
                "visual photographs must contain at most four relative iNaturalist photo references"
            )
    palette = candidate.get("palette")
    if not isinstance(palette, list) or len(palette) != 4 or not all(isinstance(color, str) and color.startswith("#") for color in palette):
        raise ValueError("visual palette must contain four hex colors")
    if not isinstance(candidate.get("seed"), int):
        raise ValueError("visual seed must be an integer")
    return candidate


def _stage_inaturalist_photographs(
    spec: dict,
    spec_file: Path,
    media_dir: Path,
) -> tuple[dict, list[dict]]:
    """Verify and stage release-compatible iNaturalist photos for Remotion."""
    render_spec = json.loads(json.dumps(spec))
    staged = []
    provenance = []
    for item in spec.get("photographs") or []:
        source = (spec_file.parent / item["path"]).resolve()
        path, sidecar, record = verify_inaturalist_photo(
            source, require_publication_compatible=True
        )
        digest = sha256(path)
        cached = media_dir / f"inat-{digest[:16]}{path.suffix.lower()}"
        if not cached.exists():
            shutil.copy2(path, cached)
        photo = record["photo"]
        source_record = record["source"]
        taxon = source_record.get("taxon") if isinstance(source_record.get("taxon"), dict) else {}
        staged.append({
            "file": f"media/{cached.name}",
            "opacity": float(item.get("opacity", 0.34)),
            "treatment": item.get("treatment", "soft-light"),
            "attribution": photo["attribution"],
            "licenseCode": photo["license_code"].upper(),
            "sourceUrl": source_record["url"],
            "label": taxon.get("common_name") or taxon.get("scientific_name") or "iNaturalist observation",
        })
        provenance.append({
            "path": item["path"],
            "sha256": digest,
            "metadata_path": str(
                Path(item["path"]).with_suffix(Path(item["path"]).suffix + ".json")
            ),
            "metadata_sha256": sha256(sidecar),
            "observation_id": source_record["observation_id"],
            "observation_url": source_record["url"],
            "photo_id": photo["id"],
            "license_code": photo["license_code"],
            "attribution": photo["attribution"],
            "publication_status": record["rights"]["publication_status"],
        })
    render_spec["photographs"] = staged
    return render_spec, provenance


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


def _stop_process_group(process: subprocess.Popen, grace_seconds: float = 1.0) -> None:
    """Stop a renderer and every Chromium/FFmpeg child in its private group."""
    if os.name == "nt":
        process.terminate()
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _run_renderer(command: list[str], timeout_seconds: float) -> subprocess.CompletedProcess:
    """Run Remotion in an owned process group with a finite time budget."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("visual render timeout must be a positive finite number")
    process = subprocess.Popen(
        command,
        cwd=VISUALS_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=os.name != "nt",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _stop_process_group(process)
        stdout, stderr = process.communicate()
        raise RuntimeError(
            f"visual render exceeded its {timeout_seconds:g}-second time budget: "
            f"{(stderr or stdout)[-3000:]}"
        ) from exc
    except BaseException:
        _stop_process_group(process)
        process.communicate()
        raise
    finally:
        # Remotion can exit before its Chrome workers. The dedicated process
        # group lets us reap those workers without touching other browsers.
        _stop_process_group(process)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def render_visual(spec_path: str | Path, audio_path: str | Path, output: str | Path,
                  seconds: float | None = None, quality: str = "draft",
                  timeout_seconds: float = DEFAULT_RENDER_TIMEOUT_SECONDS) -> tuple[Path, Path]:
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
    render_spec, photograph_provenance = _stage_inaturalist_photographs(
        spec, spec_file, media_dir
    )
    props = {
        "audioFile": f"media/{cached_audio.name}",
        "durationInFrames": duration_frames,
        "spec": render_spec,
    }
    build_dir = REPO_ROOT / "build" / "visuals"
    build_dir.mkdir(parents=True, exist_ok=True)
    name = slugify(spec.get("title", spec_file.stem))
    props_file = build_dir / f"{name}-{audio_hash[:8]}-{sha256(spec_file)[:8]}.props.json"
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
        f"--crf={'23' if quality == 'draft' else '17'}",
        f"--concurrency={RENDER_CONCURRENCY}",
    ]
    if quality == "draft":
        command.append("--scale=0.5")
    else:
        command.append("--image-format=png")
    started_at = time.monotonic()
    completed = _run_renderer(command, timeout_seconds)
    elapsed_seconds = round(time.monotonic() - started_at, 3)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-5000:] or completed.stdout[-5000:])
    provenance = destination.with_suffix(destination.suffix + ".json")
    provenance.write_text(json.dumps({
        "schema": "eprs.visual-render/v1", "rendered_at": utc_now(),
        "output": destination.name, "output_sha256": sha256(destination),
        "visual_score": spec_file.name, "visual_score_sha256": sha256(spec_file),
        "audio": audio_file.name, "audio_sha256": audio_hash,
        "photographs": photograph_provenance,
        "visual_rights": {
            "release_ready": all(
                item["publication_status"] == "commercial-compatible-subject-to-attribution"
                for item in photograph_provenance
            ),
            "attribution_embedded": bool(photograph_provenance),
        },
        "duration_seconds": duration, "duration_frames": duration_frames, "fps": fps,
        "quality": quality, "renderer": "Remotion 4.0.504 + custom EPRS SVG engine",
        "performance": {
            "elapsed_seconds": elapsed_seconds,
            "concurrency": RENDER_CONCURRENCY,
            "timeout_seconds": timeout_seconds,
        },
    }, indent=2) + "\n")
    return destination, provenance
