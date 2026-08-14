import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "minimax_music3_runner.py"


class MiniMaxMusic3RunnerTests(unittest.TestCase):
    def test_runner_help_and_version_do_not_import_heavy_runtime(self):
        help_run = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        version_run = subprocess.run(
            [sys.executable, str(RUNNER), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("MiniMax Music 3", help_run.stdout)
        self.assertIn("--instructions", help_run.stdout)
        self.assertIn("minimax-music3-runner 0.1", version_run.stdout)

    def test_profile_registry_and_docs_keep_cuda_sidecar_optional(self):
        profile = json.loads((ROOT / "config/adapters/minimax-music3.json").read_text())
        registry = json.loads((ROOT / "config/toolchain.json").read_text())
        provider = next(item for item in registry["tools"] if item["id"] == "minimax_music3")
        self.assertEqual(profile["provider"], provider["id"])
        self.assertTrue(set(profile["capabilities"]).issubset(provider["capabilities"]))
        self.assertIn("minimax-music3-cuda-collaboration", {item["id"] for item in registry["workflows"]})
        docs = (ROOT / "docs/MINIMAX_MUSIC3.md").read_text()
        self.assertIn("16 GB unified memory", docs)
        self.assertIn("Community License", docs)


if __name__ == "__main__":
    unittest.main()
