#!/usr/bin/env python3
import argparse
import math
import struct
import wave
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Create an accented mono WAV click track.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--bpm", type=float, default=100.0)
    parser.add_argument("--bars", type=int, default=8)
    parser.add_argument("--beats-per-bar", type=int, default=4)
    parser.add_argument("--sample-rate", type=int, default=44100)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.bpm <= 0 or args.bars <= 0 or args.beats_per_bar <= 0 or args.sample_rate <= 0:
        raise SystemExit("BPM, bars, beats per bar, and sample rate must be positive.")
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {args.output}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    seconds_per_beat = 60.0 / args.bpm
    total_beats = args.bars * args.beats_per_bar
    total_frames = math.ceil(total_beats * seconds_per_beat * args.sample_rate)
    samples = [0.0] * total_frames
    click_frames = max(1, round(0.045 * args.sample_rate))

    for beat in range(total_beats):
        start = round(beat * seconds_per_beat * args.sample_rate)
        downbeat = beat % args.beats_per_bar == 0
        frequency = 1760.0 if downbeat else 1100.0
        amplitude = 0.72 if downbeat else 0.5
        for offset in range(min(click_frames, total_frames - start)):
            decay = math.exp(-7.0 * offset / click_frames)
            samples[start + offset] += amplitude * decay * math.sin(
                2.0 * math.pi * frequency * offset / args.sample_rate
            )

    with wave.open(str(args.output), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(args.sample_rate)
        frames = bytearray()
        for sample in samples:
            value = max(-1.0, min(1.0, sample))
            frames.extend(struct.pack("<h", round(value * 32767)))
        wav_file.writeframes(frames)

    print(args.output)


if __name__ == "__main__":
    main()
