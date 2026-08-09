from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.master import approve_master, render_master, verify_master_provenance
from eprs.mix import render_mix, review_mix
from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, amplitude: float = 0.3, seconds: float = 0.25):
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * 220 * frame / rate) * amplitude * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def working_mix(
    root: Path,
    song: Path,
    amplitude: float = 0.3,
    copies: int = 1,
    approve: bool = True,
) -> Path:
    source = root / "source.wav"
    tone_wav(source, amplitude)
    selected, _ = select_audio(source, song, "Source", 0, 0.2)
    relative = str(selected.relative_to(song))
    spec = root / f"mix-{copies}.json"
    spec.write_text(json.dumps({
        "schema": "eprs.mix/v1",
        "title": f"Working mix {copies}",
        "intent": "Preserve the source dynamics and expose overlap headroom.",
        "tracks": [
            {"id": f"source-{index}", "path": relative, "duration_seconds": 0.2}
            for index in range(copies)
        ],
    }))
    mix, _ = render_mix(spec, song)
    if approve:
        review_mix(
            song,
            mix,
            "Listened end to end: balance, overlap headroom, edges, and decay are ready for mastering.",
            "keep",
        )
    return mix


class MasterTests(unittest.TestCase):
    def test_master_converts_float_mix_to_verified_24_bit_without_loudness_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Lossless Master")
            mix = working_mix(root, song)
            mix_digest = sha256(mix)
            spec = root / "master.json"
            spec.write_text(json.dumps({
                "schema": "eprs.master/v1",
                "title": "Lossless listening master",
                "intent": "Keep the approved balance and dynamics exactly as mixed.",
                "destination": "lossless archive and YouTube source",
                "source": str(mix.relative_to(song)),
                "gain_db": 0,
                "true_peak_ceiling_dbfs": -1,
                "output": {"sample_rate": 48_000, "bit_depth": 24},
            }))

            destination, sidecar = render_master(spec, song)

            self.assertTrue(destination.is_file())
            self.assertEqual(sha256(mix), mix_digest)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["schema"], "eprs.master-render/v1")
            output_stream = metadata["output"]["probe"]["streams"][0]
            self.assertEqual(output_stream["codec_name"], "pcm_s24le")
            self.assertEqual(output_stream["bits_per_sample"], 24)
            self.assertEqual(output_stream["sample_rate"], "48000")
            self.assertEqual(output_stream["channels"], 2)
            self.assertFalse(metadata["render"]["automatic_normalization"])
            self.assertFalse(metadata["render"]["compression"])
            self.assertFalse(metadata["render"]["limiting"])
            self.assertFalse(metadata["render"]["dither_added"])
            self.assertEqual(metadata["source"]["provenance"]["review_decision"], "keep")
            self.assertTrue(metadata["source"]["provenance"]["sha256"])
            self.assertLessEqual(
                metadata["output"]["analysis"]["loudness"]["true_peak_dbfs"],
                -0.9,
            )
            self.assertEqual(metadata["approval"]["creative_listen_through"], "not recorded by renderer")
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["masters"], 1)
            self.assertEqual(status["inventory"]["masters_pending_listen"], 1)
            self.assertEqual(status["inventory"]["masters_approved"], 0)
            self.assertIn("record creative approval", " ".join(status["next_actions"]))
            self.assertEqual(status["attention"], [])

            master_digest = sha256(destination)
            approved_sidecar = approve_master(
                song,
                destination,
                "Listened end to end: balance, fades, silence, and dynamics are the intended version.",
            )
            self.assertEqual(approved_sidecar.resolve(), sidecar.resolve())
            self.assertEqual(sha256(destination), master_digest)
            approved = json.loads(sidecar.read_text())
            self.assertEqual(approved["approval"]["creative_listen_through"], "approved")
            self.assertEqual(len(approved["approval"]["listening_notes"]), 1)
            approved_status = song_status(song, verify=True)
            self.assertEqual(approved_status["inventory"]["masters_pending_listen"], 0)
            self.assertEqual(approved_status["inventory"]["masters_approved"], 1)
            self.assertNotIn("record creative approval", " ".join(approved_status["next_actions"]))

            repeated_destination, repeated_sidecar = render_master(spec, song)
            self.assertEqual(repeated_destination, destination)
            self.assertEqual(repeated_sidecar, sidecar)

    def test_master_requires_exact_kept_mix_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Mix Approval Gate")
            mix = working_mix(root, song, approve=False)
            spec = root / "master.json"
            spec.write_text(json.dumps({
                "schema": "eprs.master/v1",
                "title": "Approval-bound master",
                "intent": "Only master an exact kept working mix.",
                "destination": "lossless archive",
                "source": str(mix.relative_to(song)),
                "gain_db": 0,
                "true_peak_ceiling_dbfs": -1,
            }))

            with self.assertRaisesRegex(ValueError, "complete-listen keep decision"):
                render_master(spec, song)

            review_mix(song, mix, "Complete listen: balance and headroom are intentionally kept.", "keep")
            master, _ = render_master(spec, song)
            mix_sidecar = mix.with_suffix(mix.suffix + ".json")
            review_mix(song, mix, "A later listen changes the mix decision.", "change")
            self.assertTrue(mix_sidecar.is_file())
            with self.assertRaisesRegex(ValueError, "provenance is missing or changed"):
                verify_master_provenance(song, master)

    def test_master_refuses_over_ceiling_then_accepts_explicit_gain_correction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Peak Guard")
            loud_mix = working_mix(root, song, amplitude=0.9, copies=2)
            spec = root / "peak-guard.json"
            recipe = {
                "schema": "eprs.master/v1",
                "title": "Peak guard master",
                "intent": "Resolve float headroom explicitly without limiting.",
                "destination": "lossless archive",
                "source": str(loud_mix.relative_to(song)),
                "gain_db": 0,
                "true_peak_ceiling_dbfs": -1,
            }
            spec.write_text(json.dumps(recipe))

            with self.assertRaisesRegex(ValueError, "above the declared"):
                render_master(spec, song)

            recipe["gain_db"] = -8
            spec.write_text(json.dumps(recipe))
            _, sidecar = render_master(spec, song)
            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["render"]["explicit_gain_db"], -8)
            self.assertFalse(metadata["render"]["limiting"])
            self.assertLessEqual(
                metadata["output"]["analysis"]["loudness"]["true_peak_dbfs"],
                -1,
            )

    def test_master_rejects_source_outside_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Master Path Safety")
            source = root / "outside.wav"
            tone_wav(source)
            spec = root / "unsafe-master.json"
            spec.write_text(json.dumps({
                "schema": "eprs.master/v1",
                "title": "Unsafe master",
                "intent": "This must stay inside the song.",
                "destination": "test",
                "source": "../../outside.wav",
            }))
            with self.assertRaisesRegex(ValueError, "escapes"):
                render_master(spec, song)


if __name__ == "__main__":
    unittest.main()
