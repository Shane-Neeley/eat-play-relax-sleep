import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.quality import (
    analyze_beatscript,
    approve_creative_quality,
    verify_creative_quality,
    write_quality_report,
)


ARRANGEMENT = """\
title "Quality Fixture"
tempo 100
meter 4/4
resolution 16
bars 16
swing 0.50
seed 11
notes identity | C4 . E4 . G4 . A4 . . . G4 . E4 . . . | ; voice=lead start_bar=1 end_bar=4
track pocket | X... .... ..x. .... | ; kind=kick start_bar=5 end_bar=12 gain=0.6
track pocket-rim | .... X... .... X... | ; kind=stick start_bar=5 end_bar=12
notes pocket-bass | C2 . . . G1 . . . A1 . . . . . . . | ; voice=bass start_bar=5 end_bar=12
notes answer | . . . . G4 . A4 . . . C5 . E5 . C5 . | ; voice=lead start_bar=9 end_bar=12
track breath | X... .... .... .... | ; kind=kick start_bar=13 end_bar=13 gain=0.1
track final-pocket | X... .... ..x. .... | ; kind=kick start_bar=14 end_bar=16 gain=0.8
notes final-answer | C5 . E5 . G5 . A5 . . . G5 . E5 . C5 . | ; voice=lead start_bar=14 end_bar=16
"""


ODD_ARRANGEMENT = ARRANGEMENT.replace(
    'meter 4/4\n',
    'meter 7/8\n',
)


class QualityTests(unittest.TestCase):
    def test_accidentals_enharmonics_and_inactive_tracks(self):
        from eprs.quality import _pitch_classes
        from eprs.beat import load
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pitches.beat"
            path.write_text(ARRANGEMENT.replace("C4 . E4 . G4 . A4", "C4 . C#4 . Db4 . D4"))
            beat = load(path)
            self.assertEqual(_pitch_classes(beat, 1, 4), {"C", "C#", "D", "E", "G"})
            self.assertNotIn("E", _pitch_classes(beat, 5, 8))

    def test_compound_meter_is_not_automatically_unfamiliar(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "compound.beat"
            path.write_text(ARRANGEMENT.replace("meter 4/4", "meter 6/8"))
            report = analyze_beatscript(path)
            self.assertNotIn("odd_or_unfamiliar_meter_requires_human_approval", report["risk_flags"])

    def test_legacy_frozen_report_still_verifies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "legacy.beat"
            source.write_text(ARRANGEMENT)
            report = analyze_beatscript(source, analysis_version=1)
            report.pop("analysis_version")
            report["source"]["path"] = "legacy.beat"
            target = root / "quality.json"
            target.write_text(json.dumps(report))
            verify_creative_quality(root, target)

    def test_ordinary_form_can_be_auto_publish_eligible(self):
        with tempfile.TemporaryDirectory() as folder:
            beat = Path(folder) / "fixture.beat"
            beat.write_text(ARRANGEMENT)
            report = analyze_beatscript(beat)

            self.assertTrue(report["auto_publish_eligible"])
            self.assertEqual(report["decision"], "pass")
            self.assertEqual(report["human_approval"]["status"], "required")
            self.assertEqual(report["risk_flags"], [])
            self.assertGreaterEqual(report["metrics"]["section_count"], 4)
            self.assertGreaterEqual(report["metrics"]["state_change_count"], 2)

    def test_odd_meter_is_held_even_when_the_form_checks_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            beat = Path(folder) / "odd.beat"
            beat.write_text(ODD_ARRANGEMENT)
            report = analyze_beatscript(beat)

            self.assertFalse(report["auto_publish_eligible"])
            self.assertEqual(report["decision"], "hold")
            self.assertIn("odd_or_unfamiliar_meter_requires_human_approval", report["risk_flags"])
            self.assertIn("odd_meter_pattern_lengths_do_not_align_to_bar_grid", report["risk_flags"])
            self.assertTrue(report["checks"]["early_identity"])

    def test_even_a_clean_form_requires_human_public_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = root / "song"
            song.mkdir()
            beat = song / "code" / "clean.beat"
            beat.parent.mkdir()
            beat.write_text(ARRANGEMENT)
            report = write_quality_report(beat, song, "notes/creative-quality.json")

            approve_creative_quality(
                song,
                report,
                "I listened to the complete arrangement and approve this public release.",
            )
            _, approved = verify_creative_quality(song, report)
            self.assertEqual(approved["human_approval"]["status"], "approved")

    def test_report_is_bound_to_source_and_can_be_explicitly_approved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = root / "song"
            song.mkdir()
            beat = song / "code" / "odd.beat"
            beat.parent.mkdir()
            beat.write_text(ODD_ARRANGEMENT)
            report_path = write_quality_report(beat, song, "notes/creative-quality.json")

            _, held = verify_creative_quality(song, report_path)
            self.assertEqual(held["human_approval"]["status"], "required")
            approve_creative_quality(
                song,
                report_path,
                "I listened to the complete arrangement and explicitly approve this odd-meter experiment.",
            )
            _, approved = verify_creative_quality(song, report_path)
            self.assertEqual(approved["human_approval"]["status"], "approved")
            self.assertIn("explicitly approve", approved["human_approval"]["note"])

            record = json.loads(report_path.read_text())
            self.assertEqual(record["schema"], "eprs.creative-quality/v1")

    def test_public_release_refuses_to_self_certify_without_report(self):
        from eprs.release import package_release
        from eprs.system import new_song

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Public Gate")
            master = song / "masters" / "master.wav"
            video = song / "video" / "youtube.mp4"
            master.write_bytes(b"master")
            video.write_bytes(b"video")
            spec = root / "release.json"
            spec.write_text(json.dumps({
                "schema": "eprs.release/v1",
                "title": "Public Gate",
                "intent": "Test the public creative approval boundary.",
                "rights_note": "Synthetic fixture only.",
                "credits": [{"name": "EPRS", "role": "author"}],
                "approved_master": str(master.relative_to(song)),
                "approved_video": str(video.relative_to(song)),
                "youtube": {
                    "title": "Public Gate",
                    "description": "Synthetic fixture.",
                    "tags": ["fixture"],
                    "visibility_intent": "public",
                },
            }))
            with patch("eprs.release.verify_master_provenance", return_value=(master, master.with_suffix(".json"), {"recipe_id": "master"})), \
                 patch("eprs.release.verify_youtube_provenance", return_value=(video, video.with_suffix(".json"), {"recipe_id": "video", "master": {"path": str(master.relative_to(song))}})), \
                 self.assertRaisesRegex(ValueError, "requires a verified creative_quality report"):
                package_release(spec, song)


if __name__ == "__main__":
    unittest.main()
