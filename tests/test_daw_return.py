import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eprs.cli import parser
from eprs.context import build_agent_context
from eprs.daw_return import capture_daw_return, verify_daw_return_mix
from eprs.interchange import prepare_daw_interchange
from eprs.lineage import trace_audio_lineage
from eprs.master import render_master
from eprs.mix import review_mix
from eprs.system import ingest, new_song, sha256, song_status
from tests import test_interchange as interchange_fixtures


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class DawReturnTests(unittest.TestCase):
    def _roundtrip(self, root: Path) -> tuple[Path, Path, Path, dict]:
        song = new_song(root / "songs", "DAW Round Trip").resolve()
        mix, _ = interchange_fixtures.DawInterchangeTests()._mix(root, song)
        package, _, _ = prepare_daw_interchange(song, mix)
        chime_source = root / "release-chime.wav"
        interchange_fixtures.tone_wav(chime_source, 880, 0.2)
        chime, _ = ingest(
            chime_source,
            song,
            role="release chime",
            note="A family-played release marker considered during the external pass.",
            rights_note="Private family recording; publication permission remains unresolved.",
        )
        spec = root / "daw-return.json"
        declaration = {
            "schema": "eprs.daw-return/v1",
            "title": "Family DAW return",
            "intent": "Let the family answer feel close while the guitar attack remains legible.",
            "operator": "mix collaborator",
            "rights_note": "Private working mix; do not publish without clearance.",
            "timeline_origin": "package-time-zero",
            "tool": {
                "name": "Example DAW",
                "version": "12.3",
                "session_format": "example-session",
            },
            "interchange_package": str(package.relative_to(song)),
            "returned_mix": str(package / "reference-mix.wav"),
            "changes": [{
                "id": "family-space",
                "type": "balance and ambience",
                "intent": "Give the family response a closer sense of space.",
                "details": "Raised the answer slightly and shaped its short ambience.",
                "settings_or_unknown": "Balance automation known; ambience plug-in state unknown.",
            }],
            "unknowns": ["Exact ambience plug-in version and hidden default state."],
            "added_sources": [{
                "id": "release-chime",
                "role": "performed release marker",
                "path": str(chime.relative_to(song)),
                "note": "Auditioned at the final release; declared even though this test bounce is unchanged.",
                "rights_note": "Private family recording; publication permission remains unresolved.",
            }],
        }
        spec.write_text(json.dumps(declaration))
        return song, mix, package, {"path": spec, "declaration": declaration, "chime": chime}

    def test_capture_review_master_and_lineage_form_a_verified_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, mix, package, setup = self._roundtrip(root)
            returned_source = Path(setup["declaration"]["returned_mix"])
            source_digest = sha256(returned_source)

            returned, sidecar, metadata = capture_daw_return(setup["path"], song)

            self.assertEqual(sha256(returned), source_digest)
            self.assertEqual(returned.read_bytes(), returned_source.read_bytes())
            self.assertEqual(metadata["schema"], "eprs.daw-return-mix/v1")
            self.assertEqual(metadata["recipe"]["source_interchange"]["path"], str(package.relative_to(song)))
            self.assertEqual(metadata["recipe"]["source_mix"]["path"], str(mix.relative_to(song)))
            self.assertEqual(metadata["external_render"]["tool"]["name"], "Example DAW")
            self.assertFalse(metadata["external_render"]["reproducible_by_eprs"])
            self.assertTrue(metadata["external_render"]["copied_without_conversion"])
            self.assertEqual(metadata["review"]["decision"], "not recorded by capture")
            self.assertTrue(all(value is False for value in metadata["authority"].values()))
            with self.assertRaisesRegex(ValueError, "complete-listen keep decision"):
                verify_daw_return_mix(song, returned, require_approval=True)

            note = "Listened end to end; balance, transitions, dynamics, decay, and silence are intentional."
            review_mix(song, returned, note, "keep")
            verify_daw_return_mix(song, returned, require_approval=True)
            repeated = capture_daw_return(setup["path"], song)
            self.assertEqual(repeated[0], returned)
            self.assertEqual(repeated[1], sidecar)
            self.assertEqual(repeated[2]["review"]["decision"], "keep")

            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["mixes"], 2)
            self.assertEqual(status["inventory"]["daw_return_mixes"], 1)
            self.assertEqual(status["inventory"]["mixes_kept"], 1)
            context = build_agent_context(song, verify=True)
            returned_context = next(
                item for item in context["recent_mixes"] if item["kind"] == "daw-return-mix"
            )
            self.assertEqual(returned_context["external_render"]["tool"]["name"], "Example DAW")
            self.assertEqual(returned_context["external_render"]["changes"][0]["id"], "family-space")
            self.assertFalse(returned_context["external_render"]["reproducible_by_eprs"])

            lineage = trace_audio_lineage(song, returned)
            self.assertEqual(len(lineage["raw_recordings"]), 3)
            self.assertEqual(lineage["untraced_leaves"], [])
            master_spec = root / "master.json"
            master_spec.write_text(json.dumps({
                "schema": "eprs.master/v1",
                "title": "Returned mix master",
                "intent": "Preserve the reviewed external balance without added loudness processing.",
                "destination": "lossless review archive",
                "source": str(returned.relative_to(song)),
                "gain_db": 0,
                "true_peak_ceiling_dbfs": -1,
            }))
            master, master_sidecar = render_master(master_spec, song)
            master_metadata = json.loads(master_sidecar.read_text())
            self.assertEqual(
                master_metadata["source"]["provenance"]["schema"],
                "eprs.daw-return-mix/v1",
            )
            self.assertEqual(len(trace_audio_lineage(song, master)["raw_recordings"]), 3)

    def test_refuses_lossy_returns_and_detects_parent_or_authority_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song, _, package, setup = self._roundtrip(root)
            lossy = root / "return.mp3"
            subprocess.run([
                shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-y",
                "-i", setup["declaration"]["returned_mix"], str(lossy),
            ], check=True)
            lossy_declaration = dict(setup["declaration"])
            lossy_declaration["returned_mix"] = str(lossy)
            lossy_spec = root / "lossy-return.json"
            lossy_spec.write_text(json.dumps(lossy_declaration))
            with self.assertRaisesRegex(ValueError, "lossless audio"):
                capture_daw_return(lossy_spec, song)

            returned, sidecar, _ = capture_daw_return(setup["path"], song)
            original_sidecar = sidecar.read_bytes()
            changed = json.loads(sidecar.read_text())
            changed["authority"]["publication_authorized"] = True
            sidecar.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "authority record"):
                verify_daw_return_mix(song, returned)
            sidecar.write_bytes(original_sidecar)

            changed = json.loads(sidecar.read_text())
            changed["recipe"]["operator"] = "undeclared replacement"
            sidecar.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "recipe id"):
                verify_daw_return_mix(song, returned)
            sidecar.write_bytes(original_sidecar)

            manifest = package / "interchange.json"
            original_manifest = manifest.read_bytes()
            changed_manifest = json.loads(manifest.read_text())
            changed_manifest["authority"]["upload_authorized"] = True
            manifest.write_text(json.dumps(changed_manifest))
            with self.assertRaisesRegex(ValueError, "authority record|manifest_sha256|source interchange"):
                verify_daw_return_mix(song, returned)
            manifest.write_bytes(original_manifest)
            verify_daw_return_mix(song, returned)

    def test_cli_exposes_declared_return(self):
        parsed = parser().parse_args([
            "interchange", "return", "code/daw-return.json", "--song", "songs/study",
        ])
        self.assertEqual(parsed.interchange_command, "return")
        self.assertEqual(parsed.spec, "code/daw-return.json")


if __name__ == "__main__":
    unittest.main()
