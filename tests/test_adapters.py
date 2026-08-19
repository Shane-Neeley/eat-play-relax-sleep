import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.adapters import (
    adapter_catalog,
    adapter_fit,
    adapter_guide,
    load_adapter_profiles,
)
from eprs.cli import parser


def profile(provider: str = "available-tool", capability: str = "capture") -> dict:
    return {
        "schema": "eprs.software-adapter/v1",
        "id": "fixture-adapter",
        "label": "Fixture adapter",
        "summary": "Exercise portable adapter discovery without running a creative tool.",
        "provider": provider,
        "capabilities": [capability],
        "handoffs": [{
            "id": "capture-source",
            "label": "Capture a source",
            "intent": "Preserve one supplied performance for a later musical decision.",
            "capabilities": [capability],
            "automation": "gui",
            "requires_user_operation": True,
            "inputs": ["One explicitly named source"],
            "outputs": ["One new lossless file"],
            "steps": ["Operate the tool without changing the only source."],
            "verification": ["Confirm the source remains unchanged."],
        }],
        "safety": {
            "preserve": ["The original source"],
            "avoid": ["In-place edits"],
        },
    }


def toolchain(path: Path) -> Path:
    value = {
        "schema": "eprs.toolchain/v1",
        "tools": [{
            "id": "available-tool",
            "label": "Available fixture",
            "kind": "command-set",
            "required": False,
            "commands": [{"name": "python3", "version_args": ["--version"]}],
            "capabilities": ["capture"],
        }, {
            "id": "missing-tool",
            "label": "Missing fixture",
            "kind": "project-path",
            "required": False,
            "paths": ["definitely/missing/fixture"],
            "capabilities": ["render"],
            "install_hints": {"default": "Install the missing fixture explicitly."},
        }],
        "workflows": [{
            "id": "capture-and-render",
            "label": "Capture and render",
            "description": "Exercise workflow matching across separate providers.",
            "capabilities": ["capture", "render"],
        }],
    }
    path.write_text(json.dumps(value))
    return path


