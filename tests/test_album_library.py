import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_album_library import snapshot, write_snapshot


class AlbumLibraryTests(unittest.TestCase):
    def setup_root(self, root):
        album = root / "albums" / "test-album"
        album.mkdir(parents=True)
        (album / "album.json").write_text(json.dumps({"title": "Test", "tracks": []}))
        # Legacy nested handoff, absent from the album index.
        handoff = album / "one" / "one"
        handoff.mkdir(parents=True)
        (handoff / "metadata.json").write_text('{"title":"One"}')
        for slug in ("one", "two"):
            song = root / "songs" / slug
            song.mkdir(parents=True)
            (song / "song.json").write_text(json.dumps({"title": slug, "status": "seed"}))
            source = song / "references" / "inaturalist-audio" / "call"
            source.mkdir(parents=True)
            media = source / "call.mp3"
            media.write_bytes(b"immutable-test-source")
            (source / "call.mp3.json").write_text(json.dumps({
                "schema": "eprs.inaturalist-audio/v1",
                "source": {"url": "https://www.inaturalist.org/observations/1", "taxon": {}},
                "sound": {"id": 7, "license_code": "cc-by", "attribution": "Recorder"},
                "output": {"path": str(media.relative_to(song)),
                           "sha256": hashlib.sha256(media.read_bytes()).hexdigest()},
            }))

    def test_discovers_nested_favorite_deduplicates_and_does_not_approve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_root(root)
            data = snapshot(root, "test-album", [])
            self.assertEqual(len(data["songs"]), 2)
            self.assertTrue(data["songs"][0]["album_candidate"])
            self.assertFalse(data["songs"][0]["handoff"]["indexed"])
            self.assertEqual(len(data["sounds"]), 1)
            self.assertEqual(len(data["sounds"][0]["copies"]), 2)
            self.assertFalse(data["sounds"][0]["source_use_eligible"])
            self.assertFalse(data["warnings"])
            out = root / "snapshot"
            write_snapshot(data, out)
            with self.assertRaises(FileExistsError):
                write_snapshot(data, out)

    def test_corruption_missing_copy_and_license_conflict_are_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_root(root)
            media = root / "songs/two/references/inaturalist-audio/call/call.mp3"
            media.write_bytes(b"changed")
            sidecar = media.with_suffix(".mp3.json")
            detail = json.loads(sidecar.read_text())
            detail["sound"]["license_code"] = "cc-by-nc"
            sidecar.write_text(json.dumps(detail))
            data = snapshot(root, "test-album", [])
            self.assertTrue(data["sounds"][0]["provenance_conflict"])
            self.assertEqual(data["sounds"][0]["copies"][1]["integrity"], "missing-or-mismatch")
            media.unlink()
            self.assertIsNone(snapshot(root, "test-album", [])["sounds"][0]["copies"][1]["actual_sha256"])

    def test_inventories_external_audio_with_provider_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_root(root)
            workspace = root / "songs/one"
            folder = workspace / "references/external-audio/field-recording"
            folder.mkdir(parents=True)
            media = folder / "recording.wav"
            media.write_bytes(b"external-test-source")
            (folder / "recording.wav.json").write_text(json.dumps({
                "schema": "eprs.external-audio/v1",
                "source": {"provider": "FieldArchive", "url": "https://example.test/recording",
                           "kind": "licensed field recording"},
                "sound": {"id": "abc", "license_code": "cc-by", "attribution": "Recorder"},
                "output": {"path": str(media.relative_to(workspace)),
                           "sha256": hashlib.sha256(media.read_bytes()).hexdigest()},
            }))
            data = snapshot(root, "test-album", [])
            external = next(sound for sound in data["sounds"] if sound["id"] == "fieldarchive:abc")
            self.assertEqual(external["provider"], "fieldarchive")
            self.assertEqual(external["source_kind"], "licensed field recording")
            self.assertEqual(external["copies"][0]["integrity"], "verified")

    def test_escape_and_missing_album_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.setup_root(root)
            with self.assertRaises(ValueError):
                snapshot(root, "../test-album", [])
            with self.assertRaises(ValueError):
                snapshot(root, "missing", [])
            with self.assertRaises(ValueError):
                snapshot(root, "test-album", [Path("../outside")])
            sidecar = root / "songs/one/references/inaturalist-audio/call/call.mp3.json"
            detail = json.loads(sidecar.read_text())
            detail["output"]["path"] = "../../outside.mp3"
            sidecar.write_text(json.dumps(detail))
            data = snapshot(root, "test-album", [])
            self.assertTrue(any("escaping media" in x for x in data["warnings"]))


if __name__ == "__main__":
    unittest.main()
