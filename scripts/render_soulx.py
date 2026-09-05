#!/usr/bin/env python3
"""Render validated scores with an installed SoulX runtime and consented voice.

Run in a prepared Torch/SoulX environment. References remain outside the public
repository; the receipt records hashes, never private reference paths or text.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eprs.singing_score import phrase_placements, validate_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "runtime",
        "model",
        "config",
        "reference",
        "reference-score",
        "score",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--consent", action="store_true", required=True)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--seed", type=int, default=20260905)
    args = parser.parse_args()
    score = json.loads(args.score.read_text())
    reference_score = json.loads(args.reference_score.read_text())
    validate_score(score)
    validate_score(reference_score)
    if len(reference_score) != 1 or reference_score[0]["time"][0] != 0:
        parser.error("Reference must be one aligned phrase starting at zero")
    if args.output.exists():
        parser.error("Output directory already exists; preserve prior takes")
    if not 1 <= args.steps <= 128:
        parser.error("Steps must be between 1 and 128")
    sys.path.insert(0, str(args.runtime.resolve()))
    import numpy as np
    import soundfile as sf
    import torch
    from cli.inference import build_model
    from soulxsinger.utils.data_processor import DataProcessor
    from soulxsinger.utils.file_utils import load_config

    config = load_config(str(args.config))
    rate = int(config.audio.sample_rate)
    reference_info = sf.info(args.reference)
    if (
        abs(
            reference_info.duration
            - sum(map(float, reference_score[0]["duration"].split()))
        )
        > 0.025
    ):
        parser.error("Reference audio duration must match aligned reference metadata")
    model = build_model(str(args.model), config, args.device)
    processor = DataProcessor(
        config.audio.hop_size,
        rate,
        str(args.runtime / "soulxsinger/utils/phoneme/phone_set.json"),
        args.device,
    )
    reference = processor.process(
        copy.deepcopy(reference_score[0]), str(args.reference)
    )
    args.output.mkdir(parents=True)
    waves = []
    for i, segment in enumerate(score):
        torch.manual_seed(args.seed + i)
        data = {
            "prompt": reference,
            "target": processor.process(copy.deepcopy(segment), None),
        }
        with torch.inference_mode():
            wave = (
                model.infer(
                    data,
                    control="score",
                    n_steps=args.steps,
                    cfg=config.infer.cfg,
                    auto_shift=False,
                    pitch_shift=0,
                )
                .squeeze()
                .cpu()
                .numpy()
            )
        if wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all():
            raise ValueError("Model returned invalid audio")
        sf.write(args.output / f"phrase-{i:02}.wav", wave, rate, subtype="FLOAT")
        waves.append(wave)
        print(f"Saved phrase {i + 1}/{len(score)}", flush=True)
    starts, total = phrase_placements(score, [len(w) for w in waves], rate)
    merged = np.zeros(total, dtype=np.float32)
    for start, wave in zip(starts, waves):
        merged[start : start + len(wave)] += wave
    sf.write(args.output / "vocal.wav", merged, rate, subtype="FLOAT")

    def digest(path):
        return hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest()

    receipt = {
        "schema": "eprs.soulx-render/v2",
        "model": "Soul-AILab/SoulX-Singer",
        "model_sha256": digest(args.model),
        "reference_sha256": digest(args.reference),
        "reference_score_sha256": digest(args.reference_score),
        "score_sha256": digest(args.score),
        "config_sha256": digest(args.config),
        "output_sha256": digest(args.output / "vocal.wav"),
        "steps": args.steps,
        "seed": args.seed,
        "device": args.device,
        "control": "score",
        "pitch_shift": 0,
        "sample_rate": rate,
        "consent": True,
        "assembly": "additive; all generated samples retained",
        "phrase_lengths": [len(w) for w in waves],
    }
    (args.output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
