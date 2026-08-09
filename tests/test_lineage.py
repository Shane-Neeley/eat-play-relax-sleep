from pathlib import Path
import tempfile
import unittest

from eprs.lineage import trace_audio_lineage
from eprs.selection import select_audio
from eprs.system import new_song
from tests.test_session import tone_wav


class AudioLineageTests(unittest.TestCase):
    def test_traces_verified_selection_to_raw_and_retains_unknown_leaf(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lineage")
            source = root / "performance.wav"
            tone_wav(source)
            selected, _ = select_audio(source, song, "performance phrase", 0, 0.05)

            lineage = trace_audio_lineage(song, selected)

            self.assertEqual(lineage["schema"], "eprs.audio-lineage/v1")
            self.assertEqual([record["schema"] for record in lineage["artifacts"]], ["eprs.audio-selection/v1"])
            self.assertEqual(len(lineage["raw_recordings"]), 1)
            self.assertEqual(lineage["untraced_leaves"], [])

            authored = song / "code" / "authored.wav"
            tone_wav(authored, 330)
            unknown = trace_audio_lineage(song, authored)
            self.assertEqual(unknown["raw_recordings"], [])
            self.assertEqual(unknown["untraced_leaves"][0]["reason"], "no supported adjacent provenance")

    def test_rejects_source_drift_and_workspace_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lineage Guard")
            source = root / "performance.wav"
            tone_wav(source)
            selected, _ = select_audio(source, song, "performance phrase", 0, 0.05)
            raw = next((song / "recordings" / "raw").rglob("*.wav"))
            with raw.open("ab") as output:
                output.write(b"drift")

            with self.assertRaisesRegex(ValueError, "checksum is invalid or changed"):
                trace_audio_lineage(song, selected)
            with self.assertRaisesRegex(ValueError, "inside the song"):
                trace_audio_lineage(song, root / "performance.wav")


if __name__ == "__main__":
    unittest.main()
