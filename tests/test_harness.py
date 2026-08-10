import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from eprs.harness import create_song_run
from eprs.production_map import write_production_map
from eprs.system import sha256, song_status


def silent_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48_000)
        wav.writeframes(b"\x00\x00" * 4800)


class SongHarnessTests(unittest.TestCase):
    def test_relative_default_root_works_from_repository_style_cwd(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            previous = Path.cwd()
            try:
                import os
                os.chdir(root)
                run_path, _ = create_song_run(
                    "Relative Song", "A tiny patient pulse.", render_visual_preview=False
                )
            finally:
                os.chdir(previous)
            self.assertTrue(run_path.is_file())
            self.assertEqual(run_path.parents[3], (root / "songs" / "relative-song").resolve())

    def test_make_song_captures_inputs_queues_work_and_writes_shallow_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "guitar.wav"
            silent_wav(source)

            run_path, manifest = create_song_run(
                "Family Signal",
                "A loose guitar invitation answered by family voices; warm and crooked.",
                root=root / "songs",
                seed=12345,
                recordings=[("guitar", source)],
                references=["https://example.com/reference"],
                render_visual_preview=False,
            )
            song = root / "songs" / "family-signal"

            self.assertEqual(manifest["schema"], "eprs.song-run/v1")
            self.assertEqual(manifest["randomness"]["mode"], "explicit-replay")
            self.assertFalse(manifest["randomness"]["novelty"]["enforced"])
            self.assertEqual(manifest["randomness"]["seed"], 12345)
            self.assertEqual(manifest["inputs"]["recordings"], 1)
            self.assertFalse(manifest["starter"]["supplied_recordings_used"])
            self.assertTrue(run_path.is_file())
            self.assertTrue((song / "NOW.md").is_file())
            self.assertTrue((song / "_LISTEN.wav").is_symlink())
            self.assertTrue((song / "_CHANGE_ME.md").is_file())
            self.assertTrue((song / "_CURRENT.json").is_file())
            self.assertTrue((song / manifest["paths"]["beat"]).is_file())
            self.assertTrue((song / manifest["paths"]["audio_preview"]).is_file())
            self.assertTrue((song / manifest["paths"]["rhythm_map"]).is_file())
            self.assertTrue((song / manifest["paths"]["production_map_dot"]).is_file())
            self.assertTrue((song / manifest["paths"]["agent_work"]).is_file())
            self.assertEqual(manifest["outputs"]["visual_preview"]["status"], "skipped")
            self.assertIn(
                manifest["outputs"]["production_map"]["renderer"]["status"],
                {"rendered", "skipped", "failed"},
            )
            map_text = (song / manifest["paths"]["production_map_dot"]).read_text()
            self.assertIn("eprs.production-map/v1", map_text)
            self.assertIn("QUEUED AGENT PLAN", map_text)
            self.assertIn("guitar", map_text.lower())
            experiment = json.loads((song / manifest["paths"]["experiment"] / "experiment.json").read_text())
            self.assertEqual(experiment["status"], "rendered")
            self.assertIsNone(experiment["decision"])
            self.assertEqual(experiment["listening_notes"], [])
            self.assertEqual(song_status(song, verify=True)["attention"], [])
            self.assertEqual(song_status(song)["inventory"]["raw_recordings"], 1)
            self.assertEqual(song_status(song)["inventory"]["work_items"]["queued"], 1)
            self.assertIn("does not yet contain", (song / "NOW.md").read_text())
            now = (song / "NOW.md").read_text()
            self.assertIn("Production map", now)
            self.assertIn("## Input routing", now)
            self.assertIn("source-sketch", now)
            self.assertIn("attributed research work", now)

    def test_default_entropy_changes_runs_but_explicit_seed_replays_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first_path, first = create_song_run(
                "Entropy Test", "A patient crooked groove.", root=root / "songs", render_visual_preview=False
            )
            song = root / "songs" / "entropy-test"
            second_path, second = create_song_run(
                None, "A patient crooked groove.", song=song, render_visual_preview=False
            )
            self.assertNotEqual(first["randomness"]["seed"], second["randomness"]["seed"])
            self.assertNotEqual(
                sha256(song / first["paths"]["beat"]), sha256(song / second["paths"]["beat"])
            )

            replay_path, replay = create_song_run(
                None,
                "A patient crooked groove.",
                song=song,
                seed=first["randomness"]["seed"],
                render_visual_preview=False,
            )
            self.assertEqual(replay["randomness"]["mode"], "explicit-replay")
            self.assertFalse(replay["randomness"]["novelty"]["enforced"])
            self.assertEqual(
                replay["randomness"]["creative_fingerprint"],
                first["randomness"]["creative_fingerprint"],
            )
            self.assertEqual(
                sha256(song / first["paths"]["beat"]), sha256(song / replay["paths"]["beat"])
            )
            self.assertEqual(
                sha256(song / first["paths"]["audio_preview"]), sha256(song / replay["paths"]["audio_preview"])
            )
            self.assertNotEqual(first_path, replay_path)
            rebuilt = write_production_map(song, render_svg=False)
            self.assertEqual(rebuilt["run"], replay["paths"]["run_manifest"])
            self.assertEqual(rebuilt["renderer"]["status"], "disabled")
            self.assertTrue((song / rebuilt["dot"]["path"]).is_file())

    def test_fresh_entropy_rejects_a_prior_musical_structure_before_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entropy = [100, 100, *range(101, 2_000)]
            with patch("eprs.harness.secrets.randbits", side_effect=entropy):
                _, first = create_song_run(
                    "Novelty Gate",
                    "A patient crooked pulse.",
                    root=root / "songs",
                    render_visual_preview=False,
                )
                song = root / "songs" / "novelty-gate"
                _, second = create_song_run(
                    None,
                    "A patient crooked pulse.",
                    song=song,
                    render_visual_preview=False,
                )

            self.assertTrue(second["randomness"]["novelty"]["enforced"])
            self.assertEqual(second["randomness"]["novelty"]["prior_fingerprints_checked"], 1)
            self.assertGreaterEqual(second["randomness"]["novelty"]["collision_rejections"], 1)
            self.assertNotEqual(
                first["randomness"]["creative_fingerprint"],
                second["randomness"]["creative_fingerprint"],
            )
            self.assertEqual(song_status(song)["inventory"]["production_requests"]["total"], 2)


if __name__ == "__main__":
    unittest.main()
