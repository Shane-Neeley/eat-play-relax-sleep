from pathlib import Path
import subprocess
import unittest

from eprs.autotune import (
    allowed_pitch_classes,
    corrected_midi_track,
    nearest_allowed_midi,
    settings_for,
    target_midi_track,
)
from eprs.cli import parser


ROOT = Path(__file__).resolve().parents[1]


class AutotuneControlTests(unittest.TestCase):
    def test_scale_notes_and_enharmonic_keys_are_explicit(self):
        self.assertEqual(allowed_pitch_classes("A", "major-pentatonic"), (1, 4, 6, 9, 11))
        self.assertEqual(allowed_pitch_classes("Bb", "major"), (0, 2, 3, 5, 7, 9, 10))
        self.assertEqual(nearest_allowed_midi(60.42, allowed_pitch_classes("C", "major")), 60)
        with self.assertRaisesRegex(ValueError, "unsupported autotune scale"):
            allowed_pitch_classes("C", "wishful")

    def test_hard_step_quantizes_voiced_frames_and_preserves_silence(self):
        source = [60.42, 60.49, None, 61.62]
        targets = target_midi_track(
            source,
            allowed_pitch_classes("C", "chromatic"),
            frame_period_ms=5,
            switch_hysteresis_cents=0,
            minimum_note_ms=0,
        )
        corrected = corrected_midi_track(
            source, targets,
            correction_strength=1,
            retune_ms=0,
            frame_period_ms=5,
        )
        self.assertEqual(corrected, [60.0, 60.0, None, 62.0])

    def test_slow_retune_and_partial_strength_do_not_flatten_source_contour(self):
        source = [60.4, 60.3, 60.2]
        targets = [60.0, 60.0, 60.0]
        corrected = corrected_midi_track(
            source, targets,
            correction_strength=0.5,
            retune_ms=70,
            frame_period_ms=5,
        )
        self.assertGreater(corrected[0], 60.2)
        self.assertLess(corrected[-1], source[-1])
        self.assertNotEqual(
            [round(value, 6) for value in corrected],
            [round(value, 6) for value in source],
        )

    def test_presets_are_bounded_and_cli_is_agent_addressable(self):
        settings = settings_for(
            "gloopy", key="A", scale="major-pentatonic",
            overrides={"wet": 0.75, "retune_ms": None},
        )
        self.assertEqual(settings.key, "A")
        self.assertEqual(settings.scale, "major-pentatonic")
        self.assertEqual(settings.wet, 0.75)
        self.assertEqual(settings.retune_ms, 8)
        arguments = parser().parse_args([
            "autotune", "voice.wav", "--out", "voice-tuned.wav",
            "--intent", "Make the held vowels answer the synth.",
            "--preset", "hard-step", "--key", "D", "--scale", "dorian",
        ])
        self.assertEqual(arguments.command, "autotune")
        self.assertEqual(arguments.preset, "hard-step")
        self.assertEqual(arguments.key, "D")

    def test_help_does_not_import_optional_audio_dependencies(self):
        completed = subprocess.run(
            [str(ROOT / "scripts" / "eprs"), "autotune", "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("formant-aware pitch correction", completed.stdout)


if __name__ == "__main__":
    unittest.main()
