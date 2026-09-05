#!/usr/bin/env python3
"""Build two deterministic, straight-4/4 wildlife-song dry-stem candidates.

The script only creates new files under the two named song workspaces.  It does
not edit or normalize the immutable iNaturalist recordings; FFmpeg makes a
song-local WAV delivery copy so the optional Pedalboard reader has a stable
integer-PCM input.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf


SAMPLE_RATE = 48_000


def midi_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    left = mono * (1.0 if pan <= 0 else 1.0 - pan)
    right = mono * (1.0 if pan >= 0 else 1.0 + pan)
    return np.column_stack((left, right)).astype(np.float32)


def write_wav(path: Path, audio: np.ndarray) -> None:
    if path.exists():
        raise FileExistsError(path)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0.92:
        audio = audio * (0.88 / peak)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio, dtype=np.float32), SAMPLE_RATE, subtype="PCM_24")


def env(length: int, attack: int, release: int) -> np.ndarray:
    result = np.ones(length, dtype=np.float32)
    if attack:
        result[:attack] = np.linspace(0.0, 1.0, attack, endpoint=False, dtype=np.float32)
    if release:
        result[-release:] *= np.linspace(1.0, 0.0, release, dtype=np.float32)
    return result


def add_tone(target: np.ndarray, start: int, duration: int, hz: float, gain: float,
             *, wave: str = "sine", pan: float = 0.0, detune: float = 0.0) -> None:
    if start >= len(target):
        return
    end = min(len(target), start + duration)
    count = end - start
    t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
    frequency = hz * (1.0 + detune * np.sin(2 * np.pi * 1.7 * t))
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    if wave == "triangle":
        osc = 2.0 * np.abs(2.0 * ((phase / (2 * np.pi)) % 1.0) - 1.0) - 1.0
    elif wave == "saw":
        osc = 2.0 * ((phase / (2 * np.pi)) % 1.0) - 1.0
    else:
        osc = np.sin(phase)
    attack = min(count // 4, max(1, int(0.012 * SAMPLE_RATE)))
    release = min(count // 3, max(1, int(0.08 * SAMPLE_RATE)))
    shaped = osc * env(count, attack, release) * gain
    if target.ndim == 1:
        target[start:end] += shaped.astype(np.float32)
    else:
        target[start:end, 0] += (shaped * (1.0 if pan <= 0 else 1.0 - pan)).astype(np.float32)
        target[start:end, 1] += (shaped * (1.0 if pan >= 0 else 1.0 + pan)).astype(np.float32)


def add_kick(target: np.ndarray, start: int, gain: float) -> None:
    length = min(len(target) - start, int(0.30 * SAMPLE_RATE))
    if length <= 0:
        return
    t = np.arange(length, dtype=np.float64) / SAMPLE_RATE
    frequency = 110.0 * np.exp(-t * 10.0) + 42.0
    phase = 2 * np.pi * np.cumsum(frequency) / SAMPLE_RATE
    body = np.sin(phase) * np.exp(-t * 13.0)
    click = np.sin(2 * np.pi * 2_400 * t) * np.exp(-t * 80.0) * 0.12
    target[start:start + length] += ((body + click) * gain).astype(np.float32)


def add_snare(target: np.ndarray, start: int, gain: float, rng: np.random.Generator) -> None:
    length = min(len(target) - start, int(0.22 * SAMPLE_RATE))
    if length <= 0:
        return
    t = np.arange(length, dtype=np.float64) / SAMPLE_RATE
    noise = rng.normal(0.0, 1.0, length) * np.exp(-t * 22.0)
    tone = np.sin(2 * np.pi * 190.0 * t) * np.exp(-t * 18.0) * 0.42
    target[start:start + length] += ((noise * 0.38 + tone) * gain).astype(np.float32)


def add_hat(target: np.ndarray, start: int, gain: float, rng: np.random.Generator) -> None:
    length = min(len(target) - start, int(0.055 * SAMPLE_RATE))
    if length <= 0:
        return
    t = np.arange(length, dtype=np.float64) / SAMPLE_RATE
    noise = rng.normal(0.0, 1.0, length) * np.exp(-t * 82.0)
    target[start:start + length] += (noise * gain).astype(np.float32)


def make_drums(total: int, bpm: float, seed: int, *, busy: bool) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = SAMPLE_RATE * 60.0 / bpm
    step = beat / 4.0
    audio = np.zeros((total, 2), dtype=np.float32)
    for index in range(int(np.ceil(total / step))):
        position = int(round(index * step))
        bar_step = index % 16
        if bar_step in (0, 6, 8, 14):
            add_kick(audio[:, 0], position, 0.58 if bar_step else 0.70)
            add_kick(audio[:, 1], position, 0.58 if bar_step else 0.70)
        if bar_step in (4, 12):
            add_snare(audio[:, 0], position, 0.34, rng)
            add_snare(audio[:, 1], position, 0.34, rng)
        if bar_step % 2 == 0 or (busy and bar_step in (3, 7, 11, 15)):
            add_hat(audio[:, 0], position, 0.075 if bar_step % 2 == 0 else 0.045, rng)
            add_hat(audio[:, 1], position, 0.075 if bar_step % 2 == 0 else 0.045, rng)
    return audio


def make_bass(total: int, bpm: float, roots: list[int], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = SAMPLE_RATE * 60.0 / bpm
    bar = beat * 4.0
    audio = np.zeros((total, 2), dtype=np.float32)
    for bar_index, root in enumerate(roots):
        bar_start = int(round(bar_index * bar))
        notes = (root, root, root + 7, root + 5)
        for beat_index, note in enumerate(notes):
            start = int(round(bar_start + beat_index * beat))
            length = int(round(beat * (0.72 if beat_index != 3 else 0.52)))
            add_tone(audio, start, length, midi_hz(note), 0.38, wave="saw", pan=0.0, detune=0.004)
            add_tone(audio, start, length, midi_hz(note - 12), 0.25, wave="sine", pan=0.0)
        if bar_index % 4 == 3:
            start = int(round(bar_start + 3.5 * beat))
            add_tone(audio, start, int(round(beat * 0.28)), midi_hz(root + 12), 0.18, wave="triangle")
    audio += rng.normal(0.0, 0.0012, audio.shape).astype(np.float32)
    return audio


def make_hook(total: int, bpm: float, bars: int, notes: list[int], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = SAMPLE_RATE * 60.0 / bpm
    step = beat / 2.0
    audio = np.zeros((total, 2), dtype=np.float32)
    for index in range(bars * 8):
        step_index = index % 8
        if step_index in (0, 2, 4, 5, 7):
            note = notes[step_index % len(notes)]
            start = int(round(index * step))
            add_tone(audio, start, int(round(step * 0.82)), midi_hz(note), 0.16,
                     wave="triangle", pan=0.14 if index % 2 else -0.08)
            add_tone(audio, start, int(round(step * 0.42)), midi_hz(note + 12), 0.045,
                     wave="sine", pan=-0.28 if index % 2 else 0.28)
    audio += rng.normal(0.0, 0.0007, audio.shape).astype(np.float32)
    return audio


def make_vocal_guide(total: int, bpm: float, starts: list[int], phrases: list[list[int]]) -> np.ndarray:
    """Make a synthetic vowel guide with deliberate small pitch drift for autotune."""
    beat = SAMPLE_RATE * 60.0 / bpm
    audio = np.zeros(total, dtype=np.float32)
    for bar_index, phrase in zip(starts, phrases):
        bar_start = int(round(bar_index * 4 * beat))
        for note_index, note in enumerate(phrase):
            start = bar_start + int(round(note_index * beat))
            length = int(round(beat * 0.78))
            end = min(total, start + length)
            if start >= total:
                continue
            count = end - start
            t = np.arange(count, dtype=np.float64) / SAMPLE_RATE
            glide = 0.018 * np.sin(2 * np.pi * 0.9 * t + note_index)
            hz = midi_hz(note) * (1.0 + glide)
            phase = 2 * np.pi * np.cumsum(hz) / SAMPLE_RATE
            # A compact vowel-like additive tone: fundamental plus formant-ish partials.
            voiced = (
                np.sin(phase)
                + 0.48 * np.sin(2 * phase + 0.2)
                + 0.24 * np.sin(3 * phase + 0.4)
                + 0.12 * np.sin(5 * phase + 0.7)
            )
            shape = env(count, int(0.025 * SAMPLE_RATE), int(0.10 * SAMPLE_RATE))
            audio[start:end] += (voiced * shape * 0.18).astype(np.float32)
    return stereo(audio)


def make_texture(total: int, bpm: float, seed: int, *, bright: bool) -> np.ndarray:
    rng = np.random.default_rng(seed)
    beat = SAMPLE_RATE * 60.0 / bpm
    audio = np.zeros((total, 2), dtype=np.float32)
    for bar_index in range(int(total / (4 * beat))):
        start = int(round((bar_index * 4 + 3.5) * beat))
        length = int(round(0.16 * SAMPLE_RATE))
        noise = rng.normal(0.0, 1.0, length).astype(np.float32)
        noise *= np.exp(-np.arange(length, dtype=np.float32) / (0.04 * SAMPLE_RATE))
        gain = 0.065 if bright else 0.045
        audio[start:min(total, start + length), 0] += noise[:max(0, min(length, total - start))] * gain
        audio[start:min(total, start + length), 1] += noise[:max(0, min(length, total - start))] * gain * 0.75
        if bar_index % 4 == 3:
            add_tone(audio, start, int(0.42 * SAMPLE_RATE), 440 if bright else 220, 0.07,
                     wave="sine", pan=0.35)
    return audio


def convert_source(raw: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", str(raw),
         "-ar", str(SAMPLE_RATE), "-ac", "2", "-c:a", "pcm_s16le", str(destination)],
        check=True,
    )


def build(song: Path, raw_source: Path, *, bpm: float, bars: int, roots: list[int],
          hook: list[int], vocal_starts: list[int], vocal_phrases: list[list[int]],
          seed: int, source_name: str) -> None:
    audio = song / "audio"
    total = int(round(bars * 4 * SAMPLE_RATE * 60.0 / bpm))
    convert_source(raw_source, audio / f"{source_name}-source.wav")
    stems = {
        "drums-dry.wav": make_drums(total, bpm, seed, busy=source_name == "monkey"),
        "bass-dry.wav": make_bass(total, bpm, roots, seed + 1),
        "hook-dry.wav": make_hook(total, bpm, bars, hook, seed + 2),
        "vocal-guide-raw.wav": make_vocal_guide(total, bpm, vocal_starts, vocal_phrases),
        "texture-dry.wav": make_texture(total, bpm, seed + 3, bright=source_name == "monkey"),
    }
    for name, data in stems.items():
        write_wav(audio / name, data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--whale-raw", type=Path, required=True)
    parser.add_argument("--monkey-raw", type=Path, required=True)
    args = parser.parse_args()
    build(
        args.repo / "songs/blue-signal-bounce", args.whale_raw,
        bpm=100, bars=32, roots=[45, 45, 48, 43] * 8,
        hook=[69, 72, 74, 76, 79], vocal_starts=[0, 4, 8, 16, 24, 28],
        vocal_phrases=[[69, 72, 74, 76], [69, 72, 74, 79], [74, 72, 69, 67],
                       [69, 72, 74, 76], [79, 76, 74, 72], [69, 72, 74, 69]],
        seed=2026090401, source_name="whale",
    )
    build(
        args.repo / "songs/canopy-click", args.monkey_raw,
        bpm=108, bars=36, roots=[40, 40, 43, 38] * 9,
        hook=[64, 67, 69, 71, 74], vocal_starts=[0, 4, 8, 16, 24, 28, 32],
        vocal_phrases=[[64, 67, 69, 71], [64, 67, 69, 74], [69, 67, 64, 62],
                       [64, 67, 69, 71], [74, 71, 69, 67], [64, 67, 69, 64],
                       [64, 67, 69, 71]],
        seed=2026090402, source_name="monkey",
    )


if __name__ == "__main__":
    main()
