import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "qwen3_tts_voice.py"


class Qwen3TTSRunnerTests(unittest.TestCase):
    def test_runner_has_safe_help_and_version_without_model_import(self):
        help_run = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Qwen3-TTS", help_run.stdout)
        version_run = subprocess.run(
            [sys.executable, str(RUNNER), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("autotune-preset", help_run.stdout)
        self.assertIn("qwen3-tts-voice 1.1", version_run.stdout)

    def test_qwen_profile_and_registry_are_provider_bound(self):
        profile = json.loads((ROOT / "config/adapters/qwen3-tts.json").read_text())
        registry = json.loads((ROOT / "config/toolchain.json").read_text())
        provider = next(item for item in registry["tools"] if item["id"] == "qwen3_tts")
        self.assertEqual(profile["provider"], provider["id"])
        self.assertTrue(set(profile["capabilities"]).issubset(provider["capabilities"]))
        self.assertIn("local-voice-collaboration", {item["id"] for item in registry["workflows"]})


if __name__ == "__main__":
    unittest.main()
