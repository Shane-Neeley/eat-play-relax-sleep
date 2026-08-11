#!/usr/bin/env python3
"""Generate bounded, song-local voice cues with Qwen3-TTS.

This is an optional provider runner. It deliberately uses VoiceDesign or
CustomVoice by default so the project can create an original character without
requiring a private human reference recording. Model weights stay in the
Hugging Face cache; generated WAVs and a provenance manifest stay in the song.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import random
import sys
from typing import Any


DEFAULT_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
DEFAULT_LANGUAGE = "English"
AUTOTUNE_PRESETS = ("none", "transparent", "tight", "hard-step", "gloopy")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face Qwen3-TTS model id")
    command.add_argument(
        "--mode",
        choices=("voice-design", "custom-voice"),
        default="voice-design",
        help="Use an original described voice or a built-in Qwen speaker",
    )
    command.add_argument("--speaker", default="Ryan", help="Built-in speaker for --mode custom-voice")
    command.add_argument("--language", default=DEFAULT_LANGUAGE)
    command.add_argument(
        "--instruct",
        required=True,
        help="Natural-language voice/prosody direction; do not name a living artist or identifiable child",
    )
    command.add_argument(
        "--text",
        action="append",
        required=True,
        help="One cue to synthesize; repeat for a cue batch",
    )
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--prefix", default="qwen-cue")
    command.add_argument("--seed", type=int, default=20260810)
    command.add_argument("--device", default="auto", choices=("auto", "mps", "cpu", "cuda"))
    command.add_argument(
        "--autotune-preset", choices=AUTOTUNE_PRESETS, default="none",
        help="Optionally keep each raw cue and render a formant-aware tuned cue",
    )
    command.add_argument("--autotune-key", default="C")
    command.add_argument("--autotune-scale", default="chromatic")
    command.add_argument("--version", action="version", version="qwen3-tts-voice 1.1")
    return command


def choose_device(torch: Any, requested: str) -> str:
    if requested != "auto":
        return requested
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def load_model(model_id: str, device: str, torch: Any, Qwen3TTSModel: Any) -> Any:
    dtype = torch.float32 if device == "cpu" else torch.float16
    kwargs = {"device_map": device, "dtype": dtype}
    try:
        return Qwen3TTSModel.from_pretrained(model_id, **kwargs)
    except (TypeError, ValueError, RuntimeError) as exc:
        if device == "mps":
            # Some Accelerate versions do not accept an MPS device map even
            # though the model can run on MPS after loading.
            try:
                model = Qwen3TTSModel.from_pretrained(model_id, device_map="cpu", dtype=torch.float32)
                return model.to("mps")
            except Exception as fallback_exc:  # pragma: no cover - hardware-dependent
                raise RuntimeError(f"Qwen3-TTS MPS load failed: {exc}; CPU-to-MPS fallback failed: {fallback_exc}") from fallback_exc
        raise


def generate(args: argparse.Namespace) -> Path:
    try:
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel
    except ImportError as exc:  # pragma: no cover - exercised by environment smoke test
        raise SystemExit(
            "Qwen3-TTS is not installed in this Python environment. "
            "Create an isolated Python 3.11+ environment and run `pip install -U qwen-tts soundfile`."
        ) from exc

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = choose_device(torch, args.device)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Qwen3-TTS render manifest already exists: {manifest_path}")
    for index in range(1, len(args.text) + 1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        candidates = [destination]
        if args.autotune_preset != "none":
            candidates.extend([
                args.out_dir / f"{args.prefix}-raw-{index:02d}.wav",
                destination.with_suffix(destination.suffix + ".json"),
            ])
        existing = next((path for path in candidates if path.exists()), None)
        if existing:
            raise FileExistsError(f"Qwen3-TTS output already exists: {existing}")
    model = load_model(args.model, device, torch, Qwen3TTSModel)
    def render_batch(active_model: Any) -> list[dict[str, Any]]:
        generated: list[tuple[str, Any, int]] = []
        # Finish inference for the whole bounded batch before writing any cue.
        # That makes the documented MPS-to-CPU retry safe: an unstable sampler
        # cannot leave earlier cues that the retry would need to overwrite.
        for text in args.text:
            if args.mode == "voice-design":
                wavs, sample_rate = active_model.generate_voice_design(
                    text=text,
                    language=args.language,
                    instruct=args.instruct,
                )
            else:
                wavs, sample_rate = active_model.generate_custom_voice(
                    text=text,
                    language=args.language,
                    speaker=args.speaker,
                    instruct=args.instruct,
                )
            generated.append((text, wavs[0], int(sample_rate)))

        rendered: list[dict[str, Any]] = []
        for index, (text, samples, sample_rate) in enumerate(generated, start=1):
            destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
            raw_destination = (
                args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
                if args.autotune_preset != "none" else destination
            )
            sf.write(raw_destination, samples, sample_rate, subtype="PCM_16")
            output = {
                "id": f"{args.prefix}-{index:02d}",
                "text": text,
                "path": str(destination),
                "sample_rate": sample_rate,
                "channels": 1,
            }
            if args.autotune_preset != "none":
                # Keep pitch processing separate and inspectable even when the
                # TTS runner orchestrates both operations in one bounded call.
                project_src = Path(__file__).resolve().parents[1] / "src"
                if str(project_src) not in sys.path:
                    sys.path.insert(0, str(project_src))
                from eprs.autotune import render_autotune, settings_for

                settings = settings_for(
                    args.autotune_preset,
                    key=args.autotune_key,
                    scale=args.autotune_scale,
                )
                _, tuning_manifest, _ = render_autotune(
                    raw_destination,
                    destination,
                    settings,
                    intent=(
                        f"Apply the {args.autotune_preset} pitch treatment to this synthetic "
                        f"cue in {args.autotune_key} {args.autotune_scale}."
                    ),
                )
                output["raw"] = {
                    "path": str(raw_destination), "sha256": sha256(raw_destination),
                }
                output["autotune_manifest"] = display_path(tuning_manifest)
            output["sha256"] = sha256(destination)
            rendered.append(output)
        return rendered

    try:
        outputs = render_batch(model)
    except RuntimeError as exc:
        # Qwen's MPS float16 sampler can produce invalid probabilities on some
        # Apple Silicon/torch combinations. Keep auto mode convenient, but make
        # the safe CPU float32 retry explicit in the manifest.
        if device != "mps" or "probability tensor" not in str(exc):
            raise
        print("Qwen3-TTS MPS sampling was unstable; retrying on CPU float32.", file=sys.stderr)
        device = "cpu"
        model = load_model(args.model, device, torch, Qwen3TTSModel)
        outputs = render_batch(model)

    try:
        package_version = version("qwen-tts")
    except PackageNotFoundError:  # pragma: no cover - import already proved an unusual install works
        package_version = "unknown"
    manifest = {
        "schema": "eprs.qwen3-tts-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": args.model,
        "qwen_tts_version": package_version,
        "mode": args.mode,
        "speaker": args.speaker if args.mode == "custom-voice" else None,
        "language": args.language,
        "instruction": args.instruct,
        "seed": args.seed,
        "device": device,
        "autotune": {
            "preset": args.autotune_preset,
            "key": args.autotune_key if args.autotune_preset != "none" else None,
            "scale": args.autotune_scale if args.autotune_preset != "none" else None,
            "raw_cues_preserved": args.autotune_preset != "none",
        },
        "outputs": outputs,
        "rights": "Synthetic local voice design/custom voice; no human reference audio supplied by this runner.",
        "review": "technical render only; creative listening and release rights remain separate gates",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    args = parser().parse_args()
    try:
        print(generate(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
