import json
from pathlib import Path
import tempfile
import unittest

from eprs.system import new_song
from eprs.work import create_work_item, finish_work_item, start_work_item
from eprs.work_origin import capture_completed_work_origin, verify_completed_work_origin
from tests.test_plan import make_request


class CompletedWorkOriginTests(unittest.TestCase):
    def test_completed_origin_preserves_captured_request_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request-Origin Result")
            request = make_request(root, song)
            item_path = create_work_item(
                song, None, None, None, request=request
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "planning-agent")
            result = root / "plan.json"
            result.write_text('{"schema":"eprs.production-plan/v2"}\n')
            finish_work_item(
                song,
                item_id,
                "Returned a request-bound plan draft for validation.",
                "complete",
                [("production plan", result)],
            )

            origin = capture_completed_work_origin(
                {"item": item_id, "run": 1}, song, "test artifact"
            )
            self.assertEqual(
                origin["request_origin"]["schema"],
                "eprs.production-request-work-origin/v1",
            )
            self.assertEqual(
                verify_completed_work_origin(song, origin, "test artifact"), origin
            )

    def test_origin_stays_valid_when_a_recurring_item_adds_a_later_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Recurring Origin")
            item_path = create_work_item(
                song,
                "Daily lyric continuity",
                "lyrics",
                "Preserve alternatives and report only new evidence.",
                cadence="daily",
                due_at="2000-01-01T09:00:00Z",
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "lyrics-agent")
            result = root / "result.md"
            result.write_text("Two alternatives remain meaningful.\n")
            finish_work_item(
                song, item_id, "Preserved both alternatives.", "complete", [("lyric result", result)]
            )

            origin = capture_completed_work_origin(
                {"item": item_id, "run": 1}, song, "test artifact"
            )
            self.assertEqual(origin["schema"], "eprs.completed-work-origin/v1")
            self.assertEqual(origin["run_number"], 1)
            self.assertEqual(len(json.loads(item_path.read_text())["runs"]), 2)
            self.assertEqual(verify_completed_work_origin(song, origin, "test artifact"), origin)

    def test_origin_detects_selected_run_or_request_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Origin Guard")
            item_path = create_work_item(song, "One pass", "research", "Inspect one relationship.")
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "research-agent")
            result = root / "result.md"
            result.write_text("One attributed relationship.\n")
            finish_work_item(song, item_id, "Completed one pass.", "complete", [("result", result)])
            origin = capture_completed_work_origin({"item": item_id, "run": 1}, song, "test artifact")

            changed = json.loads(item_path.read_text())
            changed["prompt"] = "Changed request after the artifact was captured."
            item_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "origin request is missing or changed"):
                verify_completed_work_origin(song, origin, "test artifact")


if __name__ == "__main__":
    unittest.main()
