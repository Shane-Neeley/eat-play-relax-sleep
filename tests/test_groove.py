import json
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.groove import (
    create_groove_development,
    review_groove,
    verify_groove_development,
)
from eprs.cli import parser
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.rhythm import observe_rhythm, verify_rhythm_observation
from eprs.system import new_song, sha256, song_status
from tests.test_rhythm import boom_clap_wav


def groove_spec(observation: Path, song: Path) -> dict:
    return {
        "schema": "eprs.groove/v1",
        "title": "Spoken porch pocket",
        "intent": "Hear the spoken low-high exchange as a drummer-ready call and response.",
        "observation": str(observation.relative_to(song)),
        "player_brief": {
            "meter_and_tempo": "4/4 around 120 BPM, with the spoken attacks heard as quarter-note landmarks.",
            "subdivision_and_feel": "Straight eighth-note body with sixteenth-note space available; do not fill every opening.",
            "backbeat_or_answer": "Let the bright clap gesture answer on 2 and 4 without making it harsher.",
            "bass_drum_or_low_voice": "Place the round boom on 1 and 3 as the grounded call.",
            "timekeeping_voice": "No continuous timekeeping voice in this first audition; hear the call and answer alone.",
            "dynamics": "The first boom establishes normal weight; keep the following answers conversational.",
            "orchestration": "Use a dry low drum and a compact handclap-like answer for the prototype.",
            "phrase_shape": "One bar: low call, bright answer, low call, bright answer, then breathe.",
            "pocket": "Stay close to the spoken spacing; do not manufacture looseness from random offsets.",
            "listening_question": "Does the synthetic low-high exchange preserve the bodily meaning of the spoken phrase?",
            "preserve": [
                "the alternating low and bright gestures",
                "the half-second spacing and unfilled space between attacks",
            ],
            "avoid": [
                "automatic kick/snare replacement claims",
                "extra hi-hat subdivisions before the core relationship is heard",
            ],
        },
        "prototype": {
            "tempo": 118,
            "meter": {"numerator": 4, "denominator": 4},
            "resolution": 16,
            "bars": 1,
            "swing": 0.5,
            "seed": 19,
            "anchor_event_id": 1,
            "voices": [{
                "id": "low-call",
                "kind": "kick",
                "role": "round grounded call",
                "player_instruction": "Play the boom as a short grounded call on 1 and 3.",
                "pattern": "X.......x.......",
                "gain": 0.42,
                "pan": 0,
                "offset_ms": 0,
                "humanize_ms": 0,
            }, {
                "id": "bright-answer",
                "kind": "clap",
                "role": "bright conversational answer",
                "player_instruction": "Answer compactly on 2 and 4; leave the surrounding air empty.",
                "pattern": "....x.......x...",
                "gain": 0.28,
                "pan": 0.08,
                "offset_ms": 0,
                "humanize_ms": 0,
            }],
        },
        "event_interpretations": [{
            "event_id": 1, "disposition": "pattern", "voice": "low-call",
            "bar": 1, "step": 0, "count": "1",
            "interpretation": "Hear the first low gesture as the phrase downbeat.",
            "timing_intent": "Anchor the grid here without moving the source performance.",
        }, {
            "event_id": 2, "disposition": "pattern", "voice": "bright-answer",
            "bar": 1, "step": 4, "count": "2",
            "interpretation": "Hear the bright gesture as the answer on beat 2.",
            "timing_intent": "Preserve its measured relationship to the first boom as evidence.",
        }, {
            "event_id": 3, "disposition": "pattern", "voice": "low-call",
            "bar": 1, "step": 8, "count": "3",
            "interpretation": "Repeat the grounded call on beat 3.",
            "timing_intent": "Do not use humanize to imitate the original timing.",
        }, {
            "event_id": 4, "disposition": "pattern", "voice": "bright-answer",
            "bar": 1, "step": 12, "count": "4",
            "interpretation": "Close the bar with the second bright answer.",
            "timing_intent": "Leave the following space open.",
        }],
        "alternatives": [{
            "name": "Half-time landmarks",
            "description": "Hear each low-high pair across a slower two-beat span before choosing a pulse.",
        }, {
            "name": "Free call and response",
            "description": "Keep the four attacks unmetered and let a drummer answer only after the phrase.",
        }],
    }


