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
RUNNER = ROOT / "scripts" / "qwen3_tts_voice.py"
BARK_RUNNER = ROOT / "scripts" / "bark_singer_voice.py"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("qwen3_tts_voice_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        self.assertIn("qwen3-tts-voice 1.2", version_run.stdout)

    def test_batch_loads_model_and_builds_autotune_settings_once(self):
        runner = load_runner_module()
        model_loads = []
        generated_texts = []
        settings_calls = []
        tuning_calls = []

        class FakeModel:
            def generate_voice_design(self, *, text, language, instruct):
                generated_texts.append((text, language, instruct))
                return [[0.0, 0.1]], 24000

        class FakeQwen3TTSModel:
            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                model_loads.append((model_id, kwargs))
                return FakeModel()

        soundfile = types.ModuleType("soundfile")

        def write_audio(path, samples, sample_rate, *, subtype):
            self.assertEqual(samples, [0.0, 0.1])
            self.assertEqual(sample_rate, 24000)
            self.assertEqual(subtype, "PCM_16")
            Path(path).write_bytes(b"fixture raw cue")

        soundfile.__dict__["write"] = write_audio
        torch = types.ModuleType("torch")
        torch.__dict__.update(
            {
                "float16": "float16",
                "float32": "float32",
                "manual_seed": lambda seed: None,
                "backends": types.SimpleNamespace(
                    mps=types.SimpleNamespace(is_available=lambda: False)
                ),
                "cuda": types.SimpleNamespace(is_available=lambda: False),
            }
        )
        qwen_tts = types.ModuleType("qwen_tts")
        qwen_tts.__dict__["Qwen3TTSModel"] = FakeQwen3TTSModel
        eprs = types.ModuleType("eprs")
        eprs.__dict__["__path__"] = []
        autotune = types.ModuleType("eprs.autotune")

        def settings_for(preset, *, key, scale):
            settings_calls.append((preset, key, scale))
            return {"preset": preset, "key": key, "scale": scale}

        def render_autotune(source, destination, settings, *, intent):
            tuning_calls.append((source, destination, settings, intent))
            destination.write_bytes(source.read_bytes() + b" tuned")
            tuning_manifest = destination.with_suffix(destination.suffix + ".json")
            tuning_manifest.write_text("{}\n", encoding="utf-8")
            return destination, tuning_manifest, {}

        autotune.__dict__.update(
            {"settings_for": settings_for, "render_autotune": render_autotune}
        )
        modules = {
            "soundfile": soundfile,
            "torch": torch,
            "qwen_tts": qwen_tts,
            "eprs": eprs,
            "eprs.autotune": autotune,
        }

        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            sys.modules, modules
        ):
            out_dir = Path(folder) / "voice"
            args = runner.parser().parse_args(
                [
                    "--device", "cpu",
                    "--instruct", "Original warm adult voice",
                    "--text", "First cue.",
                    "--text", "Second cue.",
                    "--out-dir", str(out_dir),
                    "--autotune-preset", "tight",
                    "--autotune-key", "D",
                    "--autotune-scale", "dorian",
                ]
            )
            manifest_path = runner.generate(args)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(model_loads), 1)
            self.assertEqual(len(generated_texts), 2)
            self.assertEqual(settings_calls, [("tight", "D", "dorian")])
            self.assertEqual(len(tuning_calls), 2)
            self.assertEqual(len(manifest["outputs"]), 2)
            self.assertGreaterEqual(manifest["timing"]["model_load_seconds"], 0)
            self.assertGreaterEqual(manifest["timing"]["generation_seconds"], 0)
            for output in manifest["outputs"]:
                self.assertEqual(output["duration_seconds"], 2 / 24000)
                self.assertGreaterEqual(output["real_time_factor"], 0)
                self.assertEqual(
                    output["sha256"], runner.sha256(Path(output["path"]))
                )
                self.assertEqual(
                    output["raw"]["sha256"],
                    runner.sha256(Path(output["raw"]["path"])),
                )

    def test_clone_reuses_one_consent_bound_prompt_for_the_batch(self):
        runner = load_runner_module()
        prompt_calls = []
        clone_calls = []

        class FakeModel:
            def create_voice_clone_prompt(self, *, ref_audio, ref_text, x_vector_only_mode):
                prompt_calls.append((ref_audio, ref_text, x_vector_only_mode))
                return ["private prompt tensors"]

            def generate_voice_clone(self, *, text, language, voice_clone_prompt):
                clone_calls.append((text, language, voice_clone_prompt))
                return [[0.0, 0.1]], 24000

        class FakeQwen3TTSModel:
            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                self.assertEqual(model_id, runner.DEFAULT_CLONE_MODEL)
                return FakeModel()

        soundfile = types.ModuleType("soundfile")
        soundfile.__dict__["write"] = (
            lambda path, samples, sample_rate, *, subtype: Path(path).write_bytes(b"clone cue")
        )
        torch = types.ModuleType("torch")
        torch.__dict__.update(
            {
                "float16": "float16",
                "float32": "float32",
                "manual_seed": lambda seed: None,
                "backends": types.SimpleNamespace(
                    mps=types.SimpleNamespace(is_available=lambda: False)
                ),
                "cuda": types.SimpleNamespace(is_available=lambda: False),
            }
        )
        qwen_tts = types.ModuleType("qwen_tts")
        qwen_tts.__dict__["Qwen3TTSModel"] = FakeQwen3TTSModel

        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            sys.modules, {"soundfile": soundfile, "torch": torch, "qwen_tts": qwen_tts}
        ):
            reference = Path(folder) / "private-reference.wav"
            reference.write_bytes(b"immutable authorized reference")
            out_dir = Path(folder) / "voice"
            args = runner.parser().parse_args(
                [
                    "--mode", "voice-clone",
                    "--device", "cpu",
                    "--reference-audio", str(reference),
                    "--reference-text", "Exact reference words.",
                    "--consent-note", "Speaker authorizes this local EPRS voice test.",
                    "--text", "First cue.",
                    "--text", "Second cue.",
                    "--out-dir", str(out_dir),
                ]
            )
            manifest_path = runner.generate(args)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(len(prompt_calls), 1)
            self.assertEqual(len(clone_calls), 2)
            self.assertEqual(reference.read_bytes(), b"immutable authorized reference")
            self.assertEqual(manifest["model"], runner.DEFAULT_CLONE_MODEL)
            self.assertEqual(manifest["reference"]["path"], "<local reference path withheld>")
            self.assertEqual(manifest["reference"]["sha256"], runner.sha256(reference))
            self.assertNotIn(str(reference), manifest_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(manifest["timing"]["clone_prompt_seconds"], 0)

    def test_clone_requires_consent_and_exact_transcript_by_default(self):
        runner = load_runner_module()
        args = runner.parser().parse_args(
            [
                "--mode", "voice-clone",
                "--text", "Cue.",
                "--out-dir", "ignored",
            ]
        )
        with self.assertRaisesRegex(ValueError, "reference-audio"):
            runner.validate_args(args)

    def test_qwen_profile_and_registry_are_provider_bound(self):
        profile = json.loads((ROOT / "config/adapters/qwen3-tts.json").read_text())
        registry = json.loads((ROOT / "config/toolchain.json").read_text())
        provider = next(item for item in registry["tools"] if item["id"] == "qwen3_tts")
        self.assertEqual(profile["provider"], provider["id"])
        self.assertTrue(set(profile["capabilities"]).issubset(provider["capabilities"]))
        self.assertIn("local-voice-collaboration", {item["id"] for item in registry["workflows"]})


class BarkSingerVoiceRunnerTests(unittest.TestCase):
    def test_runner_has_safe_help_and_version_without_model_import(self):
        help_run = subprocess.run(
            [sys.executable, str(BARK_RUNNER), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        version_run = subprocess.run(
            [sys.executable, str(BARK_RUNNER), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Bark", help_run.stdout)
        self.assertIn("autotune-preset", help_run.stdout)
        self.assertIn("bark-singer-voice 0.1", version_run.stdout)


if __name__ == "__main__":
    unittest.main()
