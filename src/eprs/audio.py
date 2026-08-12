"""Dependency-free deterministic audio renderer for BeatScript prototypes."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import random
import wave

from .beat import Beat, Track, expanded_steps, track_active


SAMPLE_RATE = 48_000


def _midi(note: str) -> int:
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
             "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
             "A": 9, "A#": 10, "Bb": 10, "B": 11}
    pitch, octave = note[:-1], int(note[-1])
    return (octave + 1) * 12 + names[pitch[0].upper() + pitch[1:]]


def _frequency(note: str) -> float:
    return 440.0 * 2 ** ((_midi(note) - 69) / 12)


def _envelope(t: float, duration: float, attack: float = 0.006, release: float = 0.08) -> float:
    if t < attack:
        return t / max(attack, 1e-6)
    if t > duration - release:
        return max(0.0, (duration - t) / max(release, 1e-6))
    return 1.0


def _hit(kind: str, duration: float, rng: random.Random, frequency: float | None = None) -> list[float]:
    length = max(1, int(duration * SAMPLE_RATE))
    out = [0.0] * length
    phase = 0.0
    for index in range(length):
        t = index / SAMPLE_RATE
        if kind == "kick":
            freq = 46 + 105 * math.exp(-t * 35)
            phase += 2 * math.pi * freq / SAMPLE_RATE
            out[index] = math.sin(phase) * math.exp(-t * 11) + (rng.random() * 2 - 1) * math.exp(-t * 90) * 0.08
        elif kind in {"snare", "clap"}:
            burst = 1.0
            if kind == "clap":
                burst = max(math.exp(-((t - center) / 0.008) ** 2) for center in (0.0, 0.026, 0.052))
            noise = rng.random() * 2 - 1
            tone = math.sin(2 * math.pi * 185 * t)
            out[index] = (noise * 0.75 + tone * 0.25) * math.exp(-t * (13 if kind == "snare" else 9)) * burst
        elif kind in {"hat", "shaker", "ride", "crash"}:
            noise = rng.random() * 2 - 1
            metallic = (
                math.sin(2 * math.pi * 6421 * t)
                + 0.55 * math.sin(2 * math.pi * 8173 * t)
                + 0.32 * math.sin(2 * math.pi * 9347 * t)
            ) * 0.18
            decay = {"hat": 50, "shaker": 24, "ride": 7.5, "crash": 2.8}[kind]
            body = math.sin(2 * math.pi * (480 if kind == "ride" else 310) * t) * 0.12
            out[index] = (noise * 0.68 + metallic + body) * math.exp(-t * decay)
        elif kind == "stick":
            noise = rng.random() * 2 - 1
            out[index] = (
                math.sin(2 * math.pi * 1580 * t) * 0.62 + noise * 0.38
            ) * math.exp(-t * 48)
        elif kind in {"tom", "perc"}:
            freq = 118 if kind == "tom" else 310
            out[index] = math.sin(2 * math.pi * freq * t + 2 * math.exp(-t * 20)) * math.exp(-t * 12)
        else:
            freq = frequency or 110.0
            phase += 2 * math.pi * freq / SAMPLE_RATE
            sine = math.sin(phase)
            triangle = 2 / math.pi * math.asin(math.sin(phase))
            waveform = 0.72 * sine + 0.28 * triangle
            out[index] = waveform * _envelope(t, duration) * (0.9 if kind == "bass" else 0.65)
    return out


def _level_sample(samples: list[float], options: dict[str, str]) -> list[float]:
    """Apply explicit per-sample leveling without allowing inter-sample overs."""
    mode = options.get("sample_level", "none").lower()
    if mode == "none":
        return samples
    if mode not in {"rms", "peak"}:
        raise ValueError(f"sample_level must be none, rms, or peak: {mode}")
    if not samples:
        return samples
    peak = max(abs(value) for value in samples)
    if peak <= 0:
        return samples
    if mode == "peak":
        target = float(options.get("sample_target_peak", "0.82"))
        scale = target / peak
    else:
        target = float(options.get("sample_target_rms", "0.16"))
        rms = math.sqrt(sum(value * value for value in samples) / len(samples))
        if rms <= 0:
            return samples
        scale = target / rms
    ceiling = float(options.get("sample_peak_ceiling", "0.88"))
    scale = min(scale, ceiling / peak)
    return [value * scale for value in samples]


def _load_sample(path: Path, options: dict[str, str] | None = None) -> tuple[list[float], int]:
    with wave.open(str(path), "rb") as wav:
        channels, width, rate, frames = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
        if width not in {1, 2, 3, 4}:
            raise ValueError(f"External sample must be 8/16/24/32-bit integer PCM WAV for headless rendering: {path}")
        payload = wav.readframes(frames)
        if width == 1:
            raw = [(value - 128) / 128 for value in payload]
        elif width == 2:
            values = array("h")
            values.frombytes(payload)
            raw = [value / 32768 for value in values]
        else:
            scale = float(1 << (width * 8 - 1))
            raw = [
                int.from_bytes(payload[index:index + width], "little", signed=True) / scale
                for index in range(0, len(payload), width)
            ]
        if channels == 1:
            mono = list(raw)
        else:
            mono = [sum(raw[i : i + channels]) / channels for i in range(0, len(raw), channels)]
    return _level_sample(mono, options or {}), rate


def _resample(samples: list[float], source_rate: int) -> list[float]:
    if source_rate == SAMPLE_RATE:
        return samples
    size = round(len(samples) * SAMPLE_RATE / source_rate)
    return [samples[min(len(samples) - 1, int(i * source_rate / SAMPLE_RATE))] for i in range(size)]


def _gain_pan(options: dict[str, str], velocity: float) -> tuple[float, float]:
    gain = float(options.get("gain", "0.65")) * velocity
    pan = max(-1.0, min(1.0, float(options.get("pan", "0"))))
    return gain * math.sqrt((1 - pan) / 2), gain * math.sqrt((1 + pan) / 2)


def _step_start(beat: Beat, index: int) -> float:
    base = index * beat.seconds_per_step
    if index % 2 == 1:
        base += (beat.swing - 0.5) * 2 * beat.seconds_per_step
    return base


def render(beat: Beat, output: str | Path) -> Path:
    tail = 1.4
    frame_count = int((beat.duration + tail) * SAMPLE_RATE)
    # Float arrays keep multi-minute renders memory-bounded.
    left = array("f", [0.0]) * frame_count
    right = array("f", [0.0]) * frame_count
    rng = random.Random(beat.seed)

    for track in beat.tracks:
        options = track.options
        sample_data: list[float] | None = None
        if "sample" in options:
            sample_path = Path(options["sample"])
            if not sample_path.is_absolute() and beat.source:
                sample_path = (beat.source.parent / sample_path).resolve()
            sample_data, rate = _load_sample(sample_path, options)
            sample_data = _resample(sample_data, rate)
        events = expanded_steps(track, beat.total_steps)
        for step_index, token in enumerate(events):
            if token in {".", "~"} or not track_active(track, step_index, beat.steps_per_bar):
                continue
            start_seconds = _step_start(beat, step_index) + float(options.get("offset_ms", "0")) / 1000
            humanize_ms = float(options.get("humanize_ms", "0"))
            if humanize_ms:
                start_seconds += rng.uniform(-humanize_ms, humanize_ms) / 1000
            start = max(0, int(start_seconds * SAMPLE_RATE))
            velocity = {"g": 0.33, "x": 0.72, "X": 1.0, "o": 0.82}.get(token, 0.72)
            gain_l, gain_r = _gain_pan(options, velocity)
            if track.kind == "notes":
                notes = token.split("+")
                duration_steps = float(options.get("length", "1.8"))
                sounds = [_hit(options.get("voice", "bass"), beat.seconds_per_step * duration_steps, rng, _frequency(note)) for note in notes]
                sound = [sum(values) / len(sounds) for values in zip(*sounds)]
            elif sample_data is not None:
                sound = sample_data
            else:
                hit_duration = {
                    "kick": 0.55,
                    "snare": 0.42,
                    "clap": 0.35,
                    "hat": 0.52 if token == "o" else 0.15,
                    "shaker": 0.28,
                    "stick": 0.16,
                    "ride": 0.72,
                    "crash": 2.4,
                }.get(track.kind, 0.38)
                sound = _hit(track.kind, hit_duration, rng)
            for offset, value in enumerate(sound):
                target = start + offset
                if target >= frame_count:
                    break
                left[target] += value * gain_l
                right[target] += value * gain_r

    # A short, quiet feedback delay creates room while preserving transients.
    delay = int(0.187 * SAMPLE_RATE)
    for index in range(delay, frame_count):
        left[index] += right[index - delay] * 0.09
        right[index] += left[index - delay] * 0.09
    peak = max(max(abs(x) for x in left), max(abs(x) for x in right))
    # Keep every non-silent render at the same safe peak. The old max(1.0, peak)
    # floor preserved quiet mixes at their input level, making sparse songs
    # needlessly quiet even when they had ample headroom.
    scale = 0.92 / peak if peak else 1.0
    pcm = array("h")
    for l_value, r_value in zip(left, right):
        pcm.append(round(max(-1, min(1, l_value * scale)) * 32767))
        pcm.append(round(max(-1, min(1, r_value * scale)) * 32767))
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return destination
