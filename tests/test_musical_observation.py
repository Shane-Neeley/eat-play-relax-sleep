from array import array
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

from eprs.musical_observation import (
    MAX_PITCH_FRAMES,
    observe_musical_performance,
    verify_musical_observation,
)
from eprs.context import build_agent_context
from eprs.system import new_song, sha256, song_status


def phrase_wav(path: Path, rate: int = 48_000) -> None:
    samples = [0.0] * (rate * 3)
    for start_seconds, end_seconds, frequency in (
        (0.20, 0.82, 220.0),
        (1.20, 1.92, 330.0),
        (2.20, 2.72, 220.0),
    ):
        first = round(start_seconds * rate)
        last = round(end_seconds * rate)
        for index in range(first, last):
            elapsed = (index - first) / rate
            remaining = (last - index) / rate
            envelope = min(1.0, elapsed / 0.015, remaining / 0.04)
            samples[index] = 0.55 * envelope * math.sin(2 * math.pi * frequency * elapsed)
    pcm = array("h", (round(max(-1, min(1, value)) * 32767) for value in samples))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())


class MusicalObservationTests(unittest.TestCase):
    def test_observation_preserves_source_and_keeps_interpretation_open(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Open Phrases")
            source = root / "phrases.wav"
            phrase_wav(source)
            original_digest = sha256(source)

            destination, report = observe_musical_performance(
                source,
                song,
                "family and guitar answer",
                note="Hear whether the last A is a return or an unresolved reply.",
            )

            self.assertTrue(destination.is_file())
            self.assertEqual(sha256(source), original_digest)
            self.assertEqual(report["schema"], "eprs.musical-observation/v1")
            phrases = report["phrase_observation"]["regions"]
            self.assertEqual(len(phrases), 3)
            for observed, expected in zip(phrases, (0.2, 1.2, 2.2)):
                self.assertAlmostEqual(observed["start_seconds"], expected, delta=0.06)
            note_names = {
                candidate["nearest_note_name"]
                for candidate in report["pitch_observation"]["candidates"]
            }
            self.assertIn("A3", note_names)
            self.assertIn("E4", note_names)
            self.assertIsNone(report["pitch_observation"]["key_or_chord"])
            self.assertIsNone(report["pulse_observation"]["selected_bpm"])
            self.assertIsNone(report["pulse_observation"]["selected_meter"])
            self.assertFalse(report["pulse_observation"]["grid_created"])
            self.assertFalse(report["interpretation_limits"]["source_modified"])
            self.assertFalse(report["interpretation_limits"]["pitch_corrected"])
            self.assertFalse(report["interpretation_limits"]["quantized"])
            self.assertLessEqual(
                report["pitch_observation"]["eligible_frames"], MAX_PITCH_FRAMES
            )
            resolved, verified = verify_musical_observation(song, destination)
            self.assertEqual(resolved, destination.resolve())
            self.assertEqual(verified["result_id"], report["result_id"])
            self.assertEqual(
                song_status(song, verify=True)["inventory"]["musical_observations"], 1
            )
            context = build_agent_context(song, verify=True)
            self.assertEqual(len(context["recent_musical_observations"]), 1)
            self.assertEqual(
                context["recent_musical_observations"][0]["source"]["sha256"],
                report["source"]["sha256"],
            )

            repeated_path, repeated = observe_musical_performance(
                source,
                song,
                "family and guitar answer",
                note="Hear whether the last A is a return or an unresolved reply.",
            )
            self.assertEqual(repeated_path, destination)
            self.assertEqual(repeated["analysis_id"], report["analysis_id"])

            tampered = json.loads(destination.read_text())
            tampered["pulse_observation"]["selected_bpm"] = 120
            result_payload = {
                key: tampered[key] for key in (
                    "phrase_observation", "pitch_observation", "pulse_observation",
                    "player_language", "interpretation_limits",
                )
            }
            tampered["result_id"] = hashlib.sha256(
                json.dumps(result_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            destination.write_text(json.dumps(tampered, indent=2) + "\n")
            with self.assertRaisesRegex(ValueError, "keep pulse interpretation open"):
                verify_musical_observation(song, destination)

    def test_observation_bounds_region_and_detects_checksum_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Bounded Ear")
            source = root / "phrases.wav"
            phrase_wav(source)
            destination, _ = observe_musical_performance(source, song, "answer")
            with self.assertRaisesRegex(ValueError, "exceeds source"):
                observe_musical_performance(source, song, "late", start=2.9, duration=1)

            stored_source = next((song / "recordings" / "raw" / "answer").glob("*.wav"))
            with stored_source.open("ab") as output:
                output.write(b"drift")
            with self.assertRaisesRegex(ValueError, "checksum has changed"):
                verify_musical_observation(song, destination)

    def test_failed_commit_leaves_no_visible_observation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Ear")
            source = root / "phrases.wav"
            phrase_wav(source)
            with mock.patch(
                "eprs.musical_observation.os.replace",
                side_effect=OSError("simulated commit failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated commit failure"):
                    observe_musical_performance(source, song, "answer")
            observation_root = song / "notes" / "musical-observations"
            self.assertEqual(list(observation_root.rglob("*.json")), [])
            self.assertEqual(list(observation_root.rglob("*.partial")), [])


if __name__ == "__main__":
    unittest.main()
