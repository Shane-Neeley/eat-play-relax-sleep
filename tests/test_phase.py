from array import array
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
import wave

from eprs.cli import parser
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.phase import observe_phase_relationship
from eprs.system import ingest, new_song, sha256, song_status


def write_pcm(path: Path, values: list[float], rate: int = 48_000) -> None:
    pcm = array("h", (round(max(-1, min(1, value)) * 32767) for value in values))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


def microphone_pair(a_path: Path, b_path: Path, delay_ms: float = 8) -> None:
    rate = 48_000
    rng = random.Random(913)
    values = []
    smoothed = 0.0
    for index in range(rate):
        # Bounded, irregular low-frequency detail survives the 2 kHz observation decode.
        smoothed = smoothed * 0.88 + rng.uniform(-0.12, 0.12)
        shaped = smoothed + 0.18 * math.sin(2 * math.pi * (127 + index / rate * 71) * index / rate)
        values.append(shaped * 0.72)
    delay = round(delay_ms * rate / 1000)
    delayed_inverted = [0.0] * delay + [-value for value in values[:-delay]]
    write_pcm(a_path, values, rate)
    write_pcm(b_path, delayed_inverted, rate)


class PhaseObservationTests(unittest.TestCase):
    def test_delayed_inverted_pair_is_observed_without_audio_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Two Microphones")
            outside_a = root / "close.wav"
            outside_b = root / "room.wav"
            microphone_pair(outside_a, outside_b)
            source_a, _ = ingest(outside_a, song, "close vocal")
            source_b, _ = ingest(outside_b, song, "room vocal")
            before = {source_a: sha256(source_a), source_b: sha256(source_b)}

            destination, report = observe_phase_relationship(
                song,
                source_a,
                source_b,
                "close vocal",
                "room vocal",
                "Hear whether the two microphones reinforce the family phrase in mono.",
                duration=0.8,
                max_shift_ms=15,
                step_ms=0.5,
            )

            strongest = report["measurement"]["strongest_absolute"]
            mono = report["measurement"]["mono_sum_at_strongest_absolute"]
            self.assertEqual(report["schema"], "eprs.phase-observation/v1")
            self.assertAlmostEqual(strongest["b_offset_relative_to_a_ms"], 8, delta=0.5)
            self.assertLess(strongest["correlation"], -0.98)
            self.assertLess(mono["normal_sum_db_relative"], -20)
            self.assertGreater(mono["b_polarity_inverted_sum_db_relative"], -1)
            self.assertEqual(set(report["actions_performed"].values()), {False})
            self.assertEqual({path: sha256(path) for path in before}, before)
            self.assertTrue(destination.is_file())
            self.assertEqual(list((song / "notes" / "phase").glob("*.wav")), [])

            repeated_path, repeated_report = observe_phase_relationship(
                song,
                source_a,
                source_b,
                "close vocal",
                "room vocal",
                "Hear whether the two microphones reinforce the family phrase in mono.",
                duration=0.8,
                max_shift_ms=15,
                step_ms=0.5,
            )
            self.assertEqual(repeated_path, destination)
            self.assertEqual(repeated_report, report)

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["phase_observations"], 1)
            self.assertEqual(status["inventory"]["invalid_phase_observations"], 0)
            self.assertEqual(status["attention"], [])
            packet = build_agent_context(song, verify=True)
            summary = packet["recent_phase_observations"][0]
            self.assertTrue(summary["scan_omitted"])
            self.assertNotIn("scan", summary)
            self.assertEqual(summary["strongest_absolute"], strongest)
            self.assertIn(
                "## Recent multi-microphone phase observations",
                render_agent_context_markdown(packet),
            )

            source_b.write_bytes(source_b.read_bytes() + b"drift")
            drifted = song_status(song, verify=True)
            self.assertEqual(drifted["inventory"]["invalid_phase_observations"], 1)
            self.assertIn("source b for phase observation", " ".join(drifted["attention"]))

    def test_silence_workspace_boundary_and_analysis_bounds_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Phase Limits")
            silence_a = root / "silence-a.wav"
            silence_b = root / "silence-b.wav"
            write_pcm(silence_a, [0.0] * 48_000)
            write_pcm(silence_b, [0.0] * 48_000)
            source_a, _ = ingest(silence_a, song, "silent close")
            source_b, _ = ingest(silence_b, song, "silent room")

            with self.assertRaisesRegex(ValueError, "silent|varying"):
                observe_phase_relationship(
                    song, source_a, source_b, "close", "room", "Check silence.", duration=0.5
                )
            with self.assertRaisesRegex(ValueError, "inside the song"):
                observe_phase_relationship(
                    song, silence_a, source_b, "close", "room", "Check boundary.", duration=0.5
                )
            with self.assertRaisesRegex(ValueError, "distinct"):
                observe_phase_relationship(
                    song, source_a, source_a, "close", "room", "Check duplicate.", duration=0.5
                )
            with self.assertRaisesRegex(ValueError, "401 candidates"):
                observe_phase_relationship(
                    song,
                    source_a,
                    source_b,
                    "close",
                    "room",
                    "Check bounded scan.",
                    duration=0.5,
                    max_shift_ms=100,
                    step_ms=0.1,
                )

    def test_cli_exposes_explicit_two_source_controls(self):
        args = parser().parse_args([
            "phase", "recordings/raw/close.wav", "recordings/raw/room.wav",
            "--song", "songs/example", "--role-a", "close", "--role-b", "room",
            "--intent", "Listen in mono.", "--duration", "2.5",
        ])
        self.assertEqual(args.command, "phase")
        self.assertEqual(args.duration, 2.5)
        self.assertEqual(args.max_shift_ms, 20)


if __name__ == "__main__":
    unittest.main()
