import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
import wave
import struct

from eprs.producer import advance, catalog, compare, history, start, validate_vocals, validate_musical_review, package
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
            alternate = song / "masters" / "alternate.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=660:duration=1",
                            "-c:a", "pcm_s24le", str(alternate)], check=True)
            def evidence(path):
                return dict(path=str(path.relative_to(song)), sha256=sha256(path), note="Fixture comparison")
            review["musical_review"] = dict(
                schema="eprs.musical-review/v1", intent="Test package", identity="Oscillator",
                development="Fixture only", source_role="Original synthesis", delivery="Instrumental",
                weakest_moment="Alternate frequency", revision_result="Changed to test frequency",
                assessment_basis="Technical fixture, no listening", unresolved_release_blockers=[],
                candidates=[evidence(master), evidence(alternate)],
                revision=dict(before=evidence(alternate), after=evidence(master)))
            target = song / "notes" / "review.json"
            target.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError, "soundtrack"):
                package(root, "package", run["token"], "notes/review.json")
            review["video"] = dict(path="video/video.mp4", sha256=sha256(video))
            target.write_text(json.dumps(review))
            run_path = root / ".eprs-local/producer/runs/package.json"
            run_record = json.loads(run_path.read_text())
            run_record["concept"]["vocals"] = {"mode": "synthetic-singing", "review": "notes/vocal.json"}
            run_path.write_text(json.dumps(run_record))
            (song / "notes/vocal.json").write_text(json.dumps(dict(
                reviewer="test agent", method="Fixture", delivery_note="Fixture context",
                decision="keep", vocal=evidence(alternate), context=evidence(alternate))))
            with self.assertRaisesRegex(ValueError, "final master"):
                package(root, "package", run["token"], "notes/review.json")
            run_record["concept"].pop("vocals")
            run_path.write_text(json.dumps(run_record))
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

    @unittest.skipUnless(shutil.which("ffprobe"), "FFprobe required")
    def test_musical_review_refuses_generic_keep_stale_and_unresolved_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            song = Path(folder)
            a, b = song / "a.wav", song / "b.wav"
            for path, amplitude in [(a, 100), (b, 200)]:
                with wave.open(str(path), "wb") as audio:
                    audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    audio.writeframes(struct.pack("<h", amplitude) * 800)
            def item(path):
                return dict(path=path.name, sha256=sha256(path), note="Concrete fixture change")
            review = {field: "Specific authored assessment" for field in (
                "intent", "identity", "development", "source_role", "delivery",
                "weakest_moment", "revision_result", "assessment_basis")}
            review.update(schema="eprs.musical-review/v1", unresolved_release_blockers=[],
                          candidates=[item(a), item(b)], revision=dict(before=item(a), after=item(b)))
            assessment = dict(musical_review=review, master=item(b))
            validate_musical_review(song, assessment)
            with self.assertRaisesRegex(ValueError, "requires eprs"):
                validate_musical_review(song, {})
            review["unresolved_release_blockers"] = ["Vocal unintelligible"]
            with self.assertRaisesRegex(ValueError, "blockers"):
                validate_musical_review(song, assessment)
            review["unresolved_release_blockers"] = []
            review["candidates"] = [item(a), item(a)]
            with self.assertRaisesRegex(ValueError, "distinct"):
                validate_musical_review(song, assessment)
            review["candidates"] = [item(a), item(b)]
            a.write_bytes(b"silently changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                validate_musical_review(song, assessment)

    def test_deliberate_method_reuse_is_advisory_not_a_genre_veto(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Refinement")
            run = start(root, "one", "agent", str(song.relative_to(root)), CONCEPT)
            record_path = root / ".eprs-local/producer/runs/one.json"
            run["stage"] = "complete"
            record_path.write_text(json.dumps(run))
            second = start(root, "two", "agent", str(song.relative_to(root)), CONCEPT)
            self.assertEqual(second["diversity"]["decision"], "rework")
            self.assertEqual(second["review_contract"], "eprs.musical-review/v1")
