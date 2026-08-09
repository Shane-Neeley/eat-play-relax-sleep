import json
from pathlib import Path
import tempfile
import unittest

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.plan import create_production_plan
from eprs.plan_progress import production_plan_progress, queue_next_plan_step
from eprs.system import new_song, song_status
from eprs.work import (
    create_work_item,
    finish_work_item,
    list_work_items,
    load_work_item,
    start_work_item,
)
from tests.test_plan import make_request, plan_score


def make_plan(root: Path, song: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    request = make_request(root, song)
    spec = root / "plan.json"
    spec.write_text(json.dumps(plan_score(request)))
    return create_production_plan(spec, song)


def complete_work(root: Path, song: Path, item: Path, decision: str = "complete") -> None:
    item_id = json.loads(item.read_text())["id"]
    start_work_item(song, item_id, "plan-agent")
    result = root / f"{item_id}-{decision}.md"
    result.write_text(f"Evidence for {decision}.\n")
    finish_work_item(
        song,
        item_id,
        f"Recorded {decision} evidence for this exact plan step.",
        decision,
        [("step evidence", result)],
    )


class ProductionPlanProgressTests(unittest.TestCase):
    def test_queue_next_prepares_one_exact_step_and_advances_after_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Queue")
            plan = make_plan(root, song)

            first = queue_next_plan_step(
                song,
                plan,
                priority=73,
                due_at="2030-01-02T09:30:00-08:00",
            )
            self.assertEqual(first["schema"], "eprs.production-plan-queue/v1")
            self.assertEqual(first["status"], "queued")
            self.assertEqual(first["selected_step"]["id"], "develop-words")
            self.assertEqual(first["selected_step"]["declared_gates"], ["user-direction"])
            self.assertFalse(first["gates_verified"])
            self.assertIn("does not execute", first["authority"]["statement"])
            self.assertEqual(first["work"]["priority"], 73)
            self.assertEqual(first["work"]["due_at"], "2030-01-02T17:30:00Z")
            _, item = load_work_item(song, first["work"]["id"])
            self.assertEqual(item["origin"]["step"]["id"], "develop-words")
            self.assertIn("lyric-fragments", item["sources"])

            repeated = queue_next_plan_step(song, plan)
            self.assertEqual(repeated["status"], "idle")
            self.assertEqual(repeated["reason"], "no-unstarted-actionable-step")
            self.assertEqual(len(list_work_items(song)["items"]), 1)

            complete_work(root, song, song / first["work"]["path"])
            second = queue_next_plan_step(song, plan)
            self.assertEqual(second["status"], "queued")
            self.assertEqual(second["selected_step"]["id"], "record-room-answer")
            self.assertEqual(second["selected_step"]["depends_on"], ["develop-words"])
            self.assertFalse(second["selected_step"]["gates_verified"])

    def test_queue_next_specific_step_is_conservative_and_lock_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Specific Plan Queue")
            plan = make_plan(root, song)

            blocked = queue_next_plan_step(song, plan, step_id="prepare private film")
            self.assertEqual(blocked["status"], "idle")
            self.assertEqual(blocked["reason"], "requested-step-not-unstarted-and-actionable")
            self.assertEqual(blocked["selected_step"]["dependency_state"], "blocked")
            self.assertIsNone(blocked["work"])
            with self.assertRaisesRegex(ValueError, "has no step"):
                queue_next_plan_step(song, plan, step_id="not a real step")

            work_root = song / "notes" / "work"
            lock = work_root / ".queue.lock"
            lock.write_text("simulated concurrent plan scheduler\n")
            with self.assertRaisesRegex(FileExistsError, "Work queue is locked"):
                queue_next_plan_step(song, plan)
            self.assertEqual(list_work_items(song)["items"], [])
            lock.unlink()
            self.assertEqual(queue_next_plan_step(song, plan)["status"], "queued")

    def test_queue_next_refuses_invalid_work_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Invalid Plan Queue")
            plan = make_plan(root, song)
            invalid = song / "notes" / "work" / "broken-item"
            invalid.mkdir(parents=True)
            (invalid / "work.json").write_text("{not-json")

            with self.assertRaisesRegex(ValueError, "refuses an invalid work queue"):
                queue_next_plan_step(song, plan)
            self.assertEqual(
                [path.name for path in (song / "notes" / "work").iterdir()],
                ["broken-item"],
            )

    def test_progress_unblocks_dependencies_only_after_complete_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Progress")
            plan = make_plan(root, song)

            initial = production_plan_progress(song, plan)
            self.assertEqual(initial["schema"], "eprs.production-plan-progress/v1")
            self.assertEqual(initial["state"], "not_started")
            self.assertEqual(initial["actionable_steps"], ["develop-words"])
            self.assertEqual(initial["queueable_steps"], ["develop-words"])
            self.assertEqual(initial["blocked_steps"], ["record-room-answer", "prepare-private-film"])
            self.assertFalse(initial["gates_verified"])
            self.assertIn("upload", initial["authority"]["statement"])
            status = song_status(song, verify=True)
            plan_counts = status["inventory"]["production_plans"]
            self.assertEqual(plan_counts["actionable_steps"], 1)
            self.assertEqual(plan_counts["queueable_steps"], 1)
            self.assertEqual(plan_counts["blocked_steps"], 2)
            self.assertIn("eprs plan queue-next", " ".join(status["next_actions"]))
            context = build_agent_context(song, verify=True)
            summary = context["recent_production_plans"][0]
            self.assertEqual(summary["progress"]["actionable_steps"], ["develop-words"])
            self.assertEqual(summary["progress"]["queueable_steps"], ["develop-words"])
            self.assertFalse(summary["steps"][0]["gates_verified"])
            self.assertIn("## Recent production plans", render_agent_context_markdown(context))

            first = create_work_item(
                song, None, None, None, plan=plan, plan_step="develop-words"
            )
            queued = production_plan_progress(song, plan)
            self.assertEqual(queued["state"], "in_progress")
            self.assertEqual(queued["steps"][0]["work_state"], "queued")
            self.assertIn("develop-words", queued["actionable_steps"])
            self.assertEqual(queued["queueable_steps"], [])
            self.assertIn("develop-words", queued["active_steps"])
            self.assertIn("record-room-answer", queued["blocked_steps"])

            complete_work(root, song, first)
            advanced = production_plan_progress(song, plan)
            self.assertEqual(advanced["steps"][0]["work_state"], "complete")
            self.assertEqual(advanced["complete_steps"], ["develop-words"])
            self.assertEqual(advanced["actionable_steps"], ["record-room-answer"])
            self.assertEqual(advanced["queueable_steps"], ["record-room-answer"])
            self.assertEqual(advanced["blocked_steps"], ["prepare-private-film"])
            self.assertFalse(advanced["steps"][1]["gates_verified"])
            status = song_status(song, verify=True)
            plan_counts = status["inventory"]["production_plans"]
            self.assertEqual(plan_counts["complete_steps"], 1)
            self.assertEqual(plan_counts["actionable_steps"], 1)
            self.assertEqual(plan_counts["queueable_steps"], 1)
            self.assertEqual(plan_counts["blocked_steps"], 1)

    def test_stopped_or_new_active_work_does_not_overstate_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Conservative Progress")
            plan = make_plan(root, song)
            first = create_work_item(
                song, None, None, None, plan=plan, plan_step="develop-words"
            )
            complete_work(root, song, first)

            # A new queued pass means the step is active again; an older complete
            # item must not make downstream work look ready.
            create_work_item(song, None, None, None, plan=plan, plan_step="develop-words")
            reopened = production_plan_progress(song, plan)
            self.assertEqual(reopened["steps"][0]["work_state"], "queued")
            self.assertIn("record-room-answer", reopened["blocked_steps"])

            # In a fresh plan, an explicit stop also cannot satisfy a dependency.
            another_song = new_song(root / "songs", "Stopped Progress")
            another_plan = make_plan(root / "another", another_song)
            stopped = create_work_item(
                another_song, None, None, None, plan=another_plan, plan_step="develop-words"
            )
            complete_work(root, another_song, stopped, decision="stop")
            report = production_plan_progress(another_song, another_plan)
            self.assertEqual(report["stopped_steps"], ["develop-words"])
            self.assertIn("record-room-answer", report["blocked_steps"])
            self.assertNotIn("record-room-answer", report["actionable_steps"])


if __name__ == "__main__":
    unittest.main()
