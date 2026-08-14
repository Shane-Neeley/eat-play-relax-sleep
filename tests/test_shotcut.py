import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from eprs.adapters import adapter_guide
from eprs.cli import parser
from eprs.shotcut import (
    compile_shotcut_project,
    prepare_shotcut_project,
    render_shotcut_project,
)
from eprs.system import doctor, load_toolchain


ROOT = Path(__file__).resolve().parents[1]
FFMPEG = shutil.which("ffmpeg")
MELT = Path("/Applications/Shotcut.app/Contents/MacOS/melt")


class ShotcutIntegrationTests(unittest.TestCase):
    def test_open_source_editor_is_optional_and_declared(self):
        registry = load_toolchain()
        provider = next(item for item in registry["tools"] if item["id"] == "shotcut")
        self.assertFalse(provider["required"])
        self.assertEqual(provider["kind"], "application")
        self.assertIn("mlt_project", provider["capabilities"])
        self.assertIn("beat_markers", provider["capabilities"])
        self.assertIn("mlt_project_generation", provider["capabilities"])
        workflow = next(
            item for item in registry["workflows"]
            if item["id"] == "open-source-visual-editing"
        )
        self.assertIn("timeline_editing", workflow["capabilities"])
        self.assertIn("beat_sync", workflow["capabilities"])

    def test_shotcut_profile_and_docs_are_local_first(self):
        guide = adapter_guide("shotcut-open-editor")
        self.assertEqual(guide["adapter"]["provider"], "shotcut")
        text = (ROOT / "docs" / "SHOTCUT.md").read_text()
        self.assertIn("no account", text)
        self.assertIn("eprs shotcut compile", text)
        profile = json.loads((ROOT / "config" / "adapters" / "shotcut.json").read_text())
        self.assertIn("Cloud uploads", profile["safety"]["avoid"][0])
        self.assertIn("beat_markers", profile["capabilities"])

    def test_shotcut_detection_is_portable(self):
        report = doctor(workflows=["open-source-visual-editing"])
        tool = next(item for item in report["tools"] if item["id"] == "shotcut")
        if sys.platform == "darwin" and Path("/Applications/Shotcut.app").is_dir():
            self.assertTrue(tool["applicable"])
            self.assertTrue(tool["available"], tool)
        elif sys.platform != "darwin":
            self.assertFalse(tool["applicable"])


