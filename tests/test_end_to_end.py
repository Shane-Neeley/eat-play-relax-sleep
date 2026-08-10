from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.dispatch import (
    accept_agent_response,
    dispatch_next_work,
    initialize_agent_response,
    write_dispatch_packet,
)
from eprs.harness import create_song_run
from eprs.plan_progress import production_plan_progress, queue_next_plan_step
from eprs.planning import accept_plan_work_result
from eprs.source_sketch import create_source_sketch, verify_source_sketch
from eprs.system import sha256, song_status
from eprs.work import load_work_item, release_work_item


def tone_wav(path: Path, frequency: float, seconds: float = 0.28) -> None:
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 0.16 * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


class PrivateMixedInputEndToEndTests(unittest.TestCase):
    def test_prompt_sources_agent_plan_and_arrangement_reach_honest_review_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guitar = root / "guitar.wav"
            family = root / "family.wav"
            spoken = root / "spoken-pocket.wav"
            lyrics = root / "lyrics.txt"
            picture = root / "color-direction.png"
            tone_wav(guitar, 196)
            tone_wav(family, 294)
            tone_wav(spoken, 98)
            lyrics.write_text("Porch light / everyone answers / leave the ending open\n")
            picture.write_bytes(b"private visual-direction evidence; not release artwork")
            original_digests = {
                path: sha256(path) for path in (guitar, family, spoken, lyrics, picture)
            }

            _, run = create_song_run(
                "Agent Room Proof",
                "A loose guitar invitation, a family answer with breath, and a spoken boom-clap pocket.",
                root=root / "songs",
                recordings=[
                    ("guitar take one", guitar),
                    ("family answer", family),
                    ("spoken pocket", spoken),
                ],
                evidence=[
                    ("lyric fragments", lyrics),
                    ("color direction", picture),
                ],
                references=["https://www.youtube.com/watch?v=research-lead"],
                preserve=["performed timing, breath, and the open cadence"],
                avoid=["automatic tuning, quantizing, and copying the reference"],
                render_visual_preview=False,
            )
            song = root / "songs" / "agent-room-proof"
            self.assertTrue(run["randomness"]["novelty"]["enforced"])
            self.assertEqual(
                {item["family"] for item in run["input_routes"]["provided"]},
                {"performed-audio", "lyrics-or-songwords", "picture"},
            )
            self.assertEqual(
                run["input_routes"]["references"][0]["family"], "youtube-reference"
            )

            sketch_path, sketch = create_source_sketch(
                song,
                "Let the guitar call twice; keep the family and spoken answers distinct and human.",
                shape="call-response",
                render_visual_preview=False,
            )
            verify_source_sketch(song, sketch_path)
            self.assertTrue(sketch["randomness"]["novelty"]["enforced"])
            self.assertEqual(sketch["arrangement"]["shape"], "call-response")
            self.assertTrue((song / "_LISTEN.wav").is_symlink())
            self.assertEqual((song / "_LISTEN.wav").resolve(), (song / sketch["paths"]["mix"]).resolve())
            self.assertFalse((song / "_WATCH.mp4").exists())
            self.assertIn("Current source-aware sketch", (song / "NOW.md").read_text())

            bundle = dispatch_next_work(song, "e2e-planning-agent")
            self.assertEqual(bundle["status"], "ready")
            self.assertEqual(
                bundle["response_contract"]["finish"]["required_result_roles"],
                ["production-plan"],
            )
            packet = write_dispatch_packet(bundle, root / "planning-dispatch.json")
            response = initialize_agent_response(packet, root / "planning-response.json")
            plan_spec = root / "agent-production-plan.json"
            plan = json.loads(
                (Path(__file__).parents[1] / "templates" / "production-plan.json").read_text()
            )
            plan["request"] = run["paths"]["request"]
            plan_spec.write_text(json.dumps(plan, indent=2) + "\n")
            response_record = json.loads(response.read_text())
            response_record.update({
                "summary": "Authored a request-bound production plan; no media was processed or approved.",
                "decision": "complete",
                "results": [{"role": "production-plan", "path": str(plan_spec)}],
            })
            response_record["actions"]["commands_run"] = [
                "read the verified dispatch packet",
                "authored one local eprs.production-plan/v2 JSON result",
            ]
            response.write_text(json.dumps(response_record, indent=2) + "\n")
            accept_agent_response(song, packet, response)

            work_id = bundle["response_contract"]["work_item"]
            _, completed_work = load_work_item(song, work_id)
            self.assertEqual(completed_work["status"], "completed")
            self.assertEqual(
                set(completed_work["runs"][0]["results"]),
                {"agent-dispatch-packet", "agent-response", "production-plan"},
            )
            _, acceptance = accept_plan_work_result(
                song, work_id, result_id="production-plan"
            )
            self.assertFalse(acceptance["authority"]["plan_executed"])
            plan_path = acceptance["recipe"]["plan"]["path"]

            queued = queue_next_plan_step(song, plan_path)
            self.assertEqual(queued["status"], "queued")
            self.assertEqual(queued["selected_step"]["id"], "document-session")
            step_bundle = dispatch_next_work(song, "session-context-agent")
            self.assertEqual(step_bundle["status"], "ready")
            self.assertTrue(step_bundle["context"]["adapter_fit"]["ready"])
            release_work_item(
                song,
                step_bundle["response_contract"]["work_item"],
                "session-context-agent",
                "Performer, setup, consent, and rights facts require real human input.",
            )
            progress = production_plan_progress(song, plan_path)
            self.assertEqual(progress["state"], "in_progress")
            self.assertFalse(progress["gates_verified"])
            self.assertIn("document-session", progress["active_steps"])

            status = song_status(song, verify=True)
            self.assertEqual(status["attention"], [])
            self.assertEqual(status["inventory"]["raw_recordings"], 3)
            self.assertEqual(status["inventory"]["source_sketches"]["pending"], 1)
            self.assertEqual(status["inventory"]["work_items"]["plan_step_items"], 1)
            self.assertEqual({path: sha256(path) for path in original_digests}, original_digests)
            self.assertEqual(
                {path.name for path in (song / "FINAL").iterdir()}, {"README.md"}
            )
            self.assertEqual(
                [path for path in (song / "FINAL").iterdir() if path.is_dir()], []
            )


if __name__ == "__main__":
    unittest.main()
