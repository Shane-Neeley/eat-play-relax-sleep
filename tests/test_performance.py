from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.performance import compare_performances, review_comparison
from eprs.system import ingest, new_song, sha256, song_status


def pulse_take(path: Path, attacks: list[float], *, grow: bool = False, seconds: float = 1.0) -> None:
    rate = 48_000
    samples = array("h", [0]) * round(seconds * rate)
    width = round(0.045 * rate)
    for attack_index, attack in enumerate(attacks):
        amplitude = (0.18 + attack_index * 0.08 if grow else 0.35) * 32767
        start = round(attack * rate)
        for offset in range(min(width, len(samples) - start)):
            envelope = math.exp(-offset / (rate * 0.012))
            samples[start + offset] += round(math.sin(2 * math.pi * 180 * offset / rate) * amplitude * envelope)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


class PerformanceComparisonTests(unittest.TestCase):
    def _takes(self, root: Path, song: Path) -> tuple[Path, Path]:
        first_external = root / "guitar-take-one.wav"
        second_external = root / "guitar-take-two.wav"
        pulse_take(first_external, [0.10, 0.30, 0.50, 0.70], grow=True)
        pulse_take(second_external, [0.12, 0.43, 0.78])
        first, _ = ingest(first_external, song, "guitar", "Four gestures that grow.")
        second, _ = ingest(second_external, song, "guitar", "Three wider gestures.")
        return first, second

    def _spec(self, root: Path, song: Path, first: Path, second: Path) -> Path:
        spec = root / "compare.json"
        spec.write_text(json.dumps({
            "schema": "eprs.performance-compare/v1",
            "title": "Guitar answer takes",
            "intent": "Hear whether the phrase should gather momentum or leave wider breaths.",
            "listening_questions": [
                "Which attack shape leaves the family entrance open?",
                "Is the growing phrase exciting or does it crowd the answer?",
            ],
            "analysis": {"sensitivity": 0.2, "min_gap_ms": 100},
            "takes": [
                {"id": "growing-four", "role": "guitar answer", "path": str(first.relative_to(song)), "player_note": "Four gestures, increasingly committed."},
                {"id": "wide-three", "role": "guitar answer", "path": str(second.relative_to(song)), "player_note": "Three gestures with more air."},
            ],
        }))
        return spec

    def test_compares_without_ranking_then_preserves_listening_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Take Listening")
            first, second = self._takes(root, song)
            first_digest, second_digest = sha256(first), sha256(second)
            spec = self._spec(root, song, first, second)

            report_path, report = compare_performances(spec, song)
            self.assertEqual(report["schema"], "eprs.performance-comparison/v1")
            self.assertFalse(report["interpretation_limits"]["automatic_winner"])
            self.assertFalse(report["interpretation_limits"]["waveform_alignment"])
            self.assertNotIn("winner", report)
            self.assertEqual(report["audition"]["orders"], [
                ["growing-four", "wide-three"], ["wide-three", "growing-four"],
            ])
            self.assertGreater(report["takes"][0]["attack_evidence"]["event_count"], 0)
            self.assertGreater(report["takes"][1]["attack_evidence"]["event_count"], 0)
            self.assertEqual(len(report["contrasts"]), 1)
            self.assertEqual(sha256(first), first_digest)
            self.assertEqual(sha256(second), second_digest)
            self.assertEqual(compare_performances(spec, song)[0], report_path)

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["performance_comparisons"], 1)
            self.assertEqual(status["inventory"]["comparisons_pending_review"], 1)
            review_comparison(song, report_path, "growing-four", "keep", "The gathering motion sets up the family entrance.")
            review_comparison(song, report_path, "wide-three", "alternate", "The extra air may suit a quieter arrangement.")
            reviewed = json.loads(report_path.read_text())
            self.assertEqual(reviewed["review_state"], "complete")
            self.assertEqual(reviewed["reviews"]["wide-three"]["decision"], "alternate")
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["comparisons_pending_review"], 0)
            self.assertEqual(status["inventory"]["comparison_take_decisions"]["keep"], 1)
            self.assertEqual(status["inventory"]["comparison_take_decisions"]["alternate"], 1)

    def test_rejects_unportable_and_incomplete_comparisons(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Comparison Limits")
            first, second = self._takes(root, song)
            spec = self._spec(root, song, first, second)
            score = json.loads(spec.read_text())
            score["takes"] = score["takes"][:1]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "between 2 and 12"):
                compare_performances(spec, song)
            score["takes"].append({"id": "outside", "path": str(root / "outside.wav")})
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "relative to the song"):
                compare_performances(spec, song)

    def test_review_refuses_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Comparison Drift")
            first, second = self._takes(root, song)
            report_path, _ = compare_performances(self._spec(root, song, first, second), song)
            with first.open("ab") as handle:
                handle.write(b"drift")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                review_comparison(song, report_path, "growing-four", "keep", "This cannot be trusted now.")


if __name__ == "__main__":
    unittest.main()
