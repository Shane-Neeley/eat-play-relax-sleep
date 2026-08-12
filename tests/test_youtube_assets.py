from array import array
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave

from eprs.delivery import approve_youtube_video, render_youtube
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.master import approve_master, render_master
from eprs.mix import render_mix, review_mix
from eprs.publication import prepare_publication_handoff, verify_publication_handoff
from eprs.release import package_release
from eprs.system import new_song, sha256, song_status
from eprs.youtube_assets import (
    create_youtube_asset_bundle,
    review_youtube_asset_bundle,
    verify_youtube_asset_bundle,
)
from tests.test_delivery import _ffmpeg_has_filter


def _tone(path: Path, seconds: float = 31.2) -> None:
    rate = 48_000
    samples = array(
        "h",
        (
            round(math.sin(2 * math.pi * 220 * frame / rate) * 0.1 * 32767)
            for frame in range(round(seconds * rate))
        ),
    )
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def _approved_video(root: Path, song: Path) -> tuple[Path, Path]:
    source = song / "code" / "generated-fixture.wav"
    _tone(source)
    mix_spec = root / "mix.json"
    mix_spec.write_text(json.dumps({
        "schema": "eprs.mix/v1",
        "title": "Asset fixture mix",
        "intent": "Keep the generated test tone unchanged for timing checks.",
        "tracks": [{
            "id": "fixture",
            "role": "generated test tone",
            "intent": "Technical fixture, not a performance.",
            "path": str(source.relative_to(song)),
            "duration_seconds": 31.2,
        }],
    }))
    mix, _ = render_mix(mix_spec, song)
    review_mix(song, mix, "Listened through the generated timing fixture.", "keep")
    master_spec = root / "master.json"
    master_spec.write_text(json.dumps({
        "schema": "eprs.master/v1",
        "title": "Asset fixture master",
        "intent": "Preserve the timing fixture without dynamics processing.",
        "destination": "YouTube asset tests",
        "source": str(mix.relative_to(song)),
        "gain_db": 0,
        "true_peak_ceiling_dbfs": -1,
    }))
    master, _ = render_master(master_spec, song)
    approve_master(song, master, "Listened through the complete generated master fixture.")
    video_spec = root / "youtube.json"
    video_spec.write_text(json.dumps({
        "schema": "eprs.youtube/v1",
        "title": "Asset Fixture",
        "intent": "Use a still title card so asset timing is deterministic.",
        "master": str(master.relative_to(song)),
        "output": {"width": 640, "height": 360, "fps": 24},
    }))
    video, _ = render_youtube(video_spec, song)
    approve_youtube_video(song, video, "Reviewed all frames and sync in the generated fixture.")
    return master, video