class GrooveDevelopmentTests(unittest.TestCase):
    def _setup(self, root: Path) -> tuple[Path, Path, Path, dict]:
        song = new_song(root / "songs", "Spoken Groove").resolve()
        source = root / "boom-clap.wav"
        boom_clap_wav(source)
        observation, _ = observe_rhythm(
            source,
            song,
            "spoken pocket",
            note="Boom, clap, boom, clap; preserve the space before adding a drummer response.",
        )
        spec = root / "groove.json"
        score = groove_spec(observation, song)
        spec.write_text(json.dumps(score))
        return song, source, observation, {"path": spec, "score": score}

    def test_authored_interpretation_preserves_offsets_and_renders_audition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, source, observation, setup = self._setup(root)
            source_digest = sha256(source)
            observation_digest = sha256(observation)

            manifest, record = create_groove_development(setup["path"], song)

            self.assertEqual(record["schema"], "eprs.groove-development/v1")
            self.assertEqual(sha256(source), source_digest)
            self.assertEqual(sha256(observation), observation_digest)
            self.assertFalse(record["interpretation_limits"]["source_audio_modified"])
            self.assertFalse(record["interpretation_limits"]["automatic_quantization"])
            self.assertFalse(record["interpretation_limits"]["automatic_role_assignment"])
            self.assertTrue(record["interpretation_limits"]["prototype_grid_quantized"])
            self.assertTrue(record["interpretation_limits"]["prototype_is_one_authored_interpretation"])
            assignments = record["recipe"]["event_interpretations"]
            self.assertEqual([item["count"] for item in assignments], ["1", "2", "3", "4"])
            self.assertAlmostEqual(assignments[0]["performed_minus_nominal_grid_ms"], 0, delta=0.1)
            self.assertAlmostEqual(assignments[1]["performed_minus_nominal_grid_ms"], -8.475, delta=1)
            self.assertAlmostEqual(assignments[3]["performed_minus_nominal_grid_ms"], -25.424, delta=1)
            beat = song / record["outputs"]["beatscript"]["path"]
            audio = song / record["outputs"]["audio_prototype"]["path"]
            self.assertIn("one explicit grid interpretation", beat.read_text())
            with wave.open(str(audio), "rb") as wav:
                self.assertEqual(wav.getframerate(), 48_000)
                self.assertEqual(wav.getnchannels(), 2)
            with self.assertRaisesRegex(ValueError, "complete-listen keep decision"):
                verify_groove_development(song, manifest, require_approval=True)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["invalid_rhythm_observations"], 0)
            self.assertEqual(status["inventory"]["groove_developments"]["total"], 1)
            self.assertEqual(status["inventory"]["groove_developments"]["pending"], 1)
            context = build_agent_context(song, verify=True)
            self.assertEqual(context["recent_rhythm_observations"][0]["events"][0]["id"], 1)
            self.assertEqual(
                context["recent_groove_developments"][0]["prototype"]["voices"][0]["id"],
                "low-call",
            )
            self.assertIn(
                "## Drummer-facing groove developments",
                render_agent_context_markdown(context),
            )

            note = "Listened to the complete prototype; the low-high relationship and open space carry the spoken idea."
            lock = manifest.parent / ".groove-review.lock"
            lock.write_text("another reviewer")
            with self.assertRaisesRegex(FileExistsError, "locked by another process"):
                review_groove(song, manifest, note, "keep")
            lock.unlink()
            review_groove(song, manifest, note, "keep")
            verify_groove_development(song, manifest, require_approval=True)
            reviewed_status = song_status(song, verify=True)
            self.assertEqual(reviewed_status["inventory"]["groove_developments"]["pending"], 0)
            self.assertEqual(reviewed_status["inventory"]["groove_developments"]["keep"], 1)
            repeated_manifest, repeated = create_groove_development(setup["path"], song)
            self.assertEqual(repeated_manifest, manifest)
            self.assertEqual(repeated["review"]["decision"], "keep")

    def test_requires_explicit_complete_event_mapping_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, _, observation, setup = self._setup(root)
            incomplete = dict(setup["score"])
            incomplete["event_interpretations"] = setup["score"]["event_interpretations"][:-1]
            incomplete_spec = root / "incomplete.json"
            incomplete_spec.write_text(json.dumps(incomplete))
            with self.assertRaisesRegex(ValueError, "cover every observed event"):
                create_groove_development(incomplete_spec, song)

            rest = json.loads(json.dumps(setup["score"]))
            rest["event_interpretations"][0]["step"] = 1
            rest_spec = root / "rest.json"
            rest_spec.write_text(json.dumps(rest))
            with self.assertRaisesRegex(ValueError, "maps to a rest"):
                create_groove_development(rest_spec, song)

            manifest, _ = create_groove_development(setup["path"], song)
            original_observation = observation.read_bytes()
            changed = json.loads(observation.read_text())
            changed["events"][1]["time_seconds"] += 0.1
            observation.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "result id|observation binding|recipe"):
                verify_groove_development(song, manifest)
            observation.write_bytes(original_observation)
            verify_groove_development(song, manifest)

            changed = json.loads(manifest.read_text())
            changed["authority"]["upload_authorized"] = True
            manifest.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "authority record"):
                verify_groove_development(song, manifest)

    def test_observation_verifier_rejects_identity_and_source_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, _, observation, setup = self._setup(root)
            verify_rhythm_observation(song, observation)
            original = observation.read_bytes()
            report = json.loads(observation.read_text())
            report["analysis_id"] = "0" * 64
            observation.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "analysis id"):
                verify_rhythm_observation(song, observation)

            observation.write_bytes(original)
            report = json.loads(observation.read_text())
            report["events"][0]["time_seconds"] += 0.05
            observation.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "result id"):
                verify_rhythm_observation(song, observation)

            observation.write_bytes(original)
            legacy = json.loads(observation.read_text())
            legacy["schema"] = "eprs.rhythm-observation/v1"
            legacy.pop("recipe")
            legacy.pop("result_id")
            observation.write_text(json.dumps(legacy))
            verify_rhythm_observation(song, observation)
            with self.assertRaisesRegex(ValueError, "result-bound rhythm observation"):
                create_groove_development(setup["path"], song)

            observation.write_bytes(original)
            source_path = song / json.loads(observation.read_text())["source"]["path"]
            with source_path.open("ab") as changed:
                changed.write(b"drift")
            with self.assertRaisesRegex(ValueError, "source checksum"):
                verify_rhythm_observation(song, observation)

    def test_cli_exposes_add_show_and_review(self):
        add = parser().parse_args([
            "groove", "add", "code/groove.json", "--song", "songs/study",
        ])
        show = parser().parse_args([
            "groove", "show", "notes/grooves/study/id", "--song", "songs/study",
        ])
        review = parser().parse_args([
            "groove", "review", "notes/grooves/study/id", "--song", "songs/study",
            "--decision", "keep", "--listening-note", "Listened through.",
        ])
        self.assertEqual(add.groove_command, "add")
        self.assertEqual(show.groove_command, "show")
        self.assertEqual(review.groove_command, "review")


if __name__ == "__main__":
    unittest.main()
