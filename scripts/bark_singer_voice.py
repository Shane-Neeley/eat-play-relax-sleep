#!/usr/bin/env python3
"""Generate song-local singer-ish vocal cues with Hugging Face Bark.

Bark is not a score-conditioned singing synthesizer. It is useful in EPRS as a
lightweight performance voice when a track needs less robotic phrasing before
the normal autotune stage. Keep prompts fictional and do not request imitation
of a real singer.
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


DEFAULT_MODEL = "suno/bark-small"


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
    command.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face Bark model id")
    command.add_argument("--voice-preset", default="v2/en_speaker_6")
    command.add_argument(
        "--prompt-prefix",
        default=(
            "Original fictional vocalist, melodic pop chant, sustained vowels, "
            "confident hook delivery, clean consonants. "
        ),
        help=(
            "Style note stored in provenance only; never synthesized as spoken text. "
            "Do not name a real performer."
        ),
    )
    command.add_argument("--text", action="append", required=True)
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--prefix", default="bark-vocal")
    command.add_argument("--seed", type=int, default=20260811)
    command.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    command.add_argument("--temperature", type=float, default=0.78)
    command.add_argument("--semantic-temperature", type=float, default=0.72)
    command.add_argument(
        "--autotune-preset",
        choices=("none", "transparent", "tight", "hard-step", "gloopy"),
        default="none",
    )
    command.add_argument("--autotune-key", default="C")
    command.add_argument("--autotune-scale", default="minor-pentatonic")
    command.add_argument("--version", action="version", version="bark-singer-voice 0.1")
    return command


def choose_device(torch: Any, requested: str) -> str:
    if requested == "cpu":
        return "cpu"
    if requested == "cuda":
        return "cuda:0"
    if requested == "mps":
        return "mps"
    if torch.cuda.is_available():
        return "cuda:0"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def generate(args: argparse.Namespace) -> Path:
    try:
        import soundfile as sf
        import torch
        from transformers import AutoProcessor, BarkModel
    except ImportError as exc:  # pragma: no cover - environment smoke covers this
        raise SystemExit(
            "Bark generation needs transformers, torch, and soundfile. "
            "Install them in the EPRS voice environment first."
        ) from exc

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Bark vocal manifest already exists: {manifest_path}")
    for index in range(1, len(args.text) + 1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        raw_destination = args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
        candidates = [destination]
        if args.autotune_preset != "none":
            candidates.extend([raw_destination, destination.with_suffix(destination.suffix + ".json")])
        existing = next((path for path in candidates if path.exists()), None)
        if existing:
            raise FileExistsError(f"Bark vocal output already exists: {existing}")

    processor = AutoProcessor.from_pretrained(args.model)
    model = BarkModel.from_pretrained(args.model)
    device = choose_device(torch, args.device)
    model.to(device)

    outputs: list[dict[str, Any]] = []
    for index, cue_text in enumerate(args.text, start=1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        raw_destination = (
            args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
            if args.autotune_preset != "none" else destination
        )
        # Bark has one text channel, so descriptive prose in this string is
        # spoken. Keep the style note in metadata and send only the lyric cue.
        prompt = cue_text
        inputs = processor(prompt, voice_preset=args.voice_preset, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            audio = model.generate(
                **inputs,
                do_sample=True,
                temperature=args.temperature,
                semantic_temperature=args.semantic_temperature,
            )
        samples = audio.detach().cpu().numpy().squeeze()
        sample_rate = int(model.generation_config.sample_rate)
        sf.write(raw_destination, samples, sample_rate, subtype="PCM_16")
        output = {
            "id": f"{args.prefix}-{index:02d}",
            "text": cue_text,
            "prompt": prompt,
            "style_note": args.prompt_prefix,
            "path": str(destination),
            "sample_rate": sample_rate,
            "channels": 1,
        }
        if args.autotune_preset != "none":
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
                    f"Apply EPRS {args.autotune_preset} tuning to this Bark "
                    f"performance cue in {args.autotune_key} {args.autotune_scale}."
                ),
            )
            output["raw"] = {"path": str(raw_destination), "sha256": sha256(raw_destination)}
            output["autotune_manifest"] = display_path(tuning_manifest)
        output["sha256"] = sha256(destination)
        outputs.append(output)

    try:
        transformers_version = version("transformers")
    except PackageNotFoundError:  # pragma: no cover
        transformers_version = "unknown"
    manifest = {
        "schema": "eprs.bark-singer-voice-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": args.model,
        "transformers_version": transformers_version,
        "voice_preset": args.voice_preset,
        "prompt_prefix": args.prompt_prefix,
        "seed": args.seed,
        "device": device,
        "temperature": args.temperature,
        "semantic_temperature": args.semantic_temperature,
        "autotune": {
            "preset": args.autotune_preset,
            "key": args.autotune_key if args.autotune_preset != "none" else None,
            "scale": args.autotune_scale if args.autotune_preset != "none" else None,
            "raw_cues_preserved": args.autotune_preset != "none",
        },
        "outputs": outputs,
        "rights": "Synthetic local Bark voice prompt; no human reference audio supplied by this runner.",
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
