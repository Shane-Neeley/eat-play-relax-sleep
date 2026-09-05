import math
from array import array
import json
from pathlib import Path
import tempfile
import unittest

from eprs.cli import parser
from eprs.source_audit import (
    MIN_REVIEW_SCORE,
    _candidate_regions,
    _frame_features,
    record_source_verification,
    _score_features,
    SOURCE_AUDIT_SCHEMA,
)


def _audio_fixture(kind: str, *, seconds: float = 4.0, rate: int = 16_000) -> array:
    samples = array("f")
    for index in range(round(seconds * rate)):
        time = index / rate
        if kind == "tonal-call":
            active = 1.0 <= time <= 1.8
            value = 0.18 * math.sin(2.0 * math.pi * 330.0 * time) if active else 0.002 * math.sin(
                2.0 * math.pi * 440.0 * time
            )
        else:
            # Several unrelated high-frequency tones plus short clicks model
            # a recorder/insect bed without giving it one dominant pitch.
            value = sum(
                0.018 * math.sin(2.0 * math.pi * frequency * time)
                for frequency in (3_100.0, 4_700.0, 6_300.0, 7_100.0)
            )
            if int(time * 11) % 13 == 0:
                value += 0.12 * math.sin(2.0 * math.pi * 5_500.0 * time)
        samples.append(value)
    return samples


class SourceAuditTests(unittest.TestCase):
    def test_audit_ranks_tonal_window_above_persistent_scratch_bed(self):
        tonal_features, _ = _score_features(
            _frame_features(_audio_fixture("tonal-call"), 16_000)
        )
        scratch_features, _ = _score_features(
            _frame_features(_audio_fixture("scratch"), 16_000)
        )
        tonal_max = max(item["call_likeness_score"] for item in tonal_features)
        scratch_max = max(item["call_likeness_score"] for item in scratch_features)
        self.assertGreater(tonal_max, MIN_REVIEW_SCORE)
        self.assertLess(scratch_max, tonal_max)
        self.assertLess(scratch_max, MIN_REVIEW_SCORE)

    def test_rejecting_source_still_returns_bounded_unverified_review_windows(self):
        features, summary = _score_features(
            _frame_features(_audio_fixture("scratch"), 16_000)
        )
        candidates = _candidate_regions(features, 4.0, max_candidates=3)
        self.assertLess(summary["maximum_score"], MIN_REVIEW_SCORE)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertLess(candidate["start_seconds"], candidate["end_seconds"])
            self.assertFalse(candidate["ranked_for_review"])
            self.assertEqual(candidate["identity_status"], "unverified")
            self.assertTrue(candidate["human_audition_required"])

    def test_cli_exposes_the_raw_source_audit(self):
        args = parser().parse_args(
            [
                "inaturalist",
                "audit",
                "references/inaturalist-audio/source.wav",
                "--song",
                "songs/study",
                "--max-candidates",
                "4",
            ]
        )
        self.assertEqual(args.inaturalist_command, "audit")
        self.assertEqual(args.max_candidates, 4)

    def test_human_verification_is_bounded_to_a_ranked_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audit = root / "audit.json"
            audit.write_text(json.dumps({
                "schema": SOURCE_AUDIT_SCHEMA,
                "source_use_eligible": False,
                "source": {"path": "source.m4a", "sha256": "abc", "iNaturalist": {"sound_id": 7}},
                "candidate_regions": [{"rank": 1, "start_seconds": 1.0, "end_seconds": 2.0}],
            }), encoding="utf-8")
            verification = record_source_verification(
                audit,
                root / "verification.json",
                start_seconds=1.2,
                end_seconds=1.8,
                what_was_heard="named call is audible",
                reviewer="human reviewer",
            )
            record = json.loads(verification.read_text(encoding="utf-8"))
            self.assertTrue(record["verified_by_human"])
            self.assertTrue(record["source_use_eligible"])

            with self.assertRaisesRegex(ValueError, "inside"):
                record_source_verification(
                    audit,
                    root / "outside.json",
                    start_seconds=0.0,
                    end_seconds=0.5,
                    what_was_heard="not inside",
                    reviewer="human reviewer",
                )

    def test_cli_exposes_human_source_verification(self):
        args = parser().parse_args(
            [
                "inaturalist",
                "verify-window",
                "audit.json",
                "--out",
                "verification.json",
                "--start",
                "1.2",
                "--end",
                "1.8",
                "--what-was-heard",
                "the call is audible",
                "--reviewer",
                "human reviewer",
            ]
        )
        self.assertEqual(args.inaturalist_command, "verify-window")
        self.assertEqual(args.start, 1.2)


if __name__ == "__main__":
    unittest.main()
