from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest

from eprs.adapters import load_adapter_profiles
from eprs.system import load_toolchain


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "sonic-pi" / "eprs-gentle-groove-v5.rb"
PULL_IN_EXAMPLE = ROOT / "examples" / "sonic-pi" / "eprs-pull-me-in-v1.rb"
WILD_EXAMPLES = tuple(
    ROOT / "examples" / "sonic-pi" / name
    for name in (
        "gravity-switchyard-v1.rb",
        "moth-court-radio-v1.rb",
        "neon-bone-machine-v1.rb",
    )
)
GUIDE = ROOT / "docs" / "SONIC_PI.md"
VISUAL_CUES = ROOT / "visuals" / "adapters" / "sonic-pi-visual-cues.rb"
PERCUSSIVE_SOURCE = ROOT / "examples" / "sonic-pi" / "percussive-animal-custom-sample-test.rb"
PERCUSSIVE_GUIDE = ROOT / "examples" / "sonic-pi" / "ANIMAL_PERCUSSION.md"


class SonicPiContractTests(unittest.TestCase):
    def test_toolchain_declares_the_v5_routes_we_actually_document(self):
        registry = load_toolchain()
        sonic_pi = next(tool for tool in registry["tools"] if tool["id"] == "sonic_pi")
        self.assertEqual(
            set(sonic_pi["capabilities"]),
            {
                "live_coding",
                "sample_playback",
                "audio_recording",
                "midi_io",
                "ableton_link",
                "session_recording",
                "local_osc",
            },
        )

    def test_adapter_covers_the_portable_and_live_handoffs(self):
        profile = next(
            item for item in load_adapter_profiles()
            if item["id"] == "sonic-pi-live-code"
        )
        handoffs = {item["id"]: item for item in profile["handoffs"]}
        self.assertTrue({
            "develop-live-code",
            "record-lossless-stem",
            "sync-midi-or-link",
            "record-session-video",
            "drive-local-visuals",
        }.issubset(handoffs))
        self.assertTrue(all(item["requires_user_operation"] for item in handoffs.values()))
        self.assertIn("preserve a standalone EPRS stem", json.dumps(handoffs["sync-midi-or-link"]))
        self.assertIn("do not silently substitute", json.dumps(handoffs["record-session-video"]))

    def test_gentle_example_is_bounded_portable_and_conservative(self):
        source = EXAMPLE.read_text()
        self.assertIn("use_bpm 96", source)
        self.assertIn("set_volume! 0.55", source)
        self.assertEqual(len(re.findall(r"12\.times|4\.times", source)), 2)
        self.assertNotIn("live_loop", source)
        self.assertNotIn("use_osc", source)
        self.assertNotRegex(source, r"(?:/Users/|/private/|https?://)")
        amps = [float(value) for value in re.findall(r"\bamp:\s*([0-9]+(?:\.[0-9]+)?)", source)]
        self.assertTrue(amps)
        self.assertLessEqual(max(amps), 0.55)
        self.assertNotIn("set_drive!", source)

    def test_pull_in_example_has_song_form_instead_of_a_repeated_loop(self):
        source = PULL_IN_EXAMPLE.read_text()
        for marker in (
            "32.times",
            ":tease",
            ":pocket",
            ":lift",
            ":drop",
            ":hook",
            ":final",
            "use_random_seed 20260812",
            "with_fx :echo",
            "Final two bars are intentionally audible as a turnaround",
        ):
            self.assertIn(marker, source)
        self.assertGreaterEqual(source.count("in_thread(name:"), 4)
        self.assertGreaterEqual(source.count("sleep 0.25"), 1)
        self.assertGreaterEqual(source.count("sleep 0.5"), 2)
        self.assertNotIn("live_loop", source)
        self.assertNotIn("use_osc", source)
        self.assertNotRegex(source, r"(?:/Users/|/private/|https?://)")

    def test_wild_examples_are_bounded_seeded_and_local(self):
        for example in WILD_EXAMPLES:
            with self.subTest(example=example.name):
                source = example.read_text()
                self.assertRegex(source, r"use_random_seed\s+\d+")
                self.assertRegex(source, r"set_volume!\s+0\.[0-6]\d*")
                self.assertNotRegex(source, r"(?m)^\s*live_loop\b")
                self.assertNotRegex(source, r"(?m)^\s*use_osc\b")
                self.assertNotRegex(source, r"(?:/Users/|/private/|https?://)")

    def test_visual_cue_source_is_local_only(self):
        source = VISUAL_CUES.read_text()
        self.assertIn('use_osc "127.0.0.1", 57121', source)
        self.assertNotRegex(source, r'use_osc\s+["\'](?!127\.0\.0\.1)')
        self.assertIn("localhost-only", source)

    def test_notes_pin_v5_behavior_and_upstream_sources(self):
        notes = GUIDE.read_text()
        for marker in (
            "5.0.0",
            "SuperSonic",
            "set_volume!",
            "set_drive!",
            "use_bpm :midi",
            "link_audio",
            "session recording and Syphon/Spout GUI streaming",
            "https://github.com/sonic-pi-net/sonic-pi/releases/tag/v5.0.0",
            "https://github.com/sonic-pi-net/sonic-pi/blob/dev/CHANGELOG.md",
        ):
            self.assertIn(marker, notes)

    def test_custom_percussive_samples_are_documented(self):
        source = PERCUSSIVE_SOURCE.read_text()
        guide = PERCUSSIVE_GUIDE.read_text()
        for marker in (
            "PACK_DIR",
            'raise "Set PACK_DIR before running"',
            "load_samples animal_sources",
            "sample BULLFROG",
            "sample WOODPECKER",
            "sample CRICKET_FROG",
            "sample KATYDID",
            "sample CICADA",
            "onset:",
            "start:",
            "finish:",
            "rate:",
            "amp:",
        ):
            self.assertIn(marker, source)
        for marker in (
            "animal-percussion-pack.example.json",
            "never overwrite",
            "bullfrog-low.wav",
            "woodpecker-roll.wav",
            "cricket-frog-rim.wav",
            "katydid-ratchet.wav",
            "cicada-carrier.wav",
            "immutable bytes",
            "Public availability is not reuse permission",
        ):
            self.assertIn(marker, guide)

    @unittest.skipUnless(shutil.which("ruby"), "Ruby is not installed")
    def test_gentle_example_has_valid_ruby_syntax(self):
        result = subprocess.run(
            ["ruby", "-c", str(EXAMPLE)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    @unittest.skipUnless(shutil.which("ruby"), "Ruby is not installed")
    def test_pull_in_example_has_valid_ruby_syntax(self):
        result = subprocess.run(
            ["ruby", "-c", str(PULL_IN_EXAMPLE)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    @unittest.skipUnless(shutil.which("ruby"), "Ruby is not installed")
    def test_wild_examples_have_valid_ruby_syntax(self):
        for example in WILD_EXAMPLES:
            with self.subTest(example=example.name):
                result = subprocess.run(
                    ["ruby", "-c", str(example)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
