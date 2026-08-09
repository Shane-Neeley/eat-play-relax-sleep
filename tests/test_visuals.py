import json
import tempfile
from pathlib import Path
import unittest

from eprs.visuals import PALETTES, compile_prompt, validate_spec, write_prompt_score


class VisualPromptTests(unittest.TestCase):
    def test_prompt_selects_orthogonal_worlds(self):
        constellation = compile_prompt("slow cold constellation of circuit nodes", "Night", 8)
        ribbons = compile_prompt("warm liquid tape ribbons follow the guitar", "Tape", 9)
        portal = compile_prompt("neon garage door opens with the kick", "Door", 10)
        no_text = compile_prompt("cold tunnel, no text, bass opens the geometry", "Hidden", 11)
        family = compile_prompt("warm family voices answer a guitar breath", "Room", 12)
        self.assertEqual(constellation["world"], "constellation")
        self.assertEqual(ribbons["world"], "ribbons")
        self.assertEqual(portal["world"], "portal")
        self.assertFalse(no_text["typography"]["show"])
        self.assertEqual(family["world"], "ribbons")
        self.assertEqual(family["palette"], PALETTES["warm"])
        self.assertLess(constellation["motion"]["speed"], portal["motion"]["speed"])
        self.assertGreater(ribbons["reactivity"]["mids"], portal["reactivity"]["mids"])

    def test_score_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "visual.json"
            write_prompt_score("acid broken tape flow", "Signal", 5, target)
            score = validate_spec(json.loads(target.read_text()))
            self.assertEqual(score["schema"], "eprs.visual/v1")
            self.assertIn("faces", score["avoid"])

    def test_rejects_unknown_world(self):
        candidate = compile_prompt("portal", "Test", 1)
        candidate["world"] = "generic-ai-video"
        with self.assertRaisesRegex(ValueError, "visual world"):
            validate_spec(candidate)


if __name__ == "__main__":
    unittest.main()
