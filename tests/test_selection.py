from array import array
import json
import math
from pathlib import Path
import tempfile
import unittest
import wave

from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, seconds: float = 0.1, rate: int = 48_000):
    samples = array("h", (
        round(math.sin(2 * math.pi * 220 * frame / rate) * 10_000)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def tone_wav_24(path: Path, seconds: float = 0.1, rate: int = 44_100):
    frames = bytearray()
    for frame in range(round(seconds * rate)):
        sample = round(math.sin(2 * math.pi * 330 * frame / rate) * 2_000_000)
        frames.extend(sample.to_bytes(3, byteorder="little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(3)
        wav.setframerate(rate)
        wav.writeframes(frames)


class SelectionTests(unittest.TestCase):
    def test_external_take_is_ingested_selected_looped_and_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Guitar Loop")
            source = root / "guitar-line.wav"
            tone_wav(source)
            source_digest = sha256(source)

            selected, sidecar = select_audio(
                source,
                song,
                "Guitar loop",
                start=0.01,
                duration=0.04,
                repeat=3,
                crossfade_ms=5,
                note="Let the pick attack recur; do not quantize within the phrase.",
            )

            self.assertEqual(sha256(source), source_digest)
            self.assertTrue(selected.is_file())
            self.assertTrue(sidecar.is_file())
            with wave.open(str(selected), "rb") as wav:
                self.assertEqual(wav.getframerate(), 48_000)
                self.assertEqual(wav.getsampwidth(), 2)
                self.assertAlmostEqual(wav.getnframes() / wav.getframerate(), 0.11, places=3)

            metadata = json.loads(sidecar.read_text())
            self.assertEqual(metadata["schema"], "eprs.audio-selection/v1")
            self.assertEqual(metadata["selection"]["repeat"], 3)
            self.assertFalse(metadata["processing"]["automatic_normalization"])
            self.assertFalse(metadata["processing"]["time_stretch"])
            self.assertIn("asetpts=PTS-STARTPTS[out]", metadata["processing"]["filter"])
            self.assertIn("atrim=start_sample=480:end_sample=2400", metadata["processing"]["filter"])
            self.assertIn("afade=t=in", metadata["processing"]["filter"])
            self.assertIn("amix=inputs=3", metadata["processing"]["filter"])
            self.assertEqual(metadata["output"]["sha256"], sha256(selected))
            raw = [
                path for path in (song / "recordings" / "raw").rglob("*")
                if path.is_file() and not path.name.endswith(".json")
            ]
            self.assertEqual(len(raw), 1)
            self.assertEqual(sha256(raw[0]), source_digest)
            self.assertEqual(song_status(song, verify=True)["inventory"]["selected_recordings"], 1)

            repeated_selection, repeated_sidecar = select_audio(
                source,
                song,
                "Guitar loop",
                start=0.01,
                duration=0.04,
                repeat=3,
                crossfade_ms=5,
                note="Let the pick attack recur; do not quantize within the phrase.",
            )
            self.assertEqual(repeated_selection, selected)
            self.assertEqual(repeated_sidecar, sidecar)

            with selected.open("ab") as handle:
                handle.write(b"drift")
            drifted = song_status(song, verify=True)
            self.assertIn("Checksum mismatch", " ".join(drifted["attention"]))

    def test_selection_rejects_invalid_time_and_crossfade(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Selection Limits")
            source = root / "chime.wav"
            tone_wav(source)
            with self.assertRaisesRegex(ValueError, "duration"):
                select_audio(source, song, "Chime", 0, 0)
            with self.assertRaisesRegex(ValueError, "requires repeat"):
                select_audio(source, song, "Chime", 0, 0.05, crossfade_ms=2)
            with self.assertRaisesRegex(ValueError, "exceeds source"):
                select_audio(source, song, "Chime", 0.09, 0.05)

    def test_pcm_bit_depth_and_sample_rate_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Twenty Four Bit Voice")
            source = root / "voice-24bit.wav"
            tone_wav_24(source)

            selected, sidecar = select_audio(source, song, "Family voice", 0.01, 0.05)

            metadata = json.loads(sidecar.read_text())
            output_stream = metadata["output"]["probe"]["streams"][0]
            self.assertEqual(output_stream["codec_name"], "pcm_s24le")
            self.assertEqual(output_stream["bits_per_sample"], 24)
            self.assertEqual(output_stream["sample_rate"], "44100")
            self.assertEqual(metadata["processing"]["output_codec"], "pcm_s24le")
            self.assertEqual(metadata["processing"]["sample_rate"], 44_100)


if __name__ == "__main__":
    unittest.main()
