import json
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.cli import main, parser
from eprs.context import build_agent_context
from eprs.plan import create_production_plan
from eprs.system import ingest, new_song, sha256, song_status
from eprs.work import (
    claim_next_work_item,
    create_work_item,
    finish_work_item,
    list_work_items,
    load_work_item,
    promote_work_run,
    release_work_item,
    start_work_item,
)
from tests.test_plan import make_request, plan_score, v2_plan_score


class WorkItemTests(unittest.TestCase):
    def test_explicit_result_contract_is_available_without_a_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Explicit Result Contract")
            output = StringIO()

            with redirect_stdout(output):
                result = main([
                    "work", "add", "--song", str(song),
                    "--title", "Inspect one relationship",
                    "--kind", "research",
                    "--prompt", "Return one attributed observation.",
                    "--require-result", "research-record",
                ])

            self.assertEqual(result, 0)
            _, item = load_work_item(song, Path(output.getvalue().strip()))
            self.assertEqual(
                item["result_contract"]["required_roles"], ["research-record"]
            )
            note = root / "blocked.md"
            note.write_text("The source needed for attribution was unavailable.\n")
            start_work_item(song, item["id"], "research-agent")
            finish_work_item(
                song,
                item["id"],
                "Preserved the blocker without claiming completion.",
                "needs-followup",
                [("blocker-note", note)],
            )
            _, followup = load_work_item(song, item["id"])
            self.assertEqual(followup["status"], "queued")
            self.assertEqual(len(followup["runs"]), 2)

    def test_custom_request_work_does_not_assume_a_planning_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Custom Request Work")
            request_path = make_request(root, song)

            item_path = create_work_item(
                song,
                "Inspect only the room note",
                "research",
                "Return uncertainty without authoring a production plan.",
                request=request_path,
            )
            _, item = load_work_item(song, item_path)

            self.assertNotIn("result_contract", item)

    def test_cli_queues_request_origin_planning_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "CLI Request Planning")
            request_path = make_request(root, song)
            output = StringIO()

            with redirect_stdout(output):
                result = main([
                    "work", "add", "--song", str(song),
                    "--request", str(request_path),
                ])

            self.assertEqual(result, 0)
            item_path = Path(output.getvalue().strip())
            _, item = load_work_item(song, item_path)
            self.assertEqual(item["kind"], "production planning")
            self.assertEqual(
                item["result_contract"]["required_roles"], ["production-plan"]
            )
            self.assertEqual(
                item["request_origin"]["request_id"], request_path.parent.name
            )

    def test_captured_request_can_become_verified_agent_planning_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request Planning Queue")
            request_path = make_request(root, song)

            item_path = create_work_item(
                song, None, None, None, request=request_path
            )
            _, item = load_work_item(song, item_path)

            self.assertIsNone(item["origin"])
            self.assertEqual(
                item["request_origin"]["schema"],
                "eprs.production-request-work-origin/v1",
            )
            self.assertEqual(
                set(item["request_origin"]["source_map"]),
                {"lyric-fragments", "room-note"},
            )
            self.assertEqual(set(item["sources"]), {"lyric-fragments", "room-note"})
            self.assertEqual(item["kind"], "production planning")
            self.assertIn("eprs.production-plan/v2", item["prompt"])
            self.assertIn("role production-plan", item["prompt"])
            self.assertIn("Do not execute the plan", item["prompt"])
            self.assertEqual(
                item["result_contract"],
                {
                    "schema": "eprs.work-result-contract/v1",
                    "required_roles": ["production-plan"],
                    "allow_additional": True,
                    "applies_to_decision": "complete",
                },
            )

            listed = list_work_items(song)["items"][0]
            self.assertIsNone(listed["plan_origin"])
            self.assertEqual(
                listed["request_origin"]["request_id"],
                item["request_origin"]["request_id"],
            )
            self.assertEqual(listed["result_contract"], item["result_contract"])
            packet = build_agent_context(song, work=item["id"], verify=True)
            self.assertEqual(
                packet["focus"]["production_request"]["record"]["id"],
                item["request_origin"]["request_id"],
            )
            self.assertEqual(
                packet["focus"]["work"]["item"]["request_origin"]["schema"],
                "eprs.production-request-work-origin/v1",
            )
            self.assertEqual(
                packet["focus"]["work"]["item"]["result_contract"],
                item["result_contract"],
            )
            self.assertEqual(packet["attention"], [])
            status = song_status(song, verify=True)
            self.assertEqual(
                status["inventory"]["work_items"]["request_origin_items"], 1
            )
            self.assertNotIn("work add --request", " ".join(status["next_actions"]))
            args = parser().parse_args([
                "work", "add", "--song", str(song), "--request", str(request_path)
            ])
            self.assertEqual(args.request, str(request_path))
            self.assertIsNone(args.title)

            changed = json.loads(request_path.read_text())
            changed["prompt"] = "Changed after the planning task was frozen."
            request_path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "origin is missing or changed"):
                load_work_item(song, item_path)

    def test_v2_plan_step_propagates_capabilities_into_work_and_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Capability Queue")
            request = make_request(root, song)
            plan_spec = root / "plan.json"
            score = v2_plan_score(request)
            score["steps"][0]["required_result_roles"] = [
                "lyric-variants", "lyric-review"
            ]
            plan_spec.write_text(json.dumps(score))
            plan = create_production_plan(plan_spec, song)

            item_path = create_work_item(
                song, None, None, None, plan=plan, plan_step="develop-words"
            )
            _, item = load_work_item(song, item_path)

            self.assertEqual(
                item["origin"]["schema"], "eprs.production-plan-step-origin/v2"
            )
            self.assertEqual(
                item["origin"]["step"]["required_capabilities"],
                ["lyric_development"],
            )
            self.assertIn(
                "Required software capabilities: lyric_development", item["prompt"]
            )
            self.assertIn(
                "Required result roles for decision complete: lyric-variants, lyric-review",
                item["prompt"],
            )
            self.assertEqual(
                item["result_contract"]["required_roles"],
                ["lyric-variants", "lyric-review"],
            )
            listed = list_work_items(song)["items"][0]
            self.assertEqual(
                listed["plan_origin"]["required_capabilities"],
                ["lyric_development"],
            )
            self.assertEqual(
                listed["result_contract"]["required_roles"],
                ["lyric-variants", "lyric-review"],
            )
            context = build_agent_context(song, work=item["id"], verify=True)
            self.assertEqual(
                context["focus"]["work"]["item"]["origin"]["step"][
                    "required_capabilities"
                ],
                ["lyric_development"],
            )
            self.assertEqual(
                context["focus"]["work"]["item"]["origin"]["step"][
                    "required_result_roles"
                ],
                ["lyric-variants", "lyric-review"],
            )
            self.assertEqual(
                context["focus"]["work"]["item"]["result_contract"],
                item["result_contract"],
            )
            self.assertEqual(context["adapter_fit"]["schema"], "eprs.adapter-fit/v1")
            self.assertTrue(context["adapter_fit"]["ready"])

            tampered = json.loads(item_path.read_text())
            tampered.pop("result_contract")
            item_path.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(
                ValueError, "result contract does not match its production-plan step"
            ):
                load_work_item(song, item["id"])
            item_path.write_text(json.dumps(item, indent=2) + "\n")

            start_work_item(song, item["id"], "lyrics-agent")
            wrong = root / "wrong.md"
            wrong.write_text("A useful note, but not the contracted evidence.\n")
            before = sha256(item_path)
            with self.assertRaisesRegex(
                ValueError, "missing required result roles: lyric-review, lyric-variants"
            ):
                finish_work_item(
                    song,
                    item["id"],
                    "Incomplete evidence.",
                    "complete",
                    [("notes", wrong)],
                )
            self.assertEqual(sha256(item_path), before)
            self.assertFalse((item_path.parent / "runs").exists())

            variants = root / "variants.md"
            variants.write_text("Two singable variants.\n")
            review = root / "review.md"
            review.write_text("Read and sung in context.\n")
            finish_work_item(
                song,
                item["id"],
                "Returned every contracted result.",
                "complete",
                [
                    ("lyric variants", variants),
                    ("lyric review", review),
                    ("notes", wrong),
                ],
            )
            _, completed = load_work_item(song, item["id"])
            self.assertEqual(
                set(completed["runs"][0]["results"]),
                {"lyric-variants", "lyric-review", "notes"},
            )

    def test_plan_step_work_inherits_inputs_and_preserves_exact_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Step Queue")
            request = make_request(root, song)
            plan_spec = root / "plan.json"
            plan_spec.write_text(json.dumps(plan_score(request)))
            plan = create_production_plan(plan_spec, song)

            item_path = create_work_item(
                song,
                None,
                None,
                None,
                plan=plan,
                plan_step="Develop Words",
            )
            _, item = load_work_item(song, item_path)
            origin = item["origin"]
            self.assertEqual(origin["schema"], "eprs.production-plan-step-origin/v1")
            self.assertEqual(origin["step"]["id"], "develop-words")
            self.assertEqual(origin["source_map"], {"lyric-fragments": "lyric-fragments"})
            self.assertEqual(item["kind"], "lyrics")
            self.assertIn("Execute only production-plan step develop-words", item["prompt"])
            self.assertNotIn("Required software capabilities", item["prompt"])
            self.assertIn("does not satisfy those gates", item["prompt"])
            frozen = item_path.parent / item["sources"]["lyric-fragments"]["path"]
            self.assertTrue(frozen.is_file())
            self.assertEqual(sha256(frozen), item["sources"]["lyric-fragments"]["sha256"])

            listed = list_work_items(song)["items"][0]
            self.assertEqual(listed["plan_origin"]["step_id"], "develop-words")
            context = build_agent_context(song, work=item["id"], verify=True)
            focused = context["focus"]["work"]["item"]["origin"]
            self.assertEqual(focused["step"]["id"], "develop-words")
            self.assertEqual(focused["step"]["gates"], ["user-direction"])
            plan_summary = context["recent_production_plans"][0]
            self.assertEqual(plan_summary["steps"][0]["work_items"][0]["id"], item["id"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["work_items"]["plan_step_items"], 1)
            self.assertEqual(status["inventory"]["work_items"]["plan_step_completed"], 0)
            self.assertEqual(status["attention"], [])

            start_work_item(song, item["id"], "lyrics-agent")
            result = root / "variants.md"
            result.write_text("Variant A keeps the breath.\nVariant B leaves the final word open.\n")
            finish_work_item(
                song,
                item["id"],
                "Preserved two meaningful lyric variants for listening.",
                "complete",
                [("lyric variants", result)],
            )
            self.assertEqual(
                song_status(song, verify=True)["inventory"]["work_items"]["plan_step_completed"],
                1,
            )

            changed_plan = json.loads(plan.read_text())
            changed_plan["authority"]["statement"] = "Changed frozen plan evidence."
            plan.write_text(json.dumps(changed_plan))
            with self.assertRaisesRegex(ValueError, "origin is missing or changed"):
                load_work_item(song, item_path)
            drifted = song_status(song, verify=True)
            self.assertIn("production-plan verification failed", " ".join(drifted["attention"]))

    def test_plan_step_work_requires_both_coordinates_and_rejects_source_collisions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Step Guard")
            request = make_request(root, song)
            plan_spec = root / "plan.json"
            plan_spec.write_text(json.dumps(plan_score(request)))
            plan = create_production_plan(plan_spec, song)

            with self.assertRaisesRegex(ValueError, "supplied together"):
                create_work_item(song, None, None, None, plan=plan)
            with self.assertRaisesRegex(ValueError, "cannot be combined"):
                create_work_item(
                    song,
                    None,
                    None,
                    None,
                    request=request,
                    plan=plan,
                    plan_step="develop-words",
                )
            with self.assertRaisesRegex(ValueError, "has no step"):
                create_work_item(song, None, None, None, plan=plan, plan_step="missing")
            extra = root / "extra.txt"
            extra.write_text("conflicting role\n")
            with self.assertRaisesRegex(ValueError, "conflicts"):
                create_work_item(
                    song,
                    None,
                    None,
                    None,
                    plan=plan,
                    plan_step="develop-words",
                    sources=[("lyric fragments", extra)],
                )

    def test_once_work_freezes_inputs_claim_and_result_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Research Queue")
            lyric_seed = root / "lyric fragments.txt"
            lyric_seed.write_text("porch light / everybody answers\n")
            item_path = create_work_item(
                song,
                "Research call-and-response references",
                "YouTube research",
                "Find three performance ideas; describe relationships, do not copy arrangements.",
                priority=80,
                references=["family group singing", "room chimes"],
                sources=[("lyric fragments", lyric_seed)],
            )

            _, created = load_work_item(song, item_path)
            frozen_input = item_path.parent / created["sources"]["lyric-fragments"]["path"]
            self.assertEqual(frozen_input.read_text(), lyric_seed.read_text())
            lyric_seed.write_text("a later idea\n")
            self.assertNotEqual(frozen_input.read_text(), lyric_seed.read_text())

            due = list_work_items(song, due_only=True)
            self.assertEqual(due["schema"], "eprs.work-list/v1")
            self.assertEqual([item["id"] for item in due["items"]], [created["id"]])
            relative_item_path = os.path.relpath(item_path, Path.cwd())
            self.assertEqual(load_work_item(song, relative_item_path)[0], item_path.resolve())
            start_work_item(song, created["id"], "research-agent")
            self.assertEqual(
                start_work_item(song, created["id"], "research-agent").resolve(),
                item_path.resolve(),
            )
            with self.assertRaisesRegex(ValueError, "already claimed"):
                start_work_item(song, created["id"], "another-agent")

            result = root / "research.md"
            result.write_text("# Findings\n\nThree relationships with source links and confidence notes.\n")
            result_digest = sha256(result)
            finish_work_item(
                song,
                created["id"],
                "Captured three attributed reference relationships for a musical experiment.",
                "complete",
                [("research notes", result)],
            )

            _, finished = load_work_item(song, created["id"])
            self.assertEqual(finished["status"], "completed")
            self.assertIsNone(finished["schedule"]["next_due_at"])
            run = finished["runs"][0]
            frozen_result = item_path.parent / run["results"]["research-notes"]["path"]
            self.assertEqual(sha256(frozen_result), result_digest)
            result.write_text("later rewrite that must not alter run history\n")
            self.assertEqual(sha256(frozen_result), result_digest)

            experiment = promote_work_run(
                song,
                created["id"],
                "Can one chime answer the family phrase while the guitar leaves the cadence open?",
                seed=23,
            )
            experiment_manifest = json.loads((experiment / "experiment.json").read_text())
            self.assertEqual(experiment_manifest["origin"]["schema"], "eprs.work-run-origin/v1")
            self.assertEqual(experiment_manifest["origin"]["run_number"], 1)
            self.assertIn("work-request", experiment_manifest["inputs"])
            self.assertIn("work-source-lyric-fragments", experiment_manifest["inputs"])
            self.assertIn("work-result-research-notes", experiment_manifest["inputs"])

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["work_items"]["total"], 1)
            self.assertEqual(status["inventory"]["work_items"]["completed"], 1)
            self.assertEqual(status["inventory"]["work_items"]["due"], 0)
            self.assertEqual(status["inventory"]["work_items"]["promotions"], 1)
            self.assertEqual(status["attention"], [])

            frozen_result.write_text("tampered evidence\n")
            with self.assertRaisesRegex(ValueError, "checksum has changed"):
                promote_work_run(song, created["id"], "This promotion must refuse drift.")
            drifted = song_status(song, verify=True)
            self.assertIn("Checksum mismatch for result", " ".join(drifted["attention"]))

    def test_raw_recording_is_referenced_while_external_source_is_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Source-Aware Queue")
            recording = root / "voice.raw"
            recording.write_bytes(b"family voice evidence")
            raw, _ = ingest(recording, song, "family voice")
            philosophy = root / "philosophy.txt"
            philosophy.write_text("Leave room for the answer.\n")

            item_path = create_work_item(
                song,
                "Develop lyric response",
                "lyrics",
                "Write alternatives around the breath and answer, without altering the voice take.",
                sources=[("family voice", raw), ("philosophy", philosophy)],
            )
            item = json.loads(item_path.read_text())
            self.assertEqual(item["sources"]["family-voice"]["storage"], "song-reference")
            self.assertEqual(item["sources"]["philosophy"]["storage"], "work-item-copy")
            self.assertEqual(song_status(song, verify=True)["attention"], [])

    def test_daily_work_requeues_for_the_next_future_due_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Daily Practice")
            item_path = create_work_item(
                song,
                "Daily continuity brief",
                "automation",
                "Summarize new evidence and propose one narrow next experiment.",
                cadence="daily",
                due_at="2000-01-01T09:00:00Z",
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "daily-agent")
            result = root / "continuity.md"
            result.write_text("No new source media; preserve the current musical question.\n")
            finish_work_item(
                song,
                item_id,
                "Recorded the daily continuity state.",
                "complete",
                [("daily brief", result)],
            )

            _, item = load_work_item(song, item_id)
            self.assertEqual(item["status"], "queued")
            self.assertEqual(len(item["runs"]), 2)
            self.assertEqual(item["runs"][0]["status"], "completed")
            self.assertEqual(item["runs"][1]["status"], "queued")
            self.assertGreater(item["runs"][1]["due_at"], item["runs"][0]["completed_at"])
            experiment = promote_work_run(
                song,
                item_id,
                "Does the continuity note identify one musical decision worth hearing?",
                run_number=1,
            )
            promoted = json.loads((experiment / "experiment.json").read_text())
            self.assertEqual(promoted["origin"]["run_number"], 1)
            self.assertEqual(list_work_items(song, due_only=True)["items"], [])
            future = list_work_items(song, due_only=True, now="2100-01-01T00:00:00Z")
            self.assertEqual([entry["id"] for entry in future["items"]], [item_id])

    def test_work_validates_due_time_roles_and_workspace_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Queue Guard")
            source = root / "note.txt"
            source.write_text("one\n")
            with self.assertRaisesRegex(ValueError, "timezone"):
                create_work_item(song, "Bad time", "research", "Check it.", due_at="2026-08-03T09:00:00")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                create_work_item(
                    song,
                    "Duplicate roles",
                    "research",
                    "Check it.",
                    sources=[("Notes", source), ("notes", source)],
                )
            with self.assertRaisesRegex(ValueError, "portable result-role slugs"):
                create_work_item(
                    song,
                    "Bad result role",
                    "research",
                    "Check it.",
                    required_result_roles=["Research Record"],
                )
            outside = root / "outside" / "work.json"
            outside.parent.mkdir()
            outside.write_text("{}")
            with self.assertRaisesRegex(ValueError, "inside the song"):
                load_work_item(song, outside)

    def test_work_creation_does_not_leave_a_visible_partial_item(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Work")
            source = root / "source.txt"
            source.write_text("one source\n")
            with patch("eprs.work.shutil.copy2", side_effect=OSError("simulated work copy failure")):
                with self.assertRaisesRegex(OSError, "simulated work copy failure"):
                    create_work_item(
                        song,
                        "Atomic request",
                        "research",
                        "Freeze all inputs or create nothing visible.",
                        sources=[("source", source)],
                    )
            work_root = song / "notes" / "work"
            self.assertEqual(list(work_root.iterdir()), [])

    def test_work_finish_copy_failure_leaves_claim_and_results_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Work Result")
            item_path = create_work_item(
                song, "Return one result", "automation", "Write one local result."
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "result-agent")
            result = root / "result.md"
            result.write_text("One complete result.\n")
            before = sha256(item_path)
            with patch("eprs.work.shutil.copy2", side_effect=OSError("simulated result copy failure")):
                with self.assertRaisesRegex(OSError, "simulated result copy failure"):
                    finish_work_item(
                        song, item_id, "Completed locally.", "complete", [("result", result)]
                    )
            self.assertEqual(sha256(item_path), before)
            self.assertEqual(load_work_item(song, item_id)[1]["status"], "in_progress")
            self.assertFalse((item_path.parent / "runs").exists())

    def test_existing_claim_lock_prevents_concurrent_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Claim Lock")
            item_path = create_work_item(song, "One owner", "research", "Claim this once.")
            lock = item_path.parent / ".work.lock"
            lock.write_text("simulated concurrent worker\n")
            with self.assertRaisesRegex(FileExistsError, "locked by another process"):
                start_work_item(song, item_path, "second-agent")
            self.assertEqual(json.loads(item_path.read_text())["status"], "queued")
            lock.unlink()
            start_work_item(song, item_path, "second-agent")
            self.assertEqual(json.loads(item_path.read_text())["status"], "in_progress")

    def test_claim_next_orders_due_work_and_release_preserves_attempt_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Atomic Daily Queue")
            due = "2000-01-01T09:00:00Z"
            low = create_work_item(
                song, "Low research", "research", "Wait behind higher priority work.",
                priority=10, due_at=due,
            )
            high = create_work_item(
                song, "High research", "research", "Claim this research first.",
                priority=90, due_at=due,
            )
            lyrics = create_work_item(
                song, "Lyric pass", "lyrics", "Keep variants and preserve the breath.",
                priority=50, due_at=due,
            )
            low_id = json.loads(low.read_text())["id"]
            high_id = json.loads(high.read_text())["id"]
            lyrics_id = json.loads(lyrics.read_text())["id"]

            lyric_claim = claim_next_work_item(song, "lyric-agent", kind="LYRICS")
            self.assertEqual(lyric_claim["schema"], "eprs.work-claim/v1")
            self.assertEqual(lyric_claim["claimed"]["id"], lyrics_id)
            high_claim = claim_next_work_item(song, "research-agent")
            self.assertEqual(high_claim["claimed"]["id"], high_id)

            with self.assertRaisesRegex(ValueError, "owned by"):
                release_work_item(song, high_id, "other-agent", "Wrong owner must not release.")
            release_work_item(song, high_id, "research-agent", "Runner lost its local tool session.")
            self.assertEqual(
                release_work_item(song, high_id, "research-agent", "Runner lost its local tool session.").resolve(),
                high.resolve(),
            )

            reclaimed = claim_next_work_item(song, "recovery-agent")
            self.assertEqual(reclaimed["claimed"]["id"], high_id)
            _, high_item = load_work_item(song, high_id)
            claims = high_item["runs"][0]["claims"]
            self.assertEqual(len(claims), 2)
            self.assertEqual(claims[0]["release_note"], "Runner lost its local tool session.")
            self.assertIsNotNone(claims[0]["released_at"])
            self.assertIsNone(claims[1]["released_at"])

            result = root / "recovered.md"
            result.write_text("Recovered the research task without changing its prompt.\n")
            finish_work_item(
                song,
                high_id,
                "Completed after a preserved release and reclaim.",
                "complete",
                [("research result", result)],
            )
            _, completed = load_work_item(song, high_id)
            self.assertIsNotNone(completed["runs"][0]["claims"][1]["completed_at"])
            next_claim = claim_next_work_item(song, "remaining-agent")
            self.assertEqual(next_claim["claimed"]["id"], low_id)
            none_left = claim_next_work_item(song, "idle-agent", kind="research")
            self.assertIsNone(none_left["claimed"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["work_items"]["released_claims"], 1)
            self.assertEqual(status["attention"], [])

    def test_queue_lock_prevents_two_claim_next_transactions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Queue Lock")
            item = create_work_item(song, "Due request", "research", "Claim safely.")
            lock = song / "notes" / "work" / ".queue.lock"
            lock.write_text("simulated queue transaction\n")
            with self.assertRaisesRegex(FileExistsError, "Work queue is locked"):
                claim_next_work_item(song, "second-runner")
            self.assertEqual(json.loads(item.read_text())["status"], "queued")
            lock.unlink()
            report = claim_next_work_item(song, "second-runner")
            self.assertIsNotNone(report["claimed"])

    def test_work_list_reports_one_invalid_item_without_hiding_valid_due_work(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Resilient Queue")
            valid = create_work_item(song, "Valid request", "research", "Keep this visible.")
            invalid_dir = song / "notes" / "work" / "broken-request"
            invalid_dir.mkdir()
            (invalid_dir / "work.json").write_text("{not-json")

            report = list_work_items(song, due_only=True)
            self.assertEqual([entry["id"] for entry in report["items"]], [json.loads(valid.read_text())["id"]])
            self.assertEqual(report["errors"][0]["id"], "broken-request")


if __name__ == "__main__":
    unittest.main()
