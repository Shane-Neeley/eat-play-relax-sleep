from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from eprs.cli import main
from eprs.context import build_agent_context
from eprs.planning import (
    accept_plan_work_result,
    list_plan_acceptances,
    verify_plan_acceptance,
)
from eprs.system import new_song, song_status
from eprs.work import create_work_item, finish_work_item, start_work_item
from tests.test_plan import make_request, plan_score, v2_plan_score


class ProductionPlanAcceptanceTests(unittest.TestCase):
    def _completed_plan_work(
        self,
        root: Path,
        song: Path,
        request: Path,
        score: dict,
        *,
        extra_result: bool = False,
    ) -> tuple[Path, str]:
        item_path = create_work_item(song, None, None, None, request=request)
        item_id = json.loads(item_path.read_text())["id"]
        start_work_item(song, item_id, "planning-agent")
        plan_result = root / f"{item_id}-plan.json"
        plan_result.write_text(json.dumps(score))
        results = [("production plan", plan_result)]
        if extra_result:
            note = root / f"{item_id}-notes.md"
            note.write_text("Planning caveats remain visible.\n")
            results.append(("planning notes", note))
        finish_work_item(
            song,
            item_id,
            "Authored a request-bound v2 roadmap for validation.",
            "complete",
            results,
        )
        return item_path, item_id

    def test_accepts_completed_agent_plan_with_idempotent_auditable_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Accepted Agent Plan")
            request = make_request(root, song)
            _, item_id = self._completed_plan_work(
                root, song, request, v2_plan_score(request)
            )

            acceptance_path, acceptance = accept_plan_work_result(song, item_id)

            self.assertEqual(
                acceptance["schema"], "eprs.production-plan-acceptance/v1"
            )
            self.assertEqual(
                acceptance["recipe"]["work"]["request_origin"]["request_id"],
                request.parent.name,
            )
            self.assertEqual(
                acceptance["recipe"]["selected_result"]["id"], "production-plan"
            )
            self.assertTrue(
                (song / acceptance["recipe"]["plan"]["path"]).is_file()
            )
            self.assertEqual(
                verify_plan_acceptance(song, acceptance_path)[1], acceptance
            )
            self.assertEqual(
                accept_plan_work_result(song, item_id)[0], acceptance_path
            )
            listing = list_plan_acceptances(
                song, acceptance["recipe"]["plan"]["path"]
            )
            self.assertEqual([item["id"] for item in listing["items"]], [acceptance["acceptance_id"]])
            self.assertEqual(listing["errors"], [])

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["production_plans"]["acceptances"], 1)
            self.assertEqual(
                status["inventory"]["production_plans"]["invalid_acceptances"], 0
            )
            context = build_agent_context(song, verify=True)
            summary = context["recent_production_plans"][0]
            self.assertEqual(summary["acceptances"][0]["id"], acceptance["acceptance_id"])
            self.assertEqual(context["attention"], [])

            output = StringIO()
            with redirect_stdout(output):
                result = main([
                    "plan", "accept-work", item_id, "--song", str(song)
                ])
            self.assertEqual(result, 0)
            self.assertEqual(
                json.loads(output.getvalue())["acceptance_id"],
                acceptance["acceptance_id"],
            )
            changed = json.loads(acceptance_path.read_text())
            changed["authority"]["plan_executed"] = True
            acceptance_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "authority is invalid"):
                verify_plan_acceptance(song, acceptance_path)

    def test_rejects_ambiguous_v1_or_wrong_request_results_before_plan_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Rejected Agent Plan")
            request = make_request(root, song)
            _, ambiguous_id = self._completed_plan_work(
                root,
                song,
                request,
                v2_plan_score(request),
                extra_result=True,
            )
            with self.assertRaisesRegex(ValueError, "requires --result"):
                accept_plan_work_result(song, ambiguous_id)
            path, accepted = accept_plan_work_result(
                song, ambiguous_id, result_id="production plan"
            )
            self.assertTrue(path.is_file())
            self.assertEqual(accepted["recipe"]["selected_result"]["id"], "production-plan")

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Wrong Request Plan")
            request = make_request(root, song)
            other_request = make_request(root, song)
            _, v1_id = self._completed_plan_work(
                root, song, request, plan_score(request)
            )
            with self.assertRaisesRegex(ValueError, "must use eprs.production-plan/v2"):
                accept_plan_work_result(song, v1_id)

            wrong_score = v2_plan_score(other_request)
            _, wrong_id = self._completed_plan_work(
                root, song, request, wrong_score
            )
            with self.assertRaisesRegex(ValueError, "does not target"):
                accept_plan_work_result(song, wrong_id)
            self.assertFalse((song / "notes" / "plans").exists())


if __name__ == "__main__":
    unittest.main()
