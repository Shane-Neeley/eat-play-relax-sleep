import json
from pathlib import Path
import tempfile
import unittest

from eprs.clearance import (
    approved_clearance_coverage,
    create_recording_clearance,
    load_recording_clearance,
)
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.session import create_recording_session
from eprs.system import new_song, sha256, song_status
from tests.test_session import session_score, tone_wav


def approved_clearance(session: Path, visibility: str = "private") -> dict:
    return {
        "schema": "eprs.recording-clearance/v1",
        "title": f"Family answer {visibility} use",
        "session": str(session),
        "intended_use": f"Prepare a local package proposing {visibility} YouTube visibility; upload remains separate.",
        "visibility_limit": visibility,
        "takes": [{
            "id": "family-one",
            "decision": "approved",
            "confirmed_by": "session permission coordinator",
            "confirmed_at": "2026-08-03",
            "permission_note": "The recording owner approved this exact stated use.",
        }],
        "participants": [{
            "id": "family-group",
            "decision": "approved",
            "confirmed_by": "session permission coordinator",
            "confirmed_at": "2026-08-03",
            "permission_note": "Every performer and any required guardian approved this exact stated use.",
            "credit_decision": "collective",
            "credit": "Family performers",
        }],
    }


def make_session(root: Path, song: Path) -> Path:
    sources = {name: root / f"{name}.wav" for name in ("guitar", "family", "room")}
    for index, source in enumerate(sources.values(), start=1):
        tone_wav(source, 180 + index * 40)
    spec = root / "session.json"
    spec.write_text(json.dumps(session_score(sources)))
    return create_recording_session(spec, song)


class RecordingClearanceTests(unittest.TestCase):
    def test_clearance_is_deterministic_session_bound_and_visibility_limited(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Clearance Record")
            session = make_session(root, song)
            session_digest = sha256(session)
            spec = root / "clearance.json"
            spec.write_text(json.dumps(approved_clearance(session)))

            path = create_recording_clearance(spec, song)
            _, record = load_recording_clearance(song, path)

            self.assertEqual(record["schema"], "eprs.recording-clearance-record/v1")
            self.assertEqual(record["status"], "approved")
            self.assertEqual(record["session"]["sha256"], session_digest)
            self.assertEqual(record["participants"][0]["credit"], "Family performers")
            self.assertIn("family-one", approved_clearance_coverage(record, "private"))
            self.assertEqual(approved_clearance_coverage(record, "public"), {})
            self.assertEqual(create_recording_clearance(spec, song).resolve(), path.resolve())
            self.assertEqual(sha256(session), session_digest)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["recording_clearances"]["approved"], 1)
            self.assertEqual(status["inventory"]["recording_clearances"]["invalid"], 0)
            self.assertEqual(status["attention"], [])
            context = build_agent_context(song, verify=True)
            summary = context["recent_recording_clearances"][0]
            self.assertEqual(summary["status"], "approved")
            self.assertEqual(summary["participants"][0]["credit"], "Family performers")
            self.assertIn("## Recent recording clearances", render_agent_context_markdown(context))

    def test_pending_clearance_is_recordable_but_incomplete_coverage_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Pending Clearance")
            session = make_session(root, song)
            score = approved_clearance(session)
            for record in [*score["takes"], *score["participants"]]:
                record["decision"] = "unknown"
                record["confirmed_by"] = ""
                record["confirmed_at"] = ""
            spec = root / "pending.json"
            spec.write_text(json.dumps(score))

            path = create_recording_clearance(spec, song)
            _, record = load_recording_clearance(song, path)
            self.assertEqual(record["status"], "pending")
            self.assertEqual(approved_clearance_coverage(record, "private"), {})
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["recording_clearances"]["pending"], 1)
            self.assertIn("Resolve pending", " ".join(status["next_actions"]))

            score["participants"] = []
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "participant coverage is incomplete"):
                create_recording_clearance(spec, song)

    def test_clearance_rejects_session_or_decision_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Clearance Drift")
            session = make_session(root, song)
            spec = root / "clearance.json"
            spec.write_text(json.dumps(approved_clearance(session)))
            clearance = create_recording_clearance(spec, song)

            changed = json.loads(clearance.read_text())
            changed["participants"][0]["permission_note"] = "Changed after the record was created."
            clearance.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "id does not match"):
                load_recording_clearance(song, clearance)

            clearance.unlink()
            clearance = create_recording_clearance(spec, song)
            changed_session = json.loads(session.read_text())
            changed_session["room_note"] = "Changed session context."
            session.write_text(json.dumps(changed_session))
            with self.assertRaisesRegex(ValueError, "normalized contents"):
                load_recording_clearance(song, clearance)


if __name__ == "__main__":
    unittest.main()
