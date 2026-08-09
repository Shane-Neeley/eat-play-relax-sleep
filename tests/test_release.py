import json
from pathlib import Path
import shutil
import tempfile
import unittest

from eprs.clearance import create_recording_clearance
from eprs.delivery import approve_youtube_video, render_youtube
from eprs.master import approve_master
from eprs.publication import prepare_publication_handoff
from eprs.release import package_release
from eprs.session import create_recording_session
from eprs.system import new_song, sha256, song_status
from tests.test_delivery import lossless_master


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ReleaseTests(unittest.TestCase):
    def _approved_media(self, root: Path, song: Path) -> tuple[Path, Path]:
        master = lossless_master(root, song)
        approve_master(song, master, "Listened through the complete release fixture.")
        video_spec = root / "youtube.json"
        video_spec.write_text(json.dumps({
            "schema": "eprs.youtube/v1",
            "title": "Family Release",
            "intent": "Keep the visual still and the performance central.",
            "master": str(master.relative_to(song)),
            "output": {"width": 640, "height": 360, "fps": 24},
        }))
        video, _ = render_youtube(video_spec, song)
        approve_youtube_video(song, video, "Watched first to last frame and checked sync.")
        return master, video

    def _recording_session(self, root: Path, song: Path) -> Path:
        raw = next((song / "recordings" / "raw").rglob("*.wav"))
        session_spec = root / "release-source-session.json"
        session_spec.write_text(json.dumps({
            "schema": "eprs.recording-session/v1",
            "title": "Release source session",
            "intent": "Keep the contributor and permission context attached to the delivered performance.",
            "captured_at": "2026-08-03",
            "tempo_or_time_reference": "Fixture tone; no musical grid asserted.",
            "participants": [{
                "id": "family-performers", "role": "voices", "credit": "Family performers",
                "consent_note": "Local development only until a separate use clearance is recorded.",
            }],
            "setups": [{
                "id": "fixture-recorder", "source": "fixture performance",
                "capture_chain": "test WAV generator",
            }],
            "takes": [{
                "id": "family-source", "role": "Family phrase", "path": str(raw.relative_to(song)),
                "participant_ids": ["family-performers"], "setup_ids": ["fixture-recorder"],
                "note": "The exact raw source used by the selected phrase.",
                "rights_note": "No platform use until a separate clearance is approved.",
            }],
        }))
        return create_recording_session(session_spec, song)

    def _recording_clearance(self, root: Path, song: Path, session: Path) -> Path:
        clearance_spec = root / "release-clearance.json"
        clearance_spec.write_text(json.dumps({
            "schema": "eprs.recording-clearance/v1",
            "title": "Private family release use",
            "session": str(session.relative_to(song.resolve())),
            "intended_use": "Prepare a local package proposing private YouTube visibility; no upload is authorized.",
            "visibility_limit": "private",
            "takes": [{
                "id": "family-source", "decision": "approved",
                "confirmed_by": "fixture permission coordinator", "confirmed_at": "2026-08-03",
                "permission_note": "The recording-use rights for this fixture were confirmed for the stated use.",
            }],
            "participants": [{
                "id": "family-performers", "decision": "approved",
                "confirmed_by": "fixture permission coordinator", "confirmed_at": "2026-08-03",
                "permission_note": "The fixture performer consent is confirmed for the stated use.",
                "credit_decision": "collective", "credit": "Family performers",
            }],
        }))
        return create_recording_clearance(clearance_spec, song)

    def _spec(
        self,
        root: Path,
        song: Path,
        master: Path,
        video: Path,
        *,
        include_clearance: bool = True,
    ) -> Path:
        spec = root / "release.json"
        score = {
            "schema": "eprs.release/v1",
            "title": "Family Release",
            "intent": "Hand the approved lossless and picture versions to the family.",
            "approved_master": str(master.relative_to(song)),
            "approved_video": str(video.relative_to(song)),
            "credits": [
                {"name": "Family performers", "role": "voices", "note": "Use agreed wording."},
                {"name": "Guitar performer", "role": "guitar"},
            ],
            "rights_note": "The owner must confirm public names and performance permission before upload.",
            "youtube": {
                "title": "Family Release",
                "description": "An original family-room performance.",
                "tags": ["original music", "family performance"],
                "visibility_intent": "private",
            },
        }
        if include_clearance:
            session = self._recording_session(root, song)
            clearance = self._recording_clearance(root, song, session)
            score["clearances"] = [str(clearance.relative_to(song.resolve()))]
        spec.write_text(json.dumps(score))
        return spec

    def test_packages_approved_media_without_mutating_or_publishing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Release Package")
            master, video = self._approved_media(root, song)
            master_digest, video_digest = sha256(master), sha256(video)
            spec = self._spec(root, song, master, video)

            destination, manifest_path = package_release(spec, song)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema"], "eprs.release-package/v1")
            self.assertTrue(all(manifest["verification"].values()))
            self.assertFalse(manifest["publication"]["uploaded"])
            self.assertFalse(manifest["publication"]["published"])
            self.assertEqual(len(manifest["artifacts"]), 6)
            self.assertEqual(sha256(master), master_digest)
            self.assertEqual(sha256(video), video_digest)
            for artifact in manifest["artifacts"]:
                artifact_path = song / artifact["path"]
                self.assertTrue(artifact_path.is_file())
                self.assertEqual(sha256(artifact_path), artifact["sha256"])
            metadata = json.loads((destination / "youtube-metadata.json").read_text())
            self.assertEqual(metadata["visibility_intent"], "private")
            self.assertFalse(metadata["uploaded"])
            self.assertIn("not been uploaded", (destination / "HANDOFF.md").read_text())
            self.assertEqual(package_release(spec, song), (destination, manifest_path))
            handoff = prepare_publication_handoff(song, destination)
            handoff_record = json.loads(handoff.read_text())
            self.assertFalse(handoff_record["authorization"]["upload_authorized"])
            self.assertEqual(handoff_record["recipe"]["release"]["release_id"], manifest["release_id"])
            self.assertFalse(json.loads(manifest_path.read_text())["publication"]["uploaded"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["release_packages"], 1)
            self.assertEqual(status["inventory"]["invalid_releases"], 0)
            self.assertEqual(status["inventory"]["publication_handoffs"], 1)
            self.assertEqual(status["inventory"]["publication_receipts"], 0)
            self.assertEqual(status["attention"], [])

    def test_refuses_video_without_complete_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Unreviewed Package")
            master = lossless_master(root, song)
            approve_master(song, master, "Listened through the complete fixture.")
            video_spec = root / "youtube.json"
            video_spec.write_text(json.dumps({
                "schema": "eprs.youtube/v1", "title": "Unreviewed",
                "intent": "Exercise release approval.", "master": str(master.relative_to(song)),
                "output": {"width": 640, "height": 360, "fps": 24},
            }))
            video, _ = render_youtube(video_spec, song)
            with self.assertRaisesRegex(ValueError, "visual and sync approval"):
                package_release(self._spec(root, song, master, video), song)
            self.assertEqual([path.name for path in (song / "FINAL").iterdir()], ["README.md"])

    def test_raw_release_refuses_missing_session_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Missing Session Gate")
            master, video = self._approved_media(root, song)
            spec = self._spec(root, song, master, video, include_clearance=False)

            with self.assertRaisesRegex(ValueError, "requires a verified recording session"):
                package_release(spec, song)
            self.assertEqual([path.name for path in (song / "FINAL").iterdir()], ["README.md"])

    def test_session_linked_raw_take_requires_visibility_and_credit_clearance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Consent Gate")
            master, video = self._approved_media(root, song)
            raw = next((song / "recordings" / "raw").rglob("*.wav"))
            session_spec = root / "session.json"
            session_spec.write_text(json.dumps({
                "schema": "eprs.recording-session/v1",
                "title": "Release source session",
                "intent": "Keep the contributor and permission context attached to the delivered performance.",
                "captured_at": "2026-08-03",
                "tempo_or_time_reference": "Fixture tone; no musical grid asserted.",
                "participants": [{
                    "id": "family-performers", "role": "voices", "credit": "Family performers",
                    "consent_note": "Local development only until a separate use clearance is recorded.",
                }],
                "setups": [{
                    "id": "fixture-recorder", "source": "fixture performance",
                    "capture_chain": "test WAV generator",
                }],
                "takes": [{
                    "id": "family-source", "role": "Family phrase", "path": str(raw.relative_to(song)),
                    "participant_ids": ["family-performers"], "setup_ids": ["fixture-recorder"],
                    "note": "The exact raw source used by the selected phrase.",
                    "rights_note": "No platform use until a separate clearance is approved.",
                }],
            }))
            session = create_recording_session(session_spec, song)
            spec = self._spec(root, song, master, video, include_clearance=False)

            with self.assertRaisesRegex(ValueError, "requires approved private clearance"):
                package_release(spec, song)

            clearance_spec = root / "clearance.json"
            clearance_spec.write_text(json.dumps({
                "schema": "eprs.recording-clearance/v1",
                "title": "Private family release use",
                "session": str(session.relative_to(song.resolve())),
                "intended_use": "Prepare a local package proposing private YouTube visibility; no upload is authorized.",
                "visibility_limit": "private",
                "takes": [{
                    "id": "family-source", "decision": "approved",
                    "confirmed_by": "fixture permission coordinator", "confirmed_at": "2026-08-03",
                    "permission_note": "The recording-use rights for this fixture were confirmed for the stated use.",
                }],
                "participants": [{
                    "id": "family-performers", "decision": "approved",
                    "confirmed_by": "fixture permission coordinator", "confirmed_at": "2026-08-03",
                    "permission_note": "The fixture performer consent is confirmed for the stated use.",
                    "credit_decision": "collective", "credit": "Family performers",
                }],
            }))
            clearance = create_recording_clearance(clearance_spec, song)
            release_score = json.loads(spec.read_text())
            release_score["clearances"] = [str(clearance.relative_to(song.resolve()))]
            spec.write_text(json.dumps(release_score))

            destination, manifest_path = package_release(spec, song)
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["verification"]["recording_clearance"])
            self.assertEqual(len(manifest["recipe"]["audio_lineage"]["raw_recordings"]), 1)
            self.assertEqual(
                {record["schema"] for record in manifest["recipe"]["audio_lineage"]["artifacts"]},
                {"eprs.audio-selection/v1", "eprs.mix-render/v1", "eprs.master-render/v1"},
            )
            self.assertEqual(manifest["recipe"]["recording_coverage"][0]["take_id"], "family-source")
            self.assertEqual(len(manifest["artifacts"]), 6)
            self.assertTrue((destination / "clearances").is_dir())

            public_score = dict(release_score)
            public_score["youtube"] = dict(release_score["youtube"], visibility_intent="public")
            spec.write_text(json.dumps(public_score))
            with self.assertRaisesRegex(ValueError, "requires approved public clearance"):
                package_release(spec, song)

            wrong_credit = json.loads(json.dumps(release_score))
            wrong_credit["credits"][0]["name"] = "Different wording"
            spec.write_text(json.dumps(wrong_credit))
            with self.assertRaisesRegex(ValueError, "do not include clearance-approved wording"):
                package_release(spec, song)


if __name__ == "__main__":
    unittest.main()
