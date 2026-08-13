import json
import os
import re
import sys
import tempfile
from pathlib import Path
import unittest

from eprs.visuals import (
    PALETTES,
    _run_renderer,
    compile_prompt,
    validate_spec,
    write_prompt_score,
)


class VisualPromptTests(unittest.TestCase):
    def test_prompt_selects_orthogonal_worlds(self):
        constellation = compile_prompt("slow cold constellation of circuit nodes", "Night", 8)
        ribbons = compile_prompt("warm liquid tape ribbons follow the guitar", "Tape", 9)
        portal = compile_prompt("neon garage door opens with the kick", "Door", 10)
        no_text = compile_prompt("cold tunnel, no text, bass opens the geometry", "Hidden", 11)
        family = compile_prompt("warm family voices answer a guitar breath", "Room", 12)
        pull = compile_prompt("pull me in: a dark room opens into a warm signal", "Pull Me In", 13)
        reggae = compile_prompt("Jamaican reggae flags over a dub bass pocket", "Reggae", 14)
        paper = compile_prompt("warm paper score cards and a constellation of notes", "Paper", 15)
        self.assertEqual(constellation["world"], "constellation")
        self.assertEqual(ribbons["world"], "ribbons")
        self.assertEqual(portal["world"], "portal")
        self.assertFalse(no_text["typography"]["show"])
        self.assertEqual(family["world"], "ribbons")
        self.assertEqual(family["palette"], PALETTES["warm"])
        self.assertLess(constellation["motion"]["speed"], portal["motion"]["speed"])
        self.assertGreater(ribbons["reactivity"]["mids"], portal["reactivity"]["mids"])
        self.assertEqual(pull["motif"], "pull-me-in")
        self.assertEqual(reggae["motif"], "jamaica-reggae")
        paper["motif"] = "paper-score"
        self.assertEqual(validate_spec(paper)["motif"], "paper-score")

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

    def test_rejects_motif_the_renderer_would_silently_drop(self):
        candidate = compile_prompt("portal", "Test", 1)
        candidate["motif"] = "genre-lock"
        with self.assertRaisesRegex(ValueError, "visual motif"):
            validate_spec(candidate)

    def test_rejects_atlas_cards_the_renderer_would_silently_drop(self):
        candidate = compile_prompt("constellation", "Test", 1)
        candidate["motif"] = "rare-signal-atlas"
        candidate["cards"] = [{"label": "Bird", "region": "Field"}]
        with self.assertRaisesRegex(ValueError, "visual cards"):
            validate_spec(candidate)

    def test_validates_bounded_relative_inaturalist_photographs(self):
        candidate = compile_prompt("constellation", "Field Signal", 21)
        candidate["photographs"] = [{
            "path": "../references/inaturalist-photos/field/photo.jpg",
            "opacity": 0.32,
            "treatment": "soft-light",
        }]
        self.assertEqual(validate_spec(candidate)["photographs"][0]["opacity"], 0.32)
        candidate["photographs"][0]["path"] = "/tmp/untracked-photo.jpg"
        with self.assertRaisesRegex(ValueError, "visual photographs"):
            validate_spec(candidate)

    @unittest.skipIf(os.name == "nt", "process-group assertion is POSIX-specific")
    def test_renderer_timeout_reaps_its_child_process_group(self):
        command = [
            sys.executable,
            "-c",
            (
                "import subprocess,sys,time; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "print(f'child={child.pid}', flush=True); time.sleep(60)"
            ),
        ]
        with self.assertRaisesRegex(RuntimeError, "time budget") as raised:
            _run_renderer(command, timeout_seconds=0.2)
        match = re.search(r"child=(\d+)", str(raised.exception))
        self.assertIsNotNone(match)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(match.group(1)), 0)


if __name__ == "__main__":
    unittest.main()
