#!/usr/bin/env python3
"""Generate consent-bound Raon-OpenTTS speech cues from a voice reference.

Raon-OpenTTS is a speech-first, zero-shot TTS model. This runner intentionally
does not call the result a singing voice: use a recorded vocal with
``eprs autotune`` for actual singing, or author target notes with
``scripts/note_aware_melody.py`` before any final pitch treatment.

The official Raon-OpenTTS checkout and its model weights remain in an ignored
local environment. Only new song-local WAV cues and a provenance manifest are
written by this runner. A human reference sample is required, along with its
transcript and an explicit consent/rights note.

This is a public-repository workflow: keep the reference and the generated
manifest in ignored local storage. The manifest records a checksum and rights
evidence, but deliberately redacts the reference path so an accidental public
copy does not reveal a private filesystem location.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import sys
from typing import Any


DEFAULT_MODEL = "KRAFTON/Raon-OpenTTS-1B"
DEFAULT_CONFIG = "src/f5_tts/configs/1b.yaml"
MODEL_LICENSE = "CC-BY-NC-4.0"
CODE_LICENSE = "Apache-2.0"
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
    command.add_argument(
        "--reference-audio", type=Path, required=True,
        help="Local-only owned/consented reference WAV; never copied or overwritten",
    )
    command.add_argument("--reference-text", required=True,
                         help="Exact words spoken in the reference sample")
    command.add_argument(
        "--consent-note", required=True,
        help="Explicit note recording ownership/consent and permitted use of the reference voice",
    )
    command.add_argument("--text", action="append", required=True,
                         help="One short speech cue; repeat for a bounded batch")
    command.add_argument(
        "--out-dir", type=Path, required=True,
        help="Ignored song-local output directory for derived cues and manifest",
    )
    command.add_argument("--prefix", default="raon-cue")
    command.add_argument("--model", default=DEFAULT_MODEL)
    command.add_argument("--model-revision", help="Exact model revision or commit when pinned")
    command.add_argument("--repo-dir", type=Path, default=Path(".eprs-local/raon-opentts"))
    command.add_argument("--config", type=Path, help="Raon config; defaults to the official 1B config")
    command.add_argument("--checkpoint", type=Path, required=True,
                         help="Downloaded Raon checkpoint (.pt/.pth/.safetensors)")
    command.add_argument("--vocoder-dir", type=Path, required=True,
                         help="Directory containing generator.ckpt for the 16 kHz HiFi-GAN vocoder")
    command.add_argument("--seed", type=int, default=20260819)
    command.add_argument("--device", default="auto", choices=("auto", "mps", "cpu", "cuda"))
    command.add_argument("--steps", type=int, default=32)
    command.add_argument("--cfg-strength", type=float, default=2.0)
    command.add_argument("--speed", type=float, default=1.0)
    command.add_argument(
        "--autotune-preset", choices=AUTOTUNE_PRESETS, default="none",
        help="Preserve raw speech and optionally render a separate EPRS pitch treatment",
    )
    command.add_argument("--autotune-key", default="C")
    command.add_argument("--autotune-scale", default="chromatic")
    command.add_argument("--version", action="version", version="raon-opentts-voice 0.1")
    return command


def choose_device(torch: Any, requested: str) -> Any:
    if requested == "cpu":
        return torch.device("cpu")
    if requested == "mps":
        if not getattr(torch.backends, "mps", None) or not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is not available")
        return torch.device("mps")
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        return torch.device("cuda:0")
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def _resolve_path(path: Path, *, base: Path | None = None) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute() and base is not None:
        candidate = base / candidate
    return candidate.resolve()


def load_model(args: argparse.Namespace, torch: Any) -> tuple[Any, Any, Any, Any, str]:
    repo_dir = _resolve_path(args.repo_dir)
    repo_src = repo_dir / "src"
    if not repo_src.is_dir():
        raise FileNotFoundError(f"Raon-OpenTTS source checkout is missing: {repo_src}")
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    try:
        import hydra
        from ema_pytorch import EMA
        from f5_tts.infer.utils_infer import infer_process, load_vocoder
        from f5_tts.model import CFM
        from f5_tts.model.utils import get_tokenizer
        from omegaconf import OmegaConf
        from safetensors.torch import load_file
    except ImportError as exc:  # pragma: no cover - optional environment
        raise RuntimeError(
            "Raon-OpenTTS is not installed in the selected environment; install the official "
            "checkout dependencies in the isolated environment at .eprs-local/raon-opentts-env."
        ) from exc

    config = _resolve_path(args.config, base=repo_dir) if args.config else repo_dir / DEFAULT_CONFIG
    checkpoint = _resolve_path(args.checkpoint)
    vocoder_dir = _resolve_path(args.vocoder_dir)
    for path, label in ((config, "Raon config"), (checkpoint, "Raon checkpoint"), (vocoder_dir, "Raon vocoder")):
        if not path.exists():
            raise FileNotFoundError(f"{label} is missing: {path}")
    device = choose_device(torch, args.device)
    model_cfg = OmegaConf.load(config)
    model_cls = hydra.utils.get_class(f"f5_tts.model.{model_cfg.model.backbone}")
    mel_spec_cfg = model_cfg.model.mel_spec
    tokenizer_name = model_cfg.model.tokenizer
    tokenizer_path = model_cfg.model.tokenizer_path
    paths = str(tokenizer_path).split("|")
    char_maps = [get_tokenizer(str(repo_dir / path), tokenizer_name)[0] for path in paths]
    vocab_tokens = sorted({token for cmap in char_maps for token in cmap})
    if checkpoint.suffix == ".safetensors":
        checkpoint_data = {"ema_model_state_dict": load_file(str(checkpoint))}
    else:
        checkpoint_data = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
    if not isinstance(checkpoint_data, dict) or "ema_model_state_dict" not in checkpoint_data:
        raise RuntimeError("Raon checkpoint does not contain ema_model_state_dict")
    text_weight = checkpoint_data["ema_model_state_dict"].get(
        "ema_model.transformer.text_embed.text_embed.weight"
    )
    if text_weight is None or len(text_weight.shape) != 2:
        raise RuntimeError("Raon checkpoint does not expose its text embedding table")
    checkpoint_vocab_size = int(text_weight.shape[0]) - 1
    vocab_adjustment: dict[str, Any] | None = None
    if len(vocab_tokens) != checkpoint_vocab_size:
        if len(vocab_tokens) < checkpoint_vocab_size:
            raise RuntimeError(
                f"Raon vocabulary has {len(vocab_tokens)} tokens but the checkpoint needs "
                f"{checkpoint_vocab_size}"
            )
        dropped = vocab_tokens[checkpoint_vocab_size:]
        vocab_tokens = vocab_tokens[:checkpoint_vocab_size]
        vocab_adjustment = {
            "source_size": len(vocab_tokens) + len(dropped),
            "checkpoint_size": checkpoint_vocab_size,
            "dropped_tail_tokens": dropped,
            "reason": "checkpoint embedding table is authoritative",
        }
    vocab_char_map = {token: index for index, token in enumerate(vocab_tokens)}
    model = CFM(
        transformer=model_cls(
            **model_cfg.model.arch,
            text_num_embeds=len(vocab_char_map),
            mel_dim=mel_spec_cfg.n_mel_channels,
        ),
        mel_spec_kwargs=mel_spec_cfg,
        vocab_char_map=vocab_char_map,
    ).to(device)
    ema = EMA(model, include_online_model=False).to(device)
    ema.load_state_dict(checkpoint_data["ema_model_state_dict"])
    for key, parameter in ema.ema_model.state_dict().items():
        model.state_dict()[key].copy_(parameter)
    model.eval()
    vocoder = load_vocoder(
        vocoder_name=model_cfg.model.mel_spec.mel_spec_type,
        is_local=True,
        local_path=str(vocoder_dir),
        device=device,
    )
    return model, vocoder, infer_process, model_cfg, str(device), vocab_adjustment


def generate(args: argparse.Namespace) -> Path:
    reference_audio = _resolve_path(args.reference_audio)
    if not reference_audio.is_file():
        raise FileNotFoundError(reference_audio)
    if not args.reference_text.strip():
        raise ValueError("--reference-text must contain the exact reference words")
    if not args.consent_note.strip():
        raise ValueError("--consent-note must record explicit voice-reference consent")
    if not args.text or any(not text.strip() or len(text) > 400 for text in args.text):
        raise ValueError("each --text cue must contain 1 to 400 characters")
    if not 1 <= args.steps <= 128:
        raise ValueError("--steps must be between 1 and 128")
    if args.cfg_strength <= 0 or args.speed <= 0:
        raise ValueError("--cfg-strength and --speed must be positive")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Raon-OpenTTS render manifest already exists: {manifest_path}")
    for index in range(1, len(args.text) + 1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        raw_destination = (
            args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
            if args.autotune_preset != "none" else destination
        )
        for candidate in (destination, raw_destination, destination.with_suffix(destination.suffix + ".json")):
            if candidate.exists():
                raise FileExistsError(f"Raon-OpenTTS output already exists: {candidate}")

    try:
        import soundfile as sf
        import torch
    except ImportError as exc:  # pragma: no cover - optional environment
        raise RuntimeError("Raon-OpenTTS rendering needs torch and soundfile") from exc
    torch.manual_seed(args.seed)
    model, vocoder, infer_process, model_cfg, device, vocab_adjustment = load_model(args, torch)
    outputs: list[dict[str, Any]] = []
    for index, cue_text in enumerate(args.text, start=1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        raw_destination = (
            args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
            if args.autotune_preset != "none" else destination
        )
        samples, sample_rate, _ = infer_process(
            str(reference_audio),
            args.reference_text,
            cue_text,
            model,
            vocoder,
            mel_spec_type=model_cfg.model.mel_spec.mel_spec_type,
            nfe_step=args.steps,
            cfg_strength=args.cfg_strength,
            speed=args.speed,
            device=device,
        )
        if samples is None or len(samples) == 0:
            raise RuntimeError(f"Raon-OpenTTS returned empty audio for cue {index}")
        sf.write(raw_destination, samples, int(sample_rate), subtype="PCM_16")
        output: dict[str, Any] = {
            "id": f"{args.prefix}-{index:02d}",
            "text": cue_text,
            "path": display_path(destination),
            "sample_rate": int(sample_rate),
            "channels": 1,
        }
        if args.autotune_preset != "none":
            project_src = Path(__file__).resolve().parents[1] / "src"
            if str(project_src) not in sys.path:
                sys.path.insert(0, str(project_src))
            from eprs.autotune import render_autotune, settings_for

            settings = settings_for(args.autotune_preset, key=args.autotune_key, scale=args.autotune_scale)
            _, tuning_manifest, _ = render_autotune(
                raw_destination,
                destination,
                settings,
                intent=(
                    f"Apply the {args.autotune_preset} EPRS pitch treatment to this "
                    f"consented Raon speech cue in {args.autotune_key} {args.autotune_scale}."
                ),
            )
            output["raw"] = {"path": display_path(raw_destination), "sha256": sha256(raw_destination)}
            output["autotune_manifest"] = display_path(tuning_manifest)
        output["sha256"] = sha256(destination)
        outputs.append(output)

    try:
        package_version = version("raon-opentts")
    except PackageNotFoundError:  # pragma: no cover - unusual editable install
        package_version = "unknown"
    checkpoint = _resolve_path(args.checkpoint)
    config = _resolve_path(args.config, base=_resolve_path(args.repo_dir)) if args.config else _resolve_path(args.repo_dir) / DEFAULT_CONFIG
    manifest = {
        "schema": "eprs.raon-opentts-voice-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": args.model,
        "model_revision": args.model_revision,
        "model_license": MODEL_LICENSE,
        "code_license": CODE_LICENSE,
        "raon_opentts_version": package_version,
        "repo_dir": display_path(_resolve_path(args.repo_dir)),
        "config": {"path": display_path(config), "sha256": sha256(config)},
        "checkpoint": {"path": display_path(checkpoint), "sha256": sha256(checkpoint)},
        "vocoder": {"path": display_path(_resolve_path(args.vocoder_dir)), "sample_rate": 16000},
        "reference": {
            "path": "<local reference path withheld>",
            "sha256": sha256(reference_audio),
            "transcript": args.reference_text,
            "consent_note": args.consent_note,
        },
        "seed": args.seed,
        "device": device,
        "settings": {"steps": args.steps, "cfg_strength": args.cfg_strength, "speed": args.speed},
        "tokenizer": {"checkpoint_compatible_adjustment": vocab_adjustment},
        "autotune": {
            "preset": args.autotune_preset,
            "key": args.autotune_key if args.autotune_preset != "none" else None,
            "scale": args.autotune_scale if args.autotune_preset != "none" else None,
            "raw_cues_preserved": args.autotune_preset != "none",
        },
        "outputs": outputs,
        "voice_role": "consented reference-conditioned speech cue; not a singing model",
        "rights": "Reference use is consented as recorded above; Raon-OpenTTS model license is CC-BY-NC-4.0.",
        "review": "technical render only; creative listening, identity disclosure, and release rights remain separate gates",
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
