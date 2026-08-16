from pathlib import Path
import json
import unittest

from eprs.adapters import load_adapter_profiles


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "MIDASHENGLM.md"


class MiDashengLMContractTests(unittest.TestCase):
    def test_adapter_is_optional_and_preserves_local_authority(self):
        profile = next(
            item for item in load_adapter_profiles()
            if item["id"] == "midashenglm-gen-scene-generator"
        )
        self.assertEqual(profile["provider"], "midashenglm_gen")
        self.assertIn("unified_audio_scene_generation", profile["capabilities"])
        self.assertIn("scene-brief-to-sketch", {item["id"] for item in profile["handoffs"]})
        self.assertIn("Sonic Pi", json.dumps(profile))
        self.assertIn("Shotcut", json.dumps(profile))
        self.assertIn("Do not publish", json.dumps(profile))

    def test_guide_records_real_endpoint_and_structured_fields(self):
        guide = GUIDE.read_text()
        for marker in (
            "ZeroGPU/A10G",
            "ZeroGPU quota",
            "<|caption|>",
            "<|asr|>",
            "<|speech|>",
            "<|music|>",
            "<|sfx|>",
            "<|env|>",
            "https://github.com/xiaomi-research/midashenglm-gen",
            "do not retry in a loop",
            "Sonic Pi",
            "Shotcut",
        ):
            self.assertIn(marker, guide)

    def test_adapter_does_not_turn_the_scene_lane_into_a_fixed_style(self):
        profile = next(
            item for item in load_adapter_profiles()
            if item["id"] == "midashenglm-gen-scene-generator"
        )
        self.assertIn("weird beats", json.dumps(profile))
        self.assertIn("future tools", json.dumps(profile))
        self.assertIn("model did not render", GUIDE.read_text())


if __name__ == "__main__":
    unittest.main()
