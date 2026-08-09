import json
from pathlib import Path
import tempfile
import unittest

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.plan import create_production_plan, load_production_plan
from eprs.request import create_production_request
from eprs.system import new_song, sha256, song_status


def make_request(root: Path, song: Path) -> Path:
    lyrics = root / "lyrics.txt"
    lyrics.write_text("Porch light / everyone answers / leave the ending open\n")
    note = root / "room-note.txt"
    note.write_text("The room decay belongs after the family breath.\n")
    spec = root / "request.json"
    spec.write_text(json.dumps({
        "schema": "eprs.production-request/v1",
        "title": "Family room song",
        "prompt": "Build from the supplied writing and room idea, then leave space for performances.",
        "intended_experience": "An invitation, a shared answer, and enough room to hear real people breathe.",
        "preserve": ["Human breath and an open cadence"],
        "avoid": ["Copying references or silently polishing performances"],
        "questions": ["What is the smallest first musical test?"],
        "deliverables": ["A reviewed listening film and local handoff package"],
        "references": ["Call and response as a relationship"],
        "provided": [{
            "id": "lyric-fragments",
            "role": "lyric ideas",
            "kind": "writing",
            "handling": "frozen-evidence",
            "path": str(lyrics),
            "note": "Keep variants.",
            "rights_note": "Original private project writing; public wording is not approved.",
        }, {
            "id": "room-note",
            "role": "room intent",
            "kind": "philosophy",
            "handling": "frozen-evidence",
            "path": str(note),
            "note": "Treat this as intent, not processing instructions.",
            "rights_note": "Private project note.",
        }],
    }))
    return create_production_request(spec, song)


def plan_score(request: Path) -> dict:
    return {
        "schema": "eprs.production-plan/v1",
        "title": "First path from prompt to listening film",
        "request": str(request),
        "north_star": "Let original performances carry the song; agents expose choices and preserve uncertainty.",
        "assumptions": ["No public sharing is authorized."],
        "open_questions": ["Who will perform the guitar invitation and family answer?"],
        "steps": [{
            "id": "Develop Words",
            "kind": "lyrics",
            "intent": "Develop several singable answer variants without erasing the supplied fragments.",
            "depends_on": [],
            "uses": ["lyric-fragments"],
            "smallest_action": "Queue one lyric-variant pass and preserve every meaningful alternative.",
            "outputs": ["Versioned lyric variants"],
            "done_when": ["Variants retain source wording and identify unresolved choices"],
            "listening_question": "Which words leave enough breath for a group response?",
            "gates": ["user-direction"],
        }, {
            "id": "record-room-answer",
            "kind": "recording",
            "intent": "Capture the invitation, answer, and room as a documented session.",
            "depends_on": ["develop words"],
            "uses": ["room-note"],
            "smallest_action": "Record one invitation, one family answer, and room tone without printed processing.",
            "outputs": ["Immutable takes", "Recording-session record"],
            "done_when": ["Every take has performer, setup, consent, and rights context"],
            "listening_question": "Does the response feel shared while individual timing remains audible?",
            "gates": ["performer-consent", "source-rights", "listening-decision"],
        }, {
            "id": "prepare-private-film",
            "kind": "delivery",
            "intent": "Prepare a reviewed private listening film and local handoff package.",
            "depends_on": ["record-room-answer"],
            "uses": [],
            "smallest_action": "Render from an approved master, watch end to end, and package locally.",
            "outputs": ["Reviewed video", "Local FINAL package"],
            "done_when": ["Picture and sync are reviewed", "Credits and clearance match proposed visibility"],
            "listening_question": "Does the film preserve the approved song and room decay?",
            "gates": ["listening-decision", "technical-verification", "performer-consent"],
        }],
    }


