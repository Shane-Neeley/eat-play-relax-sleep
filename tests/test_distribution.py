import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eprs.clearance import create_recording_clearance
from eprs.distribution import package_distribution
from eprs.master import approve_master
from eprs.session import create_recording_session
from eprs.system import new_song, sha256, song_status
from tests.test_delivery import lossless_master


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class DistributionTests(unittest.TestCase):
    def _clearance(self, root: Path, song: Path) -> Path:
        raw = next((song / "recordings" / "raw").rglob("*.wav"))
        session_spec = root / "session.json"
        session_spec.write_text(json.dumps({
            "schema": "eprs.recording-session/v1",
            "title": "Public fixture session",
            "intent": "Bind the exact performer and take to distribution rights.",
            "captured_at": "2026-08-09",
            "tempo_or_time_reference": "Fixture tone; no grid asserted.",
            "participants": [{
                "id": "fixture-artist", "role": "performer", "credit": "Fixture Artist",
                "consent_note": "Fixture contributor approves public test-package use.",
            }],
            "setups": [{
                "id": "fixture-generator", "source": "test tone",
                "capture_chain": "standard-library WAV fixture",
            }],
            "takes": [{
                "id": "fixture-take", "role": "source performance",
                "path": str(raw.relative_to(song)),
                "participant_ids": ["fixture-artist"], "setup_ids": ["fixture-generator"],
                "note": "Exact source used in the test master.",
                "rights_note": "Public fixture-package use approved below.",
            }],
        }))
        session = create_recording_session(session_spec, song)
        clearance_spec = root / "clearance.json"
        clearance_spec.write_text(json.dumps({
            "schema": "eprs.recording-clearance/v1",
            "title": "Public fixture clearance",
            "session": str(session.relative_to(song.resolve())),
            "intended_use": "Public Spotify and Apple Music distribution-package fixture.",
            "visibility_limit": "public",
            "takes": [{
                "id": "fixture-take", "decision": "approved", "confirmed_by": "Fixture Artist",
                "confirmed_at": "2026-08-09", "permission_note": "Public fixture use confirmed.",
            }],
            "participants": [{
                "id": "fixture-artist", "decision": "approved", "confirmed_by": "Fixture Artist",
                "confirmed_at": "2026-08-09", "permission_note": "Public fixture use confirmed.",
                "credit_decision": "named", "credit": "Fixture Artist",
            }],
        }))
        return create_recording_clearance(clearance_spec, song)

    def _artwork(self, song: Path, size: int = 3000) -> Path:
        artwork = song / "visuals" / f"fixture-{size}.png"
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
            f"color=c=0x172554:s={size}x{size}", "-frames:v", "1", "-y", str(artwork),
        ], check=True)
        return artwork

    def _spec(self, root: Path, song: Path, master: Path, artwork: Path, clearance: Path) -> Path:
        spec = root / "distribution.json"
        spec.write_text(json.dumps({
            "schema": "eprs.distribution/v1",
            "title": "Blue Pressure",
            "artist": "Fixture Artist",
            "release_type": "single",
            "approved_master": str(master.relative_to(song)),
            "artwork": str(artwork.relative_to(song)),
            "genre": "Electronic",
            "language": "en",
            "explicit": "not-explicit",
            "label": "Self-released",
            "destinations": ["spotify", "apple-music"],
            "credits": [{"name": "Fixture Artist", "role": "primary artist, writer, producer"}],
            "rights": {
                "confirmed": True,
                "copyright": "© 2026 Fixture Artist",
                "phonographic_copyright": "℗ 2026 Fixture Artist",
                "note": "Fixture composition, recording, performance, and artwork rights confirmed.",
            },
            "identifiers": {"isrc": None, "upc": None},
            "clearances": [str(clearance.relative_to(song.resolve()))],
        }))
        return spec

    def test_packages_streaming_assets_without_submission(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Streaming Package")
            master = lossless_master(root, song)
            approve_master(song, master, "Listened through the complete streaming fixture.")
            artwork = self._artwork(song)
            clearance = self._clearance(root, song)
            source_digests = (sha256(master), sha256(artwork))

            destination, manifest_path = package_distribution(
                self._spec(root, song, master, artwork, clearance), song
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["schema"], "eprs.distribution-package/v1")
            self.assertTrue(all(manifest["verification"].values()))
            self.assertFalse(manifest["distribution"]["submitted"])
            self.assertEqual((sha256(master), sha256(artwork)), source_digests)
            self.assertIn("requires a distributor account", (destination / "HANDOFF.md").read_text())
            for artifact in manifest["artifacts"]:
                self.assertEqual(sha256(song / artifact["path"]), artifact["sha256"])
            self.assertEqual(package_distribution(root / "distribution.json", song), (destination, manifest_path))
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["distribution_packages"], 1)
            self.assertEqual(status["inventory"]["invalid_releases"], 0)
            self.assertEqual(status["attention"], [])

    def test_refuses_unconfirmed_rights_and_small_artwork(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Streaming Gates")
            master = lossless_master(root, song)
            approve_master(song, master, "Listened through the complete streaming gate fixture.")
            clearance = self._clearance(root, song)
            artwork = self._artwork(song, 1000)
            spec = self._spec(root, song, master, artwork, clearance)
            record = json.loads(spec.read_text())
            record["rights"]["confirmed"] = False
            spec.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "rights.confirmed"):
                package_distribution(spec, song)
            record["rights"]["confirmed"] = True
            spec.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "3000x3000"):
                package_distribution(spec, song)
