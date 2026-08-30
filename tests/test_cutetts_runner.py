import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "cutetts_voice.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("cutetts_voice_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeWaveform:
    def squeeze(self, _dimension):
        return self

    def float(self):
        return self

    def numpy(self):
        return [0.0, 0.1, 0.0]


class CuteTTSRunnerTests(unittest.TestCase):
    def test_help_and_version_do_not_import_the_optional_model(self):
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
        self.assertIn("consent-bound", help_run.stdout)
        self.assertIn("cutetts-voice 0.1", version_run.stdout)

    def test_batch_loads_once_preserves_reference_and_records_provenance(self):
        runner = load_runner_module()
        model_loads = []
        generation_calls = []

        class FakeModel:
            variant = "base"

            def generate(self, text, **kwargs):
                generation_calls.append((text, kwargs))
                return types.SimpleNamespace(waveform=FakeWaveform(), sample_rate=24000)

        class FakeCuteTTS:
            @classmethod
            def from_pretrained(cls, model_dir, *, device):
                model_loads.append((model_dir, device))
                return FakeModel()

        soundfile = types.ModuleType("soundfile")
        soundfile.__dict__["write"] = (
            lambda path, samples, sample_rate, *, subtype: Path(path).write_bytes(b"cue")
        )
        cutetts = types.ModuleType("cutetts")
        cutetts.__dict__["CuteTTS"] = FakeCuteTTS

        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            sys.modules, {"soundfile": soundfile, "cutetts": cutetts}
        ):
            root = Path(folder)
            model_dir = root / "model"
            checkpoint = model_dir / "weights" / "model.safetensors"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_bytes(b"model fixture")
            reference = root / "reference.wav"
            reference.write_bytes(b"authorized immutable voice")
            out_dir = root / "outputs"
            args = runner.parser().parse_args([
                "--model-dir", str(model_dir),
                "--model-revision", "fixture-model",
                "--code-revision", "fixture-code",
                "--reference-audio", str(reference),
                "--consent-note", "Speaker authorizes this local test.",
                "--text", "First cue.",
                "--text", "Second cue.",
                "--out-dir", str(out_dir),
                "--device", "cpu",
                "--seed", "4242",
            ])
            manifest_path = runner.generate(args)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(len(model_loads), 1)
            self.assertEqual(len(generation_calls), 2)
            self.assertEqual(
                [call[1]["seed"] for call in generation_calls], [4242, 4243]
            )
            self.assertEqual(reference.read_bytes(), b"authorized immutable voice")
            self.assertEqual(manifest["reference"]["path"], "<local reference path withheld>")
            self.assertEqual(manifest["reference"]["sha256"], runner.sha256(reference))
            self.assertEqual(len(manifest["outputs"]), 2)
            self.assertEqual(manifest["checkpoints"][0]["sha256"], runner.sha256(checkpoint))
            self.assertGreaterEqual(manifest["timing"]["model_load_seconds"], 0)
            self.assertNotIn(str(reference), manifest_path.read_text(encoding="utf-8"))

    def test_profile_and_registry_are_provider_bound(self):
        profile = json.loads((ROOT / "config/adapters/cutetts.json").read_text())
        registry = json.loads((ROOT / "config/toolchain.json").read_text())
        provider = next(item for item in registry["tools"] if item["id"] == "cutetts")
        self.assertEqual(profile["provider"], provider["id"])
        self.assertTrue(set(profile["capabilities"]).issubset(provider["capabilities"]))


if __name__ == "__main__":
    unittest.main()
