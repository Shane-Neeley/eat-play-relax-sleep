from array import array
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from eprs.comp import render_comp, review_comp
from eprs.context import build_agent_context
from eprs.system import ingest, new_song, sha256, song_status


def tone_wav(path: Path, frequency: float, rate: int = 48_000, seconds: float = 0.2) -> None:
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 7000)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class CompTests(unittest.TestCase):
    def _sources(self, root: Path, song: Path) -> tuple[Path, Path]:
        first_external = root / "family-one.wav"
        second_external = root / "family-two.wav"
        tone_wav(first_external, 220)
        tone_wav(second_external, 330)
        first, _ = ingest(first_external, song, "family voices", "First answer.")
        second, _ = ingest(second_external, song, "family voices", "Second answer.")
        return first, second

    def _spec(self, root: Path, song: Path, first: Path, second: Path) -> Path:
        spec = root / "comp.json"
        spec.write_text(json.dumps({
            "schema": "eprs.comp/v1",
            "title": "Family answer comp",
            "role": "family voices",
            "intent": "Begin with the intimate answer, let the overlap feel communal, then preserve a breath before the last phrase.",
            "segments": [
                {"id": "intimate-open", "path": str(first.relative_to(song)), "start_seconds": 0.01, "duration_seconds": 0.08, "intent": "Keep the close first word and its breath."},
                {"id": "shared-middle", "path": str(second.relative_to(song)), "start_seconds": 0.04, "duration_seconds": 0.07, "intent": "Use the take where the voices overlap naturally."},
                {"id": "laughing-end", "path": str(first.relative_to(song)), "start_seconds": 0.11, "duration_seconds": 0.06, "intent": "Preserve the released ending and hint of laughter."},
            ],
            "transitions": [
                {"from": "intimate-open", "to": "shared-middle", "type": "crossfade", "duration_seconds": 0.01, "intent": "Let the room overlap hide the edit without changing the internal timing."},
                {"from": "shared-middle", "to": "laughing-end", "type": "silence", "duration_seconds": 0.02, "intent": "Keep a real breath before the final phrase."},
            ],
        }))
        return spec

    def test_comp_preserves_sources_and_declares_every_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Family Comp")
            first, second = self._sources(root, song)
            first_digest, second_digest = sha256(first), sha256(second)
            spec = self._spec(root, song, first, second)

            stem, sidecar = render_comp(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["schema"], "eprs.comp-render/v1")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["codec_name"], "pcm_f32le")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["sample_rate"], "48000")
            self.assertEqual(metadata["output"]["probe"]["streams"][0]["channels"], 1)
            self.assertAlmostEqual(float(metadata["output"]["probe"]["format"]["duration"]), 0.22, places=2)
            self.assertEqual([item["type"] for item in metadata["transitions"]], ["crossfade", "silence"])
            self.assertTrue(all(item["intent"] for item in metadata["segments"]))
            self.assertTrue(all(item["intent"] for item in metadata["transitions"]))
            self.assertTrue(all(not metadata["render"][key] for key in (
                "automatic_normalization", "automatic_gain_control", "pitch_correction",
                "time_stretch", "denoise", "compression", "limiting",
            )))
            self.assertEqual(sha256(first), first_digest)
            self.assertEqual(sha256(second), second_digest)
            self.assertEqual(render_comp(spec, song), (stem, sidecar))

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["stems"], 1)
            self.assertEqual(status["inventory"]["comp_stems"], 1)
            self.assertEqual(status["inventory"]["stems_pending_review"], 1)

            stem_digest = sha256(stem)
            review_comp(song, stem, "The joins disappear into the room, and the held breath still feels intentional.", "keep")
            self.assertEqual(sha256(stem), stem_digest)
            self.assertEqual(json.loads(sidecar.read_text())["review"]["decision"], "keep")
            reviewed_status = song_status(song, verify=True)
            self.assertEqual(reviewed_status["inventory"]["stems_pending_review"], 0)
            self.assertEqual(reviewed_status["inventory"]["stems_kept"], 1)
            context = build_agent_context(song, verify=True)
            stem_summary = context["recent_stems"][0]
            self.assertEqual(stem_summary["kind"], "performance-comp")
            self.assertEqual(stem_summary["review_decision"], "keep")
            self.assertEqual([item["type"] for item in stem_summary["transitions"]], ["crossfade", "silence"])
            self.assertFalse(context["limits"]["binary_media_embedded"])

    def test_requires_explicit_adjacent_transitions_and_safe_regions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Comp Limits")
            first, second = self._sources(root, song)
            spec = self._spec(root, song, first, second)
            score = json.loads(spec.read_text())
            score["transitions"][0]["to"] = "laughing-end"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "must connect"):
                render_comp(spec, song)
            score["transitions"][0]["to"] = "shared-middle"
            score["segments"][0]["duration_seconds"] = 1
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "exceeds"):
                render_comp(spec, song)

    def test_mixed_sample_rates_require_explicit_output_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Comp Format")
            first_external = root / "one.wav"
            second_external = root / "two.wav"
            tone_wav(first_external, 220, rate=44_100)
            tone_wav(second_external, 330, rate=48_000)
            first, _ = ingest(first_external, song, "voice", "44.1 kHz")
            second, _ = ingest(second_external, song, "voice", "48 kHz")
            spec = root / "mixed.json"
            score = {
                "schema": "eprs.comp/v1", "title": "Mixed rates", "role": "voice",
                "intent": "Make the required conversion choice visible.",
                "segments": [
                    {"id": "one", "path": str(first.relative_to(song)), "duration_seconds": 0.05, "intent": "First phrase."},
                    {"id": "two", "path": str(second.relative_to(song)), "duration_seconds": 0.05, "intent": "Second phrase."},
                ],
                "transitions": [{"from": "one", "to": "two", "type": "cut", "intent": "An audible direct edit."}],
            }
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "requires output.sample_rate"):
                render_comp(spec, song)
            score["output"] = {"sample_rate": 48_000, "channels": 1}
            spec.write_text(json.dumps(score))
            _, sidecar = render_comp(spec, song)
            self.assertTrue(json.loads(sidecar.read_text())["render"]["sample_rate_conversion"])


if __name__ == "__main__":
    unittest.main()
