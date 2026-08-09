from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.mix import render_mix, review_mix, verify_mix_provenance
from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, frequency: float, amplitude: float = 0.25, seconds: float = 0.25):
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * amplitude * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


class MixTests(unittest.TestCase):
    def test_mix_places_balances_and_preserves_sources_without_normalizing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Family Arrangement")
            guitar_source = root / "guitar.wav"
            voice_source = root / "voice.wav"
            tone_wav(guitar_source, 220)
            tone_wav(voice_source, 330)
            guitar, _ = select_audio(guitar_source, song, "Guitar phrase", 0, 0.2)
            voice, _ = select_audio(voice_source, song, "Family voice", 0, 0.2)
            guitar_digest = sha256(guitar)
            voice_digest = sha256(voice)
            spec = root / "mix.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Family answer study",
                "intent": "The guitar opens; the family voice enters into its remaining air.",
                "tracks": [
                    {
                        "id": "guitar",
                        "role": "opening phrase",
                        "intent": "Stay left of center and keep the attack.",
                        "path": str(guitar.relative_to(song)),
                        "duration_seconds": 0.1,
                        "gain_db": -6,
                        "pan": -0.25,
                        "fade_out_ms": 5,
                    },
                    {
                        "id": "family-voice",
                        "role": "answer",
                        "intent": "Enter after the guitar breath without tuning.",
                        "path": str(voice.relative_to(song)),
                        "start_seconds": 0.05,
                        "duration_seconds": 0.1,
                        "gain_db": -8,
                        "pan": 0.15,
                        "fade_in_ms": 5,
                    },
                ],
            }))

            destination, sidecar = render_mix(spec, song)

            self.assertTrue(destination.is_file())
            self.assertTrue(sidecar.is_file())
            self.assertEqual(sha256(guitar), guitar_digest)
            self.assertEqual(sha256(voice), voice_digest)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["schema"], "eprs.mix-render/v1")
            self.assertEqual(metadata["render"]["output_codec"], "pcm_f32le")
            self.assertFalse(metadata["render"]["automatic_normalization"])
            self.assertFalse(metadata["render"]["compression"])
            self.assertFalse(metadata["render"]["limiting"])
            output_probe = metadata["output"]["probe"]
            self.assertEqual(output_probe["streams"][0]["codec_name"], "pcm_f32le")
            self.assertEqual(output_probe["streams"][0]["channels"], 2)
            self.assertAlmostEqual(float(output_probe["format"]["duration"]), 0.15, places=3)
            self.assertEqual(metadata["warnings"], [])
            self.assertEqual(metadata["review"]["decision"], "not recorded by renderer")
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["mixes"], 1)
            self.assertEqual(status["inventory"]["mixes_pending_review"], 1)
            self.assertEqual(status["attention"], [])

            mix_digest = sha256(destination)
            reviewed_sidecar = review_mix(
                song,
                destination,
                "Listened end to end: the entrance, balance, overlap headroom, decay, and silence work.",
                "keep",
            )
            self.assertEqual(reviewed_sidecar.resolve(), sidecar.resolve())
            self.assertEqual(sha256(destination), mix_digest)
            reviewed = json.loads(sidecar.read_text())
            self.assertEqual(reviewed["review"]["decision"], "keep")
            self.assertEqual(len(reviewed["review"]["listening_notes"]), 1)
            verify_mix_provenance(song, destination, require_approval=True)
            reviewed_status = song_status(song, verify=True)
            self.assertEqual(reviewed_status["inventory"]["mixes_pending_review"], 0)
            self.assertEqual(reviewed_status["inventory"]["mixes_kept"], 1)
            context = build_agent_context(song, verify=True)
            self.assertEqual(context["recent_mixes"][0]["review_decision"], "keep")
            self.assertEqual(context["recent_mixes"][0]["tracks"][0]["role"], "opening phrase")
            self.assertIn("## Recent working mixes", render_agent_context_markdown(context))

            repeated_destination, repeated_sidecar = render_mix(spec, song)
            self.assertEqual(repeated_destination, destination)
            self.assertEqual(repeated_sidecar, sidecar)
            self.assertEqual(json.loads(sidecar.read_text())["review"]["decision"], "keep")
            self.assertEqual(
                review_mix(
                    song,
                    destination,
                    "Listened end to end: the entrance, balance, overlap headroom, decay, and silence work.",
                    "keep",
                ).resolve(),
                sidecar.resolve(),
            )
            self.assertEqual(len(json.loads(sidecar.read_text())["review"]["listening_notes"]), 1)
            review_mix(song, destination, "The family answer needs another balance pass.", "change")
            review_mix(
                song,
                destination,
                "Listened end to end: the entrance, balance, overlap headroom, decay, and silence work.",
                "keep",
            )
            restored = json.loads(sidecar.read_text())["review"]
            self.assertEqual(restored["decision"], "keep")
            self.assertEqual(len(restored["listening_notes"]), 2)

    def test_float_working_mix_reports_over_zero_peak_without_clipping_recipe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Headroom Warning")
            source = root / "loud.wav"
            tone_wav(source, 110, amplitude=0.9)
            selected, _ = select_audio(source, song, "Loud source", 0, 0.2)
            relative = str(selected.relative_to(song))
            spec = root / "loud-mix.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Headroom study",
                "intent": "Expose the overlap level; do not hide it with a limiter.",
                "tracks": [
                    {"id": "one", "path": relative, "duration_seconds": 0.1},
                    {"id": "two", "path": relative, "duration_seconds": 0.1},
                ],
            }))

            _, sidecar = render_mix(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertGreater(metadata["output"]["analysis"]["loudness"]["true_peak_dbfs"], 0)
            self.assertIn("lower explicit track gains", " ".join(metadata["warnings"]))
            status = song_status(song, verify=True)
            self.assertIn("lower explicit track gains", " ".join(status["attention"]))

    def test_mix_review_rechecks_audio_and_source_checksums(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Mix Review Integrity")
            source = root / "source.wav"
            tone_wav(source, 220)
            selected, _ = select_audio(source, song, "Source", 0, 0.1)
            spec = root / "mix.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Integrity mix",
                "intent": "Keep source and review evidence inseparable.",
                "tracks": [{"id": "source", "path": str(selected.relative_to(song))}],
            }))
            destination, _ = render_mix(spec, song)

            with destination.open("ab") as changed:
                changed.write(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum has changed"):
                review_mix(song, destination, "This must not attach to changed audio.", "keep")

    def test_mix_rejects_paths_outside_the_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Path Safety")
            source = root / "outside.wav"
            tone_wav(source, 440)
            spec = root / "unsafe.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Unsafe",
                "intent": "This should not escape the project.",
                "tracks": [{"id": "outside", "path": "../../outside.wav"}],
            }))
            with self.assertRaisesRegex(ValueError, "escapes"):
                render_mix(spec, song)

    def test_mix_rejects_non_finite_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Finite Controls")
            source = root / "source.wav"
            tone_wav(source, 440)
            selected, _ = select_audio(source, song, "Source", 0, 0.1)
            spec = root / "nan.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Finite",
                "intent": "Reject controls that FFmpeg cannot interpret safely.",
                "tracks": [{
                    "id": "source",
                    "path": str(selected.relative_to(song)),
                    "gain_db": float("nan"),
                }],
            }))
            with self.assertRaisesRegex(ValueError, "finite"):
                render_mix(spec, song)

    def test_mix_binds_research_and_detects_recipe_or_evidence_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Evidence Bound Mix")
            source = root / "source.wav"
            tone_wav(source, 440)
            selected, _ = select_audio(source, song, "Source", 0, 0.1)
            research = song / "notes" / "research" / "room-note.json"
            research.parent.mkdir(parents=True)
            original_research = json.dumps({
                "schema": "eprs.research-record/v1",
                "finding": "Leave a full breath after the family answer.",
            })
            research.write_text(original_research)
            spec = root / "mix-evidence.json"
            spec.write_text(json.dumps({
                "schema": "eprs.mix/v1",
                "title": "Evidence mix",
                "intent": "Leave the researched breath after the answer.",
                "evidence": [{
                    "id": "room research",
                    "role": "arrangement research",
                    "path": str(research.relative_to(song)),
                    "use": "The final decay must leave the documented full breath.",
                }],
                "tracks": [{
                    "id": "source", "path": str(selected.relative_to(song)), "gain_db": -6,
                }],
            }))

            mix, sidecar = render_mix(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["recipe"]["evidence"][0]["sha256"], sha256(research))
            research.write_text(original_research + "\n")
            with self.assertRaisesRegex(ValueError, "evidence is missing or changed"):
                review_mix(song, mix, "Do not approve stale evidence.", "keep")

            # Restore evidence, then prove the recipe id protects the binding itself.
            research.write_text(original_research)
            metadata = json.loads(sidecar.read_text())
            metadata["recipe"]["evidence"][0]["use"] = "Tampered use."
            sidecar.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "recipe id does not match"):
                verify_mix_provenance(song, mix)


if __name__ == "__main__":
    unittest.main()
