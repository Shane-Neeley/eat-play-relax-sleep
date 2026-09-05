import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess

from eprs.producer import advance, catalog, compare, history, start, validate_vocals, package
from eprs.system import new_song, sha256, song_status


CONCEPT = dict(engine="supercollider-nrt", composition="physical modeling",
               groove="broken beat", sound_world="resonant wood", form="rondo", visual="illustrated ocean")


class ProducerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
    def test_package_checks_soundtrack_and_preserves_actual_review_method(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Package")
            master = song / "masters" / "master.wav"
            video = song / "video" / "video.mp4"
            wrong = song / "video" / "wrong.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                            "-c:a", "pcm_s24le", str(master)], check=True)
            for path, hz in [(video, 440), (wrong, 660)]:
                subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=s=32x32:d=1",
                                "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=1",
                                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path)], check=True)
            run = start(root, "package", "test", str(song.relative_to(root)), CONCEPT)
            evidence = song / "notes" / "evidence.txt"
            evidence.write_text("Authored test evidence")
            for stage in ("arrange", "mix", "picture", "package"):
                advance(root, "package", run["token"], stage, "Explicit fixture stage decision", ["notes/evidence.txt"])
            review = dict(schema="eprs.producer-review/v1", reviewer="test agent", reviewer_type="agent",
                          method="Technical fixture assessment", decision="keep", decision_note="Fixture is correct",
                          rights_note="Original oscillator", limitations="No human audition claimed",
                          master=dict(path="masters/master.wav", sha256=sha256(master)),
                          video=dict(path="video/wrong.mp4", sha256=sha256(wrong)))
            target = song / "notes" / "review.json"
            target.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "soundtrack"):
                package(root, "package", run["token"], "notes/review.json")
            review["video"] = dict(path="video/video.mp4", sha256=sha256(video))
            target.write_text(json.dumps(review))
            final = package(root, "package", run["token"], "notes/review.json")
            record = json.loads((final / "release.json").read_text())
            self.assertEqual(record["review"]["reviewer_type"], "agent")
            self.assertFalse(record["publication"]["performed"])
            self.assertEqual(sha256(final / "master.wav"), sha256(master))
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["producer_packages"], 1)
            self.assertEqual(status["inventory"]["invalid_releases"], 0)
            with self.assertRaises(FileExistsError):
                package(root, "package", run["token"], "notes/review.json")

    def test_nested_favorites_survive_a_stale_album_index(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            album = root / "albums" / "favorites"
            track = album / "hidden" / "hidden"
            track.mkdir(parents=True)
            (album / "album.json").write_text(json.dumps({"title": "Favorites", "tracks": []}))
            (track / "metadata.json").write_text(json.dumps({"title": "Hidden Favorite"}))
            result = catalog(root)
            self.assertEqual(result["favorites"][0]["title"], "Hidden Favorite")
            self.assertFalse(result["favorites"][0]["indexed"])

    def test_repainting_or_renaming_does_not_change_music_method(self):
        prior = [{"stage": "complete", "concept": CONCEPT}]
        changed = {**CONCEPT, "visual": "red desert", "title": "New Name"}
        self.assertEqual(compare(changed, prior)["decision"], "rework")
        changed.update(engine="sonic-pi", composition="sample slicing", groove="shuffle 4/4", sound_world="acoustic strings")
        self.assertEqual(compare(changed, prior)["decision"], "explore")

    def test_vocals_cannot_silently_fall_back_to_raw_tts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            validate_vocals(root, {"mode": "instrumental"})
            with self.assertRaisesRegex(ValueError, "Untreated TTS"):
                validate_vocals(root, {"mode": "tts"})
            with self.assertRaisesRegex(ValueError, "in-context"):
                validate_vocals(root, {"mode": "processed-synthetic"})
            with self.assertRaisesRegex(ValueError, "explicit user request"):
                validate_vocals(root, {"mode": "spoken-requested"})

    def test_duplicate_concurrent_and_wrong_owner_runs_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "One")
            relative = str(song.relative_to(root))
            run = start(root, "day-1", "producer-a", relative, CONCEPT)
            with self.assertRaisesRegex(ValueError, "already exists"):
                start(root, "day-1", "producer-b", relative, CONCEPT)
            with self.assertRaisesRegex(ValueError, "already owned"):
                start(root, "day-2", "producer-b", relative, CONCEPT)
            with self.assertRaisesRegex(ValueError, "token"):
                advance(root, "day-1", "wrong", "hold", "Specific failure and next repair", [])
            advance(root, "day-1", run["token"], "hold", "Specific failure and next repair", [])
            start(root, "day-2", "producer-b", relative, CONCEPT)
            self.assertEqual(len(history(root)), 2)

    def test_no_stage_skips_missing_evidence_escape_or_silent_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "One")
            run = start(root, "one", "agent", str(song.relative_to(root)), CONCEPT)
            def step(stage, artifacts):
                return advance(root, "one", run["token"], stage, "This records a concrete production decision", artifacts)
            with self.assertRaisesRegex(ValueError, "exactly one"):
                step("package", [])
            with self.assertRaisesRegex(ValueError, "actual artifact"):
                step("arrange", [])
            with self.assertRaisesRegex(ValueError, "escapes"):
                step("arrange", ["../../../outside"])
            file = song / "code" / "sketch.txt"
            file.write_text("first candidate")
            step("arrange", ["code/sketch.txt"])
            file.write_text("changed candidate")
            with self.assertRaisesRegex(ValueError, "changed"):
                step("mix", ["code/sketch.txt"])
            step("hold", [])
            with self.assertRaisesRegex(ValueError, "immutable"):
                step("mix", ["code/sketch.txt"])
