"""Tests for the optional Pedalboard recipe boundary and renderer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.pedalboard_fx import _normalize_plugin, render_pedalboard, review_pedalboard, verify_pedalboard_provenance


class PedalboardRecipeTests(unittest.TestCase):
    def test_normalizes_ordered_and_parallel_chains(self):
        spec = _normalize_plugin({
            "type": "mix",
            "branches": [
                [{"type": "gain", "gain_db": -3}, {"type": "delay", "delay_seconds": 0.2}],
                [{"type": "chorus", "mix": 0.2}, {"type": "reverb", "wet_level": 0.1}],
            ],
        }, 48_000, 0, "plugins[0]")
        self.assertEqual(spec["type"], "mix")
        self.assertEqual(len(spec["branches"]), 2)
        self.assertEqual(spec["branches"][0][1]["delay_seconds"], 0.2)

    def test_rejects_unsafe_frequency(self):
        with self.assertRaises(ValueError):
            _normalize_plugin({"type": "lowpass_filter", "cutoff_frequency_hz": 30_000}, 48_000, 0, "plugins[0]")


@unittest.skipUnless(__import__("importlib.util").util.find_spec("pedalboard"), "optional Pedalboard extra is not installed")
class PedalboardRenderTests(unittest.TestCase):
    def test_renders_and_reviews_checksum_bound_stem(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            song = root / "song"
            song.mkdir()
            (song / "recordings").mkdir()
            (song / "song.json").write_text(json.dumps({"schema": "eprs.song/v1", "title": "Test", "sample_rate": 48_000}))
            source = song / "recordings" / "source.wav"
            with wave.open(str(source), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(48_000)
                handle.writeframes(b"\0\0" * 48_000)
            spec = root / "pedalboard.json"
            spec.write_text(json.dumps({
                "schema": "eprs.pedalboard/v1",
                "title": "Test Chain",
                "role": "hook",
                "intent": "Verify a short ordered and parallel effects chain.",
                "source": "recordings/source.wav",
                "plugins": [
                    {"type": "compressor", "threshold_db": -24, "ratio": 3},
                    {"type": "mix", "branches": [
                        [{"type": "gain", "gain_db": 0}],
                        [{"type": "delay", "delay_seconds": 0.08, "feedback": 0.1, "mix": 0.2}],
                    ]},
                    {"type": "limiter", "threshold_db": -1},
                ],
            }))
            stem, _ = render_pedalboard(spec, song)
            verify_pedalboard_provenance(song, stem)
            review_pedalboard(song, stem, "The dry center stays present and the delayed branch reads as a tail.", "keep")
            _, _, metadata = verify_pedalboard_provenance(song, stem)
            self.assertEqual(metadata["review"]["decision"], "keep")

