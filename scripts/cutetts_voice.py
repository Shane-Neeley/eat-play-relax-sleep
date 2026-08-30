#!/usr/bin/env python3
"""Generate consent-bound local voice-clone cues with CuteTTS.

The reference is never copied or uploaded. This optional runner loads one
model for a bounded cue batch, refuses existing outputs, verifies the immutable
reference before and after inference, and records timing plus checkpoint hashes
in an ignored song-local or model-lab manifest.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from time import perf_counter
from typing import Any


MODEL_LICENSE = "Apache-2.0"
MAX_CUES = 32


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
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
    command.add_argument("--model-dir", type=Path, required=True)
    command.add_argument("--model-revision", required=True)
    command.add_argument("--code-revision", required=True)
    command.add_argument(
        "--reference-audio",
        type=Path,
        required=True,
        help="Local-only owned or explicitly consented voice reference",
    )
    command.add_argument(
        "--consent-note",
        required=True,
        help="Ownership/consent and permitted-use record for the reference voice",
    )
    command.add_argument("--text", action="append", required=True)
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--prefix", default="cutetts-cue")
    command.add_argument("--device", choices=("auto", "mps", "cpu", "cuda"), default="auto")
    command.add_argument("--seed", type=int, default=20260830)
    command.add_argument("--cfg-strength", type=float, default=2.0)
    command.add_argument("--diffusion-steps", type=int)
    command.add_argument("--max-decode-length", type=int, default=750)
    command.add_argument("--version", action="version", version="cutetts-voice 0.1")
    return command


def validate_args(args: argparse.Namespace) -> tuple[Path, Path]:
    model_dir = args.model_dir.expanduser().resolve()
    reference = args.reference_audio.expanduser().resolve()
    if not model_dir.is_dir():
        raise FileNotFoundError(model_dir)
    if not reference.is_file():
        raise FileNotFoundError(reference)
    if not args.consent_note.strip():
        raise ValueError("--consent-note must record explicit voice-reference consent")
    if not args.model_revision.strip() or not args.code_revision.strip():
        raise ValueError("CuteTTS model and code revisions must be non-empty")
    if not 1 <= len(args.text) <= MAX_CUES:
        raise ValueError(f"CuteTTS accepts 1 to {MAX_CUES} cues per bounded batch")
    if any(not text.strip() or len(text) > 1000 for text in args.text):
        raise ValueError("each CuteTTS cue must contain 1 to 1000 characters")
    if args.max_decode_length <= 0:
        raise ValueError("--max-decode-length must be positive")
    return model_dir, reference


def checkpoint_hashes(model_dir: Path) -> list[dict[str, str]]:
    checkpoints = sorted(model_dir.rglob("*.safetensors"))
    if not checkpoints:
        raise ValueError(f"CuteTTS model directory has no safetensors checkpoints: {model_dir}")
    return [
        {"path": str(path.relative_to(model_dir)), "sha256": sha256(path)}
        for path in checkpoints
    ]


def generate(args: argparse.Namespace) -> Path:
    run_started = perf_counter()
    model_dir, reference = validate_args(args)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"CuteTTS manifest already exists: {manifest_path}")
    destinations = [
        args.out_dir / f"{args.prefix}-{index:02d}.wav"
        for index in range(1, len(args.text) + 1)
    ]
    existing = next((path for path in destinations if path.exists()), None)
    if existing:
        raise FileExistsError(f"CuteTTS output already exists: {existing}")

    try:
        import soundfile as sf
        from cutetts import CuteTTS
    except ImportError as exc:  # pragma: no cover - optional environment
        raise SystemExit(
            "CuteTTS is not installed. Use an isolated Python environment and the official checkout."
        ) from exc

    reference_digest = sha256(reference)
    weights = checkpoint_hashes(model_dir)
    load_started = perf_counter()
    model = CuteTTS.from_pretrained(model_dir, device=args.device)
    model_load_seconds = perf_counter() - load_started

    generated: list[tuple[str, Any, int, int, float]] = []
    for index, text in enumerate(args.text, start=1):
        seed = args.seed + index - 1
        generation_started = perf_counter()
        result = model.generate(
            text,
            mode="voice_clone",
            reference_audio=reference,
            cfg_strength=args.cfg_strength,
            diffusion_steps=args.diffusion_steps,
            max_decode_length=args.max_decode_length,
            seed=seed,
            show_progress=False,
        )
        generation_seconds = perf_counter() - generation_started
        samples = result.waveform.squeeze(0).float().numpy()
        generated.append((text, samples, int(result.sample_rate), seed, generation_seconds))

    if sha256(reference) != reference_digest:
        raise RuntimeError("CuteTTS reference audio changed during generation")

    outputs = []
    for destination, item in zip(destinations, generated):
        text, samples, sample_rate, seed, generation_seconds = item
        sf.write(destination, samples, sample_rate, subtype="PCM_16")
        duration_seconds = len(samples) / sample_rate
        outputs.append({
            "id": destination.stem,
            "text": text,
            "path": display_path(destination),
            "sha256": sha256(destination),
            "sample_rate": sample_rate,
            "channels": 1,
            "duration_seconds": duration_seconds,
            "seed": seed,
            "generation_seconds": generation_seconds,
            "real_time_factor": generation_seconds / duration_seconds,
        })

    try:
        package_version = version("cutetts")
    except PackageNotFoundError:  # pragma: no cover
        package_version = "unknown"
    manifest = {
        "schema": "eprs.cutetts-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": "OPPO-Mente-Lab CuteTTS",
        "cutetts_version": package_version,
        "code_revision": args.code_revision,
        "model_revision": args.model_revision,
        "model_license": MODEL_LICENSE,
        "model_variant": getattr(model, "variant", "unknown"),
        "model_path": "<local model path withheld>",
        "checkpoints": weights,
        "device": args.device,
        "reference": {
            "path": "<local reference path withheld>",
            "sha256": reference_digest,
            "consent_note": args.consent_note,
            "copied": False,
            "uploaded": False,
        },
        "settings": {
            "cfg_strength": args.cfg_strength,
            "diffusion_steps": args.diffusion_steps,
            "max_decode_length": args.max_decode_length,
            "seed": args.seed,
        },
        "timing": {
            "model_load_seconds": model_load_seconds,
            "generation_seconds": sum(output["generation_seconds"] for output in outputs),
            "through_audio_render_seconds": perf_counter() - run_started,
            "reference_conditioning_reused": False,
        },
        "outputs": outputs,
        "rights": "Local reference use is limited to the explicit consent note above.",
        "review": "technical clone trial only; identity, musical fit, disclosure, and release remain separate gates",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    args = parser().parse_args()
    try:
        print(generate(args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
