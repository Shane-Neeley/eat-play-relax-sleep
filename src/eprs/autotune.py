"""Optional, formant-aware pitch correction for monophonic voice audio.

The control plane is dependency-light. NumPy, SoundFile, and PyWorld are loaded
only when a render is requested so ordinary EPRS commands remain portable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence


AUTOTUNE_SCHEMA = "eprs.autotune-render/v1"
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
NOTE_ALIASES = {
    "DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#",
    "CB": "B", "B#": "C", "FB": "E", "E#": "F",
}
SCALES = {
    "chromatic": tuple(range(12)),
    "major": (0, 2, 4, 5, 7, 9, 11),
    "natural-minor": (0, 2, 3, 5, 7, 8, 10),
    "harmonic-minor": (0, 2, 3, 5, 7, 8, 11),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "major-pentatonic": (0, 2, 4, 7, 9),
    "minor-pentatonic": (0, 3, 5, 7, 10),
}


@dataclass(frozen=True)
class AutotuneSettings:
    preset: str
    key: str = "C"
    scale: str = "chromatic"
    correction_strength: float = 1.0
    retune_ms: float = 0.0
    switch_hysteresis_cents: float = 0.0
    minimum_note_ms: float = 20.0
    wet: float = 1.0
    formant_shift_semitones: float = 0.0
    output_gain_db: float = -1.0
    f0_floor_hz: float = 65.0
    f0_ceil_hz: float = 700.0
    frame_period_ms: float = 5.0


PRESETS = {
    "transparent": AutotuneSettings(
        preset="transparent", correction_strength=0.55, retune_ms=70,
        switch_hysteresis_cents=55, minimum_note_ms=65, wet=1.0,
    ),
    "tight": AutotuneSettings(
        preset="tight", correction_strength=0.88, retune_ms=22,
        switch_hysteresis_cents=25, minimum_note_ms=35, wet=1.0,
    ),
    "hard-step": AutotuneSettings(
        preset="hard-step", correction_strength=1.0, retune_ms=0,
        switch_hysteresis_cents=0, minimum_note_ms=15, wet=1.0,
    ),
    "gloopy": AutotuneSettings(
        preset="gloopy", correction_strength=1.0, retune_ms=8,
        switch_hysteresis_cents=12, minimum_note_ms=45, wet=0.88,
        formant_shift_semitones=-0.35, output_gain_db=-1.5,
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_key(value: str) -> str:
    key = value.strip().replace("♭", "b").replace("♯", "#")
    if not key:
        raise ValueError("autotune key cannot be empty")
    key = key[0].upper() + key[1:]
    normalized = NOTE_ALIASES.get(key.upper(), key.upper())
    if normalized not in NOTE_NAMES:
        raise ValueError(f"unsupported autotune key: {value}")
    return normalized


def allowed_pitch_classes(key: str, scale: str) -> tuple[int, ...]:
    root = NOTE_NAMES.index(normalize_key(key))
    if scale not in SCALES:
        raise ValueError(f"unsupported autotune scale: {scale}")
    return tuple(sorted((root + interval) % 12 for interval in SCALES[scale]))


def nearest_allowed_midi(midi: float, pitch_classes: Sequence[int]) -> float:
    """Return the closest MIDI note in the allowed pitch-class set."""
    if not math.isfinite(midi):
        raise ValueError("MIDI pitch must be finite")
    rounded = round(midi)
    candidates = [
        note for note in range(rounded - 12, rounded + 13)
        if note % 12 in pitch_classes
    ]
    return float(min(candidates, key=lambda note: (abs(note - midi), note)))


def target_midi_track(
    midi_values: Sequence[float | None],
    pitch_classes: Sequence[int],
    *,
    frame_period_ms: float,
    switch_hysteresis_cents: float,
    minimum_note_ms: float,
) -> list[float | None]:
    """Quantize voiced frames with note-switch hysteresis and a minimum hold.

    Hysteresis prevents adjacent-note chatter around a scale boundary. A large
    leap can still break the hold so consonant-to-vowel pitch attacks do not
    drag the previous target across the new phrase.
    """
    minimum_frames = max(1, round(minimum_note_ms / frame_period_ms))
    current: float | None = None
    held_frames = 0
    targets: list[float | None] = []
    for midi in midi_values:
        if midi is None or not math.isfinite(midi):
            current = None
            held_frames = 0
            targets.append(None)
            continue
        candidate = nearest_allowed_midi(midi, pitch_classes)
        if current is None:
            current = candidate
            held_frames = 1
        elif candidate == current:
            held_frames += 1
        else:
            current_distance = abs(current - midi) * 100
            candidate_distance = abs(candidate - midi) * 100
            advantage = current_distance - candidate_distance
            force_large_leap = current_distance >= 350
            if force_large_leap or (
                held_frames >= minimum_frames and advantage > switch_hysteresis_cents
            ):
                current = candidate
                held_frames = 1
            else:
                held_frames += 1
        targets.append(current)
    return targets


def corrected_midi_track(
    midi_values: Sequence[float | None],
    targets: Sequence[float | None],
    *,
    correction_strength: float,
    retune_ms: float,
    frame_period_ms: float,
) -> list[float | None]:
    """Move pitch toward targets while preserving unvoiced frames.

    Retune smoothing is applied to the correction delta, rather than flattening
    the whole source contour. That keeps a transparent preset from erasing every
    inflection while a zero-millisecond setting still produces exact steps.
    """
    if len(midi_values) != len(targets):
        raise ValueError("autotune source and target pitch tracks must align")
    alpha = 1.0 if retune_ms <= 0 else 1 - math.exp(-frame_period_ms / retune_ms)
    smoothed_delta = 0.0
    corrected: list[float | None] = []
    for midi, target in zip(midi_values, targets):
        if midi is None or target is None:
            smoothed_delta = 0.0
            corrected.append(None)
            continue
        desired_delta = (target - midi) * correction_strength
        smoothed_delta += alpha * (desired_delta - smoothed_delta)
        corrected.append(midi + smoothed_delta)
    return corrected


def settings_for(
    preset: str,
    *,
    key: str,
    scale: str,
    overrides: dict[str, float | None] | None = None,
) -> AutotuneSettings:
    if preset not in PRESETS:
        raise ValueError(f"unsupported autotune preset: {preset}")
    settings = replace(PRESETS[preset], key=normalize_key(key), scale=scale)
    allowed_pitch_classes(settings.key, settings.scale)
    replacements = {name: value for name, value in (overrides or {}).items() if value is not None}
    settings = replace(settings, **replacements)
    limits = {
        "correction_strength": (0, 1), "retune_ms": (0, 500),
        "switch_hysteresis_cents": (0, 200), "minimum_note_ms": (0, 1000),
        "wet": (0, 1), "formant_shift_semitones": (-6, 6),
        "output_gain_db": (-24, 0), "f0_floor_hz": (40, 400),
        "f0_ceil_hz": (100, 1600), "frame_period_ms": (1, 20),
    }
    for name, (low, high) in limits.items():
        value = getattr(settings, name)
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"autotune {name} must be between {low:g} and {high:g}")
    if settings.f0_floor_hz >= settings.f0_ceil_hz:
        raise ValueError("autotune f0 floor must be below the f0 ceiling")
    return settings


def _shift_formants(spectral_envelope: Any, semitones: float, np: Any) -> Any:
    if abs(semitones) < 1e-9:
        return spectral_envelope
    ratio = 2 ** (semitones / 12)
    bins = np.arange(spectral_envelope.shape[1], dtype=np.float64)
    source_bins = bins / ratio
    shifted = np.empty_like(spectral_envelope)
    for frame in range(spectral_envelope.shape[0]):
        shifted[frame] = np.interp(
            source_bins, bins, spectral_envelope[frame],
            left=spectral_envelope[frame, 0], right=spectral_envelope[frame, -1],
        )
    return shifted


def render_autotune(
    source: str | Path,
    destination: str | Path,
    settings: AutotuneSettings,
    *,
    intent: str,
) -> tuple[Path, Path, dict[str, Any]]:
    """Render a new tuned WAV and checksum-bearing sidecar."""
    if not intent.strip():
        raise ValueError("autotune render requires player-facing intent")
    # Callers can construct the dataclass directly, bypassing the CLI factory.
    settings = settings_for(settings.preset, key=settings.key, scale=settings.scale,
                            overrides={k: v for k, v in asdict(settings).items()
                                       if k not in {"preset", "key", "scale"}})
    try:
        import numpy as np
        import pyworld as pw
        import soundfile as sf
    except ImportError as exc:  # pragma: no cover - depends on optional environment
        raise RuntimeError(
            "Autotune rendering needs NumPy, SoundFile, and PyWorld. Install them "
            "in an isolated environment with "
            "`pip install 'setuptools<81' numpy soundfile pyworld`."
        ) from exc

    source_requested = Path(source)
    destination_requested = Path(destination)
    source_path = source_requested.resolve()
    destination_path = destination_requested.resolve()
    sidecar_path = destination_path.with_suffix(destination_path.suffix + ".json")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if destination_path.suffix.lower() != ".wav":
        raise ValueError("autotune output must be a WAV path")
    if destination_path == source_path:
        raise ValueError("autotune output must not overwrite its source")
    if destination_path.exists() or sidecar_path.exists():
        raise FileExistsError(destination_path if destination_path.exists() else sidecar_path)

    audio, sample_rate = sf.read(source_path, dtype="float64", always_2d=True)
    if not 16_000 <= sample_rate <= 192_000 or audio.shape[1] not in {1, 2} or len(audio) == 0:
        raise ValueError("WORLD autotune requires non-empty mono/stereo audio at 16–192 kHz")
    if not np.all(np.isfinite(audio)):
        raise ValueError("autotune source contains non-finite samples")
    # A stereo mean can erase a perfectly voiced, polarity-inverted recording.
    analysis_channel = int(np.argmax(np.mean(audio ** 2, axis=0)))
    analysis_signal = np.ascontiguousarray(audio[:, analysis_channel])
    source_f0, temporal_positions = pw.dio(
        analysis_signal,
        sample_rate,
        f0_floor=settings.f0_floor_hz,
        f0_ceil=settings.f0_ceil_hz,
        frame_period=settings.frame_period_ms,
    )
    source_f0 = pw.stonemask(analysis_signal, source_f0, temporal_positions, sample_rate)
    midi_values = [
        69 + 12 * math.log2(float(f0) / 440) if f0 > 0 else None
        for f0 in source_f0
    ]
    pitch_classes = allowed_pitch_classes(settings.key, settings.scale)
    targets = target_midi_track(
        midi_values, pitch_classes,
        frame_period_ms=settings.frame_period_ms,
        switch_hysteresis_cents=settings.switch_hysteresis_cents,
        minimum_note_ms=settings.minimum_note_ms,
    )
    corrected = corrected_midi_track(
        midi_values, targets,
        correction_strength=settings.correction_strength,
        retune_ms=settings.retune_ms,
        frame_period_ms=settings.frame_period_ms,
    )
    tuned_f0 = np.array([
        440 * (2 ** ((midi - 69) / 12)) if midi is not None else 0.0
        for midi in corrected
    ], dtype=np.float64)

    synthesized_channels = []
    for channel_index in range(audio.shape[1]):
        channel = np.ascontiguousarray(audio[:, channel_index], dtype=np.float64)
        spectral = pw.cheaptrick(channel, source_f0, temporal_positions, sample_rate)
        spectral = _shift_formants(spectral, settings.formant_shift_semitones, np)
        aperiodicity = pw.d4c(channel, source_f0, temporal_positions, sample_rate)
        rendered = pw.synthesize(
            tuned_f0, spectral, aperiodicity, sample_rate,
            frame_period=settings.frame_period_ms,
        )
        if len(rendered) < len(channel):
            rendered = np.pad(rendered, (0, len(channel) - len(rendered)))
        synthesized_channels.append(rendered[:len(channel)])
    wet_audio = np.stack(synthesized_channels, axis=1)
    # Keep breath and consonants from the original. Crossfade over pitch-frame
    # boundaries rather than replacing all unvoiced material with vocoder noise.
    voiced_weight = np.interp(
        np.arange(len(audio)) / sample_rate, temporal_positions,
        (source_f0 > 0).astype(np.float64),
    )[:, None]
    wet_audio = voiced_weight * wet_audio + (1 - voiced_weight) * audio
    mixed = ((1 - settings.wet) * audio + settings.wet * wet_audio)
    mixed *= 10 ** (settings.output_gain_db / 20)
    peak = float(np.max(np.abs(mixed)))
    if not np.all(np.isfinite(mixed)):
        raise ValueError("autotune synthesis contains non-finite samples")
    if peak >= 1:
        raise ValueError(
            f"autotune render would clip at {20 * math.log10(peak):.2f} dBFS; "
            "lower --output-gain-db and render to a new path"
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination_path, mixed, sample_rate, subtype="PCM_24")
    voiced_pairs = [
        (source_midi, corrected_midi, target)
        for source_midi, corrected_midi, target in zip(midi_values, corrected, targets)
        if source_midi is not None and corrected_midi is not None and target is not None
    ]
    corrections = [abs(after - before) * 100 for before, after, _ in voiced_pairs]
    target_notes = sorted({int(round(target)) for _, _, target in voiced_pairs})
    metadata = {
        "schema": AUTOTUNE_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "intent": intent.strip(),
        "source": {"path": str(source_requested), "sha256": sha256(source_path)},
        "settings": asdict(settings),
        "analysis": {
            "sample_rate": sample_rate,
            "channels": audio.shape[1],
            "pitch_analysis_channel": analysis_channel,
            "duration_seconds": len(audio) / sample_rate,
            "total_pitch_frames": len(source_f0),
            "voiced_pitch_frames": len(voiced_pairs),
            "voiced_ratio": len(voiced_pairs) / max(1, len(source_f0)),
            "mean_absolute_correction_cents": sum(corrections) / max(1, len(corrections)),
            "maximum_correction_cents": max(corrections, default=0),
            "target_midi_notes": target_notes,
            "target_note_names": [f"{NOTE_NAMES[note % 12]}{note // 12 - 1}" for note in target_notes],
        },
        "output": {
            "path": str(destination_requested), "sha256": sha256(destination_path),
            "sample_rate": sample_rate, "channels": audio.shape[1],
            "subtype": "PCM_24", "peak_dbfs": 20 * math.log10(max(peak, 1e-12)),
        },
        "render": {
            "engine": "WORLD vocoder via PyWorld",
            "formant_aware": True,
            "unvoiced_source_preserved": True,
            "time_stretch": False,
            "normalization": False,
            "limiting": False,
        },
        "review": "technical render only; compare raw and tuned cues in the complete arrangement",
    }
    sidecar_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return destination_path, sidecar_path, metadata
