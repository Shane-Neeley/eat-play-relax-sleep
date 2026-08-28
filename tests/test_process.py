from array import array
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from eprs.context import build_agent_context
from eprs.process import render_process, review_processed_stem
from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, seconds: float = 0.25, rate: int = 44_100):
    samples = array("h", (
        round(math.sin(2 * math.pi * 220 * frame / rate) * 8_000)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class ProcessTests(unittest.TestCase):
    def _source(self, root: Path, song: Path) -> Path:
        external = root / "family.wav"
        tone_wav(external)
        selected, _ = select_audio(external, song, "Family voice", 0, 0.2)
        return selected

    def _spec(self, root: Path, song: Path, source: Path, operations: list[dict]) -> Path:
        spec = root / "process.json"
        spec.write_text(json.dumps({
            "schema": "eprs.process/v1",
            "title": "Family answer clarity",
            "role": "Family voices",
            "intent": "Keep the shared room while making the answer readable.",
            "source": str(source.relative_to(song)),
            "operations": operations,
        }))
        return spec

    def test_render_preserves_source_format_and_requires_listening_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Family Processing")
            source = self._source(root, song)
            source_digest = sha256(source)
            spec = self._spec(root, song, source, [
                {"type": "highpass", "intent": "Remove floor movement, not chest.", "frequency_hz": 55},
                {"type": "eq", "intent": "Ease one boxy area.", "frequency_hz": 280, "gain_db": -1.5, "q": 0.8},
                {"type": "fade", "intent": "Avoid a hard edit at the entrance.", "direction": "in", "start_seconds": 0, "duration_seconds": 0.01},
                {"type": "gain", "intent": "Leave arrangement headroom.", "db": -3},
            ])

            stem, sidecar = render_process(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(sha256(source), source_digest)
            self.assertEqual(metadata["schema"], "eprs.process-render/v1")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["codec_name"], "pcm_f32le")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["sample_rate"], "44100")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["channels"], 1)
            self.assertFalse(metadata["render"]["compression"])
            self.assertTrue(all(not metadata["render"][key] for key in (
                "automatic_normalization", "automatic_gain_control", "pitch_correction",
                "time_stretch", "denoise", "limiting",
            )))
            self.assertEqual(metadata["review"]["decision"], "not recorded by renderer")
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["stems"], 1)
            self.assertEqual(status["inventory"]["stems_pending_review"], 1)

            stem_digest = sha256(stem)
            review_processed_stem(song, stem, "Words clearer; room still feels shared.", "keep")
            self.assertEqual(sha256(stem), stem_digest)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["stems_pending_review"], 0)
            self.assertEqual(status["inventory"]["stems_kept"], 1)
            self.assertEqual(render_process(spec, song), (stem, sidecar))

    def test_compressor_is_explicit_and_fully_resolved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Explicit Dynamics")
            source = self._source(root, song)
            spec = self._spec(root, song, source, [{
                "type": "compressor", "intent": "Hold only the shouted answer near the group.",
                "threshold_db": -20, "ratio": 1.8, "attack_ms": 25,
                "release_ms": 300, "makeup_db": 0, "knee": 3, "mix": 0.7,
                "detection": "rms", "link": "average",
            }])
            _, sidecar = render_process(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertTrue(metadata["render"]["compression"])
            self.assertEqual(metadata["operations"][0]["ratio"], 1.8)
            self.assertIn("level-matched", " ".join(metadata["warnings"]))
            self.assertFalse(metadata["render"]["limiting"])
            self.assertFalse(metadata["render"]["automatic_normalization"])

    def test_trim_and_time_stretch_make_an_explicit_beat_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Rattle Pocket")
            source = self._source(root, song)
            source_digest = sha256(source)
            spec = self._spec(root, song, source, [
                {
                    "type": "trim",
                    "intent": "Chop to the bright call-bearing burst without editing the source.",
                    "start_seconds": 0.02,
                    "duration_seconds": 0.16,
                },
                {
                    "type": "time_stretch",
                    "intent": "Slow the burst into the authored pocket without changing its pitch.",
                    "tempo_ratio": 0.8,
                },
                {
                    "type": "fade",
                    "intent": "Remove the edit seam before placing the hit on the grid.",
                    "direction": "in",
                    "start_seconds": 0,
                    "duration_seconds": 0.01,
                },
            ])

            stem, sidecar = render_process(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(sha256(source), source_digest)
            self.assertTrue(metadata["render"]["source_trim"])
            self.assertTrue(metadata["render"]["time_stretch"])
            self.assertEqual([operation["type"] for operation in metadata["operations"]], [
                "trim", "time_stretch", "fade",
            ])
            self.assertAlmostEqual(
                float(metadata["output"]["probe"]["format"]["duration"]),
                0.2,
                delta=0.03,
            )
            self.assertIn("timing was deliberately edited", " ".join(metadata["warnings"]))
            self.assertEqual(song_status(song, verify=True)["inventory"]["stems_pending_review"], 1)
            self.assertTrue(stem.is_file())

    def test_echo_declares_and_verifies_its_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Chime Tail")
            source = self._source(root, song)
            spec = self._spec(root, song, source, [{
                "type": "echo", "intent": "Let the chime answer once into the room.",
                "input_gain": 0.8, "output_gain": 0.7,
                "taps": [{"delay_ms": 80, "decay": 0.3}],
            }])
            _, sidecar = render_process(spec, song)
            duration = float(json.loads(sidecar.read_text())["output"]["probe"]["format"]["duration"])
            self.assertAlmostEqual(duration, 0.28, places=2)

    def test_rejects_implicit_or_unsafe_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Process Limits")
            source = self._source(root, song)
            with self.assertRaisesRegex(ValueError, "at least one"):
                render_process(self._spec(root, song, source, []), song)
            with self.assertRaisesRegex(ValueError, "player-facing intent"):
                render_process(self._spec(root, song, source, [{"type": "gain", "db": -3}]), song)
            with self.assertRaisesRegex(ValueError, "unsupported"):
                render_process(self._spec(root, song, source, [{"type": "normalize", "intent": "Make it loud."}]), song)
            with self.assertRaisesRegex(ValueError, "tempo_ratio"):
                render_process(self._spec(root, song, source, [{
                    "type": "time_stretch", "intent": "Reject an unsafe ratio.", "tempo_ratio": 0.49,
                }]), song)
            with self.assertRaisesRegex(ValueError, "between"):
                render_process(self._spec(root, song, source, [{
                    "type": "trim", "intent": "Reject a slice outside the source.",
                    "start_seconds": 0.2, "duration_seconds": 0.2,
                }]), song)
            with self.assertRaisesRegex(ValueError, "finite"):
                render_process(self._spec(root, song, source, [{"type": "gain", "intent": "Reject NaN.", "db": float("nan")}]), song)

    def test_review_rejects_provenance_that_points_at_another_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Stem Identity")
            source = self._source(root, song)
            spec = self._spec(root, song, source, [
                {"type": "gain", "intent": "Leave room for the answer.", "db": -3},
            ])
            stem, sidecar = render_process(spec, song)
            metadata = json.loads(sidecar.read_text())
            metadata["output"]["path"] = "stems/not-this-file.wav"
            sidecar.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "invalid output path"):
                review_processed_stem(song, stem, "Should not bind to this file.", "keep")

    def test_process_binds_decision_evidence_and_refuses_later_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Evidence Bound Processing")
            source = self._source(root, song)
            phase = song / "notes" / "phase" / "vocal-relationship.json"
            phase.parent.mkdir(parents=True)
            phase.write_text(json.dumps({
                "schema": "eprs.phase-observation/v1",
                "player_language": "The room microphone arrives later; audition unchanged in mono.",
            }))
            spec = self._spec(root, song, source, [
                {"type": "gain", "intent": "Leave room for the unchanged room microphone.", "db": -3},
            ])
            score = json.loads(spec.read_text())
            score["evidence"] = [{
                "id": "vocal relationship",
                "role": "two-microphone phase observation",
                "path": str(phase.relative_to(song)),
                "use": "Preserve the measured room relationship; this recipe does not align or invert it.",
            }]
            spec.write_text(json.dumps(score))

            stem, sidecar = render_process(spec, song)
            metadata = json.loads(sidecar.read_text())
            binding = metadata["recipe"]["evidence"][0]
            self.assertEqual(binding["declared_schema"], "eprs.phase-observation/v1")
            self.assertEqual(binding["sha256"], sha256(phase))
            self.assertEqual(song_status(song, verify=True)["inventory"]["render_evidence"], {
                "bindings": 1, "invalid_renders": 0,
            })
            summary = build_agent_context(song, verify=True)["recent_stems"][0]
            self.assertEqual(summary["evidence"][0]["id"], "vocal-relationship")

            phase.write_text(phase.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "evidence is missing or changed"):
                review_processed_stem(song, stem, "This must not approve stale evidence.", "keep")
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["render_evidence"]["invalid_renders"], 1)
            self.assertIn("Invalid processed-stem evidence", " ".join(status["attention"]))


if __name__ == "__main__":
    unittest.main()