def v2_plan_score(request: Path) -> dict:
    score = plan_score(request)
    score["schema"] = "eprs.production-plan/v2"
    for step, capabilities in zip(
        score["steps"],
        (["lyric_development"], ["recording_session_intake"], []),
    ):
        step["required_capabilities"] = capabilities
    return score


class ProductionPlanTests(unittest.TestCase):
    def test_v2_template_declares_result_roles_for_every_step(self):
        template = json.loads(
            (Path(__file__).parents[1] / "templates" / "production-plan.json").read_text()
        )

        self.assertEqual(template["schema"], "eprs.production-plan/v2")
        self.assertTrue(template["steps"])
        for step in template["steps"]:
            roles = step.get("required_result_roles")
            self.assertIsInstance(roles, list, step["id"])
            self.assertTrue(roles, step["id"])
            self.assertEqual(len(roles), len(set(roles)), step["id"])

    def test_v2_plan_can_freeze_machine_enforced_result_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Result Role Plan")
            request = make_request(root, song)
            spec = root / "plan.json"
            score = v2_plan_score(request)
            score["steps"][0]["required_result_roles"] = [
                "lyric-variants", "lyric-review"
            ]
            spec.write_text(json.dumps(score))

            path = create_production_plan(spec, song)
            _, record = load_production_plan(song, path)

            self.assertEqual(
                record["recipe"]["steps"][0]["required_result_roles"],
                ["lyric-variants", "lyric-review"],
            )
            packet = build_agent_context(song, verify=True)
            self.assertEqual(
                packet["recent_production_plans"][0]["steps"][0][
                    "required_result_roles"
                ],
                ["lyric-variants", "lyric-review"],
            )

            score["steps"][0]["required_result_roles"] = ["Lyric Variants"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "portable result-role slugs"):
                create_production_plan(spec, song)

            score = v2_plan_score(request)
            score["steps"][0]["required_result_roles"] = ["notes", "notes"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "must not contain duplicates"):
                create_production_plan(spec, song)

            score = v2_plan_score(request)
            score["steps"][0]["required_result_roles"] = []
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "must be a non-empty list"):
                create_production_plan(spec, song)

            score = plan_score(request)
            score["steps"][0]["required_result_roles"] = ["lyric-variants"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "requires eprs.production-plan/v2"):
                create_production_plan(spec, song)

    def test_v2_plan_freezes_explicit_capability_requirements(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Capability Plan")
            request = make_request(root, song)
            spec = root / "plan.json"
            score = v2_plan_score(request)
            spec.write_text(json.dumps(score))

            path = create_production_plan(spec, song)
            _, record = load_production_plan(song, path)

            self.assertEqual(record["schema"], "eprs.production-plan-record/v2")
            self.assertEqual(
                record["recipe"]["steps"][0]["required_capabilities"],
                ["lyric_development"],
            )
            self.assertEqual(record["recipe"]["steps"][2]["required_capabilities"], [])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["production_plans"]["invalid"], 0)
            packet = build_agent_context(song, verify=True)
            self.assertEqual(
                packet["recent_production_plans"][0]["steps"][0][
                    "required_capabilities"
                ],
                ["lyric_development"],
            )

            score["steps"][0]["required_capabilities"] = ["Lyric Development"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "portable capability slugs"):
                create_production_plan(spec, song)

            score = v2_plan_score(request)
            score["steps"][0]["required_capabilities"] = [
                "lyric_development", "lyric_development"
            ]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "must not contain duplicates"):
                create_production_plan(spec, song)

            score = plan_score(request)
            score["steps"][0]["required_capabilities"] = []
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "requires eprs.production-plan/v2"):
                create_production_plan(spec, song)

    def test_plan_is_deterministic_request_bound_and_dependency_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Planned Song")
            request = make_request(root, song)
            request_before = sha256(request)
            spec = root / "plan.json"
            spec.write_text(json.dumps(plan_score(request)))

            path = create_production_plan(spec, song)
            _, record = load_production_plan(song, path)

            self.assertEqual(record["schema"], "eprs.production-plan-record/v1")
            self.assertEqual(record["recipe"]["request"]["sha256"], request_before)
            self.assertEqual(record["entry_steps"], ["develop-words"])
            self.assertEqual(record["recipe"]["steps"][1]["depends_on"], ["develop-words"])
            self.assertEqual(create_production_plan(spec, song).resolve(), path.resolve())
            self.assertEqual(sha256(request), request_before)

            status = song_status(song, verify=True)
            counts = status["inventory"]["production_plans"]
            self.assertEqual(counts["total"], 1)
            self.assertEqual(counts["steps"], 3)
            self.assertEqual(counts["entry_steps"], 1)
            self.assertEqual(counts["gated_steps"], 3)
            self.assertEqual(counts["invalid"], 0)
            self.assertIn("actionable production-plan", " ".join(status["next_actions"]))

            packet = build_agent_context(song, verify=True)
            summary = packet["recent_production_plans"][0]
            self.assertEqual(summary["entry_steps"], ["develop-words"])
            self.assertTrue(summary["steps"][0]["entry_step"])
            self.assertIn("user-direction", summary["steps"][0]["gates"])
            self.assertIn("## Recent production plans", render_agent_context_markdown(packet))
            self.assertEqual(packet["attention"], [])

    def test_plan_rejects_unknown_inputs_cycles_and_unsupported_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Guard")
            request = make_request(root, song)
            score = plan_score(request)
            spec = root / "plan.json"

            score["steps"][0]["uses"] = ["missing-take"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "unknown request inputs"):
                create_production_plan(spec, song)

            score = plan_score(request)
            score["steps"][0]["depends_on"] = ["prepare-private-film"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "contain a cycle"):
                create_production_plan(spec, song)

            score = plan_score(request)
            score["steps"][0]["gates"] = ["automatic-approval"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "unsupported gates"):
                create_production_plan(spec, song)

    def test_plan_detects_request_drift_and_can_supersede_same_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Revised Plan")
            request = make_request(root, song)
            spec = root / "plan.json"
            score = plan_score(request)
            spec.write_text(json.dumps(score))
            first = create_production_plan(spec, song)

            score["title"] = "Second path from prompt to listening film"
            score["supersedes"] = str(first)
            score["open_questions"].append("Should the chime appear only after the answer?")
            spec.write_text(json.dumps(score))
            second = create_production_plan(spec, song)
            _, revised = load_production_plan(song, second)
            self.assertEqual(revised["recipe"]["supersedes"]["plan_id"], json.loads(first.read_text())["plan_id"])

            changed = json.loads(request.read_text())
            changed["prompt"] = "Changed after plan capture."
            request.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "request evidence is missing or changed"):
                load_production_plan(song, first)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["production_plans"]["invalid"], 2)
            self.assertIn("Production plan verification failed", " ".join(status["attention"]))

    def test_plan_resolution_stays_inside_the_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Plan Boundary")
            outside = root / "outside" / "plan.json"
            outside.parent.mkdir()
            outside.write_text("{}")
            with self.assertRaisesRegex(ValueError, "inside the song"):
                load_production_plan(song, outside)

    def test_plan_context_respects_the_cumulative_text_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Bounded Plan")
            request = make_request(root, song)
            score = plan_score(request)
            large = "private planning detail " * 300
            score["north_star"] = large
            score["open_questions"] = [large]
            score["steps"][0]["intent"] = large
            spec = root / "plan.json"
            spec.write_text(json.dumps(score))
            create_production_plan(spec, song)

            packet = build_agent_context(song, max_text_bytes=1024)
            self.assertLessEqual(packet["limits"]["text_bytes_used"], 1024)
            self.assertNotIn(large, json.dumps(packet))
            summary = packet["recent_production_plans"][0]
            self.assertTrue(summary["north_star_truncated"])


if __name__ == "__main__":
    unittest.main()