class SoftwareAdapterTests(unittest.TestCase):
    def test_fit_separates_readiness_from_nonranking_handoff_guidance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = toolchain(root / "toolchain.json")
            registry_value = json.loads(registry.read_text())
            registry_value["tools"][1] = {
                "id": "missing-tool",
                "label": "Second available fixture",
                "kind": "command-set",
                "required": False,
                "commands": [{"name": "python3", "version_args": ["--version"]}],
                "capabilities": ["render"],
            }
            registry.write_text(json.dumps(registry_value))
            profiles = root / "adapters"
            profiles.mkdir()
            (profiles / "capture.json").write_text(json.dumps(profile()))
            render_profile = profile(provider="missing-tool", capability="render")
            render_profile["id"] = "render-adapter"
            render_profile["label"] = "Render adapter"
            (profiles / "render.json").write_text(json.dumps(render_profile))

            fit = adapter_fit(
                ["capture", "render"], directory=profiles, toolchain=registry
            )
            self.assertTrue(fit["ready"])
            self.assertTrue(fit["guidance_complete"])
            self.assertEqual(
                [item["id"] for item in fit["matching_adapters"]],
                ["fixture-adapter", "render-adapter"],
            )
            self.assertTrue(all(value is False for value in fit["authority"].values()))
            self.assertNotIn(str(root), json.dumps(fit))

            (profiles / "render.json").unlink()
            uncovered = adapter_fit(
                ["capture", "render"], directory=profiles, toolchain=registry
            )
            self.assertTrue(uncovered["ready"])
            self.assertFalse(uncovered["guidance_complete"])
            self.assertEqual(uncovered["guidance_uncovered_capabilities"], ["render"])

            registry_value["tools"][1] = {
                "id": "missing-tool",
                "label": "Missing fixture",
                "kind": "project-path",
                "required": False,
                "paths": ["definitely/missing/fixture"],
                "capabilities": ["render"],
            }
            registry.write_text(json.dumps(registry_value))
            missing = adapter_fit(["render"], directory=profiles, toolchain=registry)
            self.assertFalse(missing["ready"])
            self.assertEqual(missing["missing_capabilities"], ["render"])
            self.assertEqual(missing["unknown_capabilities"], [])

            unknown = adapter_fit(
                ["capture", "future-capability"],
                directory=profiles,
                toolchain=registry,
            )
            self.assertFalse(unknown["ready"])
            self.assertEqual(unknown["unknown_capabilities"], ["future-capability"])
            self.assertEqual(unknown["missing_capabilities"], [])

    def test_project_profiles_are_valid_provider_bound_and_read_only(self):
        profiles = load_adapter_profiles()
        self.assertEqual(
            {item["id"] for item in profiles},
            {
                "ace-step-local-generator", "amphion-vevo15-singing-converter", "audacity-editor", "basic-pitch-contour-analysis", "chatcut-visual-handoff", "demucs-stem-laboratory", "diffsinger-note-controlled-voice", "ffmpeg-media", "firered-tts3-space-voice", "minimax-music3-cuda-generator", "openvpi-game-animal-melody", "qwen3-tts-local-voice", "raon-opentts-local-voice", "seed-vc-singing-converter",
                "shotcut-open-editor", "midashenglm-gen-scene-generator",
                "remotion-picture", "sonic-pi-live-code",
            },
        )
        catalog = adapter_catalog(available_only=True)
        self.assertEqual(catalog["schema"], "eprs.adapter-catalog/v1")
        self.assertGreaterEqual(catalog["profiles_total"], 1)
        self.assertTrue(all(
            item["provider"]["available"] for item in catalog["profiles"]
        ))
        self.assertTrue(all(value is False for value in catalog["authority"].values()))
        self.assertNotIn("located", json.dumps(catalog))

        guide = adapter_guide("audacity-editor", handoff_id="record-to-eprs")
        self.assertEqual(guide["schema"], "eprs.adapter-guide/v1")
        self.assertEqual(guide["adapter"]["handoffs"][0]["id"], "record-to-eprs")
        self.assertTrue(guide["adapter"]["handoffs"][0]["requires_user_operation"])
        self.assertTrue(all(value is False for value in guide["authority"].values()))

    def test_drop_in_profile_matching_uses_capabilities_not_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = toolchain(root / "toolchain.json")
            profiles = root / "adapters"
            profiles.mkdir()
            (profiles / "fixture.json").write_text(json.dumps(profile()))

            catalog = adapter_catalog(
                profiles,
                toolchain=registry,
                available_only=True,
                capabilities=["capture"],
                workflows=["capture-and-render"],
            )
            self.assertEqual(catalog["profiles_total"], 1)
            selected = catalog["profiles"][0]
            self.assertEqual(selected["id"], "fixture-adapter")
            self.assertEqual(selected["matched_workflow_capabilities"], ["capture"])
            self.assertTrue(selected["provider"]["available"])

            with self.assertRaisesRegex(ValueError, "unknown software adapter capability"):
                adapter_catalog(profiles, toolchain=registry, capabilities=["unknown"])
            with self.assertRaisesRegex(ValueError, "unknown software adapter workflow"):
                adapter_catalog(profiles, toolchain=registry, workflows=["unknown"])

    def test_profile_validation_rejects_provider_capability_and_shape_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = toolchain(root / "toolchain.json")
            profiles = root / "adapters"
            profiles.mkdir()
            candidate = profiles / "fixture.json"

            value = profile(provider="not-declared")
            candidate.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "unknown toolchain provider"):
                load_adapter_profiles(profiles, toolchain=registry)

            value = profile(capability="render")
            candidate.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "not declared"):
                load_adapter_profiles(profiles, toolchain=registry)

            value = profile()
            value["handoffs"][0]["unexpected"] = True
            candidate.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                load_adapter_profiles(profiles, toolchain=registry)

            value = profile()
            value["handoffs"][0]["capabilities"] = ["render"]
            candidate.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "profile-unsupported"):
                load_adapter_profiles(profiles, toolchain=registry)

            candidate.write_text(json.dumps(profile()))
            (profiles / "duplicate.json").write_text(json.dumps(profile()))
            with self.assertRaisesRegex(ValueError, "duplicate software adapter ids"):
                load_adapter_profiles(profiles, toolchain=registry)

    def test_ignored_checkout_local_provider_and_profile_are_auto_discovered(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            local_tool = root / "private-editor"
            local_tool.write_text("available\n")
            extension = root / "toolchain.json"
            extension.write_text(json.dumps({
                "schema": "eprs.toolchain-extension/v1",
                "tools": [{
                    "id": "private-editor",
                    "label": "Private editor",
                    "kind": "application",
                    "required": False,
                    "paths": [str(local_tool)],
                    "capabilities": ["interactive_audio_editing"],
                }],
                "workflows": [],
            }))
            profiles = root / "adapters"
            profiles.mkdir()
            local_profile = profile(
                provider="private-editor", capability="interactive_audio_editing"
            )
            local_profile["id"] = "private-editor-handoff"
            local_profile["label"] = "Private editor handoff"
            (profiles / "private-editor.json").write_text(json.dumps(local_profile))

            with (
                patch("eprs.system.REPOSITORY_LOCAL_TOOLCHAIN_PATH", extension),
                patch(
                    "eprs.adapters.REPOSITORY_LOCAL_ADAPTER_PROFILE_DIR", profiles
                ),
            ):
                catalog = adapter_catalog(
                    available_only=True,
                    capabilities=["interactive_audio_editing"],
                )
            private = next(
                item for item in catalog["profiles"]
                if item["id"] == "private-editor-handoff"
            )
            self.assertTrue(private["provider"]["available"])
            self.assertNotIn(str(local_tool), json.dumps(catalog))
            self.assertEqual(len(load_adapter_profiles()), 18)

    def test_cli_exposes_list_filters_and_exact_guides(self):
        diagnostic = parser().parse_args([
            "doctor", "--extension", ".eprs-local/toolchain.json"
        ])
        listing = parser().parse_args([
            "adapter", "list", "--available",
            "--capability", "live_coding", "--workflow", "full-local-production",
            "--toolchain-extension", ".eprs-local/toolchain.json",
            "--profile-dir", ".eprs-local/adapters",
        ])
        guide = parser().parse_args([
            "adapter", "show", "sonic-pi-live-code", "--handoff", "develop-live-code",
        ])
        context = parser().parse_args([
            "context", "songs/example",
            "--toolchain-extension", "/private/toolchain.json",
            "--profile-dir", "/private/adapters",
        ])
        dispatch = parser().parse_args([
            "dispatch", "next", "--song", "songs/example", "--agent", "fixture",
            "--toolchain-extension", "/private/toolchain.json",
            "--profile-dir", "/private/adapters",
        ])
        self.assertEqual(listing.adapter_command, "list")
        self.assertEqual(diagnostic.extension, [".eprs-local/toolchain.json"])
        self.assertTrue(listing.available)
        self.assertEqual(listing.capability, ["live_coding"])
        self.assertEqual(listing.toolchain_extension, [".eprs-local/toolchain.json"])
        self.assertEqual(listing.profile_dir, [".eprs-local/adapters"])
        self.assertEqual(guide.adapter_command, "show")
        self.assertEqual(guide.handoff, "develop-live-code")
        self.assertEqual(context.toolchain_extension, ["/private/toolchain.json"])
        self.assertEqual(context.profile_dir, ["/private/adapters"])
        self.assertEqual(dispatch.toolchain_extension, ["/private/toolchain.json"])


if __name__ == "__main__":
    unittest.main()
