"""Creative quality preflight for public EPRS releases.

Technical provenance can prove that a file rendered correctly.  It cannot prove
that a listener has a reason to stay.  This module adds a small, deterministic
form/risk check so experimental arrangements are held for an explicit human
approval instead of being promoted on the strength of a free-form note.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .beat import Beat, expanded_steps, load, track_active


QUALITY_SCHEMA = "eprs.creative-quality/v1"
DECISIONS = {"pass", "hold"}
HUMAN_APPROVAL = {"not-required", "required", "approved"}
_NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)-?\d$")
_PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_NATURAL_PITCHES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_FAMILIAR_METERS = {(4, 4), (3, 4), (2, 4), (6, 8), (12, 8)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pitch_classes(beat: Beat, start_bar: int, end_bar: int, *, legacy: bool = False) -> set[str]:
    pitches: set[str] = set()
    start = (start_bar - 1) * beat.steps_per_bar
    end = end_bar * beat.steps_per_bar
    for track in beat.tracks:
        if track.kind != "notes":
            continue
        for index, token in enumerate(expanded_steps(track, beat.total_steps)[start:end], start):
            if not legacy and not track_active(track, index, beat.steps_per_bar):
                continue
            for note in token.split("+"):
                match = _NOTE_RE.match(note)
                if match:
                    letter = match.group(1).upper()
                    accidental = {"": 0, "#": 1, "b": -1}[match.group(2)]
                    pitches.add(letter if legacy else _PITCH_NAMES[(_NATURAL_PITCHES[letter] + accidental) % 12])
    return pitches


def _event_count(beat: Beat, track_index: int, start_bar: int, end_bar: int) -> int:
    track = beat.tracks[track_index]
    start = (start_bar - 1) * beat.steps_per_bar
    end = end_bar * beat.steps_per_bar
    steps = expanded_steps(track, beat.total_steps)[start:end]
    return sum(step not in {".", "-", "~"} for step in steps)


def _section_boundaries(beat: Beat) -> list[tuple[int, int]]:
    boundaries = {1, beat.bars + 1}
    for track in beat.tracks:
        start = int(track.options.get("start_bar", "1"))
        end = int(track.options.get("end_bar", str(beat.bars)))
        boundaries.update({start, end + 1})
    ordered = sorted(boundary for boundary in boundaries if 1 <= boundary <= beat.bars + 1)
    return [(start, end - 1) for start, end in zip(ordered, ordered[1:]) if start <= end - 1]


def _section_record(beat: Beat, start_bar: int, end_bar: int, *, legacy: bool = False) -> dict:
    active = [
        track.name
        for track in beat.tracks
        if track_active(track, (start_bar - 1) * beat.steps_per_bar, beat.steps_per_bar)
    ]
    density = sum(
        _event_count(beat, index, start_bar, end_bar)
        for index, track in enumerate(beat.tracks)
        if track.name in active
    ) / max(1, end_bar - start_bar + 1)
    return {
        "start_bar": start_bar,
        "end_bar": end_bar,
        "active_tracks": active,
        "track_count": len(active),
        "events_per_bar": round(density, 3),
        "pitch_classes": sorted(_pitch_classes(beat, start_bar, end_bar, legacy=legacy)),
    }


def analyze_beatscript(beat_path: str | Path, *, analysis_version: int = 2) -> dict:
    """Return deterministic form/risk findings for one BeatScript arrangement."""
    source = Path(beat_path).resolve()
    beat = load(source)
    if analysis_version not in {1, 2}:
        raise ValueError("Unsupported quality analysis version")
    legacy = analysis_version == 1
    sections = [_section_record(beat, start, end, legacy=legacy) for start, end in _section_boundaries(beat)]
    signatures = [tuple(section["active_tracks"]) for section in sections]
    transitions = sum(left != right for left, right in zip(signatures, signatures[1:]))
    early_pitches = _pitch_classes(beat, 1, min(8, beat.bars), legacy=legacy)
    late_start = max(1, round(beat.bars * 0.65))
    late_sections = [section for section in sections if section["end_bar"] >= late_start]
    final_signature = signatures[-1] if signatures else ()
    prior_signature = signatures[-2] if len(signatures) > 1 else final_signature
    positive_densities = [section["events_per_bar"] for section in sections if section["events_per_bar"] > 0]
    contrast_ratio = (
        max(positive_densities) / min(positive_densities)
        if positive_densities else 0.0
    )
    alignment_warnings = [
        {
            "track": track.name,
            "length": len(track.steps),
            "steps_per_bar": beat.steps_per_bar,
            "remainder": len(track.steps) % beat.steps_per_bar,
        }
        for track in beat.tracks
        if len(track.steps) >= beat.steps_per_bar and len(track.steps) % beat.steps_per_bar
    ]

    checks = {
        "early_identity": bool(len(early_pitches) >= 3),
        "section_count": len(sections) >= 4,
        "state_change": transitions >= 2,
        "contrast": contrast_ratio >= 1.25,
        "late_payoff": bool(late_sections and any(
            section["pitch_classes"] != sections[0]["pitch_classes"]
            or section["track_count"] != sections[0]["track_count"]
            for section in late_sections
        )),
        "changed_ending": bool(final_signature and final_signature != prior_signature),
    }
    hard_failures = [name for name, passed in checks.items() if not passed]
    risk_flags: list[str] = []
    unfamiliar_meter = beat.meter != (4, 4) if legacy else beat.meter not in _FAMILIAR_METERS
    if unfamiliar_meter:
        risk_flags.append("odd_or_unfamiliar_meter_requires_human_approval")
    if alignment_warnings and unfamiliar_meter:
        risk_flags.append("odd_meter_pattern_lengths_do_not_align_to_bar_grid")
    if beat.duration > 150:
        risk_flags.append("long_form_requires_evidence_of_sustained_attention")
    if not any(track.kind == "notes" for track in beat.tracks):
        risk_flags.append("no_melodic_identity_lane")
    if hard_failures:
        risk_flags.append("form_check_failed")

    score = max(0, 10 - (2 * len(hard_failures)) - len(risk_flags))
    auto_publish_eligible = not hard_failures and not risk_flags and score >= 8
    return {
        "schema": QUALITY_SCHEMA,
        "analysis_version": analysis_version,
        "source": {"path": str(source), "sha256": _sha256(source)},
        "arrangement": {
            "title": beat.title,
            "tempo": beat.tempo,
            "meter": f"{beat.meter[0]}/{beat.meter[1]}",
            "resolution": beat.resolution,
            "bars": beat.bars,
            "duration_seconds": round(beat.duration, 3),
            "steps_per_bar": beat.steps_per_bar,
        },
        "checks": checks,
        "hard_failures": hard_failures,
        "risk_flags": risk_flags,
        "alignment_warnings": alignment_warnings,
        "sections": sections,
        "metrics": {
            "section_count": len(sections),
            "state_change_count": transitions,
            "early_pitch_class_count": len(early_pitches),
            "contrast_ratio": round(contrast_ratio, 3),
        },
        "score": score,
        "auto_publish_eligible": auto_publish_eligible,
        "decision": "pass" if auto_publish_eligible else "hold",
        "human_approval": {
            "status": "required",
            "note": "",
        },
        "generated_at": _utc_now(),
    }


def write_quality_report(beat: str | Path, song: str | Path, out: str | Path) -> Path:
    """Analyze a BeatScript and write a song-relative quality report."""
    song_path = Path(song).resolve()
    source = Path(beat).resolve()
    report = analyze_beatscript(source)
    try:
        report["source"]["path"] = str(source.relative_to(song_path))
    except ValueError as exc:
        raise ValueError("quality BeatScript must be inside the song workspace") from exc
    destination = Path(out)
    if not destination.is_absolute():
        destination = song_path / destination
    destination = destination.resolve()
    try:
        destination.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("quality report must be inside the song workspace") from exc
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.partial")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination


def verify_creative_quality(song: str | Path, report: str | Path) -> tuple[Path, dict]:
    """Verify a quality report against its exact BeatScript source."""
    song_path = Path(song).resolve()
    requested = Path(report)
    report_path = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        report_path.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("creative quality report must be inside the song workspace") from exc
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    try:
        record = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid creative quality JSON: {report_path}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != QUALITY_SCHEMA:
        raise ValueError("unsupported creative quality schema")
    source_value = record.get("source", {}).get("path") if isinstance(record.get("source"), dict) else None
    if not isinstance(source_value, str) or Path(source_value).is_absolute():
        raise ValueError("creative quality source path must be song-relative")
    source = (song_path / source_value).resolve()
    try:
        source.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("creative quality source escapes the song workspace") from exc
    if not source.is_file() or record["source"].get("sha256") != _sha256(source):
        raise ValueError("creative quality source is missing or changed")
    # Frozen v1 evidence retains its original interpretation; new reports use
    # sounding pitches, active regions and familiar compound meters.
    expected = analyze_beatscript(source, analysis_version=record.get("analysis_version", 1))
    for key in ("arrangement", "checks", "hard_failures", "risk_flags", "alignment_warnings", "sections", "metrics", "score", "auto_publish_eligible", "decision"):
        if record.get(key) != expected.get(key):
            raise ValueError(f"creative quality {key} does not match its BeatScript source")
    approval = record.get("human_approval")
    if not isinstance(approval, dict) or approval.get("status") not in HUMAN_APPROVAL:
        raise ValueError("creative quality human_approval status is invalid")
    if record.get("decision") not in DECISIONS:
        raise ValueError("creative quality decision is invalid")
    return report_path, record


def approve_creative_quality(song: str | Path, report: str | Path, note: str) -> Path:
    """Record explicit human approval for a report that was held."""
    approval_note = note.strip()
    if len(approval_note) < 24:
        raise ValueError("creative quality approval requires a specific note of at least 24 characters")
    report_path, record = verify_creative_quality(song, report)
    record["human_approval"] = {
        "status": "approved",
        "note": approval_note,
        "approved_at": _utc_now(),
    }
    temporary = report_path.with_name(f".{report_path.name}.approval.partial")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    return report_path
