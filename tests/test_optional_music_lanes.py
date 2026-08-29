from pathlib import Path
import subprocess
import sys
import unittest

from eprs.adapters import load_adapter_profiles
from eprs.system import load_toolchain


ROOT = Path(__file__).resolve().parents[1]


class OptionalMusicLaneTests(unittest.TestCase):
    def test_optional_providers_and_workflows_are_declared(self):
        registry = load_toolchain()
        providers = {item["id"]: item for item in registry["tools"]}
        expected = {
            "opencv": {"video_quality_analysis", "thumbnail_quality_analysis"},
            "supercollider": {"audio_synthesis", "algorithmic_composition"},
            "raon_opentts": {"local_voice_generation", "reference_voice_cloning"},
            "seed_vc": {"singing_voice_conversion", "local_voice_conversion"},
            "openvpi_game": {"audio_to_midi", "animal_pitch_extraction"},
            "diffsinger": {"note_controlled_singing", "singing_voice_synthesis"},
            "amphion_vevo15": {"zero_shot_singing_conversion", "prosody_transfer"},
            "basic_pitch": {"polyphonic_pitch_extraction", "pitch_bend_extraction"},
            "demucs": {"stem_separation", "bass_isolation"},
        }
        for provider_id, capabilities in expected.items():
            self.assertIn(provider_id, providers)
            self.assertFalse(providers[provider_id]["required"])
            self.assertTrue(capabilities <= set(providers[provider_id]["capabilities"]))
        workflows = {item["id"]: item for item in registry["workflows"]}
        self.assertTrue({
            "animal-to-melody-lab", "singing-voice-lab", "stem-repair-lab",
            "local-reference-voice-collaboration", "video-quality-gate",
            "supercollider-audio-lab",
        } <= workflows.keys())

    def test_optional_adapter_profiles_are_valid_and_capability_bound(self):
        profiles = load_adapter_profiles()
        expected = {
            "opencv-video-quality-gate",
            "supercollider-audio-server",
            "seed-vc-singing-converter",
            "openvpi-game-animal-melody",
            "diffsinger-note-controlled-voice",
            "amphion-vevo15-singing-converter",
            "basic-pitch-contour-analysis",
            "demucs-stem-laboratory",
            "raon-opentts-local-voice",
        }
        loaded = {item["id"]: item for item in profiles}
        self.assertTrue(expected <= loaded.keys())
        providers = {item["id"]: item for item in load_toolchain()["tools"]}
        for profile_id in expected:
            profile = loaded[profile_id]
            self.assertTrue(set(profile["capabilities"]) <= set(providers[profile["provider"]]["capabilities"]))
            self.assertTrue(all(handoff["requires_user_operation"] for handoff in profile["handoffs"]))

    def test_raon_runner_exposes_consent_and_speech_boundaries(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "raon_opentts_voice.py"), "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("--consent-note", completed.stdout)
        self.assertIn("speech-first", completed.stdout)
        self.assertIn("--reference-text", completed.stdout)

    def test_lane_docs_keep_fallback_and_rights_language_visible(self):
        text = (ROOT / "docs" / "OPTIONAL_MUSIC_LANES.md").read_text()
        lowered = text.lower()
        for phrase in ("optional", "fallback", "license", "seed-vc", "animal-to-melody", "opencv", "supercollider"):
            self.assertIn(phrase, lowered)
