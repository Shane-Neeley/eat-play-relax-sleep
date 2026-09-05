from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import wave

from eprs.system import (
    create_experiment,
    doctor,
    finish_experiment,
    ingest,
    load_toolchain,
    new_song,
    record_experiment_result,
    sha256,
    song_status,
    toolchain_extension_paths,
)


def tiny_wav(path: Path):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\x00\x00" * 480)


class SystemTests(unittest.TestCase):
    def test_toolchain_registry_drives_actionable_doctor_report(self):
        registry = load_toolchain()
        self.assertEqual(registry["schema"], "eprs.toolchain/v1")
        self.assertIn("ffmpeg", {tool["id"] for tool in registry["tools"]})

        report = doctor()
        self.assertEqual(report["schema"], "eprs.doctor/v1")
        self.assertIn("python3", report["commands"])
        self.assertIn("youtube_preparation", report["capabilities"])
        self.assertIn("full-local-production", {
            workflow["id"] for workflow in report["workflow_catalog"]
        })
        self.assertIsInstance(report["next_actions"], list)
        self.assertEqual(
            report["ok"],
            all(tool["available"] for tool in report["tools"] if tool["required"]),
        )

    def test_toolchain_registry_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            registry_path = Path(folder) / "toolchain.json"
            registry_path.write_text(json.dumps({
                "schema": "eprs.toolchain/v1",
                "tools": [
                    {"id": "same", "kind": "project-path", "paths": ["one"]},
                    {"id": "same", "kind": "project-path", "paths": ["two"]},
                ],
            }))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_toolchain(registry_path)

    def test_toolchain_registry_validates_workflow_capabilities(self):
        with tempfile.TemporaryDirectory() as folder:
            registry_path = Path(folder) / "toolchain.json"
            registry_path.write_text(json.dumps({
                "schema": "eprs.toolchain/v1",
                "tools": [{
                    "id": "adapter",
                    "kind": "project-path",
                    "paths": ["missing"],
                    "capabilities": ["known"],
                }],
                "workflows": [{
                    "id": "bad-workflow",
                    "label": "Bad workflow",
                    "description": "References an undeclared capability.",
                    "capabilities": ["unknown"],
                }],
            }))

            with self.assertRaisesRegex(ValueError, "unknown capabilities: unknown"):
                load_toolchain(registry_path)

    def test_doctor_runs_only_bounded_read_only_version_probes(self):
        with tempfile.TemporaryDirectory() as folder:
            registry_path = Path(folder) / "toolchain.json"
            value = {
                "schema": "eprs.toolchain/v1",
                "tools": [{
                    "id": "python",
                    "kind": "command-set",
                    "required": True,
                    "commands": [{"name": "python3"}],
                    "capabilities": ["core"],
                }],
                "workflows": [],
            }
            registry_path.write_text(json.dumps(value))
            with patch("eprs.system.subprocess.run") as run:
                report = doctor(registry_path)
            run.assert_not_called()
            self.assertTrue(report["core_ready"])

            value["tools"][0]["commands"][0]["version_args"] = ["--inspect-project"]
            registry_path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "unsafe version probe"):
                load_toolchain(registry_path)

    def test_doctor_can_skip_versions_without_changing_availability(self):
        with patch("eprs.system._command_version", return_value="fixture 1.0") as probe:
            report = doctor(include_versions=False)
        probe.assert_not_called()
        self.assertTrue(report["commands"]["python3"])
        self.assertTrue(report["capabilities"]["song_workspace"])
        self.assertTrue(all(not tool["versions"] for tool in report["tools"]))

    def test_doctor_can_gate_an_optional_provider_on_python_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            registry_path = Path(folder) / "toolchain.json"
            registry_path.write_text(json.dumps({
                "schema": "eprs.toolchain/v1",
                "tools": [{
                    "id": "module-provider",
                    "kind": "command-set",
                    "required": False,
                    "commands": [{"name": "python3"}],
                    "python_modules": ["json"],
                    "capabilities": ["module_capability"],
                }, {
                    "id": "missing-module-provider",
                    "kind": "command-set",
                    "required": False,
                    "commands": [{"name": "python3"}],
                    "python_modules": ["definitely_missing_eprs_module"],
                    "capabilities": ["missing_module_capability"],
                }],
                "workflows": [],
            }))

            report = doctor(registry_path)
            providers = {item["id"]: item for item in report["tools"]}
            self.assertTrue(providers["module-provider"]["available"])
            # Optional module checks must describe the same interpreter as the
            # running import probe, not an unrelated python3 found on PATH.
            import sys
            self.assertEqual(providers["module-provider"]["located"], [sys.executable])
            self.assertFalse(providers["missing-module-provider"]["available"])
            self.assertEqual(
                providers["missing-module-provider"]["python_modules"],
                [{"name": "definitely_missing_eprs_module", "available": False}],
            )

    def test_doctor_resolves_workflows_through_interchangeable_capability_providers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            alternate = root / "alternate-renderer"
            alternate.write_text("available\n")
            registry_path = root / "toolchain.json"

            def registry(alternate_path: Path) -> dict:
                return {
                    "schema": "eprs.toolchain/v1",
                    "tools": [{
                        "id": "core",
                        "label": "Core adapter",
                        "kind": "command-set",
                        "required": True,
                        "commands": [{"name": "python3", "version_args": ["--version"]}],
                        "capabilities": ["capture"],
                    }, {
                        "id": "preferred-renderer",
                        "label": "Preferred renderer",
                        "kind": "project-path",
                        "paths": [str(root / "missing-preferred")],
                        "capabilities": ["render"],
                        "install_hints": {"default": "Install the preferred renderer."},
                    }, {
                        "id": "alternate-renderer",
                        "label": "Alternate renderer",
                        "kind": "project-path",
                        "paths": [str(alternate_path)],
                        "capabilities": ["render"],
                        "install_hints": {"default": "Install the alternate renderer."},
                    }],
                    "workflows": [{
                        "id": "capture-and-render",
                        "label": "Capture and render",
                        "description": "Exercise provider-neutral workflow readiness.",
                        "capabilities": ["capture", "render"],
                    }],
                }

            registry_path.write_text(json.dumps(registry(alternate)))
            ready = doctor(
                registry_path,
                workflows=["capture-and-render"],
                required_capabilities=["render"],
            )
            self.assertTrue(ready["ok"])
            self.assertTrue(ready["requirements"]["ready"])
            self.assertEqual(
                ready["requirements"]["resolved_capabilities"],
                ["render", "capture"],
            )
            self.assertEqual(ready["requirements"]["workflows"][0]["missing_capabilities"], [])

            registry_path.write_text(json.dumps(registry(root / "missing-alternate")))
            missing = doctor(registry_path, workflows=["capture-and-render"])
            self.assertTrue(missing["core_ready"])
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["requirements"]["missing_capabilities"], ["render"])
            self.assertEqual(
                {provider["tool_id"] for provider in missing["requirements"]["providers"]["render"]},
                {"preferred-renderer", "alternate-renderer"},
            )
            self.assertIn("Missing capability `render`", missing["requirements"]["next_actions"][0])

            with self.assertRaisesRegex(ValueError, "unknown doctor workflow"):
                doctor(registry_path, workflows=["not-declared"])
            with self.assertRaisesRegex(ValueError, "unknown doctor capability"):
                doctor(registry_path, required_capabilities=["not-declared"])

    def test_private_toolchain_extension_is_additive_optional_and_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            available = root / "local-editor"
            available.write_text("fixture\n")
            registry_path = root / "toolchain.json"
            registry_path.write_text(json.dumps({
                "schema": "eprs.toolchain/v1",
                "tools": [{
                    "id": "core",
                    "label": "Core",
                    "kind": "command-set",
                    "required": True,
                    "commands": [{"name": "python3", "version_args": ["--version"]}],
                    "capabilities": ["core_work"],
                }],
                "workflows": [{
                    "id": "core-work",
                    "label": "Core work",
                    "description": "Exercise the shared base registry.",
                    "capabilities": ["core_work"],
                }],
            }))
            before = sha256(registry_path)
            extension = root / "local-toolchain.json"
            extension.write_text(json.dumps({
                "schema": "eprs.toolchain-extension/v1",
                "tools": [{
                    "id": "private-editor",
                    "label": "Private editor",
                    "kind": "application",
                    "required": False,
                    "paths": [str(available)],
                    "capabilities": ["private_editing"],
                }],
                "workflows": [{
                    "id": "private-edit",
                    "label": "Private edit",
                    "description": "Use one locally configured editor without changing shared config.",
                    "capabilities": ["private_editing"],
                }],
            }))

            merged = load_toolchain(registry_path, extensions=[extension])
            self.assertEqual(sha256(registry_path), before)
            self.assertIn("private-editor", {item["id"] for item in merged["tools"]})
            report = doctor(
                registry_path,
                extensions=[extension],
                workflows=["private-edit"],
            )
            self.assertTrue(report["ok"])
            self.assertEqual(report["extensions"], [str(extension.resolve())])
            self.assertTrue(report["capabilities"]["private_editing"])

            with patch("eprs.system.REPOSITORY_LOCAL_TOOLCHAIN_PATH", extension):
                self.assertEqual(toolchain_extension_paths(registry_path), [])
                with patch("eprs.system.TOOLCHAIN_PATH", registry_path):
                    self.assertEqual(
                        toolchain_extension_paths(registry_path), [extension.resolve()]
                    )

            duplicate = json.loads(extension.read_text())
            duplicate["tools"][0]["id"] = "core"
            extension.write_text(json.dumps(duplicate))
            with self.assertRaisesRegex(ValueError, "may not replace"):
                load_toolchain(registry_path, extensions=[extension])

            required = json.loads(json.dumps(duplicate))
            required["tools"][0]["id"] = "required-private"
            required["tools"][0]["required"] = True
            extension.write_text(json.dumps(required))
            with self.assertRaisesRegex(ValueError, "must remain optional"):
                load_toolchain(registry_path, extensions=[extension])

            relative = json.loads(json.dumps(required))
            relative["tools"][0]["id"] = "relative-private"
            relative["tools"][0]["required"] = False
            relative["tools"][0]["paths"] = ["relative/private-editor"]
            extension.write_text(json.dumps(relative))
            with self.assertRaisesRegex(ValueError, "paths must be absolute"):
                load_toolchain(registry_path, extensions=[extension])

    def test_new_song_has_expected_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(folder, "A Nice Song")
            manifest = json.loads((song / "song.json").read_text())
            self.assertEqual(song.name, "a-nice-song")
            self.assertEqual(manifest["schema"], "eprs.song/v1")
            self.assertIn("FINAL", manifest["delivery_policy"])
            self.assertTrue((song / "recordings" / "raw").is_dir())
            self.assertTrue((song / "interchange").is_dir())
            self.assertTrue((song / "FINAL").is_dir())
            self.assertIn("handoff folder", (song / "FINAL" / "README.md").read_text())
            with self.assertRaises(FileExistsError):
                new_song(folder, "A Nice Song")

    def test_ingest_copies_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Source Safety")
            source = root / "outside.wav"
            tiny_wav(source)
            before = sha256(source)
            stored, sidecar = ingest(source, song, "Electric Guitar", "roomy")
            self.assertTrue(source.exists())
            self.assertEqual(sha256(source), before)
            self.assertEqual(sha256(stored), before)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["role"], "Electric Guitar")
            self.assertEqual(metadata["instrument"], "Electric Guitar")
            self.assertEqual(metadata["sha256"], before)
            self.assertEqual(metadata["stored_path"], f"recordings/raw/electric-guitar/{stored.name}")
            self.assertNotIn(str(root), metadata["stored_path"])

            original_sidecar = sidecar.read_bytes()
            _, compatibility_sidecar = ingest(source, song, instrument="Electric Guitar", note="a later note")
            compatibility = json.loads(compatibility_sidecar.read_text())
            self.assertEqual(compatibility["role"], "Electric Guitar")
            self.assertEqual(compatibility_sidecar.read_bytes(), original_sidecar)

    def test_ingest_rejects_a_role_without_a_portable_folder_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Role Safety")
            source = root / "idea.wav"
            tiny_wav(source)
            with self.assertRaisesRegex(ValueError, "source role"):
                ingest(source, song, "🎵", "")

    def test_experiment_can_record_a_listening_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Decision Loop")
            beat = root / "test.beat"
            beat.write_text("title Test\ntempo 90\nbars 1\ntrack kick | x... .... .... .... |\n")
            result = root / "result.wav"
            tiny_wav(result)
            experiment = create_experiment(song, beat, None, "Does it leave space?", 4)
            manifest_path = finish_experiment(experiment, result, "The rest is the hook.", "keep")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema"], "eprs.experiment/v2")
            self.assertEqual(manifest["inputs"]["beat"]["role"], "beat")
            self.assertTrue((experiment / manifest["inputs"]["beat"]["path"]).is_file())
            self.assertEqual(manifest["status"], "decided")
            self.assertEqual(manifest["decision"], "keep")
            self.assertEqual(manifest["listening_notes"], ["The rest is the hook."])
            self.assertEqual(manifest["results"][0]["sha256"], sha256(result))
            preserved = experiment / manifest["results"][0]["path"]
            self.assertTrue(preserved.is_file())
            self.assertEqual(sha256(preserved), sha256(result))
            self.assertTrue(result.is_file())

    def test_experiment_render_can_wait_for_a_real_listening_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Pending Listen")
            beat = root / "test.beat"
            beat.write_text("title Test\ntempo 90\nbars 1\ntrack kick | x... .... .... .... |\n")
            result = root / "result.wav"
            tiny_wav(result)
            experiment = create_experiment(song, beat, None, "Does it leave space?", 4)

            manifest_path = record_experiment_result(
                experiment, result, "Technical render completed without a creative verdict."
            )
            rendered = json.loads(manifest_path.read_text())
            self.assertEqual(rendered["status"], "rendered")
            self.assertIsNone(rendered["decision"])
            self.assertEqual(rendered["listening_notes"], [])
            self.assertEqual(rendered["render_notes"], [
                "Technical render completed without a creative verdict."
            ])
            self.assertIn("rendered experiment", " ".join(song_status(song)["next_actions"]))

            finish_experiment(experiment, result, "The rest is the hook.", "keep")
            decided = json.loads(manifest_path.read_text())
            self.assertEqual(decided["status"], "decided")
            self.assertEqual(len(decided["results"]), 1)
            self.assertEqual(decided["listening_notes"], ["The rest is the hook."])

    def test_experiment_freezes_mixed_sources_without_duplicating_raw_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Mixed Sources")
            performance = root / "family.wav"
            tiny_wav(performance)
            raw_recording, _ = ingest(performance, song, "Family voices", "Keep the laugh at the end")
            lyrics = root / "lyric fragments.txt"
            lyrics.write_text("Porch light / late chimes / everybody answers\n")

            experiment = create_experiment(
                song,
                None,
                None,
                "Can the chimes answer the family phrase without crowding it?",
                12,
                [("family voices", raw_recording), ("lyric fragments", lyrics)],
            )
            manifest = json.loads((experiment / "experiment.json").read_text())
            self.assertEqual(manifest["schema"], "eprs.experiment/v2")

            voices = manifest["inputs"]["family-voices"]
            self.assertEqual(voices["base"], "song")
            self.assertEqual(voices["storage"], "song-reference")
            self.assertEqual((song / voices["path"]).resolve(), raw_recording.resolve())
            self.assertFalse((experiment / "inputs" / raw_recording.name).exists())

            fragments = manifest["inputs"]["lyric-fragments"]
            self.assertEqual(fragments["base"], "experiment")
            self.assertEqual(fragments["storage"], "experiment-copy")
            frozen_lyrics = experiment / fragments["path"]
            self.assertEqual(frozen_lyrics.read_text(), lyrics.read_text())

            lyrics.write_text("A later edit that must not rewrite experiment history.\n")
            self.assertNotEqual(frozen_lyrics.read_text(), lyrics.read_text())
            verified = song_status(song, verify=True)
            self.assertTrue(verified["checksums_verified"])
            self.assertEqual(verified["attention"], [])

            frozen_lyrics.write_text("A changed frozen input must be visible to the next agent.\n")
            drifted = song_status(song, verify=True)
            self.assertIn("Checksum mismatch", " ".join(drifted["attention"]))

    def test_experiment_requires_inputs_and_unique_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Input Contract")
            idea = root / "idea.txt"
            idea.write_text("one idea\n")
            with self.assertRaisesRegex(ValueError, "requires"):
                create_experiment(song, None, None, "", 1)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                create_experiment(song, None, None, "", 1, [("Voice", idea), ("voice", idea)])

    def test_experiment_creation_does_not_leave_a_visible_partial_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Experiment")
            idea = root / "idea.txt"
            idea.write_text("one fragile input\n")
            with patch("eprs.system.shutil.copy2", side_effect=OSError("simulated copy failure")):
                with self.assertRaisesRegex(OSError, "simulated copy failure"):
                    create_experiment(song, None, None, "Can this copy safely?", 1, [("idea", idea)])
            self.assertEqual(list((song / "experiments").iterdir()), [])

    def test_v1_experiment_history_remains_finishable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Old History")
            experiment = song / "experiments" / "legacy-v1"
            experiment.mkdir()
            beat = experiment / "legacy.beat"
            beat.write_text("title Legacy\ntempo 80\nbars 1\ntrack kick | x... .... .... .... |\n")
            (experiment / "experiment.json").write_text(json.dumps({
                "schema": "eprs.experiment/v1",
                "status": "planned",
                "inputs": {"beat": {"path": beat.name, "sha256": sha256(beat)}, "brief": None},
                "results": [],
                "listening_notes": [],
                "decision": None,
            }))
            result = root / "legacy-result.wav"
            tiny_wav(result)

            manifest_path = finish_experiment(experiment, result, "Still useful.", "keep")
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema"], "eprs.experiment/v1")
            self.assertEqual(manifest["status"], "decided")
            self.assertEqual(song_status(song, verify=True)["attention"], [])

    def test_song_status_orients_the_next_agent_and_finds_missing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Continuity")
            (song / "briefs" / "v1.md").write_text("Leave room for the family voices.\n")
            source = root / "boom-clap.wav"
            tiny_wav(source)
            ingest(source, song, "Vocal beat idea", "Loose pocket, do not quantize")
            beat = root / "idea.beat"
            beat.write_text("title Idea\ntempo 90\nbars 1\ntrack kick | x... .... .... .... |\n")
            experiment = create_experiment(song, beat, song / "briefs" / "v1.md", "Can it breathe?", 8)

            report = song_status(song)
            self.assertEqual(report["schema"], "eprs.status/v1")
            self.assertEqual(report["inventory"]["briefs"], 1)
            self.assertEqual(report["inventory"]["raw_recordings"], 1)
            self.assertEqual(report["inventory"]["experiments"]["planned"], 1)
            self.assertIn("finish the planned experiment", " ".join(report["next_actions"]))
            self.assertEqual(report["attention"], [])

            (experiment / "experiment.json").write_text(json.dumps({
                "schema": "eprs.experiment/v1",
                "status": "decided",
                "decision": "keep",
                "results": [{"path": "missing.wav"}],
            }))
            broken = song_status(song)
            self.assertIn("references a missing result", " ".join(broken["attention"]))

            (experiment / "experiment.json").write_text(json.dumps({
                "schema": "eprs.experiment/v1",
                "status": "decided",
                "decision": "keep",
                "results": [{"path": "../../boom-clap.wav"}],
            }))
            escaped = song_status(song)
            self.assertIn("references a missing result", " ".join(escaped["attention"]))


if __name__ == "__main__":
    unittest.main()
