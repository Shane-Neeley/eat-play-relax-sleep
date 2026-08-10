import json
from pathlib import Path
import tempfile
import unittest

from eprs.cli import parser
from eprs.dispatch import (
    accept_agent_response,
    dispatch_next_work,
    initialize_agent_response,
    write_dispatch_packet,
)
from eprs.plan import create_production_plan
from eprs.system import new_song, sha256
from eprs.work import create_work_item, load_work_item
from tests.test_plan import make_request, v2_plan_score


class AgentDispatchTests(unittest.TestCase):
    def test_cli_exposes_packet_permission_response_and_accept_commands(self):
        next_args = parser().parse_args([
            "dispatch", "next", "--song", "songs/example", "--agent", "runner",
            "--allow-network-research", "--out", "/tmp/packet.json",
        ])
        self.assertTrue(next_args.allow_network_research)
        self.assertEqual(next_args.out, "/tmp/packet.json")
        init_args = parser().parse_args([
            "dispatch", "response-init", "--packet", "/tmp/packet.json",
            "--out", "/tmp/response.json",
        ])
        self.assertEqual(init_args.dispatch_command, "response-init")
        accept_args = parser().parse_args([
            "dispatch", "accept", "/tmp/response.json", "--packet",
            "/tmp/packet.json", "--song", "songs/example",
        ])
        self.assertEqual(accept_args.dispatch_command, "accept")

    @staticmethod
    def _response(packet: Path, bundle: dict, **action_overrides) -> dict:
        actions = {
            "network_accessed": False,
            "raw_recordings_modified": False,
            "remote_state_changed": False,
            "uploaded_published_or_sent": False,
            "local_audio_processed": False,
            "listening_performed": False,
            "commands_run": ["wrote one bounded local result"],
        }
        actions.update(action_overrides)
        contract = bundle["response_contract"]
        return {
            "schema": "eprs.agent-response/v1",
            "dispatch": {
                "packet_sha256": sha256(packet),
                "work_item": contract["work_item"],
                "run_number": contract["run_number"],
                "agent": contract["agent"],
            },
            "summary": "Prepared one bounded continuity observation.",
            "decision": "complete",
            "actions": actions,
            "results": [{"role": "continuity-note", "path": "continuity.md"}],
        }

    def test_packet_response_roundtrip_freezes_both_sides_and_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Agent Protocol")
            item_path = create_work_item(
                song,
                "Prepare one local observation",
                "automation",
                "Write one bounded note without browsing, processing audio, or publishing.",
            )
            item_id = json.loads(item_path.read_text())["id"]
            bundle = dispatch_next_work(song, "protocol-agent")
            packet = write_dispatch_packet(bundle, root / "dispatch.json")
            result = root / "continuity.md"
            result.write_text("The family answer needs one more breath.\n")
            response = initialize_agent_response(packet, root / "response.json")
            initialized = json.loads(response.read_text())
            self.assertEqual(
                initialized["dispatch"], self._response(packet, bundle)["dispatch"]
            )
            with self.assertRaisesRegex(ValueError, "placeholder"):
                accept_agent_response(song, packet, response)
            response.write_text(json.dumps(self._response(packet, bundle), indent=2))

            accepted = accept_agent_response(song, packet, response)

            self.assertEqual(accepted.resolve(), item_path.resolve())
            _, item = load_work_item(song, item_id)
            self.assertEqual(item["status"], "completed")
            run = item["runs"][-1]
            self.assertEqual(run["decision"], "complete")
            self.assertEqual(
                set(run["results"]),
                {"agent-dispatch-packet", "agent-response", "continuity-note"},
            )
            self.assertIsNotNone(run["claims"][0]["completed_at"])
            for record in run["results"].values():
                frozen = item_path.parent / record["path"]
                self.assertTrue(frozen.is_file())
                self.assertEqual(record["sha256"], sha256(frozen))

    def test_response_refuses_undeclared_or_drifted_execution_before_freezing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Agent Protocol Refusal")
            item_path = create_work_item(
                song, "Local only", "research", "Use only local supplied evidence."
            )
            item_id = json.loads(item_path.read_text())["id"]
            bundle = dispatch_next_work(song, "protocol-agent")
            packet = write_dispatch_packet(bundle, root / "dispatch.json")
            (root / "continuity.md").write_text("One local observation.\n")
            response = root / "response.json"
            response.write_text(json.dumps(self._response(
                packet, bundle, network_accessed=True
            )))

            with self.assertRaisesRegex(ValueError, "network access"):
                accept_agent_response(song, packet, response)
            self.assertEqual(load_work_item(song, item_id)[1]["status"], "in_progress")
            self.assertFalse((item_path.parent / "runs").exists())

            allowed_bundle = dict(bundle)
            allowed_bundle["authority"] = {
                **bundle["authority"],
                "permissions": {
                    **bundle["authority"]["permissions"],
                    "network_research": True,
                },
            }
            allowed_packet = write_dispatch_packet(allowed_bundle, root / "network-dispatch.json")
            allowed_response = self._response(
                allowed_packet, allowed_bundle, raw_recordings_modified=True
            )
            response.write_text(json.dumps(allowed_response))
            with self.assertRaisesRegex(ValueError, "immutable raw"):
                accept_agent_response(song, allowed_packet, response)

            changed = json.loads(item_path.read_text())
            changed["prompt"] = "Changed after dispatch."
            item_path.write_text(json.dumps(changed, indent=2) + "\n")
            allowed_response["actions"]["raw_recordings_modified"] = False
            response.write_text(json.dumps(allowed_response))
            with self.assertRaisesRegex(ValueError, "changed after"):
                accept_agent_response(song, allowed_packet, response)
            self.assertFalse((item_path.parent / "runs").exists())

    def test_dispatch_can_explicitly_permit_read_only_network_research(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder), "Network Research Packet")
            create_work_item(
                song, "Research one reference", "research", "Read and attribute one source."
            )
            bundle = dispatch_next_work(
                song, "research-agent", allow_network_research=True
            )
            self.assertTrue(bundle["authority"]["permissions"]["network_research"])
            self.assertNotIn("network access or browsing", bundle["authority"]["does_not_authorize"])
            self.assertIn("read-only network research", bundle["authority"]["statement"])

    def test_agent_response_cannot_bypass_required_result_roles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Required Agent Evidence")
            item_path = create_work_item(
                song,
                "Return a plan",
                "planning",
                "Return the exact required plan evidence.",
                required_result_roles=["production-plan"],
            )
            bundle = dispatch_next_work(song, "planning-agent")
            packet = write_dispatch_packet(bundle, root / "dispatch.json")
            (root / "continuity.md").write_text("Not a production plan.\n")
            response = root / "response.json"
            response.write_text(json.dumps(self._response(packet, bundle)))

            with self.assertRaisesRegex(ValueError, "missing required result roles"):
                accept_agent_response(song, packet, response)
            self.assertEqual(load_work_item(song, item_path)[1]["status"], "in_progress")
            self.assertFalse((item_path.parent / "runs").exists())

    def test_request_origin_dispatch_includes_exact_prompt_and_supplied_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request Planning Dispatch")
            request_path = make_request(root, song)
            item_path = create_work_item(
                song, None, None, None, request=request_path
            )
            item_id = json.loads(item_path.read_text())["id"]

            bundle = dispatch_next_work(song, "planning-agent")

            self.assertEqual(bundle["status"], "ready")
            self.assertEqual(bundle["claim"]["claimed"]["id"], item_id)
            focused_request = bundle["context"]["focus"]["production_request"]["record"]
            self.assertEqual(focused_request["title"], "Family room song")
            self.assertEqual(
                set(focused_request["provided"]), {"lyric-fragments", "room-note"}
            )
            self.assertEqual(
                {item["id"] for item in focused_request["input_routes"]["provided"]},
                {"lyric-fragments", "room-note"},
            )
            self.assertIn(
                "does not execute", focused_request["input_routes"]["authority"]
            )
            self.assertEqual(
                bundle["context"]["focus"]["work"]["item"]["request_origin"][
                    "schema"
                ],
                "eprs.production-request-work-origin/v1",
            )
            self.assertIsNone(bundle["context"]["adapter_fit"])
            self.assertEqual(bundle["response_contract"]["work_item"], item_id)
            self.assertEqual(
                bundle["response_contract"]["finish"]["required_result_roles"],
                ["production-plan"],
            )
            self.assertEqual(
                bundle["response_contract"]["finish"][
                    "required_result_roles_apply_to_decision"
                ],
                "complete",
            )

    def test_plan_capabilities_gate_dispatch_but_missing_guidance_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Capability Dispatch")
            request = make_request(root, song)
            score = v2_plan_score(request)
            score["steps"][0]["required_capabilities"] = ["song_workspace"]
            score["steps"][0]["required_result_roles"] = ["lyric-variants"]
            spec = root / "plan.json"
            spec.write_text(json.dumps(score))
            plan = create_production_plan(spec, song)
            ready_path = create_work_item(
                song, None, None, None, plan=plan, plan_step="develop-words"
            )
            ready_id = json.loads(ready_path.read_text())["id"]

            ready = dispatch_next_work(song, "plan-agent")
            self.assertEqual(ready["status"], "ready")
            self.assertEqual(ready["claim"]["claimed"]["id"], ready_id)
            self.assertTrue(ready["context"]["adapter_fit"]["ready"])
            self.assertFalse(ready["context"]["adapter_fit"]["guidance_complete"])
            self.assertEqual(
                ready["response_contract"]["finish"]["required_result_roles"],
                ["lyric-variants"],
            )

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Unknown Capability Dispatch")
            request = make_request(root, song)
            score = v2_plan_score(request)
            score["steps"][0]["required_capabilities"] = ["future-studio-control"]
            spec = root / "plan.json"
            spec.write_text(json.dumps(score))
            plan = create_production_plan(spec, song)
            item_path = create_work_item(
                song, None, None, None, plan=plan, plan_step="develop-words"
            )
            item_id = json.loads(item_path.read_text())["id"]

            released = dispatch_next_work(song, "plan-agent")
            self.assertEqual(released["status"], "released")
            self.assertIn("required software capabilities unavailable", released["release"]["reason"])
            self.assertIn("future-studio-control", released["release"]["reason"])
            self.assertIsNone(released["response_contract"])
            _, item = load_work_item(song, item_id)
            self.assertEqual(item["status"], "queued")
            self.assertIsNotNone(item["runs"][-1]["claims"][0]["released_at"])

    def test_empty_queue_returns_idle_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder), "Quiet Scheduler")

            bundle = dispatch_next_work(song, "daily-agent")

            self.assertEqual(bundle["schema"], "eprs.agent-dispatch/v1")
            self.assertEqual(bundle["status"], "idle")
            self.assertIsNone(bundle["claim"]["claimed"])
            self.assertIsNone(bundle["context"])
            self.assertIsNone(bundle["release"])
            self.assertFalse((song / "notes" / "work").exists())

    def test_due_work_is_claimed_with_verified_bounded_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Daily Listening Notes")
            source = root / "idea.txt"
            source.write_text("The family phrase leaves one breath before the chime.\n")
            item_path = create_work_item(
                song,
                "Prepare one continuity observation",
                "automation",
                "Describe one relationship to audition; do not process or publish anything.",
                cadence="daily",
                sources=[("verbal note", source)],
            )
            item_id = json.loads(item_path.read_text())["id"]

            bundle = dispatch_next_work(
                song,
                "daily-agent",
                kind="AUTOMATION",
                max_text_bytes=4096,
            )

            self.assertEqual(bundle["status"], "ready")
            self.assertEqual(bundle["claim"]["claimed"]["id"], item_id)
            self.assertTrue(bundle["context"]["workspace"]["checksums_verified"])
            self.assertEqual(bundle["context"]["attention"], [])
            self.assertLessEqual(bundle["context"]["limits"]["text_bytes_used"], 4096)
            self.assertEqual(bundle["response_contract"]["work_item"], item_id)
            self.assertIn("work finish", bundle["response_contract"]["finish"]["command"])
            self.assertEqual(
                bundle["response_contract"]["finish"]["required_result_roles"], []
            )
            self.assertIn("does not launch an agent", bundle["authority"]["statement"])
            self.assertIn("uploading, publishing, sending, or remote control", bundle["authority"]["does_not_authorize"])

            _, claimed = load_work_item(song, item_id)
            self.assertEqual(claimed["status"], "in_progress")
            self.assertEqual(claimed["runs"][-1]["agent"], "daily-agent")
            self.assertIsNone(dispatch_next_work(song, "another-agent")["claim"]["claimed"])

    def test_missing_frozen_evidence_releases_claim_with_attempt_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Broken Preparation")
            source = root / "reference.txt"
            source.write_text("A local reference that should be frozen.\n")
            item_path = create_work_item(
                song,
                "Inspect a local reference",
                "research",
                "Read only the supplied reference and report uncertainty.",
                sources=[("reference", source)],
            )
            _, item = load_work_item(song, item_path)
            frozen = item_path.parent / item["sources"]["reference"]["path"]
            frozen.unlink()

            bundle = dispatch_next_work(song, "research-agent")

            self.assertEqual(bundle["status"], "released")
            self.assertIsNone(bundle["context"])
            self.assertIn("FileNotFoundError", bundle["release"]["reason"])
            self.assertEqual(bundle["release"]["work_status"], "queued")
            self.assertIsNone(bundle["response_contract"])

            _, released = load_work_item(song, item["id"])
            run = released["runs"][-1]
            self.assertEqual(released["status"], "queued")
            self.assertIsNone(run["agent"])
            self.assertIsNotNone(run["claims"][0]["released_at"])
            self.assertEqual(run["claims"][0]["release_note"], bundle["release"]["reason"])

    def test_checksum_attention_returns_context_and_releases_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Drifted Preparation")
            source = root / "reference.txt"
            source.write_text("Original observation.\n")
            item_path = create_work_item(
                song,
                "Inspect a changed reference",
                "research",
                "Use only checksum-verified evidence.",
                sources=[("reference", source)],
            )
            _, item = load_work_item(song, item_path)
            frozen = item_path.parent / item["sources"]["reference"]["path"]
            frozen.write_text("Changed after capture.\n")

            bundle = dispatch_next_work(song, "research-agent")

            self.assertEqual(bundle["status"], "released")
            self.assertIsNotNone(bundle["context"])
            self.assertIn("Checksum mismatch", " ".join(bundle["context"]["attention"]))
            self.assertIn("requires attention", bundle["release"]["reason"])
            self.assertEqual(load_work_item(song, item["id"])[1]["status"], "queued")

    def test_invalid_context_budget_also_releases_the_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder), "Invalid Dispatch Budget")
            item_path = create_work_item(
                song,
                "Prepare a note",
                "automation",
                "Prepare one local note.",
            )
            item_id = json.loads(item_path.read_text())["id"]

            bundle = dispatch_next_work(song, "daily-agent", max_text_bytes=100)

            self.assertEqual(bundle["status"], "released")
            self.assertIn("ValueError", bundle["release"]["reason"])
            self.assertEqual(load_work_item(song, item_id)[1]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