@unittest.skipUnless(FFMPEG and MELT.is_file(), "FFmpeg and Shotcut melt are required")
class ShotcutProjectTests(unittest.TestCase):
    def make_song(self, root: Path) -> Path:
        song = root / "song"
        song.mkdir()
        (song / "song.json").write_text(json.dumps({
            "schema": "eprs.song/v1", "title": "Fixture", "slug": "fixture"
        }) + "\n")
        video = song / "video" / "source.mp4"
        video.parent.mkdir()
        subprocess.run([
            FFMPEG, "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=4",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=4",
            "-t", "4", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", str(video),
        ], check=True)
        master = song / "masters" / "master.wav"
        master.parent.mkdir()
        subprocess.run([
            FFMPEG, "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=330:duration=4", "-c:a", "pcm_s24le",
            "-ar", "48000", str(master),
        ], check=True)
        return song

    def score(self) -> dict:
        return {
            "schema": "eprs.shotcut-project/v1",
            "title": "Fixture Beat Map",
            "intent": "Exercise real editable Shotcut annotations, filters, and tracks.",
            "source_video": "video/source.mp4",
            "master": "masters/master.wav",
            "width": 320,
            "height": 180,
            "fps": 30,
            "sections": [
                {
                    "id": "intro", "label": "INTRO", "start_seconds": 0,
                    "end_seconds": 2, "source_start_seconds": 0,
                    "look": {"saturation": 0},
                    "transform": {
                        "start_rect": "0%/0%:100%x100%:100%",
                        "end_rect": "-3%/-3%:106%x106%:100%",
                    },
                    "text": {"value": "DON'T BLINK", "size": 36},
                },
                {
                    "id": "drop", "label": "DROP", "start_seconds": 2,
                    "end_seconds": 4, "source_start_seconds": 2,
                    "look": {"contrast": 1.2, "saturation": 1.5},
                    "glow": 0.2,
                },
            ],
            "overlays": [
                {
                    "id": "accent", "label": "RGB ACCENT", "start_seconds": 2,
                    "end_seconds": 2.5, "source_start_seconds": 2,
                    "rgb_shift": 8,
                }
            ],
            "overlay_blend_mode": 22,
        }

    def test_compile_creates_editable_original_media_mlt(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".shotcut-test-") as folder:
            song = self.make_song(Path(folder))
            spec = song / "score.json"
            spec.write_text(json.dumps(self.score()) + "\n")
            result = compile_shotcut_project(spec, song)
            project = Path(result["project"])
            record = json.loads(Path(result["manifest"]).read_text())
            root = ET.parse(project).getroot()
            self.assertEqual(root.find("tractor/property[@name='shotcut']").text, "1")
            self.assertIsNotNone(root.find("playlist[@id='main bin']"))
            self.assertIsNotNone(root.find("playlist[@id='background']"))
            self.assertIsNotNone(root.find("playlist[@id='video_base']"))
            self.assertIsNotNone(root.find("playlist[@id='video_accents']"))
            self.assertIsNotNone(root.find("chain[@id='master_audio']"))
            self.assertIsNotNone(root.find("chain/filter/property[@name='shotcut:filter']"))
            accent_blend = root.find(
                "tractor/transition[@id='composite_accents']/property[@name='mlt_service']"
            )
            self.assertIsNotNone(accent_blend)
            self.assertEqual(accent_blend.text, "frei0r.difference")
            marker_text = root.find("tractor/property[@name='shotcut:markers']").text
            self.assertEqual(json.loads(marker_text), [])
            for element in root.iter():
                resource = element.get("resource")
                if resource and not resource.startswith("#"):
                    self.assertFalse(Path(resource).is_absolute(), resource)
            self.assertEqual(record["schema"], "eprs.shotcut-project-package/v1")
            self.assertTrue(record["verification"]["mlt_parse_and_null_render"])
            self.assertTrue(record["verification"]["original_media_only"])

    def test_render_uses_bundled_melt_and_preserves_sidecar(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".shotcut-test-") as folder:
            song = self.make_song(Path(folder))
            spec = song / "score.json"
            score = self.score()
            score["sections"] = [
                {"id": "plain", "label": "PLAIN", "start_seconds": 0,
                 "end_seconds": 4, "source_start_seconds": 0}
            ]
            score["overlays"] = []
            spec.write_text(json.dumps(score) + "\n")
            prepared = compile_shotcut_project(spec, song)
            rendered = render_shotcut_project(
                prepared["project"], song, out="video/rendered.mp4", quality="draft"
            )
            self.assertTrue(Path(rendered["video"]).is_file())
            record = json.loads(Path(rendered["metadata"]).read_text())
            self.assertEqual(record["schema"], "eprs.shotcut-render/v1")
            self.assertEqual(record["quality"], "draft")
            self.assertEqual(record["output"]["sha256"], rendered["sha256"])
            self.assertIn("lossy guide", record["audio_policy"])

    def test_legacy_prepare_compiles_through_same_score(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".shotcut-test-") as folder:
            song = self.make_song(Path(folder))
            result = prepare_shotcut_project(
                song,
                title="Legacy Fixture",
                video_segments=[
                    {"video": "video/source.mp4", "start_seconds": 0,
                     "duration_seconds": 2, "label": "hook"},
                    {"video": "video/source.mp4", "start_seconds": 2,
                     "duration_seconds": 2, "label": "answer"},
                ],
                audio="masters/master.wav",
                title_cues=[{"start_seconds": 0, "duration_seconds": 1, "text": "HOOK"}],
                markers=[{"time_seconds": 0, "label": "HOOK"}],
            )
            self.assertTrue(Path(result["project"]).is_file())
            self.assertTrue(Path(result["score"]).is_file())
            self.assertEqual(result["markers"][0]["label"], "HOOK")

    def test_rejects_raw_outside_and_overwriting(self):
        with tempfile.TemporaryDirectory(dir=ROOT, prefix=".shotcut-test-") as folder:
            root = Path(folder)
            song = self.make_song(root)
            raw = song / "raw" / "source.mp4"
            raw.parent.mkdir()
            raw.write_bytes(b"raw")
            score = self.score()
            score["source_video"] = "raw/source.mp4"
            spec = song / "unsafe.json"
            spec.write_text(json.dumps(score) + "\n")
            with self.assertRaisesRegex(ValueError, "immutable raw material"):
                compile_shotcut_project(spec, song)
            with tempfile.TemporaryDirectory(prefix="eprs-shotcut-outside-") as outside:
                outside_path = Path(outside) / "outside.mp4"
                outside_path.write_bytes(b"outside")
                score["source_video"] = str(outside_path)
                spec.write_text(json.dumps(score) + "\n")
                with self.assertRaisesRegex(ValueError, "inside the EPRS repository"):
                    compile_shotcut_project(spec, song)


class ShotcutCliTests(unittest.TestCase):
    def test_cli_exposes_compile_render_open_and_inline_prepare(self):
        compile_args = parser().parse_args([
            "shotcut", "compile", "score.json", "--song", "songs/example",
        ])
        self.assertEqual(compile_args.shotcut_command, "compile")
        render_args = parser().parse_args([
            "shotcut", "render", "project.mlt", "--song", "songs/example",
            "--out", "video/candidate.mp4", "--quality", "draft",
        ])
        self.assertEqual(render_args.quality, "draft")
        open_args = parser().parse_args([
            "shotcut", "open", "project.mlt", "--song", "songs/example",
        ])
        self.assertEqual(open_args.shotcut_command, "open")
        inline = parser().parse_args([
            "shotcut", "prepare", "songs/example", "--title", "Test",
            "--segment", '{"video":"video/a.mp4","duration_seconds":2}',
            "--audio", "masters/a.wav",
        ])
        self.assertEqual(inline.shotcut_command, "prepare")


if __name__ == "__main__":
    unittest.main()
