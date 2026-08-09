from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.session import create_recording_session, load_recording_session
from eprs.system import ingest, new_song, sha256, song_status


def tone_wav(path: Path, frequency: float = 220, seconds: float = 0.08) -> None:
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 0.2 * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def session_score(sources: dict[str, Path]) -> dict:
    return {
        "schema": "eprs.recording-session/v1",
        "title": "Family room afternoon",
        "intent": "Keep the guitar invitation, group answer, and room as one performance context.",
        "captured_at": "2026-08-03 afternoon",
        "location_note": "Private room; precise address intentionally omitted.",
        "tempo_or_time_reference": "No click; the group follows the guitar breath.",
        "tuning_or_reference": "Guitar tuning was not documented; do not infer correction.",
        "room_note": "Keep the silence and room decay around every take.",
        "participants": [
            {
                "id": "guitar-player", "role": "guitar invitation", "credit": "credit pending",
                "consent_note": "Local production approved; sharing and publication are not approved.",
            },
            {
                "id": "family-group", "role": "family response", "credit": "collective credit pending",
                "consent_note": "Private family use only until all performer and guardian permissions are confirmed.",
            },
        ],
        "setups": [
            {
                "id": "amp-mic", "source": "guitar amplifier", "capture_chain": "dynamic mic into interface",
                "input": "input 1", "placement": "off-axis near speaker edge", "monitoring": "no printed effects",
            },
            {
                "id": "room-mic", "source": "voices and room", "capture_chain": "single room microphone",
                "input": "input 2", "placement": "in front of the group", "monitoring": "no printed effects",
            },
        ],
        "takes": [
            {
                "id": "guitar-one", "role": "guitar invitation", "path": str(sources["guitar"]),
                "participant_ids": ["guitar-player"], "setup_ids": ["amp-mic"],
                "note": "Keep the uneven release.", "rights_note": "Private performance; do not publish.",
            },
            {
                "id": "family-one", "role": "family response", "path": str(sources["family"]),
                "participant_ids": ["family-group"], "setup_ids": ["room-mic"],
                "note": "Keep breath, overlap, and laughter.", "rights_note": "Private family performance; do not share or publish.",
            },
            {
                "id": "room-tone", "role": "room sound", "path": str(sources["room"]),
                "participant_ids": [], "setup_ids": ["room-mic"],
                "note": "Uninterrupted room tail.", "rights_note": "Private location sound; do not publish.",
            },
        ],
    }


class RecordingSessionTests(unittest.TestCase):
    def test_session_preserves_multi_take_capture_consent_and_agent_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Session Handoff")
            sources = {name: root / f"{name}.wav" for name in ("guitar", "family", "room")}
            for index, source in enumerate(sources.values(), start=1):
                tone_wav(source, 180 + index * 40)
            source_hashes = {name: sha256(path) for name, path in sources.items()}
            spec = root / "session.json"
            spec.write_text(json.dumps(session_score(sources)))

            manifest_path = create_recording_session(spec, song)
            _, session = load_recording_session(song, manifest_path)

            self.assertEqual(session["schema"], "eprs.recording-session-record/v1")
            self.assertEqual(set(session["participants"]), {"guitar-player", "family-group"})
            self.assertEqual(set(session["setups"]), {"amp-mic", "room-mic"})
            self.assertEqual(set(session["takes"]), {"guitar-one", "family-one", "room-tone"})
            self.assertEqual(session["takes"]["room-tone"]["participant_ids"], [])
            self.assertTrue(all(Path(song / take["path"]).is_file() for take in session["takes"].values()))
            self.assertEqual({name: sha256(path) for name, path in sources.items()}, source_hashes)
            self.assertEqual(create_recording_session(spec, song).resolve(), manifest_path.resolve())

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["recording_sessions"]["total"], 1)
            self.assertEqual(status["inventory"]["recording_sessions"]["takes"], 3)
            self.assertEqual(status["inventory"]["raw_recordings"], 3)
            self.assertEqual(status["attention"], [])
            context = build_agent_context(song, verify=True)
            summary = context["recent_recording_sessions"][0]
            self.assertEqual(summary["title"], "Family room afternoon")
            self.assertEqual(summary["takes"][1]["participant_ids"], ["family-group"])
            self.assertIn("Private family use", summary["participants"][1]["consent_note"])
            self.assertFalse(context["limits"]["binary_media_embedded"])
            self.assertIn("## Recent recording sessions", render_agent_context_markdown(context))

    def test_session_references_existing_raw_take_without_duplication(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Existing Intake")
            external = root / "guitar.wav"
            tone_wav(external)
            raw, raw_sidecar = ingest(external, song, "guitar", rights_note="Private performance; do not publish.")
            score = session_score({"guitar": raw, "family": raw, "room": raw})
            score["takes"] = score["takes"][:1]
            spec = root / "session.json"
            spec.write_text(json.dumps(score))

            manifest = create_recording_session(spec, song)
            session = json.loads(manifest.read_text())

            self.assertEqual(len(list((song / "recordings" / "raw").rglob("*.wav"))), 1)
            self.assertEqual(session["takes"]["guitar-one"]["path"], str(raw.relative_to(song)))
            self.assertEqual(session["takes"]["guitar-one"]["provenance_path"], str(raw_sidecar.relative_to(song)))

    def test_session_validates_all_relationships_before_intake_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Session Guard")
            sources = {name: root / f"{name}.wav" for name in ("guitar", "family", "room")}
            for index, source in enumerate(sources.values(), start=1):
                tone_wav(source, 180 + index * 40)
            score = session_score(sources)
            score["takes"][1]["participant_ids"] = ["missing-person"]
            spec = root / "invalid.json"
            spec.write_text(json.dumps(score))

            with self.assertRaisesRegex(ValueError, "unknown participants"):
                create_recording_session(spec, song)
            self.assertEqual(list((song / "notes").glob("sessions/*")), [])
            self.assertEqual(list((song / "recordings" / "raw").rglob("*.wav")), [])

            duplicate_score = session_score(sources)
            duplicate_score["takes"][1]["path"] = duplicate_score["takes"][0]["path"]
            spec.write_text(json.dumps(duplicate_score))
            with self.assertRaisesRegex(ValueError, "duplicates another take's media"):
                create_recording_session(spec, song)
            self.assertEqual(list((song / "recordings" / "raw").rglob("*.wav")), [])

            spec.write_text(json.dumps(session_score(sources)))
            manifest = create_recording_session(spec, song)
            session = json.loads(manifest.read_text())
            changed = song / session["takes"]["guitar-one"]["path"]
            with changed.open("ab") as output:
                output.write(b"drift")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                load_recording_session(song, manifest)
            status = song_status(song, verify=True)
            self.assertIn("Checksum mismatch for take guitar-one", " ".join(status["attention"]))
            with self.assertRaisesRegex(ValueError, "inside the song"):
                load_recording_session(song, root / "outside-session.json")


if __name__ == "__main__":
    unittest.main()