def _thumbnail(path: Path) -> None:
    subprocess.run([
        shutil.which("ffmpeg") or "ffmpeg",
        "-nostdin", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x26364a:s=640x360",
        "-frames:v", "1", str(path),
    ], check=True)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe") and _ffmpeg_has_filter("drawtext"),
    "FFmpeg with drawtext required for title-card fixtures",
)
class YouTubeAssetTests(unittest.TestCase):
    def test_reviewed_assets_flow_through_final_and_offline_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Publishing Assets")
            master, video = _approved_video(root, song)
            image = song / "visuals" / "thumbnail.png"
            _thumbnail(image)
            spec = root / "youtube-assets.json"
            score = {
                "schema": "eprs.youtube-assets/v1",
                "title": "Asset Fixture",
                "intent": "Prepare authored upload context for the approved listening video.",
                "approved_video": str(video.relative_to(song)),
                "accessibility_note": (
                    "The video is a static title card with a generated test tone; captions name the sound."
                ),
                "thumbnail": {
                    "path": str(image.relative_to(song)),
                    "alt_text": "Slate-blue title-card background for the Asset Fixture.",
                    "review_question": "Is the image legible, representative, and safe at small sizes?",
                },
                "captions": [{
                    "language": "en",
                    "label": "English",
                    "completeness_note": "The only audible content is the continuous generated tone.",
                    "cues": [{
                        "start_seconds": 0,
                        "end_seconds": 31.1,
                        "text": "[Continuous generated test tone]",
                    }],
                }],
                "chapters": [
                    {"start_seconds": 0, "title": "Opening tone"},
                    {"start_seconds": 10, "title": "Middle tone"},
                    {"start_seconds": 20, "title": "Closing tone"},
                ],
            }
            spec.write_text(json.dumps(score))

            destination, manifest_path = create_youtube_asset_bundle(spec, song)
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema"], "eprs.youtube-assets-bundle/v1")
            self.assertFalse(manifest["authority"]["upload_authorized"])
            self.assertEqual(len(manifest["artifacts"]), 3)
            self.assertIn("00:00:00,000 --> 00:00:31,100", (destination / "captions-en.srt").read_text())
            self.assertEqual(
                (destination / "chapters.txt").read_text().splitlines(),
                ["0:00 Opening tone", "0:10 Middle tone", "0:20 Closing tone"],
            )
            with self.assertRaisesRegex(ValueError, "editorial and accessibility approval"):
                verify_youtube_asset_bundle(song, destination)

            review_youtube_asset_bundle(
                song,
                destination,
                "Reviewed the thumbnail at small size, all caption timing, chapter labels, and accessibility note.",
            )
            _, reviewed = verify_youtube_asset_bundle(song, destination)
            self.assertEqual(reviewed["review"]["editorial_and_accessibility_review"], "approved")

            release_spec = root / "release.json"
            release_spec.write_text(json.dumps({
                "schema": "eprs.release/v1",
                "title": "Asset Fixture",
                "intent": "Freeze the approved media and upload-facing assets locally.",
                "approved_master": str(master.relative_to(song)),
                "approved_video": str(video.relative_to(song)),
                "youtube_assets": str(manifest_path.relative_to(song.resolve())),
                "credits": [{"name": "EPRS test generator", "role": "generated fixture"}],
                "rights_note": "Generated technical fixture; no external upload is authorized.",
                "youtube": {
                    "title": "Asset Fixture",
                    "description": "A generated local pipeline fixture.",
                    "tags": ["test fixture"],
                    "visibility_intent": "private",
                },
            }))
            final, release_manifest = package_release(release_spec, song)
            release_record = json.loads(release_manifest.read_text())
            roles = [artifact["role"] for artifact in release_record["artifacts"]]
            self.assertIn("approved YouTube thumbnail", roles)
            self.assertIn("YouTube captions", roles)
            self.assertIn("YouTube chapters", roles)
            metadata = json.loads((final / "youtube-metadata.json").read_text())
            self.assertIn("0:00 Opening tone", metadata["description"])
            self.assertIn("EPRS test generator", metadata["description"])
            self.assertEqual(metadata["thumbnail"]["alt_text"], score["thumbnail"]["alt_text"])

            handoff = prepare_publication_handoff(song, final)
            _, handoff_record = verify_publication_handoff(song, handoff)
            self.assertEqual(len(handoff_record["recipe"]["upload_assets"]), 4)
            self.assertFalse(handoff_record["authorization"]["upload_authorized"])
            for artifact in handoff_record["recipe"]["upload_assets"]:
                self.assertEqual(sha256(song / artifact["path"]), artifact["sha256"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["videos"], 1)
            self.assertEqual(status["inventory"]["youtube_asset_bundles"]["approved"], 1)
            self.assertEqual(status["attention"], [])
            context = build_agent_context(song, verify=True)
            self.assertEqual(context["recent_youtube_assets"][0]["id"], reviewed["bundle_id"])
            self.assertIn(
                "## YouTube publishing asset bundles",
                render_agent_context_markdown(context),
            )

            captions = destination / "captions-en.srt"
            captions.write_text(captions.read_text() + "changed\n")
            with self.assertRaisesRegex(ValueError, "checksum has changed"):
                verify_youtube_asset_bundle(song, destination)


if __name__ == "__main__":
    unittest.main()
