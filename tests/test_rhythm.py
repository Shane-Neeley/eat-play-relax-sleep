from array import array
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock
import wave

from eprs.rhythm import observe_rhythm
from eprs.system import new_song, sha256, song_status


def boom_clap_wav(path: Path, rate: int = 48_000):
    rng = random.Random(19)
    samples = [rng.uniform(-0.0015, 0.0015) for _ in range(rate * 2)]
    for onset, kind in ((0.2, "boom"), (0.7, "clap"), (1.2, "boom"), (1.7, "clap")):
        start = round(onset * rate)
        length = round((0.12 if kind == "boom" else 0.07) * rate)
        for offset in range(length):
            time = offset / rate
            attack = min(1.0, time / 0.004)
            if kind == "boom":
                value = math.sin(2 * math.pi * 115 * time) * math.exp(-time * 18) * attack * 0.72
            else:
                burst = rng.uniform(-1, 1) * math.exp(-time * 42)
                value = burst * attack * 0.62
            samples[start + offset] += value
    pcm = array("h", (round(max(-1, min(1, value)) * 32767) for value in samples))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


class RhythmObservationTests(unittest.TestCase):
    def test_boom_clap_observation_preserves_timing_and_cautious_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Spoken Pocket")
            source = root / "boom-clap.wav"
            boom_clap_wav(source)
            source_digest = sha256(source)

            destination, report = observe_rhythm(
                source,
                song,
                "Spoken pocket",
                note="Boom, clap, boom, clap; keep the performed spacing.",
            )

            self.assertTrue(destination.is_file())
            self.assertEqual(sha256(source), source_digest)
            self.assertEqual(report["schema"], "eprs.rhythm-observation/v2")
            self.assertEqual(len(report["events"]), 4)
            for observed, expected in zip(report["events"], (0.2, 0.7, 1.2, 1.7)):
                self.assertAlmostEqual(observed["time_seconds"], expected, delta=0.035)
            self.assertEqual(
                [event["timbre_hint"] for event in report["events"]],
                ["lower/rounder", "brighter/noisier", "lower/rounder", "brighter/noisier"],
            )
            self.assertAlmostEqual(report["timing_observation"]["tempo_hint_bpm"], 120, delta=1)
            self.assertIn("alternate", report["player_language"]["timbre"])
            self.assertFalse(report["interpretation_limits"]["quantized"])
            self.assertFalse(report["interpretation_limits"]["drum_roles_assigned"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["rhythm_observations"], 1)
            self.assertEqual(status["attention"], [])

            repeated_destination, repeated_report = observe_rhythm(
                source,
                song,
                "Spoken pocket",
                note="Boom, clap, boom, clap; keep the performed spacing.",
            )
            self.assertEqual(repeated_destination, destination)
            self.assertEqual(repeated_report["analysis_id"], report["analysis_id"])

    def test_observation_validates_analysis_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Observation Limits")
            source = root / "idea.wav"
            boom_clap_wav(source)
            with self.assertRaisesRegex(ValueError, "sensitivity"):
                observe_rhythm(source, song, "Idea", sensitivity=1.1)
            with self.assertRaisesRegex(ValueError, "minimum gap"):
                observe_rhythm(source, song, "Idea", min_gap_ms=10)
            with self.assertRaisesRegex(ValueError, "exceeds source"):
                observe_rhythm(source, song, "Idea", start=1.9, duration=1)

    def test_failed_observation_commit_leaves_no_visible_or_partial_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Observation")
            source = root / "idea.wav"
            boom_clap_wav(source)
            with mock.patch("eprs.rhythm.os.replace", side_effect=OSError("simulated commit failure")):
                with self.assertRaisesRegex(OSError, "simulated commit failure"):
                    observe_rhythm(source, song, "spoken idea")
            rhythm_root = song / "notes" / "rhythm"
            self.assertEqual(list(rhythm_root.rglob("*.json")), [])
            self.assertEqual(list(rhythm_root.rglob("*.partial")), [])


if __name__ == "__main__":
    unittest.main()
