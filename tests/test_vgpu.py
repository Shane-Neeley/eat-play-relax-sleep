import math
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from eprs.vgpu import build_audio_controls, render_vgpu
from eprs.visuals import compile_prompt


class VgpuTests(unittest.TestCase):
    def _audio(self, folder: str) -> Path:
        path = Path(folder) / "tone.wav"
        frames = []
        for index in range(9_600):
            sample = int(12_000 * math.sin(2 * math.pi * 110 * index / 48_000))
            frames.append(struct.pack("<hh", sample, sample))
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(48_000)
            handle.writeframes(b"".join(frames))
        return path

    def test_audio_controls_are_deterministic_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = self._audio(folder)
            first = build_audio_controls(audio, duration=0.2)
            second = build_audio_controls(audio, duration=0.2)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "eprs.vgpu-audio-controls/v1")
        self.assertEqual(len(first["frames"]), 6)
        for frame in first["frames"]:
            for key in ("energy", "onset", "bass", "mids", "highs"):
                self.assertGreaterEqual(frame[key], 0.0)
                self.assertLessEqual(frame[key], 1.0)

    def test_vgpu_refuses_photo_scores_instead_of_dropping_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            spec = compile_prompt("field recording of a bird call", "Field", 12)
            spec["photographs"] = [{"path": "photo.jpg"}]
            score = root / "score.json"
            score.write_text(json.dumps(spec))
            audio = root / "audio.wav"
            audio.touch()
            with self.assertRaisesRegex(ValueError, "does not stage"):
                render_vgpu(score, audio, root / "film.mp4")


if __name__ == "__main__":
    unittest.main()
