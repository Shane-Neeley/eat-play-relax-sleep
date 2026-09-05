"""Conservative source-window review for iNaturalist audio.

The ordinary creative study measures timing and energy.  Those measurements
are useful, but an onset detector can mistake handling noise, insects, or a
recorder bed for the animal named by an observation.  This module adds a
bounded acoustic triage pass: it ranks windows using contrast, tonal
concentration, low/mid-band energy, and noise indicators, then leaves species
identity and call identity explicitly unverified for human listening.

The scores are review aids, not a classifier and not evidence of animal
communication.  A report can reject a source for lacking a plausible window,
but it can never approve a window for publication by itself.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .inaturalist_study import _decode, _source_path
from .lineage import trace_audio_lineage
from .system import load_song_manifest, probe, sha256, utc_now


SOURCE_AUDIT_SCHEMA = "eprs.inaturalist-source-audit/v1"
SOURCE_VERIFICATION_SCHEMA = "eprs.inaturalist-source-verification/v1"
AUDIT_FRAME_SECONDS = 0.20
AUDIT_HOP_SECONDS = 0.05
MIN_REVIEW_SCORE = 0.42
MAX_AUDIT_SECONDS = 120.0


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = _clip01(fraction) * (len(ordered) - 1)
    left = math.floor(position)
    right = math.ceil(position)
    if left == right:
        return ordered[left]
    amount = position - left
    return ordered[left] + (ordered[right] - ordered[left]) * amount


def _goertzel_power(samples: list[float], sample_rate: int, frequency: float) -> float:
    """Return one frequency-bin power without requiring NumPy."""
    if not samples or frequency <= 0 or frequency >= sample_rate / 2:
        return 0.0
    omega = 2.0 * math.pi * frequency / sample_rate
    coefficient = 2.0 * math.cos(omega)
    previous = 0.0
    previous_previous = 0.0
    last_index = len(samples) - 1
    for index, sample in enumerate(samples):
        window = 0.5 * (1.0 - math.cos(2.0 * math.pi * index / max(last_index, 1)))
        current = coefficient * previous - previous_previous + sample * window
        previous_previous = previous
        previous = current
    return max(
        0.0,
        previous * previous
        + previous_previous * previous_previous
        - coefficient * previous * previous_previous,
    )


def _frame_features(samples: Any, sample_rate: int) -> list[dict[str, float]]:
    frame_size = max(32, round(AUDIT_FRAME_SECONDS * sample_rate))
    hop_size = max(1, round(AUDIT_HOP_SECONDS * sample_rate))
    frequencies = [
        120.0,
        180.0,
        240.0,
        300.0,
        400.0,
        500.0,
        650.0,
        800.0,
        1_000.0,
        1_250.0,
        1_500.0,
        1_800.0,
        2_200.0,
        2_600.0,
        3_200.0,
        4_000.0,
        5_000.0,
        6_000.0,
        7_000.0,
    ]
    features: list[dict[str, float]] = []
    for start in range(0, max(1, len(samples) - frame_size + 1), hop_size):
        frame = [float(value) for value in samples[start:start + frame_size]]
        if len(frame) < frame_size:
            frame.extend([0.0] * (frame_size - len(frame)))
        energy = math.sqrt(sum(value * value for value in frame) / frame_size)
        peak = max((abs(value) for value in frame), default=0.0)
        crossings = sum(
            1
            for left, right in zip(frame, frame[1:])
            if (left < 0 <= right) or (left >= 0 > right)
        ) / max(1, len(frame) - 1)
        powers = [
            (frequency, _goertzel_power(frame, sample_rate, frequency))
            for frequency in frequencies
            if frequency < sample_rate / 2
        ]
        total_power = sum(power for _, power in powers)
        low_power = sum(power for frequency, power in powers if frequency <= 800.0)
        mid_power = sum(
            power for frequency, power in powers if 800.0 < frequency <= 2_400.0
        )
        high_power = sum(power for frequency, power in powers if frequency > 2_400.0)
        dominant_frequency, dominant_power = max(
            powers, key=lambda item: item[1], default=(0.0, 0.0)
        )
        largest_bins = sorted((power for _, power in powers), reverse=True)[:3]
        features.append(
            {
                "start_seconds": start / sample_rate,
                "energy": energy,
                "peak": peak,
                "crest_factor": peak / max(energy, 1e-9),
                "zero_crossing_rate": crossings,
                "low_mid_ratio": (low_power + mid_power) / max(total_power, 1e-12),
                "high_ratio": high_power / max(total_power, 1e-12),
                "harmonic_concentration": sum(largest_bins)
                / max(total_power, 1e-12),
                "dominant_frequency_hz": dominant_frequency,
                "dominant_power": dominant_power,
            }
        )
    return features


def _score_features(features: list[dict[str, float]]) -> tuple[list[dict[str, float]], dict[str, float]]:
    energies = [item["energy"] for item in features]
    baseline = max(_percentile(energies, 0.20), 1e-9)
    zcr_values = [item["zero_crossing_rate"] for item in features]
    zcr_floor = _percentile(zcr_values, 0.20)
    zcr_ceiling = max(_percentile(zcr_values, 0.90), zcr_floor + 1e-6)
    for item in features:
        snr_db = 20.0 * math.log10(max(item["energy"], 1e-9) / baseline)
        # Keep a small neutral score for a sustained tonal source whose whole
        # clip is active; absence of contrast must not be mistaken for proof
        # of noise.  It still cannot pass without human identity review.
        contrast = 0.15 if snr_db < 3.0 else _clip01((snr_db - 3.0) / 15.0)
        tonal = _clip01((item["harmonic_concentration"] - 0.12) / 0.45)
        low_mid = _clip01((item["low_mid_ratio"] - 0.38) / 0.55)
        high_noise = _clip01((item["high_ratio"] - 0.52) / 0.36)
        bright_noise = _clip01(
            (item["zero_crossing_rate"] - zcr_floor)
            / max(zcr_ceiling - zcr_floor, 1e-6)
        )
        score = (
            0.45 * contrast
            + 0.27 * tonal
            + 0.20 * low_mid
            - 0.10 * high_noise
            - 0.08 * bright_noise
        )
        item["snr_db"] = snr_db
        item["call_likeness_score"] = _clip01(score)
    summary = {
        "noise_floor_rms": baseline,
        "noise_floor_dbfs": 20.0 * math.log10(baseline),
        "median_score": _median([item["call_likeness_score"] for item in features]),
        "maximum_score": max(
            (item["call_likeness_score"] for item in features), default=0.0
        ),
    }
    return features, summary


def _candidate_regions(
    features: list[dict[str, float]],
    duration: float,
    *,
    max_candidates: int,
) -> list[dict[str, Any]]:
    if not features:
        return []
    threshold = max(
        MIN_REVIEW_SCORE,
        _percentile([item["call_likeness_score"] for item in features], 0.85),
    )
    active = [
        index
        for index, item in enumerate(features)
        if item["call_likeness_score"] >= threshold
    ]
    groups: list[list[int]] = []
    group: list[int] = []
    max_gap = max(1, round(0.15 / AUDIT_HOP_SECONDS))
    for index in active:
        if group and index - group[-1] > max_gap:
            groups.append(group)
            group = []
        group.append(index)
    if group:
        groups.append(group)

    candidates: list[dict[str, Any]] = []
    for indices in groups:
        best_index = max(
            indices,
            key=lambda index: features[index]["call_likeness_score"],
        )
        start = max(0.0, features[indices[0]]["start_seconds"] - 0.30)
        end = min(
            duration,
            features[indices[-1]]["start_seconds"] + AUDIT_FRAME_SECONDS + 0.30,
        )
        candidates.append(
            _candidate_record(features[best_index], start, end, threshold)
        )

    # Even a rejecting source gets bounded regions for a real human to check.
    # Pick separated high-scoring windows instead of presenting detector
    # attacks as if they were confirmed animal events.
    if not candidates:
        ordered = sorted(
            range(len(features)),
            key=lambda index: features[index]["call_likeness_score"],
            reverse=True,
        )
        chosen: list[float] = []
        for index in ordered:
            center = features[index]["start_seconds"] + AUDIT_FRAME_SECONDS / 2
            if any(abs(center - previous) < 0.75 for previous in chosen):
                continue
            start = max(0.0, center - 0.5)
            end = min(duration, center + 0.5)
            candidates.append(
                _candidate_record(features[index], start, end, threshold)
            )
            chosen.append(center)
            if len(candidates) >= max_candidates:
                break
    candidates.sort(key=lambda item: item["call_likeness_score"], reverse=True)
    for rank, item in enumerate(candidates[:max_candidates], start=1):
        item["rank"] = rank
    return candidates[:max_candidates]


def _candidate_record(
    feature: dict[str, float],
    start: float,
    end: float,
    threshold: float,
) -> dict[str, Any]:
    score = feature["call_likeness_score"]
    return {
        "start_seconds": round(start, 3),
        "end_seconds": round(end, 3),
        "center_seconds": round(
            feature["start_seconds"] + AUDIT_FRAME_SECONDS / 2, 3
        ),
        "call_likeness_score": round(score, 4),
        "ranked_for_review": score >= threshold and score >= MIN_REVIEW_SCORE,
        "features": {
            "snr_db": round(feature["snr_db"], 3),
            "dominant_frequency_hz": round(feature["dominant_frequency_hz"], 1),
            "harmonic_concentration": round(feature["harmonic_concentration"], 4),
            "low_mid_ratio": round(feature["low_mid_ratio"], 4),
            "high_ratio": round(feature["high_ratio"], 4),
            "zero_crossing_rate": round(feature["zero_crossing_rate"], 4),
            "crest_factor": round(feature["crest_factor"], 3),
        },
        "identity_status": "unverified",
        "human_audition_required": True,
        "source_use_eligible": False,
    }


def audit_inaturalist_sound(
    source: str | Path,
    song: str | Path,
    *,
    max_candidates: int = 6,
) -> dict[str, Any]:
    """Rank bounded review windows for a frozen iNaturalist recording."""
    if isinstance(max_candidates, bool) or not 1 <= int(max_candidates) <= 20:
        raise ValueError("max_candidates must be between 1 and 20")
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    source_path = _source_path(song_path, source)
    lineage = trace_audio_lineage(song_path, source_path)
    external = lineage.get("external_audio", [])
    if not external:
        raise ValueError("source does not trace to an iNaturalist sound")
    source_probe = probe(source_path)
    duration_value = source_probe.get("format", {}).get("duration")
    if duration_value is None:
        raise ValueError("source duration is unavailable")
    duration = float(duration_value)
    if not 0.0 < duration <= MAX_AUDIT_SECONDS:
        raise ValueError(
            f"source audit is limited to {MAX_AUDIT_SECONDS:g} seconds"
        )
    samples = _decode(source_path, duration)
    features, summary = _score_features(_frame_features(samples, 16_000))
    candidates = _candidate_regions(
        features,
        duration,
        max_candidates=int(max_candidates),
    )
    maximum_score = summary["maximum_score"]
    decision = "review-required" if maximum_score >= MIN_REVIEW_SCORE else "reject"
    reasons = [
        "acoustic heuristics do not identify a species or confirm a call",
        "human audition of the raw source is required before source-derived production",
    ]
    if decision == "reject":
        reasons.append("no window cleared the conservative call-likeness threshold")
    return {
        "schema": SOURCE_AUDIT_SCHEMA,
        "created_at": utc_now(),
        "decision": decision,
        "identity_status": "unverified",
        "human_audition_required": True,
        "source_use_eligible": False,
        "source": {
            "path": str(source_path.relative_to(song_path)),
            "sha256": sha256(source_path),
            "probe": source_probe,
            "iNaturalist": external[0],
        },
        "analysis": {
            "sample_rate": 16_000,
            "frame_seconds": AUDIT_FRAME_SECONDS,
            "hop_seconds": AUDIT_HOP_SECONDS,
            "maximum_score": round(maximum_score, 4),
            "median_score": round(summary["median_score"], 4),
            "noise_floor_rms": round(summary["noise_floor_rms"], 9),
            "noise_floor_dbfs": round(summary["noise_floor_dbfs"], 3),
            "minimum_review_score": MIN_REVIEW_SCORE,
        },
        "candidate_regions": candidates,
        "reasons": reasons,
        "verification_contract": {
            "required_before_source_use": [
                "listen to each bounded raw candidate at normal gain",
                "record the exact window where the named animal call is audible",
                "record what was heard and who performed the review",
                "reject and replace the source if no call-bearing window is identifiable",
            ],
            "not_satisfied_by": [
                "attack_count",
                "waveform amplitude alone",
                "spectrogram brightness alone",
                "iNaturalist taxon label alone",
            ],
        },
    }


def write_source_audit_report(
    report: dict[str, Any],
    out: str | Path,
    *,
    protected_paths: list[str | Path] | None = None,
) -> Path:
    """Write a new portable audit report without overwriting evidence."""
    destination = Path(out).expanduser().resolve()
    protected = {
        Path(path).expanduser().resolve()
        for path in (protected_paths or [])
        if path
    }
    source_path = report.get("source", {}).get("path")
    if isinstance(source_path, str) and Path(source_path).resolve() == destination:
        raise ValueError("source audit report must not overwrite its source")
    if destination in protected:
        raise ValueError("source audit report must not overwrite protected evidence")
    if destination.exists():
        raise FileExistsError(f"source audit report already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.partial")
    try:
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def record_source_verification(
    audit_report: str | Path,
    out: str | Path,
    *,
    start_seconds: float,
    end_seconds: float,
    what_was_heard: str,
    reviewer: str,
) -> Path:
    """Record a human's exact listening result without changing the audit."""
    audit_path = Path(audit_report).expanduser().resolve()
    if not audit_path.is_file():
        raise FileNotFoundError(audit_path)
    if not math.isfinite(float(start_seconds)) or not math.isfinite(float(end_seconds)):
        raise ValueError("verification window must be finite")
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise ValueError("verification window must have positive duration")
    if not isinstance(what_was_heard, str) or len(what_was_heard.strip()) < 3:
        raise ValueError("what_was_heard must describe the audible source")
    if not isinstance(reviewer, str) or len(reviewer.strip()) < 2:
        raise ValueError("reviewer is required")
    report = json.loads(audit_path.read_text(encoding="utf-8"))
    if report.get("schema") != SOURCE_AUDIT_SCHEMA:
        raise ValueError("audit report has an unsupported schema")
    if report.get("source_use_eligible") is True:
        raise ValueError("audit report is already verified; create no duplicate record")
    candidates = report.get("candidate_regions")
    if not isinstance(candidates, list):
        raise ValueError("audit report has no candidate regions")
    matching = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and float(candidate.get("start_seconds", -1)) <= start_seconds
        and end_seconds <= float(candidate.get("end_seconds", -1))
    ]
    if not matching:
        raise ValueError("verification window must be inside a ranked audit candidate")
    destination = Path(out).expanduser().resolve()
    if destination in {audit_path, Path(report.get("source", {}).get("path", "")).resolve()}:
        raise ValueError("verification record must not overwrite source evidence")
    if destination.exists():
        raise FileExistsError(f"source verification already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": SOURCE_VERIFICATION_SCHEMA,
        "created_at": utc_now(),
        "verified_by_human": True,
        "source_use_eligible": True,
        "audit_report": {
            "path": str(audit_path),
            "sha256": sha256(audit_path),
        },
        "source": {
            "path": report.get("source", {}).get("path"),
            "sha256": report.get("source", {}).get("sha256"),
            "iNaturalist": report.get("source", {}).get("iNaturalist"),
        },
        "verified_window": {
            "start_seconds": round(float(start_seconds), 3),
            "end_seconds": round(float(end_seconds), 3),
            "what_was_heard": what_was_heard.strip(),
            "reviewer": reviewer.strip(),
            "candidate_rank": matching[0].get("rank"),
        },
        "boundary": "This is a human listening attestation for an exact raw window, not a species classifier or animal-intent claim.",
    }
    temporary = destination.with_name(f".{destination.name}.partial")
    try:
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination
