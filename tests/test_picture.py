import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eprs.master import approve_master
from eprs.delivery import approve_youtube_video, render_youtube, verify_youtube_provenance
from eprs.cli import parser
from eprs.clearance import create_recording_clearance
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.picture import capture_picture, review_picture, verify_picture
from eprs.release import package_release
from eprs.session import create_recording_session
from eprs.system import new_song, sha256, song_status
from tests.test_delivery import lossless_master


def picture_video(path: Path, seconds: float = 0.18) -> None:
    subprocess.run([
        shutil.which("ffmpeg") or "ffmpeg",
        "-nostdin", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x17243b:s=640x360:r=24",
        "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000",
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(seconds),
        "-vf", "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709",
        "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", str(path),
    ], check=True)


def unsupported_picture_video(path: Path, seconds: float = 0.18) -> None:
    subprocess.run([
        shutil.which("ffmpeg") or "ffmpeg",
        "-nostdin", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x17243b:s=640x360:r=24",
        "-t", str(seconds),
        "-vf", "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709",
        "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        str(path),
    ], check=True)


def private_clearance(root: Path, song: Path) -> Path:
    raw = next((song / "recordings" / "raw").rglob("*.wav"))
    session_spec = root / "picture-session.json"
    session_spec.write_text(json.dumps({
        "schema": "eprs.recording-session/v1",
        "title": "Picture fixture source",
        "intent": "Bind the short family fixture to its participant and private-use context.",
        "captured_at": "2026-08-03",
        "tempo_or_time_reference": "Short fixture tone; no grid asserted.",
        "participants": [{
            "id": "family-performers", "role": "voices", "credit": "Family performers",
            "consent_note": "Private fixture use pending explicit release clearance.",
        }],
        "setups": [{
            "id": "fixture-recorder", "source": "fixture performance",
            "capture_chain": "test WAV generator",
        }],
        "takes": [{
            "id": "family-source", "role": "family phrase", "path": str(raw.relative_to(song)),
            "participant_ids": ["family-performers"], "setup_ids": ["fixture-recorder"],
            "note": "Exact raw source used by the delivery fixture.",
            "rights_note": "Private fixture only until separately cleared.",
        }],
    }))
    session = create_recording_session(session_spec, song)
    clearance_spec = root / "picture-clearance.json"
    clearance_spec.write_text(json.dumps({
        "schema": "eprs.recording-clearance/v1",
        "title": "Private picture fixture",
        "session": str(session.relative_to(song)),
        "intended_use": "Prepare a private local YouTube handoff without uploading.",
        "visibility_limit": "private",
        "takes": [{
            "id": "family-source", "decision": "approved",
            "confirmed_by": "fixture coordinator", "confirmed_at": "2026-08-03",
            "permission_note": "Approved for the stated private fixture use.",
        }],
        "participants": [{
            "id": "family-performers", "decision": "approved",
            "confirmed_by": "fixture coordinator", "confirmed_at": "2026-08-03",
            "permission_note": "Participant consent confirmed for the private fixture.",
            "credit_decision": "collective", "credit": "Family performers",
        }],
    }))
    return create_recording_clearance(clearance_spec, song)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class PictureCandidateTests(unittest.TestCase):
    def test_cli_exposes_capture_review_and_youtube_v2_recipe(self):
        capture = parser().parse_args([
            "picture", "add", "code/picture.json", "--song", "songs/study",
        ])
        review = parser().parse_args([
            "picture", "review", "video/pictures/study/picture.mp4",
            "--song", "songs/study", "--decision", "keep",
            "--review-note", "Watched every frame.",
        ])
        self.assertEqual(capture.picture_command, "add")
        self.assertEqual(review.picture_command, "review")
        self.assertEqual(review.decision, "keep")

    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        song = new_song(root / "songs", "Picture Candidate").resolve()
        master = lossless_master(root, song)
        approve_master(song, master, "Listened through the complete picture fixture master.")
        source = root / "external-picture.mp4"
        picture_video(source)
        score = root / "visual-score.json"
        score.write_text(json.dumps({
            "schema": "example.visual/v1",
            "prompt": "A patient blue field opens when the family phrase begins.",
            "seed": 17,
        }))
        spec = root / "picture.json"
        spec.write_text(json.dumps({
            "schema": "eprs.picture/v1",
            "title": "Patient blue field",
            "intent": "Let one restrained field make room for the short family phrase.",
            "source_video": str(source),
            "approved_master": str(master.relative_to(song)),
            "operator": "fixture visual artist",
            "tool": {
                "name": "Fixture Renderer",
                "version": "1.2.3",
                "session_format": "example.visual/v1 JSON",
            },
            "timeline_origin": "master-time-zero",
            "audio_policy": "replace-with-approved-master",
            "changes": [{
                "id": "blue-field",
                "type": "color and motion",
                "intent": "Keep attention on the performance rather than constant movement.",
                "details": "One static slate-blue frame spans the complete master.",
                "settings_or_unknown": "640x360, 24 fps, known color; renderer defaults otherwise unknown.",
            }],
            "unknowns": ["Exact encoder build metadata is not exposed by the fixture."],
            "evidence": [{
                "id": "visual-score",
                "role": "editable visual score",
                "path": str(score),
                "note": "The prompt and seed used for the picture candidate.",
                "rights_note": "Original fixture score; no third-party visual material.",
            }],
            "rights_note": "Original generated fixture picture; no upload is authorized.",
        }))
        return song, master, source, spec

    def test_capture_preserves_bytes_discloses_tool_and_requires_picture_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, master, source, spec = self._fixture(root)
            source_digest = sha256(source)

            picture, sidecar, record = capture_picture(spec, song)

            self.assertEqual(sha256(picture), source_digest)
            self.assertEqual(picture.read_bytes(), source.read_bytes())
            self.assertEqual(record["schema"], "eprs.picture-candidate/v1")
            self.assertEqual(record["recipe"]["master"]["sha256"], sha256(master))
            self.assertEqual(record["external_render"]["tool"]["name"], "Fixture Renderer")
            self.assertTrue(record["external_render"]["copied_without_conversion"])
            self.assertFalse(record["external_render"]["reproducible_by_eprs"])
            self.assertTrue(record["recipe"]["source_video"]["media"]["guide_audio"]["present"])
            self.assertTrue(all(value is False for value in record["authority"].values()))
            evidence = song / record["evidence"][0]["path"]
            self.assertEqual(sha256(evidence), record["evidence"][0]["sha256"])
            with self.assertRaisesRegex(ValueError, "complete-picture keep decision"):
                verify_picture(song, picture, require_keep=True)

            note = "Watched the complete picture; framing, motion, first/last frames, and master-time-zero sync intent are keepers."
            review_picture(song, picture, "keep", note)
            _, _, reviewed = verify_picture(song, picture, require_keep=True)
            self.assertEqual(reviewed["review"]["decision"], "keep")
            self.assertEqual(capture_picture(spec, song)[0], picture)

            youtube_spec = root / "youtube-picture.json"
            youtube_spec.write_text(json.dumps({
                "schema": "eprs.youtube/v2",
                "title": "Patient blue field",
                "intent": "Preserve the reviewed picture while replacing its guide tone with the approved master.",
                "master": str(master.relative_to(song)),
                "visual": {
                    "kind": "picture-candidate",
                    "path": str(picture.relative_to(song)),
                },
            }))
            youtube, youtube_sidecar = render_youtube(youtube_spec, song)
            youtube_record = json.loads(youtube_sidecar.read_text())
            self.assertEqual(youtube_record["schema"], "eprs.youtube-render/v2")
            self.assertTrue(all(youtube_record["verification"].values()))
            self.assertGreater(youtube_record["output"]["video_packet_count"], 0)
            self.assertGreater(youtube_record["output"]["audio_packet_count"], 0)
            self.assertEqual(
                youtube_record["recipe"]["assembly"]["embedded_guide_audio"], "discard"
            )
            self.assertNotEqual(sha256(youtube), source_digest)
            with self.assertRaisesRegex(ValueError, "visual and sync approval"):
                verify_youtube_provenance(song, youtube)
            approve_youtube_video(
                song,
                youtube,
                "Watched the assembled picture end to end and checked approved-master sync and first/last frames.",
            )
            verify_youtube_provenance(song, youtube)
            self.assertEqual(render_youtube(youtube_spec, song)[0], youtube)

            clearance = private_clearance(root, song)
            release_spec = root / "picture-release.json"
            release_spec.write_text(json.dumps({
                "schema": "eprs.release/v1",
                "title": "Patient blue field",
                "intent": "Freeze the reviewed renderer-neutral film and approved master locally.",
                "approved_master": str(master.relative_to(song)),
                "approved_video": str(youtube.relative_to(song)),
                "clearances": [str(clearance.relative_to(song))],
                "credits": [{"name": "Family performers", "role": "voices"}],
                "rights_note": "Private fixture release; no upload is authorized.",
                "youtube": {
                    "title": "Patient blue field",
                    "description": "A renderer-neutral local delivery fixture.",
                    "tags": ["original music", "fixture"],
                    "visibility_intent": "private",
                },
            }))
            final, final_manifest = package_release(release_spec, song)
            final_record = json.loads(final_manifest.read_text())
            self.assertEqual(
                final_record["recipe"]["sources"]["youtube_video"]["recipe_id"],
                youtube_record["recipe_id"],
            )
            self.assertTrue((final / "patient-blue-field-youtube.mp4").is_file())
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["picture_candidates"]["keep"], 1)
            self.assertEqual(status["inventory"]["youtube_videos"], 1)
            self.assertEqual(status["inventory"]["videos_approved"], 1)
            self.assertEqual(status["attention"], [])
            context = build_agent_context(song, verify=True)
            self.assertEqual(
                context["recent_picture_candidates"][0]["id"], reviewed["recipe_id"]
            )
            self.assertIn(
                "## Renderer-neutral picture candidates",
                render_agent_context_markdown(context),
            )

            original = sidecar.read_bytes()
            changed = json.loads(sidecar.read_text())
            changed["authority"]["upload_authorized"] = True
            sidecar.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "authority record"):
                verify_picture(song, picture)
            sidecar.write_bytes(original)

            evidence.write_text("changed evidence\n")
            with self.assertRaisesRegex(ValueError, "evidence copy"):
                verify_picture(song, picture)

    def test_refuses_wrong_timeline_audio_policy_and_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, master, _, spec = self._fixture(root)
            score = json.loads(spec.read_text())
            score["timeline_origin"] = "unknown"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "timeline_origin"):
                capture_picture(spec, song)

            score["timeline_origin"] = "master-time-zero"
            score["audio_policy"] = "trust-embedded-guide"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "audio_policy"):
                capture_picture(spec, song)

            long_picture = root / "long-picture.mp4"
            picture_video(long_picture, 1.0)
            score["audio_policy"] = "replace-with-approved-master"
            score["source_video"] = str(long_picture)
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "duration does not match"):
                capture_picture(spec, song)

            unsupported = root / "unsupported-picture.mp4"
            unsupported_picture_video(unsupported)
            score["source_video"] = str(unsupported)
            spec.write_text(json.dumps(score))
            picture, _, _ = capture_picture(spec, song)
            review_picture(
                song,
                picture,
                "keep",
                "Watched the complete compatibility-boundary fixture picture.",
            )
            youtube_spec = root / "unsupported-youtube.json"
            youtube_spec.write_text(json.dumps({
                "schema": "eprs.youtube/v2",
                "title": "Unsupported stream copy",
                "intent": "Exercise the explicit delivery codec boundary.",
                "master": str(master.relative_to(song)),
                "visual": {
                    "kind": "picture-candidate",
                    "path": str(picture.relative_to(song)),
                },
            }))
            with self.assertRaisesRegex(ValueError, "requires an H.264"):
                render_youtube(youtube_spec, song)


if __name__ == "__main__":
    unittest.main()
