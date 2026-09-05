"""Validate SoulX word/note alignment before expensive singing inference.

Type 3 means another note on the SAME word, not a long or accented word.
Timing checks prevent inference assemblers from silently losing phrase tails.
This module deliberately has no model/runtime dependencies.
"""

from __future__ import annotations

import math


def validate_score(segments: list[dict], *, minimum_tail: float = 0.3) -> None:
    """Reject inconsistent note arrays, orphan slurs and overlapping phrases.

    All times are milliseconds except per-note durations (seconds). A final
    explicit rest reserves room for consonants and release. This is structural
    validation, not evidence of intelligibility or voice likeness.
    """
    if not segments:
        raise ValueError("Score must contain at least one phrase")
    previous_end = 0.0
    for segment in segments:
        durations = [float(x) for x in segment["duration"].split()]
        phones = segment["phoneme"].split()
        words = segment["text"].split()
        pitches = [int(x) for x in segment["note_pitch"].split()]
        types = [int(x) for x in segment["note_type"].split()]
        if (
            not durations
            or len({len(x) for x in (durations, phones, words, pitches, types)}) != 1
        ):
            raise ValueError(
                "Word, phoneme, duration, pitch and type counts must match"
            )
        start, end = map(float, segment["time"])
        if not all(math.isfinite(x) for x in (start, end, *durations)):
            raise ValueError("Score times must be finite")
        if start < previous_end or end <= start or any(d <= 0 for d in durations):
            raise ValueError(
                "Phrase times must be positive, ordered and non-overlapping"
            )
        if abs(sum(durations) - (end - start) / 1000) > 0.021:
            raise ValueError("Phrase window must match the sum of note durations")
        for i, (phone, word, pitch, kind) in enumerate(
            zip(phones, words, pitches, types)
        ):
            if kind not in (1, 2, 3) or not 0 <= pitch <= 127:
                raise ValueError("Invalid note type or MIDI pitch")
            if phone == "<SP>":
                if word != "<SP>" or kind != 1 or pitch != 0:
                    raise ValueError("Rest must use <SP>, type 1 and pitch 0")
            elif kind == 1 or pitch == 0 or word == "<SP>":
                raise ValueError("Sung words require type 2/3 and a pitched note")
            if kind == 3 and (
                i == 0
                or types[i - 1] == 1
                or phones[i - 1] != phone
                or words[i - 1] != word
            ):
                raise ValueError(f"Continuation must repeat the previous word: {word}")
        if phones[-1] != "<SP>" or durations[-1] < minimum_tail:
            raise ValueError("Reserve an explicit final rest for the phrase release")
        previous_end = end


def phrase_placements(
    segments: list[dict], lengths: list[int], sample_rate: int
) -> tuple[list[int], int]:
    """Plan additive assembly retaining every generated sample, including tails."""
    validate_score(segments)
    if (
        len(lengths) != len(segments)
        or sample_rate <= 0
        or any(n <= 0 for n in lengths)
    ):
        raise ValueError(
            "One nonempty waveform per phrase and a positive rate are required"
        )
    starts = [round(float(s["time"][0]) * sample_rate / 1000) for s in segments]
    total = max(
        round(float(segments[-1]["time"][1]) * sample_rate / 1000),
        max(start + length for start, length in zip(starts, lengths)),
    )
    return starts, total
