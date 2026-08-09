from array import array
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from eprs.delivery import approve_youtube_video, render_youtube
from eprs.master import approve_master, render_master
from eprs.mix import render_mix, review_mix
from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, seconds: float = 0.2) -> None:
    rate = 48_000
    samples = array(
        "h",
        (
            round(math.sin(2 * math.pi * 220 * frame / rate) * 0.2 * 32767)
            for frame in range(round(seconds * rate))
        ),
    )
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def lossless_master(root: Path, song: Path) -> Path:
    source = root / "family-take.wav"
    tone_wav(source)
    selected, _ = select_audio(source, song, "Family phrase", 0, 0.18)
    mix_spec = root / "mix.json"
    mix_spec.write_text(json.dumps({
        "schema": "eprs.mix/v1",
        "title": "Family phrase mix",
        "intent": "Keep the short source intact for delivery testing.",
        "tracks": [{
            "id": "family",
            "path": str(selected.relative_to(song)),
            "duration_seconds": 0.18,
        }],
    }))
    mix, _ = render_mix(mix_spec, song)
    review_mix(
        song,
        mix,
        "Listened end to end: the fixture balance, headroom, and edges are ready for mastering.",
        "keep",
    )
    master_spec = root / "master.json"
    master_spec.write_text(json.dumps({
        "schema": "eprs.master/v1",
        "title": "Family delivery master",
        "intent": "Preserve the approved balance and dynamics.",
        "destination": "YouTube source",
        "source": str(mix.relative_to(song)),
        "gain_db": 0,
        "true_peak_ceiling_dbfs": -1,
    }))
    master, _ = render_master(master_spec, song)
    return master


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class YouTubeDeliveryTests(unittest.TestCase):
    def test_youtube_requires_approval_then_renders_and_records_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Safe Video")
            master = lossless_master(root, song)
            master_digest = sha256(master)
            spec = root / "youtube.json"
            spec.write_text(json.dumps({
                "schema": "eprs.youtube/v1",
                "title": "Family: 'Yes' [Live]",
                "intent": "A restrained title card that keeps attention on the performance.",
                "master": str(master.relative_to(song)),
                "visual": {
                    "kind": "title-card",
                    "background_color": "#15151a",
                    "text_color": "#ffffff",
                    "font_size": 48,
                },
                "output": {"width": 640, "height": 360, "fps": 24},
            }))

            with self.assertRaisesRegex(ValueError, "full-listen approval"):
                render_youtube(spec, song)

            approve_master(song, master, "Test listener reviewed the complete generated fixture.")
            video, sidecar = render_youtube(spec, song)

            self.assertTrue(video.is_file())
            self.assertEqual(sha256(master), master_digest)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["schema"], "eprs.youtube-render/v1")
            self.assertTrue(all(metadata["verification"].values()))
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["codec_name"], "h264")
            self.assertEqual(metadata["approval"]["visual_and_sync_review"], "not recorded by renderer")
            self.assertFalse(metadata["publication"]["uploaded"])
            self.assertFalse(metadata["publication"]["published"])

            repeated_video, repeated_sidecar = render_youtube(spec, song)
            self.assertEqual(repeated_video, video)
            self.assertEqual(repeated_sidecar, sidecar)

            video_digest = sha256(video)
            approved_sidecar = approve_youtube_video(
                song,
                video,
                "Reviewed the full title card, first and last frames, and audio sync.",
            )
            self.assertEqual(approved_sidecar.resolve(), sidecar.resolve())
            self.assertEqual(sha256(video), video_digest)
            approved = json.loads(sidecar.read_text())
            self.assertEqual(approved["approval"]["visual_and_sync_review"], "approved")
            self.assertFalse(approved["publication"]["published"])

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["videos"], 1)
            self.assertEqual(status["inventory"]["youtube_videos"], 1)
            self.assertEqual(status["inventory"]["videos_pending_review"], 0)
            self.assertEqual(status["inventory"]["videos_approved"], 1)
            self.assertEqual(status["attention"], [])

    def test_youtube_rejects_master_outside_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Path Guard")
            outside = root / "outside.wav"
            tone_wav(outside)
            spec = root / "youtube.json"
            spec.write_text(json.dumps({
                "schema": "eprs.youtube/v1",
                "title": "Unsafe source",
                "intent": "Exercise the delivery boundary.",
                "master": str(outside),
            }))
            with self.assertRaisesRegex(ValueError, "inside the song masters"):
                render_youtube(spec, song)


if __name__ == "__main__":
    unittest.main()
