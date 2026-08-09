from pathlib import Path
import tempfile
import unittest

from eprs.frontdoor import expose_current_media, verify_current_media
from eprs.system import new_song, song_status
from tests.test_system import tiny_wav


class FrontDoorTests(unittest.TestCase):
    def test_exposes_and_repoints_current_media_without_copying(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Visible Song")
            first = song / "experiments" / "first.wav"
            second = song / "mixes" / "second.wav"
            tiny_wav(first)
            tiny_wav(second)

            record = expose_current_media(
                song, first, label="First diagnostic", status="diagnostic"
            )
            listen = song / "_LISTEN.wav"
            self.assertTrue(listen.is_symlink())
            self.assertEqual(listen.resolve(), first.resolve())
            self.assertIn("diagnostic starter", (song / "_CHANGE_ME.md").read_text())

            self.assertEqual(
                expose_current_media(song, second, label="Second review", status="review"),
                record,
            )
            self.assertEqual(listen.resolve(), second.resolve())
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            _, current = verify_current_media(song)
            self.assertEqual(current["sources"]["audio"]["path"], "mixes/second.wav")
            self.assertTrue(song_status(song, verify=True)["inventory"]["current_media"]["available"])

            second.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum changed"):
                verify_current_media(song)
            self.assertIn("Invalid current review media", " ".join(song_status(song, verify=True)["attention"]))

    def test_refuses_to_replace_a_user_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Protected Song")
            source = song / "experiments" / "source.wav"
            tiny_wav(source)
            (song / "_LISTEN.wav").write_bytes(b"user file")
            with self.assertRaisesRegex(FileExistsError, "non-link"):
                expose_current_media(song, source, label="Must refuse")
