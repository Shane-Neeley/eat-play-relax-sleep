import unittest
from pathlib import Path

from scripts.note_aware_melody import MelodyItem, midi_name, parse_item, render


class NoteAwareMelodyTests(unittest.TestCase):
    def test_item_parser_preserves_authored_note_and_timing(self):
        item = parse_item("voice.wav|auto|69|2.5|12.0|-4")
        self.assertEqual(item.path, Path("voice.wav"))
        self.assertIsNone(item.source_midi)
        self.assertEqual(item.target_midi, 69)
        self.assertEqual(item.duration_seconds, 2.5)
        self.assertEqual(item.start_seconds, 12.0)
        self.assertEqual(item.gain_db, -4)

    def test_item_parser_rejects_bad_shape_and_negative_time(self):
        with self.assertRaises(ValueError):
            parse_item("voice.wav|60|69|2")
        with self.assertRaises(ValueError):
            parse_item("voice.wav|60|69|2|-1")

    def test_note_names_are_stable_for_manifest_and_credits(self):
        self.assertEqual(midi_name(69), "A4")
        self.assertEqual(midi_name(60), "C4")
        self.assertEqual(midi_name(79), "G5")

    def test_render_rejects_same_output_and_manifest_before_optional_imports(self):
        target = Path("new-melody.wav")
        with self.assertRaisesRegex(ValueError, "different paths"):
            render([], target, target, total_seconds=1)

    def test_render_rejects_nonfinite_total_before_optional_imports(self):
        item = MelodyItem(Path("missing.wav"), 60, 69, 1, 0)
        with self.assertRaisesRegex(ValueError, "positive and finite"):
            render([item], Path("new-melody.wav"), Path("new-melody.json"), total_seconds=float("nan"))


if __name__ == "__main__":
    unittest.main()
