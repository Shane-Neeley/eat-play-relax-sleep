from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.harness import create_song_run
from eprs.mix import review_mix, verify_mix_provenance
from eprs.source_sketch import create_source_sketch, verify_source_sketch
from eprs.system import sha256, song_status


def tone_wav(path: Path, frequency: float, seconds: float = 0.3) -> None:
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 0.2 * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


class SourceSketchTests(unittest.TestCase):
    def test_source_sketch_arranges_real_inputs_replays_and_surfaces_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guitar = root / "guitar.wav"
            voices = root / "family-voices.wav"
            tone_wav(guitar, 220)
            tone_wav(voices, 337)
            _, run = create_song_run(
                "Living Room Answer",
                "A loose guitar invitation answered by unpolished family voices.",
                root=root / "songs",
                seed=123,
                recordings=[("guitar invitation", guitar), ("family voices", voices)],
                render_visual_preview=False,
            )
            song = root / "songs" / "living-room-answer"
            raw_digests = {
                path: sha256(path) for path in (song / "recordings" / "raw").glob("*.wav")
            }

            manifest_path, sketch = create_source_sketch(
                song,
                "Let the guitar ask first, then let the voices answer without cleaning up the room.",
                seed=777,
                render_visual_preview=False,
            )

            self.assertEqual(sketch["schema"], "eprs.source-sketch/v1")
            self.assertEqual(sketch["randomness"]["mode"], "explicit-replay")
            self.assertEqual(sketch["randomness"]["seed"], 777)
            self.assertEqual(
                {item["classification"] for item in sketch["sources"]},
                {"harmonic", "vocal"},
            )
            self.assertEqual(
                {path: sha256(path) for path in raw_digests}, raw_digests
            )
            verified_path, _ = verify_source_sketch(song, manifest_path)
            self.assertEqual(verified_path, manifest_path)
            mix = song / sketch["paths"]["mix"]
            _, _, mix_record = verify_mix_provenance(song, mix)
            self.assertEqual(mix_record["output"]["probe"]["streams"][0]["codec_name"], "pcm_f32le")
            self.assertFalse(mix_record["render"]["automatic_normalization"])
            self.assertFalse(mix_record["render"]["compression"])
            self.assertFalse(mix_record["render"]["limiting"])
            self.assertTrue((song / "_LISTEN.wav").is_symlink())
            self.assertEqual((song / "_LISTEN.wav").resolve(), mix.resolve())
            self.assertFalse((song / "_WATCH.mp4").exists())
            self.assertIn("Current source-aware sketch", (song / "NOW.md").read_text())
            production_map = song / run["paths"]["production_map_dot"]
            self.assertIn("SOURCE-AWARE MIX", production_map.read_text())

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["source_sketches"]["total"], 1)
            self.assertEqual(status["inventory"]["source_sketches"]["pending"], 1)
            context = build_agent_context(song, verify=True)
            self.assertEqual(context["recent_source_sketches"][0]["id"], sketch["id"])
            self.assertEqual(
                {item["classification"] for item in context["recent_source_sketches"][0]["sources"]},
                {"harmonic", "vocal"},
            )
            self.assertIn("## Recent source-aware sketches", render_agent_context_markdown(context))

            replay_path, replay = create_source_sketch(
                song,
                sketch["intent"],
                seed=777,
                render_visual_preview=False,
            )
            self.assertEqual(replay_path, manifest_path)
            self.assertEqual(replay["outputs"]["mix"]["sha256"], sketch["outputs"]["mix"]["sha256"])

            review_mix(
                song,
                mix,
                "Listened end to end: the guitar invitation and family answer leave enough air.",
                "keep",
            )
            verify_source_sketch(song, manifest_path)
            reviewed_status = song_status(song, verify=True)
            self.assertEqual(reviewed_status["inventory"]["source_sketches"]["pending"], 0)
            self.assertEqual(reviewed_status["inventory"]["source_sketches"]["keep"], 1)

            fresh_path, fresh = create_source_sketch(
                song,
                sketch["intent"],
                render_visual_preview=False,
            )
            self.assertNotEqual(fresh_path, manifest_path)
            self.assertNotEqual(fresh["randomness"]["seed"], 777)
            self.assertNotEqual(
                fresh["outputs"]["mix_score_sha256"], sketch["outputs"]["mix_score_sha256"]
            )

    def test_source_sketch_requires_an_explicitly_captured_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, run = create_song_run(
                "Words Only",
                "A beat idea with no recording supplied.",
                root=root / "songs",
                seed=456,
                render_visual_preview=False,
            )
            song = root / "songs" / "words-only"
            with self.assertRaisesRegex(ValueError, "at least one captured recording"):
                create_source_sketch(
                    song,
                    "Arrange the captured recording.",
                    run=run["paths"]["run_manifest"],
                    render_visual_preview=False,
                )


if __name__ == "__main__":
    unittest.main()
