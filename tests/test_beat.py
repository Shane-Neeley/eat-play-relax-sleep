from pathlib import Path
import math
import tempfile
import unittest
import wave

from eprs.audio import SAMPLE_RATE, render
from eprs.beat import dumps, load, mutate, parse, track_active
from eprs.visualize import svg


BEAT = """\
title "Test Pocket"
tempo 100
meter 4/4
resolution 16
bars 2
swing 0.55
seed 42
track kick | X... .... x... .... | ; gain=0.7
track snare | .... x... .... x... |
notes bass | C2 . . . G1 . . . | ; voice=bass length=1.2
"""


class BeatTests(unittest.TestCase):
    def test_parse_musical_properties(self):
        beat = parse(BEAT)
        self.assertEqual(beat.title, "Test Pocket")
        self.assertEqual(beat.total_steps, 32)
        self.assertAlmostEqual(beat.duration, 4.8)
        self.assertEqual(beat.tracks[0].steps[0], "X")

    def test_dump_round_trip(self):
        first = parse(BEAT)
        second = parse(dumps(first))
        self.assertEqual(second.title, first.title)
        self.assertEqual(second.tracks[2].steps, first.tracks[2].steps)

    def test_mutation_is_deterministic_and_preserves_downbeat(self):
        beat = parse(BEAT)
        a = mutate(beat, 9, 0.3)
        b = mutate(beat, 9, 0.3)
        self.assertEqual(dumps(a), dumps(b))
        self.assertEqual(a.tracks[0].steps[0], "X")

    def test_render_has_expected_format_and_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "test.wav"
            beat = parse(BEAT)
            render(beat, target)
            with wave.open(str(target), "rb") as wav:
                self.assertEqual(wav.getframerate(), SAMPLE_RATE)
                self.assertEqual(wav.getnchannels(), 2)
                self.assertGreater(wav.getnframes(), beat.duration * SAMPLE_RATE)

    def test_render_accepts_lossless_24_bit_voice_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample = root / "voice.wav"
            rate = 24_000
            values = [round(math.sin(2 * math.pi * 220 * frame / rate) * 1_000_000) for frame in range(rate // 10)]
            payload = b"".join(value.to_bytes(3, "little", signed=True) for value in values)
            with wave.open(str(sample), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(3)
                wav.setframerate(rate)
                wav.writeframes(payload)
            source = root / "sample.beat"
            source.write_text(BEAT.replace(
                "track kick | X... .... x... .... | ; gain=0.7",
                "track voice | X... .... .... .... | ; sample=voice.wav gain=0.7",
            ))
            target = root / "render.wav"
            render(load(source), target)
            with wave.open(str(target), "rb") as wav:
                self.assertEqual(wav.getframerate(), SAMPLE_RATE)
                self.assertGreater(wav.getnframes(), 0)

    def test_visualization_contains_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "test.svg"
            svg(parse(BEAT), target)
            text = target.read_text()
            self.assertIn("Test Pocket", text)
            self.assertIn("kick", text)
            self.assertIn("<circle", text)

    def test_invalid_symbol_has_line_context(self):
        with self.assertRaisesRegex(ValueError, r"<beat>:8"):
            parse(BEAT.replace("X...", "?..."))

    def test_sharp_notes_are_not_comments(self):
        beat = parse(BEAT.replace("C2 . . . G1", "C#2 . . . G#1"))
        self.assertEqual(beat.tracks[-1].steps[0], "C#2")

    def test_arrangement_options_scope_tracks_to_bars(self):
        arranged = BEAT.replace(
            "track kick | X... .... x... .... | ; gain=0.7",
            "track kick | X... .... x... .... | ; gain=0.7 start_bar=1 end_bar=2 every_bars=2",
        )
        beat = parse(arranged)
        kick = beat.tracks[0]
        self.assertTrue(track_active(kick, 0, beat.steps_per_bar))
        self.assertFalse(track_active(kick, beat.steps_per_bar, beat.steps_per_bar))

    def test_invalid_arrangement_range_is_rejected(self):
        arranged = BEAT.replace("; gain=0.7", "; gain=0.7 start_bar=3")
        with self.assertRaisesRegex(ValueError, "bar range"):
            parse(arranged)


class ExampleTests(unittest.TestCase):
    def test_all_examples_parse(self):
        examples = Path(__file__).parents[1] / "examples" / "beats"
        for path in examples.glob("*.beat"):
            with self.subTest(path=path):
                self.assertGreater(load(path).duration, 0)


if __name__ == "__main__":
    unittest.main()
