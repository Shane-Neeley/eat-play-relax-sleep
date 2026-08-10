from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.harness import create_song_run
from eprs.mix import review_mix, verify_mix_provenance
from eprs.musical_observation import observe_musical_performance
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


def separated_phrases_wav(path: Path, rate: int = 48_000) -> None:
    samples = [0.0] * rate
    for start_seconds, end_seconds, frequency in (
        (0.15, 0.42, 220.0),
        (0.66, 0.90, 330.0),
    ):
        first = round(start_seconds * rate)
        last = round(end_seconds * rate)
        for index in range(first, last):
            elapsed = (index - first) / rate
            remaining = (last - index) / rate
            envelope = min(1.0, elapsed / 0.01, remaining / 0.03)
            samples[index] = 0.3 * envelope * math.sin(2 * math.pi * frequency * elapsed)
    pcm = array("h", (round(value * 32767) for value in samples))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())


class SourceSketchTests(unittest.TestCase):
    def test_explicit_observation_binds_and_places_one_unchanged_phrase(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guitar = root / "guitar-phrases.wav"
            separated_phrases_wav(guitar)
            _, run = create_song_run(
                "Observed Reply",
                "A two-part guitar reply with silence that should remain meaningful.",
                root=root / "songs",
                seed=212,
                recordings=[("guitar reply", guitar)],
                render_visual_preview=False,
            )
            song = root / "songs" / "observed-reply"
            request_path = song / run["paths"]["request"]
            request = json.loads(request_path.read_text())
            captured = next(
                song / value["path"] for value in request["provided"].values()
                if value.get("handling") == "immutable-recording"
            )
            source_digest = sha256(captured)
            observation_path, observation = observe_musical_performance(
                captured,
                song,
                "guitar reply",
                note="Use one complete reply, but keep both pulse readings open.",
            )

            manifest_path, sketch = create_source_sketch(
                song,
                "Let one observed guitar sentence invite a later answer.",
                seed=313,
                include_bed=False,
                observations=[observation_path],
                render_visual_preview=False,
            )

            self.assertEqual(sha256(captured), source_digest)
            self.assertEqual(len(sketch["musical_observations"]), 1)
            binding = sketch["musical_observations"][0]
            self.assertEqual(binding["result_id"], observation["result_id"])
            source = sketch["sources"][0]
            selected = source["musical_observation"]["selected_phrase"]
            self.assertIn(selected, observation["phrase_observation"]["regions"])
            self.assertEqual(
                source["placements"][0]["source_start_seconds"],
                selected["start_seconds"],
            )
            self.assertEqual(
                source["placements"][0]["duration_seconds"],
                selected["duration_seconds"],
            )
            self.assertFalse(
                source["musical_observation"]["interpretation"]["tempo_selected"]
            )
            self.assertIn("no key or chord was inferred", source["player_intent"])
            score = json.loads((song / sketch["paths"]["mix_score"]).read_text())
            track = score["tracks"][0]
            self.assertEqual(track["source_start_seconds"], selected["start_seconds"])
            _, _, mix_record = verify_mix_provenance(song, song / sketch["paths"]["mix"])
            self.assertEqual(
                mix_record["recipe"]["evidence"][1]["declared_schema"],
                "eprs.musical-observation/v1",
            )
            verify_source_sketch(song, manifest_path)
            context = build_agent_context(song, verify=True)
            self.assertEqual(
                context["recent_source_sketches"][0]["sources"][0]
                ["musical_observation"]["result_id"],
                observation["result_id"],
            )
            tampered = json.loads(manifest_path.read_text())
            tampered["sources"][0]["musical_observation"]["tempo_candidates"] = []
            manifest_path.write_text(json.dumps(tampered, indent=2) + "\n")
            with self.assertRaisesRegex(ValueError, "candidates have drifted"):
                verify_source_sketch(song, manifest_path)

    def test_source_sketch_refuses_observation_for_an_uncaptured_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            captured = root / "captured.wav"
            unrelated = root / "unrelated.wav"
            tone_wav(captured, 220)
            tone_wav(unrelated, 330)
            _, _ = create_song_run(
                "Wrong Evidence",
                "Only the captured guitar belongs in this pass.",
                root=root / "songs",
                seed=11,
                recordings=[("captured guitar", captured)],
                render_visual_preview=False,
            )
            song = root / "songs" / "wrong-evidence"
            observation_path, _ = observe_musical_performance(
                unrelated, song, "unrelated voice"
            )
            with self.assertRaisesRegex(ValueError, "captured recording"):
                create_source_sketch(
                    song,
                    "Use only exact evidence.",
                    observations=[observation_path],
                    render_visual_preview=False,
                )

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
            self.assertFalse(sketch["randomness"]["novelty"]["enforced"])
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
            self.assertEqual(status["inventory"]["source_sketches"]["shapes"]["one-pass"], 1)
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

            with patch(
                "eprs.source_sketch.secrets.randbits",
                side_effect=[777, *range(778, 2_000)],
            ):
                fresh_path, fresh = create_source_sketch(
                    song,
                    sketch["intent"],
                    render_visual_preview=False,
                )
            self.assertNotEqual(fresh_path, manifest_path)
            self.assertNotEqual(fresh["randomness"]["seed"], 777)
            self.assertTrue(fresh["randomness"]["novelty"]["enforced"])
            self.assertEqual(fresh["randomness"]["novelty"]["prior_fingerprints_checked"], 1)
            self.assertGreaterEqual(fresh["randomness"]["novelty"]["collision_rejections"], 1)
            self.assertNotEqual(
                fresh["randomness"]["creative_fingerprint"],
                sketch["randomness"]["creative_fingerprint"],
            )
            self.assertNotEqual(
                fresh["outputs"]["mix_score_sha256"], sketch["outputs"]["mix_score_sha256"]
            )

    def test_explicit_conversation_and_loop_shapes_repeat_without_warping_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            guitar = root / "guitar.wav"
            voices = root / "voices.wav"
            tone_wav(guitar, 196)
            tone_wav(voices, 294)
            _, run = create_song_run(
                "Two Turn Room",
                "A guitar call, a family answer, and a spoken loop that can leave gaps.",
                root=root / "songs",
                seed=321,
                recordings=[("guitar call", guitar), ("family voices", voices)],
                render_visual_preview=False,
            )
            song = root / "songs" / "two-turn-room"
            raw_digests = {
                path: sha256(path) for path in (song / "recordings" / "raw").glob("*.wav")
            }

            conversation_path, conversation = create_source_sketch(
                song,
                "Let the guitar call twice and let the family answer each turn.",
                seed=991,
                include_bed=False,
                shape="call-response",
                render_visual_preview=False,
            )
            self.assertEqual(conversation["arrangement"]["shape"], "call-response")
            self.assertTrue(conversation["arrangement"]["repetition_is_explicit"])
            self.assertTrue(conversation["arrangement"]["excerpting_is_explicit"])
            self.assertEqual(conversation["arrangement"]["occurrences"], 4)
            self.assertEqual(
                {source["relationship_role"] for source in conversation["sources"]},
                {"call", "answer"},
            )
            relationship_starts = {
                source["relationship_role"]: source["placements"][0]["start_bars"]
                for source in conversation["sources"]
            }
            self.assertEqual(
                relationship_starts["answer"] - relationship_starts["call"], 2
            )
            for source in conversation["sources"]:
                self.assertEqual(len(source["placements"]), 2)
                self.assertEqual(
                    source["placements"][1]["start_bars"]
                    - source["placements"][0]["start_bars"],
                    4,
                )
                self.assertIn("conversational turn", source["player_intent"])
            conversation_score = json.loads(
                (song / conversation["paths"]["mix_score"]).read_text()
            )
            self.assertEqual(len(conversation_score["tracks"]), 4)
            self.assertEqual(conversation_score["source_sketch"]["shape"], "call-response")
            verify_source_sketch(song, conversation_path)
            conversation_context = build_agent_context(song, verify=True)
            self.assertEqual(
                conversation_context["recent_source_sketches"][0]["arrangement"]["shape"],
                "call-response",
            )
            self.assertEqual(
                len(conversation_context["recent_source_sketches"][0]["sources"][0]["placements"]),
                2,
            )

            loop_path, loop = create_source_sketch(
                song,
                "Let each complete phrase recur as an ostinato while its performed length stays untouched.",
                seed=992,
                include_bed=False,
                shape="loop",
                render_visual_preview=False,
            )
            self.assertEqual(loop["arrangement"]["shape"], "loop")
            self.assertGreater(loop["arrangement"]["occurrences"], 4)
            for source in loop["sources"]:
                self.assertGreater(len(source["placements"]), 2)
                self.assertTrue(all(
                    placement["duration_seconds"] == 0.3
                    for placement in source["placements"]
                ))
                starts = [placement["start_bars"] for placement in source["placements"]]
                self.assertEqual(len(set(b - a for a, b in zip(starts, starts[1:]))), 1)
                self.assertIn("without time-stretching", source["player_intent"])
            self.assertEqual({path: sha256(path) for path in raw_digests}, raw_digests)
            verify_source_sketch(song, loop_path)
            shaped_status = song_status(song, verify=True)["inventory"]["source_sketches"]
            self.assertEqual(shaped_status["shapes"]["call-response"], 1)
            self.assertEqual(shaped_status["shapes"]["loop"], 1)
            production_map = (song / run["paths"]["production_map_dot"]).read_text()
            self.assertIn("loop · seed 992", production_map)

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
