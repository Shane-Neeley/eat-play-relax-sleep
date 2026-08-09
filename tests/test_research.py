import json
from pathlib import Path
import tempfile
import unittest

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.research import create_research_record, load_research_record
from eprs.system import new_song, sha256, song_status
from eprs.work import create_work_item, finish_work_item, start_work_item


def research_score(evidence: Path | None = None) -> dict:
    sources = [{
        "id": "porch-video",
        "kind": "youtube",
        "title": "Attributed performance reference",
        "creator": "Example ensemble",
        "locator": "https://www.youtube.com/watch?v=example",
        "published_at": "Publication date not confirmed",
        "accessed_at": "2026-08-03",
        "rights_note": "Reference for private analysis only; no audio, lyrics, melody, or arrangement copied.",
        "note": "Listen for relationships, not content to imitate.",
    }]
    if evidence is not None:
        sources.append({
            "id": "room-notes",
            "kind": "local-file",
            "title": "Room listening notes",
            "creator": "Project team",
            "locator": "Private project evidence",
            "published_at": "",
            "accessed_at": "2026-08-03",
            "rights_note": "Private project evidence; do not publish.",
            "note": "A firsthand note, not an external authority.",
            "evidence_path": str(evidence),
        })
    return {
        "schema": "eprs.research/v1",
        "title": "Room response relationships",
        "question": "How can a group answer feel communal while leaving the invitation open?",
        "musical_purpose": "Inform one sparse call-and-response experiment for guitar, voices, and chime.",
        "researched_at": "2026-08-03",
        "sources": sources,
        "findings": [{
            "id": "shared-entry",
            "kind": "observation",
            "statement": "Several voices enter as one response while their individual attacks remain audible.",
            "source_ids": ["porch-video"],
            "confidence": "direct",
            "musical_consequence": "Try a shared family entrance without aligning or tightening the individual voices.",
            "copying_boundary": "Use only the relationship of shared entry and independent timing; do not reproduce notes, words, rhythm, harmony, or arrangement.",
        }, {
            "id": "open-cadence",
            "kind": "interpretation",
            "statement": "The response may feel inviting because the preceding gesture does not sound fully closed.",
            "source_ids": ["porch-video"],
            "confidence": "tentative",
            "musical_consequence": "Test a guitar ending with space before the family answer.",
            "copying_boundary": "Invent an original guitar gesture and answer; retain only the abstract question of openness.",
        }, {
            "id": "chime-space",
            "kind": "open-question",
            "statement": "Could a single chime extend the released breath without becoming a cue?",
            "source_ids": [],
            "confidence": "unknown",
            "musical_consequence": "Place one optional chime after the response and compare it with silence.",
            "copying_boundary": "Derive the chime placement from this song's performance, not from a reference arrangement.",
        }],
        "experiments": [{
            "id": "one-chime-or-silence",
            "finding_ids": ["open-cadence", "chime-space"],
            "hypothesis": "One late chime can extend the family breath without closing the guitar invitation.",
            "smallest_test": "Render two otherwise identical eight-bar versions: silence versus one chime after the response.",
            "listening_question": "Does the chime preserve the invitation, or does silence leave more human space?",
        }],
    }


class ResearchRecordTests(unittest.TestCase):
    def test_research_is_deterministic_attributed_and_freezes_local_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Research Evidence")
            evidence = root / "room.txt"
            evidence.write_text("The room decay overlaps the first breath.\n")
            evidence_before = sha256(evidence)
            spec = root / "research.json"
            spec.write_text(json.dumps(research_score(evidence)))

            path = create_research_record(spec, song)
            _, record = load_research_record(song, path)

            self.assertEqual(record["schema"], "eprs.research-record/v1")
            self.assertEqual(record["recipe"]["findings"][0]["kind"], "observation")
            self.assertEqual(record["recipe"]["findings"][1]["kind"], "interpretation")
            self.assertEqual(record["recipe"]["findings"][2]["source_ids"], [])
            frozen = path.parent / record["sources"]["room-notes"]["evidence_path"]
            self.assertEqual(sha256(frozen), evidence_before)
            self.assertEqual(sha256(evidence), evidence_before)
            self.assertEqual(create_research_record(spec, song).resolve(), path.resolve())

            status = song_status(song, verify=True)
            counts = status["inventory"]["research_records"]
            self.assertEqual(counts["total"], 1)
            self.assertEqual(counts["sources"], 2)
            self.assertEqual(counts["findings"], 3)
            self.assertEqual(counts["experiments"], 1)
            self.assertEqual(counts["invalid"], 0)
            self.assertIn("smallest audible test", " ".join(status["next_actions"]))

            packet = build_agent_context(song, verify=True)
            summary = packet["recent_research"][0]
            self.assertEqual(summary["findings"][0]["source_ids"], ["porch-video"])
            self.assertTrue(summary["sources"][1]["frozen_evidence"])
            self.assertNotIn("content", summary["sources"][1])
            self.assertIn("## Recent attributed research", render_agent_context_markdown(packet))
            self.assertEqual(packet["attention"], [])

    def test_research_refuses_missing_attribution_bad_youtube_and_evidence_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Research Guard")
            evidence = root / "notes.txt"
            evidence.write_text("firsthand note\n")
            score = research_score(evidence)
            spec = root / "research.json"

            score["findings"][0]["source_ids"] = []
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "must contain valid ids"):
                create_research_record(spec, song)

            score = research_score(evidence)
            score["sources"][0]["locator"] = "https://example.com/not-youtube"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "non-YouTube"):
                create_research_record(spec, song)

            score = research_score(evidence)
            spec.write_text(json.dumps(score))
            path = create_research_record(spec, song)
            record = json.loads(path.read_text())
            frozen = path.parent / record["sources"]["room-notes"]["evidence_path"]
            frozen.write_text("changed frozen evidence\n")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                load_research_record(song, path)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["research_records"]["invalid"], 1)
            self.assertIn("Research verification failed", " ".join(status["attention"]))

    def test_research_can_bind_a_completed_work_run_and_detect_result_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Research Work Origin")
            item_path = create_work_item(
                song,
                "Study answer relationships",
                "YouTube research",
                "Separate observation from interpretation and propose one original experiment.",
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "research-agent")
            result = root / "research-result.md"
            result.write_text("Attributed observations and an original experiment boundary.\n")
            finish_work_item(
                song,
                item_id,
                "Completed an attributed research pass.",
                "complete",
                [("research result", result)],
            )
            score = research_score()
            score["work"] = {"item": item_id, "run": 1}
            spec = root / "research.json"
            spec.write_text(json.dumps(score))

            path = create_research_record(spec, song)
            _, record = load_research_record(song, path)
            origin = record["recipe"]["work_origin"]
            self.assertEqual(origin["item_id"], item_id)
            self.assertEqual(origin["run_number"], 1)
            self.assertEqual(origin["results"][0]["role"], "research result")
            self.assertEqual(song_status(song, verify=True)["inventory"]["research_records"]["work_origins"], 1)

            frozen_result = song / origin["results"][0]["path"]
            frozen_result.write_text("drifted work result\n")
            with self.assertRaisesRegex(ValueError, "work origin result is missing or changed"):
                load_research_record(song, path)

    def test_research_record_resolution_stays_inside_the_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Research Boundary")
            outside = root / "outside" / "research.json"
            outside.parent.mkdir()
            outside.write_text("{}")
            with self.assertRaisesRegex(ValueError, "inside the song"):
                load_research_record(song, outside)


if __name__ == "__main__":
    unittest.main()
