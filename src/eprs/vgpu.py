"""Headless vgpu rendering for deterministic EPRS picture candidates."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import tempfile
import time

from .system import probe, sha256, slugify, utc_now
from .visuals import validate_spec


REPO_ROOT = Path(__file__).resolve().parents[2]
VISUALS_ROOT = REPO_ROOT / "visuals"
VGPU_SCRIPT = VISUALS_ROOT / "vgpu-render.mjs"
DEFAULT_RENDER_TIMEOUT_SECONDS = 1_800.0
RENDER_FPS = 30
CONTROL_SAMPLE_RATE = 8_000
RENDER_SIZES = {"draft": (640, 360), "full": (1280, 720)}
WORLD_IDS = {"portal": 0.0, "ribbons": 1.0, "constellation": 2.0, "meadow": 3.0}
MOTIF_IDS = {
    "rare-signal-atlas": 1.0,
    "cloud-braid": 2.0,
    "paper-score": 3.0,
    "screenprint-count": 4.0,
    "cricket-pulse": 5.0,
    "eclipse-shadow": 6.0,
    "paper-pond": 7.0,
}
_BASS_FREQUENCIES = (45.0, 60.0, 80.0, 110.0, 150.0, 200.0)
_MID_FREQUENCIES = (250.0, 350.0, 500.0, 700.0, 900.0, 1_200.0)
_HIGH_FREQUENCIES = (1_600.0, 2_200.0, 2_800.0, 3_400.0, 3_800.0)


def _audio_duration(path: Path) -> float:
    details = probe(path)
    value = details.get("format", {}).get("duration")
    if value is None:
        raise ValueError(f"audio duration is unavailable: {path}")
    duration = float(value)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("audio duration must be positive and finite")
    return duration


def _decode_audio(path: Path, duration: float) -> list[float]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for vgpu audio controls")
    completed = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-t",
            f"{duration:.12g}",
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(CONTROL_SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    usable = len(completed.stdout) - (len(completed.stdout) % 4)
    if usable < 4:
        raise ValueError("audio decoded no samples for vgpu controls")
    return [
        value[0]
        for value in struct.iter_unpack("<f", completed.stdout[:usable])
    ]


def _frequency_energy(
    samples: list[float], center: int, frequency: float, window_size: int = 256
) -> float:
    start = center - window_size // 2
    real = 0.0
    imaginary = 0.0
    for offset in range(window_size):
        index = start + offset
        sample = samples[index] if 0 <= index < len(samples) else 0.0
        window = 0.5 - 0.5 * math.cos(2.0 * math.pi * offset / (window_size - 1))
        phase = 2.0 * math.pi * frequency * offset / CONTROL_SAMPLE_RATE
        real += sample * window * math.cos(phase)
        imaginary -= sample * window * math.sin(phase)
    return math.sqrt(real * real + imaginary * imaginary) / window_size


def _band_energy(samples: list[float], center: int, frequencies: tuple[float, ...]) -> float:
    return sum(_frequency_energy(samples, center, frequency) for frequency in frequencies)


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    high = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    low = ordered[max(0, int(len(ordered) * 0.10) - 1)]
    span = max(high - low, 1e-9)
    return [max(0.0, min(1.0, (value - low) / span)) for value in values]


def build_audio_controls(
    audio: str | Path,
    *,
    duration: float | None = None,
    fps: int = RENDER_FPS,
) -> dict:
    """Derive bounded, reproducible visual controls without changing the audio."""
    audio_path = Path(audio).resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)
    if not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0:
        raise ValueError("vgpu control fps must be a positive integer")
    source_duration = _audio_duration(audio_path)
    if duration is None:
        duration = source_duration
    duration = float(duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("vgpu control duration must be positive and finite")
    duration = min(duration, source_duration)
    samples = _decode_audio(audio_path, duration)
    frame_count = max(1, math.ceil(duration * fps))
    raw_bass: list[float] = []
    raw_mids: list[float] = []
    raw_highs: list[float] = []
    raw_energy: list[float] = []
    for index in range(frame_count):
        center = round((index + 0.5) * CONTROL_SAMPLE_RATE / fps)
        bass = _band_energy(samples, center, _BASS_FREQUENCIES)
        mids = _band_energy(samples, center, _MID_FREQUENCIES)
        highs = _band_energy(samples, center, _HIGH_FREQUENCIES)
        raw_bass.append(bass)
        raw_mids.append(mids)
        raw_highs.append(highs)
        raw_energy.append(bass + mids + highs)
    bass_values = _normalize(raw_bass)
    mid_values = _normalize(raw_mids)
    high_values = _normalize(raw_highs)
    energy_values = _normalize(raw_energy)
    frames = []
    previous = 0.0
    for index in range(frame_count):
        energy = energy_values[index]
        frames.append({
            "index": index,
            "time": round(index / fps, 6),
            "energy": round(energy, 6),
            "onset": round(max(0.0, energy - previous), 6),
            "bass": round(bass_values[index], 6),
            "mids": round(mid_values[index], 6),
            "highs": round(high_values[index], 6),
        })
        previous = energy
    return {
        "schema": "eprs.vgpu-audio-controls/v1",
        "source": {"path": audio_path.name, "sha256": sha256(audio_path)},
        "method": {
            "description": "Hann-windowed single-bin DFT bands from mono PCM",
            "sample_rate": CONTROL_SAMPLE_RATE,
            "fps": fps,
            "normalization": "10th-to-95th percentile per band, clamped to 0..1",
        },
        "duration_seconds": round(duration, 6),
        "frames": frames,
    }


def _run_renderer(command: list[str], timeout_seconds: float) -> subprocess.CompletedProcess:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("vgpu render timeout must be a positive finite number")
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
            f"vgpu render exceeded its {timeout_seconds:g}-second time budget: "
            f"{(stderr or stdout)[-3000:]}"
        ) from exc
    except BaseException:
        _stop_process_group(process)
        process.communicate()
        raise
    finally:
        _stop_process_group(process)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _stop_process_group(process: subprocess.Popen, grace_seconds: float = 1.0) -> None:
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


def _probe_render(path: Path, width: int, height: int, duration: float) -> dict:
    details = probe(path)
    streams = details.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if not isinstance(video, dict) or not isinstance(audio, dict):
        raise RuntimeError("vgpu render did not produce both video and audio streams")
    expected = {
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": width,
        "height": height,
        "pixel_format": "yuv420p",
        "field_order": "progressive",
        "color_space": "bt709",
        "color_primaries": "bt709",
        "color_transfer": "bt709",
        "sample_rate": "48000",
        "channels": 2,
    }
    actual = {
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "width": video.get("width"),
        "height": video.get("height"),
        "pixel_format": video.get("pix_fmt"),
        "field_order": video.get("field_order"),
        "color_space": video.get("color_space"),
        "color_primaries": video.get("color_primaries"),
        "color_transfer": video.get("color_transfer"),
        "sample_rate": audio.get("sample_rate"),
        "channels": audio.get("channels"),
    }
    mismatches = {
        key: {"expected": expected[key], "actual": actual[key]}
        for key in expected
        if actual[key] != expected[key]
    }
    if mismatches:
        raise RuntimeError(f"vgpu render technical verification failed: {mismatches}")
    actual_duration = float(details.get("format", {}).get("duration") or 0.0)
    duration_tolerance = (1.0 / RENDER_FPS) + 0.02
    if abs(actual_duration - duration) > duration_tolerance:
        raise RuntimeError(
            "vgpu render duration verification failed: "
            f"expected {duration:.6f}s, actual {actual_duration:.6f}s"
        )
    return {
        "expected": expected,
        "actual": actual,
        "duration": {
            "expected_seconds": duration,
            "actual_seconds": actual_duration,
            "tolerance_seconds": duration_tolerance,
        },
        "probe": details,
    }


def render_vgpu(
    spec_path: str | Path,
    audio_path: str | Path,
    output: str | Path,
    seconds: float | None = None,
    quality: str = "draft",
    timeout_seconds: float = DEFAULT_RENDER_TIMEOUT_SECONDS,
) -> tuple[Path, Path]:
    """Render an EPRS visual score through vgpu and mux the original audio."""
    if quality not in RENDER_SIZES:
        raise ValueError("vgpu visual quality must be draft or full")
    spec_file = Path(spec_path).resolve()
    audio_file = Path(audio_path).resolve()
    if not spec_file.is_file():
        raise FileNotFoundError(spec_file)
    if not audio_file.is_file():
        raise FileNotFoundError(audio_file)
    if not VGPU_SCRIPT.is_file():
        raise RuntimeError(f"vgpu renderer script is missing: {VGPU_SCRIPT}")
    spec = validate_spec(json.loads(spec_file.read_text()))
    if spec.get("photographs"):
        raise ValueError(
            "vgpu renderer does not stage iNaturalist photographs; use Remotion for photo scores"
        )
    source_duration = _audio_duration(audio_file)
    duration = source_duration if seconds is None else min(source_duration, float(seconds))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("vgpu preview seconds must be positive and finite")
    width, height = RENDER_SIZES[quality]
    controls = build_audio_controls(audio_file, duration=duration, fps=RENDER_FPS)
    controls_json = json.dumps(controls, sort_keys=True, separators=(",", ":"))
    controls_hash = hashlib.sha256(controls_json.encode()).hexdigest()
    score_hash = sha256(spec_file)
    audio_hash = sha256(audio_file)
    renderer_hash = sha256(VGPU_SCRIPT)
    recipe = {
        "schema": "eprs.vgpu-render/v1",
        "spec_sha256": score_hash,
        "audio_sha256": audio_hash,
        "controls_sha256": controls_hash,
        "quality": quality,
        "width": width,
        "height": height,
        "fps": RENDER_FPS,
        "duration_seconds": round(duration, 6),
        "adapter": os.environ.get("VGPU_ADAPTER", "auto"),
        "renderer_source_sha256": renderer_hash,
    }
    recipe_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    provenance = destination.with_suffix(destination.suffix + ".json")
    controls_path = destination.with_suffix(".controls.json")
    if destination.exists() or provenance.exists() or controls_path.exists():
        if destination.is_file() and provenance.is_file() and controls_path.is_file():
            try:
                existing = json.loads(provenance.read_text())
            except json.JSONDecodeError:
                existing = {}
            if existing.get("recipe_id") == recipe_id and sha256(destination) == existing.get("output_sha256"):
                return destination, provenance
        raise FileExistsError(f"refusing to overwrite existing vgpu render: {destination}")
    build_dir = REPO_ROOT / "build" / "visuals"
    build_dir.mkdir(parents=True, exist_ok=True)
    controls_path.write_text(json.dumps(controls, indent=2) + "\n")
    props_file = build_dir / f"{slugify(spec.get('title', spec_file.stem))}-{recipe_id[:12]}.vgpu.json"
    props_file.write_text(json.dumps({
        "width": width,
        "height": height,
        "fps": RENDER_FPS,
        "frames": len(controls["frames"]),
        "framesDir": "",
        "controlsPath": str(controls_path),
        "spec": spec,
    }, indent=2) + "\n")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to mux the vgpu picture and audio")
    started_at = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="eprs-vgpu-", dir=build_dir) as temporary:
            frames_dir = Path(temporary) / "frames"
            frames_dir.mkdir()
            title_file = Path(temporary) / "title.txt"
            subtitle_file = Path(temporary) / "subtitle.txt"
            title_file.write_text(str(spec.get("title", "EPRS")) + "\n")
            subtitle_file.write_text(str(spec.get("subtitle", "EAT · PLAY · RELAX · SLEEP")) + "\n")
            props = json.loads(props_file.read_text())
            props["framesDir"] = str(frames_dir)
            props_file.write_text(json.dumps(props, indent=2) + "\n")
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Node.js is required for the vgpu renderer")
            completed = _run_renderer(
                [node, str(VGPU_SCRIPT), "--props", str(props_file)], timeout_seconds
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr[-5000:] or completed.stdout[-5000:])
            frame_paths = sorted(frames_dir.glob("frame-*.png"))
            if len(frame_paths) != len(controls["frames"]):
                raise RuntimeError(
                    f"vgpu renderer wrote {len(frame_paths)} frames, expected {len(controls['frames'])}"
                )
            temporary_output = Path(temporary) / "render.mp4"
            typography = spec.get("typography") or {}
            video_filter = None
            typography_method = "not-requested"
            if typography.get("show", True):
                filters = subprocess.run(
                    [ffmpeg, "-filters"], capture_output=True, text=True, check=False
                )
                if "drawtext" in filters.stdout:
                    video_filter = (
                        f"drawtext=textfile={title_file}:fontcolor=white@0.92:"
                        "fontsize=42:x=48:y=42:box=1:boxcolor=black@0.28:boxborderw=14,"
                        f"drawtext=textfile={subtitle_file}:fontcolor=white@0.72:"
                        "fontsize=18:x=48:y=104"
                    )
                    typography_method = "ffmpeg-drawtext"
                else:
                    typography_method = "not-embedded-ffmpeg-drawtext-unavailable"
            mux = subprocess.run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-framerate",
                    str(RENDER_FPS),
                    "-i",
                    str(frames_dir / "frame-%06d.png"),
                    "-i",
                    str(audio_file),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    *( ["-vf", video_filter] if video_filter else [] ),
                    "-t",
                    f"{duration:.12g}",
                    "-c:v",
                    "libx264",
                    "-profile:v",
                    "high",
                    "-pix_fmt",
                    "yuv420p",
                    "-colorspace",
                    "bt709",
                    "-color_primaries",
                    "bt709",
                    "-color_trc",
                    "bt709",
                    "-x264-params",
                    "colorprim=bt709:transfer=bt709:colormatrix=bt709",
                    "-crf",
                    "23" if quality == "draft" else "17",
                    "-preset",
                    "medium",
                    "-g",
                    "15",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "320k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    str(temporary_output),
                ],
                capture_output=True,
                check=False,
            )
            if mux.returncode:
                raise RuntimeError(mux.stderr.decode(errors="replace")[-5000:])
            technical = _probe_render(temporary_output, width, height, duration)
            temporary_output.replace(destination)
        elapsed_seconds = round(time.monotonic() - started_at, 3)
        record = {
            "schema": "eprs.vgpu-render/v1",
            "rendered_at": utc_now(),
            "recipe_id": recipe_id,
            "output": destination.name,
            "output_sha256": sha256(destination),
            "visual_score": spec_file.name,
            "visual_score_sha256": score_hash,
            "audio": audio_file.name,
            "audio_sha256": audio_hash,
            "audio_controls": controls_path.name,
            "audio_controls_sha256": controls_hash,
            "source_reference": spec.get("source_reference"),
            "duration_seconds": round(duration, 6),
            "duration_frames": len(controls["frames"]),
            "fps": RENDER_FPS,
            "quality": quality,
            "renderer": "vgpu 0.3.1 headless WebGPU + FFmpeg",
            "renderer_source_sha256": renderer_hash,
            "adapter": os.environ.get("VGPU_ADAPTER", "auto"),
            "typography": {
                "requested": bool(typography.get("show", True)),
                "embedded": video_filter is not None,
                "method": typography_method,
            },
            "performance": {
                "elapsed_seconds": elapsed_seconds,
                "timeout_seconds": timeout_seconds,
            },
            "technical": technical,
            "authority": {
                "creative_approval": False,
                "picture_reviewed": False,
                "publication_ready": False,
                "statement": "Technical render only; watch the complete candidate before any picture decision.",
            },
        }
        temporary_sidecar = provenance.with_name(f".{provenance.name}.partial")
        temporary_sidecar.write_text(json.dumps(record, indent=2) + "\n")
        temporary_sidecar.replace(provenance)
    except Exception:
        destination.unlink(missing_ok=True)
        provenance.unlink(missing_ok=True)
        controls_path.unlink(missing_ok=True)
        raise
    return destination, provenance
