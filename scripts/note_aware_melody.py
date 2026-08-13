#!/usr/bin/env python3
"""Turn short voice or field-recording cues into declared musical notes.

This is deliberately a composition aid, not a replacement for listening.  A
source cue is pitch-estimated, formant-preserving pitch-shifted with Rubber
Band, stretched to an explicit duration, and placed on a timeline.  The
important distinction from ordinary autotune is that the note and its hold
length are authored before pitch correction is rendered.

Item syntax::

    --item PATH|SOURCE_MIDI|TARGET_MIDI|DURATION_SECONDS|START_SECONDS|GAIN_DB

SOURCE_MIDI may be ``auto``.  Paths are resolved from the current directory.
The output and JSON manifest are always new files.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any


SCHEMA = "eprs.note-aware-melody/v1"


@dataclass(frozen=True)
class MelodyItem:
    path: Path
    source_midi: float | None
    target_midi: float
    duration_seconds: float
    start_seconds: float
    gain_db: float = -6.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def midi_name(midi: float) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    rounded = int(round(midi))
    return f"{names[rounded % 12]}{rounded // 12 - 1}"


def parse_item(value: str) -> MelodyItem:
    fields = value.split("|")
    if len(fields) not in (5, 6):
        raise ValueError("melody item must be PATH|SOURCE_MIDI|TARGET_MIDI|DURATION|START[|GAIN_DB]")
    path = Path(fields[0]).expanduser()
    source = None if fields[1].strip().lower() == "auto" else float(fields[1])
    target = float(fields[2])
    duration = float(fields[3])
    start = float(fields[4])
    gain = float(fields[5]) if len(fields) == 6 else -6.0
    if duration <= 0 or start < 0:
        raise ValueError("melody item duration must be positive and start must be non-negative")
    if not all(math.isfinite(number) for number in (target, duration, start, gain)):
        raise ValueError("melody item fields must be finite")
    if source is not None and not math.isfinite(source):
        raise ValueError("melody source MIDI must be finite or auto")
    return MelodyItem(path, source, target, duration, start, gain)


def estimate_source_midi(path: Path) -> tuple[float, float]:
    try:
        import numpy as np
        import pyworld as imported_pyworld
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("note-aware rendering needs numpy, soundfile, and pyworld") from exc
    pw: Any = imported_pyworld
    audio, sample_rate = sf.read(path, dtype="float64", always_2d=True)
    signal = np.mean(audio, axis=1).astype(np.float64)
    f0, positions = pw.dio(signal, sample_rate, f0_floor=55, f0_ceil=900, frame_period=5)
    f0 = pw.stonemask(signal, f0, positions, sample_rate)
    voiced = f0[f0 > 0]
    if len(voiced) < 3:
        raise ValueError(f"no stable voiced pitch found in {path}")
    # Ignore the quietest edge material where TTS and field recordings often
    # contain breath, handling noise, or a tail that should not set the note.
    median_hz = float(np.median(voiced))
    midi = 69 + 12 * math.log2(median_hz / 440)
    return midi, len(voiced) / max(1, len(f0))


def run_rubberband(source: Path, destination: Path, *, shift: float, duration: float) -> None:
    if shutil.which("rubberband") is None:
        raise RuntimeError("Rubber Band is required; install it with `brew install rubberband`")
    command = [
        "rubberband", "-3", "-F", "-q",
        f"-p{shift:.6f}", f"-D{duration:.6f}", str(source), str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"Rubber Band failed: {completed.stderr.strip() or completed.stdout.strip()}")


def render(items: list[MelodyItem], output: Path, manifest_path: Path, *, total_seconds: float) -> Path:
    if output.resolve() == manifest_path.resolve():
        raise ValueError("audio output and manifest must use different paths")
    if output.exists() or manifest_path.exists():
        raise FileExistsError(output if output.exists() else manifest_path)
    if not items:
        raise ValueError("at least one melody item is required")
    if not math.isfinite(total_seconds) or total_seconds <= 0:
        raise ValueError("total duration must be positive and finite")
    if any(item.start_seconds + item.duration_seconds > total_seconds + 1e-6 for item in items):
        raise ValueError("a melody item extends past the declared total duration")
    for item in items:
        if not item.path.is_file():
            raise FileNotFoundError(item.path)
    try:
        import numpy as np
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("note-aware rendering needs numpy and soundfile") from exc

    with tempfile.TemporaryDirectory(prefix="eprs-note-aware-") as temp_dir:
        temp = Path(temp_dir)
        rendered_items: list[dict[str, Any]] = []
        sample_rate: int | None = None
        output_buffer: Any = None
        for index, item in enumerate(items, start=1):
            source_midi = item.source_midi
            voiced_ratio = None
            if source_midi is None:
                source_midi, voiced_ratio = estimate_source_midi(item.path)
            shifted = temp / f"item-{index:02d}.wav"
            run_rubberband(
                item.path, shifted,
                shift=item.target_midi - source_midi,
                duration=item.duration_seconds,
            )
            audio, rate = sf.read(shifted, dtype="float64", always_2d=True)
            if sample_rate is None:
                sample_rate = int(rate)
                output_buffer = np.zeros((round(total_seconds * sample_rate), audio.shape[1]), dtype=np.float64)
            if int(rate) != sample_rate:
                raise ValueError("all melody items must use one sample rate")
            if audio.shape[1] != output_buffer.shape[1]:
                if audio.shape[1] == 1 and output_buffer.shape[1] == 2:
                    audio = np.repeat(audio, 2, axis=1)
                elif audio.shape[1] == 2 and output_buffer.shape[1] == 1:
                    audio = np.mean(audio, axis=1, keepdims=True)
                else:
                    raise ValueError("melody items have incompatible channel layouts")
            length = min(len(audio), round(item.duration_seconds * sample_rate))
            # Tiny fades prevent clicks when a field recording or TTS cue is
            # placed on a hard grid. The musical note itself remains intact.
            envelope = np.ones(length, dtype=np.float64)
            fade = min(round(0.015 * sample_rate), length // 2)
            if fade:
                envelope[:fade] *= np.linspace(0, 1, fade)
                envelope[-fade:] *= np.linspace(1, 0, fade)
            start = round(item.start_seconds * sample_rate)
            gain = 10 ** (item.gain_db / 20)
            output_buffer[start:start + length] += audio[:length] * envelope[:, None] * gain
            rendered_items.append({
                "source": str(item.path),
                "source_sha256": sha256(item.path),
                "source_midi": source_midi,
                "source_note": midi_name(source_midi),
                "estimated_voiced_ratio": voiced_ratio,
                "target_midi": item.target_midi,
                "target_note": midi_name(item.target_midi),
                "pitch_shift_semitones": item.target_midi - source_midi,
                "duration_seconds": item.duration_seconds,
                "start_seconds": item.start_seconds,
                "gain_db": item.gain_db,
                "render": "Rubber Band R3 with formant preservation",
            })
        assert sample_rate is not None and output_buffer is not None
        peak = float(np.max(np.abs(output_buffer)))
        if not math.isfinite(peak):
            raise ValueError("note-aware melody contains non-finite samples")
        if peak >= 0.98:
            raise ValueError(f"note-aware melody would clip at {20 * math.log10(peak):.2f} dBFS")
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output, output_buffer, sample_rate, subtype="PCM_24")
    manifest = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "output": {
            "path": str(output), "sha256": sha256(output),
            "sample_rate": sample_rate, "channels": int(output_buffer.shape[1]),
            "duration_seconds": len(output_buffer) / sample_rate,
        },
        "items": rendered_items,
        "method": "source-pitch estimate -> authored target MIDI -> formant-preserving pitch shift -> authored duration -> timeline placement",
        "review": "Technical note placement only; listen in the full arrangement and compare raw sources before release.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return output


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--item", action="append", required=True, help="PATH|SOURCE_MIDI|TARGET_MIDI|DURATION|START[|GAIN_DB]")
    command.add_argument("--out", type=Path, required=True)
    command.add_argument("--manifest", type=Path, required=True)
    command.add_argument("--total-seconds", type=float, required=True)
    return command


def main() -> int:
    args = parser().parse_args()
    render([parse_item(value) for value in args.item], args.out, args.manifest, total_seconds=args.total_seconds)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
