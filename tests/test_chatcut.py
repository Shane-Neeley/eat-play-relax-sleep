import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eprs.chatcut import prepare_chatcut_handoff
from eprs.cli import parser


FFMPEG = shutil.which("ffmpeg")


@unittest.skipUnless(FFMPEG, "ffmpeg is required for ChatCut derivative tests")
class ChatCutHandoffTests(unittest.TestCase):
    def make_song(self, root: Path) -> tuple[Path, Path, Path]:
        song = root / "song"
        song.mkdir()
        (song / "song.json").write_text(json.dumps({"title": "Fixture Song"}) + "\n")
        video = song / "video" / "candidate.mp4"
        video.parent.mkdir()
        subprocess.run([
            FFMPEG, "-y", "-v", "error",
            "-f", "lavfi", "-i", "color=c=black:s=320x180:r=12:d=2",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=2",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", str(video),
        ], check=True)
        master = song / "masters" / "fixture-master.wav"
        master.parent.mkdir()
        subprocess.run([
            FFMPEG, "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=330:duration=2", "-c:a", "pcm_s24le",
            "-ar", "48000", str(master),
        ], check=True)
        return song, video, master

    def test_prepare_creates_bounded_derivatives_and_no_remote_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            song, video, master = self.make_song(Path(folder))
            captions = song / "captions.srt"
            captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nFixture\n")
            result = prepare_chatcut_handoff(
                song,
                video="video/candidate.mp4",
                audio="masters/fixture-master.wav",
                captions="captions.srt",
                prompt="Cut the visual sections around the real musical drop.",
                seconds=1,
                resolution=480,
            )
            package = Path(result["package"])
            record = json.loads((package / "handoff.json").read_text())
            self.assertFalse(result["upload_performed"])
            self.assertFalse(result["publication_authorized"])
            self.assertEqual(record["schema"], "eprs.chatcut-handoff/v1")
            self.assertEqual(record["submission"]["prompt"], "Cut the visual sections around the real musical drop.")
            self.assertFalse(record["submission"]["upload_performed"])
            self.assertTrue(record["submission"]["requires_explicit_user_operation"])
            self.assertTrue(all(value is False for value in record["authority"].values()))
            self.assertTrue(record["safety"]["local_master_preserved"])
            self.assertEqual(record["source_inputs"]["audio"]["path"], "masters/fixture-master.wav")
            self.assertTrue((package / "assets/preview-video.mp4").is_file())
            self.assertTrue((package / "assets/guide-audio.m4a").is_file())
            self.assertTrue((package / "assets/captions.srt").is_file())
            self.assertFalse((package / "masters").exists())
            probe = json.loads(subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "json",
                str(package / "assets/preview-video.mp4"),
            ], capture_output=True, text=True, check=True).stdout)
            self.assertEqual(
                (probe["streams"][0]["width"], probe["streams"][0]["height"]),
                (854, 480),
            )
            readme = (package / "README.md").read_text()
            self.assertIn("ChatCut disposable visual handoff", readme)
            self.assertIn("Remote authentication and upload were not performed", readme)
            self.assertNotIn(str(song), (package / "handoff.json").read_text())
            self.assertTrue(master.is_file())

    def test_rejects_raw_and_outside_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, _, _ = self.make_song(root)
            raw = song / "raw" / "take.mp4"
            raw.parent.mkdir()
            raw.write_bytes(b"raw")
            with self.assertRaisesRegex(ValueError, "immutable raw material"):
                prepare_chatcut_handoff(song, video="raw/take.mp4")
            outside = root / "outside.mp4"
            outside.write_bytes(b"outside")
            with self.assertRaisesRegex(ValueError, "inside the song workspace"):
                prepare_chatcut_handoff(song, video=outside)


class ChatCutCliTests(unittest.TestCase):
    def test_cli_exposes_local_prepare_only(self):
        args = parser().parse_args([
            "chatcut", "prepare", "songs/example", "--video", "video/candidate.mp4",
            "--audio", "masters/example.wav", "--seconds", "12", "--resolution", "1080",
        ])
        self.assertEqual(args.command, "chatcut")
        self.assertEqual(args.chatcut_command, "prepare")
        self.assertEqual(args.seconds, 12)
        self.assertEqual(args.resolution, 1080)
        self.assertFalse(hasattr(args, "upload"))


if __name__ == "__main__":
    unittest.main()
