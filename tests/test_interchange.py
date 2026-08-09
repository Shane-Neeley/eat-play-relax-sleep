from array import array
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from eprs.cli import parser
from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.interchange import prepare_daw_interchange, verify_daw_interchange
from eprs.mix import render_mix, review_mix
from eprs.selection import select_audio
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, frequency: float, seconds: float = 0.35) -> None:
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 0.22 * 32767)
        for frame in range(round(seconds * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class DawInterchangeTests(unittest.TestCase):
    def _mix(self, root: Path, song: Path) -> tuple[Path, list[Path]]:
        guitar_source = root / "guitar.wav"
        voice_source = root / "voice.wav"
        tone_wav(guitar_source, 220)
        tone_wav(voice_source, 337)
        guitar, _ = select_audio(guitar_source, song, "Guitar", 0, 0.3)
        voice, _ = select_audio(voice_source, song, "Family voice", 0, 0.3)
        spec = root / "mix.json"
        spec.write_text(json.dumps({
            "schema": "eprs.mix/v1",
            "title": "Family DAW handoff",
            "intent": "Keep the guitar invitation and delayed family answer portable.",
            "tracks": [{
                "id": "guitar", "role": "invitation",
                "intent": "Keep its pick edge left of center.",
                "path": str(guitar.relative_to(song)),
                "duration_seconds": 0.22, "gain_db": -6, "pan": -0.2,
                "fade_out_ms": 7,
            }, {
                "id": "family", "role": "answer",
                "intent": "Enter after the invitation without tuning or alignment.",
                "path": str(voice.relative_to(song)),
                "start_seconds": 0.08, "source_start_seconds": 0.02,
                "duration_seconds": 0.2, "gain_db": -8, "pan": 0.1,
                "fade_in_ms": 5,
            }],
        }))
        mix, _ = render_mix(spec, song)
        return mix, [guitar, voice]

    def test_common_start_stems_reconstruct_mix_and_preserve_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Portable Arrangement")
            mix, sources = self._mix(root, song)
            before = {path: sha256(path) for path in [mix, *sources]}

            package, manifest_path, manifest = prepare_daw_interchange(song, mix)

            self.assertEqual(manifest["schema"], "eprs.daw-interchange/v1")
            self.assertEqual(len(manifest["tracks"]), 2)
            self.assertTrue(all(track["common_start"] for track in manifest["tracks"]))
            self.assertTrue(all(track["timeline_start_seconds"] == 0 for track in manifest["tracks"]))
            self.assertTrue(manifest["reconstruction_verification"]["passed"])
            self.assertLessEqual(
                manifest["reconstruction_verification"]["max_absolute_error"], 1e-5
            )
            self.assertEqual(set(manifest["actions_performed"].values()), {False})
            self.assertFalse(manifest["authority"]["creative_approval_inferred"])
            self.assertEqual(sha256(package / manifest["reference_mix"]["path"]), sha256(mix))
            self.assertTrue((package / "README.md").is_file())
            self.assertEqual({path: sha256(path) for path in before}, before)

            verified_path, verified = verify_daw_interchange(
                song, package.name, verify_checksums=True, verify_media=True
            )
            self.assertEqual(verified_path, package)
            self.assertEqual(verified["package_id"], manifest["package_id"])
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["daw_interchange"], {
                "packages": 1, "tracks": 2, "invalid": 0,
            })
            context = build_agent_context(song, verify=True)
            self.assertEqual(context["recent_daw_interchange"][0]["tracks"][1]["id"], "family")
            self.assertIn(
                "## DAW-neutral interchange packages",
                render_agent_context_markdown(context),
            )
            repeated = prepare_daw_interchange(song, mix)
            self.assertEqual(repeated[0], package)
            self.assertEqual(repeated[1], manifest_path)
            self.assertEqual(repeated[2], manifest)

    def test_review_snapshot_creates_new_package_and_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Interchange Integrity")
            mix, _ = self._mix(root, song)
            working_package, _, _ = prepare_daw_interchange(song, mix)
            review_mix(
                song,
                mix,
                "Listened end to end; entrances, balance, overlap, and final silence are kept.",
                "keep",
            )
            reviewed_package, _, reviewed = prepare_daw_interchange(song, mix)
            self.assertNotEqual(reviewed_package, working_package)
            self.assertEqual(reviewed["recipe"]["review_snapshot"]["decision"], "keep")

            stem = reviewed_package / reviewed["tracks"][0]["path"]
            original_stem = stem.read_bytes()
            stem.write_bytes(original_stem + b"changed")
            with self.assertRaisesRegex(ValueError, "checksum has changed"):
                verify_daw_interchange(song, reviewed_package)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["daw_interchange"]["invalid"], 1)
            stem.write_bytes(original_stem)
            manifest_path = reviewed_package / "interchange.json"
            changed_manifest = json.loads(manifest_path.read_text())
            changed_manifest["authority"]["upload_authorized"] = True
            manifest_path.write_text(json.dumps(changed_manifest))
            with self.assertRaisesRegex(ValueError, "authority record"):
                verify_daw_interchange(song, reviewed_package)
            with self.assertRaisesRegex(ValueError, "inside the song interchange"):
                verify_daw_interchange(song, root)

    def test_cli_exposes_prepare_and_verify_without_implying_approval(self):
        prepare = parser().parse_args([
            "interchange", "prepare", "mixes/study/mix.wav", "--song", "songs/study",
        ])
        verify = parser().parse_args([
            "interchange", "verify", "interchange/study-package", "--song", "songs/study",
        ])
        self.assertEqual(prepare.interchange_command, "prepare")
        self.assertEqual(verify.interchange_command, "verify")


if __name__ == "__main__":
    unittest.main()
