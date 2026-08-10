from array import array
from contextlib import redirect_stdout
from io import StringIO
import json
import math
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
import wave

from eprs.context import build_agent_context
from eprs.cli import main, parser
from eprs.request import (
    capture_production_request,
    create_production_request,
    load_production_request,
)
from eprs.system import new_song, sha256, song_status


def tone_wav(path: Path, frequency: float) -> None:
    rate = 48_000
    samples = array("h", (
        round(math.sin(2 * math.pi * frequency * frame / rate) * 5000)
        for frame in range(round(0.1 * rate))
    ))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


class ProductionRequestTests(unittest.TestCase):
    def test_direct_capture_accepts_prompt_recordings_and_evidence_without_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Direct Intake")
            guitar = root / "guitar.wav"
            beat = root / "beat-idea.wav"
            lyrics = root / "lyrics.txt"
            picture = root / "porch-colors.png"
            tone_wav(guitar, 220)
            tone_wav(beat, 110)
            lyrics.write_text("Keep the porch light / leave the ending open\n")
            picture.write_bytes(b"frozen visual-direction evidence")
            digests = {path: sha256(path) for path in (guitar, beat, lyrics, picture)}
            prompt = "Loop the guitar invitation and let the lyric remain unfinished."

            manifest = capture_production_request(
                song,
                "Prompt and files",
                prompt,
                preserve=["The hesitation before the guitar resolves"],
                avoid=["Automatic timing correction"],
                questions=["Where can a family response enter without crowding the guitar?"],
                deliverables=["One small audition before arranging"],
                references=[
                    "Call and response as a relationship",
                    "https://www.youtube.com/watch?v=example",
                ],
                recordings=[("guitar invitation", guitar), ("spoken boom—clap", beat)],
                evidence=[("lyric fragments", lyrics), ("porch color direction", picture)],
            )
            _, request = load_production_request(song, manifest)

            self.assertEqual(request["prompt"], prompt)
            self.assertEqual(request["intended_experience"], prompt)
            self.assertEqual(
                request["provided"]["guitar-invitation"]["handling"],
                "immutable-recording",
            )
            self.assertEqual(
                request["provided"]["lyric-fragments"]["handling"],
                "frozen-evidence",
            )
            self.assertIn(
                "permissions not yet confirmed",
                request["provided"]["guitar-invitation"]["rights_note"],
            )
            self.assertEqual({path: sha256(path) for path in digests}, digests)
            self.assertTrue((song / request["provided"]["guitar-invitation"]["path"]).is_file())
            self.assertTrue((manifest.parent / request["provided"]["lyric-fragments"]["path"]).is_file())
            routes = {item["id"]: item for item in request["input_routes"]["provided"]}
            self.assertEqual(routes["guitar-invitation"]["family"], "performed-audio")
            self.assertIn("source-sketch", routes["guitar-invitation"]["first_action"])
            self.assertIn(
                "rhythm:", " ".join(routes["spoken-boom-clap"]["optional_followups"])
            )
            self.assertEqual(routes["lyric-fragments"]["family"], "lyrics-or-songwords")
            self.assertEqual(routes["porch-color-direction"]["family"], "picture")
            reference_families = {
                item["family"] for item in request["input_routes"]["references"]
            }
            self.assertEqual(reference_families, {"research-lead", "youtube-reference"})
            self.assertIn("does not execute", request["input_routes"]["authority"])
            packet = build_agent_context(song, request=manifest.parent.name, verify=True)
            routed_families = {
                item["family"]
                for item in packet["focus"]["production_request"]["record"]["input_routes"]["provided"]
            }
            self.assertEqual(
                routed_families,
                {"performed-audio", "lyrics-or-songwords", "picture"},
            )

            args = parser().parse_args([
                "request", "capture", "--song", str(song),
                "--title", "CLI intake", "--prompt", prompt,
                "--recording", f"guitar invitation={guitar}",
                "--evidence", f"lyric fragments={lyrics}",
                "--preserve", "room timing", "--question", "where does it breathe?",
            ])
            self.assertEqual(args.request_command, "capture")
            self.assertEqual(args.recording, [("guitar invitation", str(guitar))])
            self.assertEqual(args.evidence, [("lyric fragments", str(lyrics))])

            output = StringIO()
            with redirect_stdout(output):
                result = main([
                    "request", "capture", "--song", str(song),
                    "--title", "CLI intake", "--prompt", prompt,
                    "--recording", f"second guitar={guitar}",
                    "--evidence", f"second lyric sheet={lyrics}",
                ])
            self.assertEqual(result, 0)
            cli_manifest = Path(output.getvalue().strip())
            self.assertTrue(cli_manifest.is_file())
            self.assertEqual(
                load_production_request(song, cli_manifest)[1]["title"], "CLI intake"
            )

    def test_direct_capture_validates_all_roles_before_immutable_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Direct Intake Guard")
            guitar = root / "guitar.wav"
            lyrics = root / "lyrics.txt"
            tone_wav(guitar, 220)
            lyrics.write_text("Unresolved line\n")

            with self.assertRaisesRegex(ValueError, "duplicated"):
                capture_production_request(
                    song,
                    "Duplicate roles",
                    "Preserve both supplied files.",
                    recordings=[("main idea", guitar)],
                    evidence=[("main-idea", lyrics)],
                )
            self.assertEqual(list((song / "recordings" / "raw").rglob("*")), [])

    def _fixture(self, root: Path, song: Path) -> tuple[Path, list[Path]]:
        guitar = root / "guitar.wav"
        voices = root / "family-voices.wav"
        lyrics = root / "lyrics.txt"
        tone_wav(guitar, 220)
        tone_wav(voices, 330)
        lyrics.write_text("Keep the porch light / let everybody answer\n")
        spec = root / "request.json"
        spec.write_text(json.dumps({
            "schema": "eprs.production-request/v1",
            "title": "Porch-light family session",
            "prompt": "Build from these performances, keeping the room and the family response central.",
            "intended_experience": "A guitar invitation answered by people who sound together, not polished apart.",
            "preserve": ["The breath before the family entrance", "The guitar's uneven final gesture"],
            "avoid": ["Automatic tuning", "Generic replacement drums"],
            "questions": ["Can a chime answer without closing the phrase?"],
            "deliverables": ["Audition mix", "YouTube listening film after approval"],
            "references": ["call and response", "the room as an instrument"],
            "provided": [
                {
                    "id": "guitar-one", "role": "guitar invitation", "kind": "performance",
                    "handling": "immutable-recording", "path": "guitar.wav",
                    "note": "No click; keep the last hesitation.",
                    "rights_note": "Recorded by the project owner; public performer credit still needs confirmation.",
                },
                {
                    "id": "family-answer", "role": "family voices", "kind": "performance",
                    "handling": "immutable-recording", "path": "family-voices.wav",
                    "note": "One room microphone; preserve laughter after the line.",
                    "rights_note": "Private family recording; do not share or publish without explicit consent.",
                },
                {
                    "id": "lyric-fragments", "role": "lyric ideas", "kind": "lyrics",
                    "handling": "frozen-evidence", "path": "lyrics.txt",
                    "note": "Fragments, not an approved final lyric.",
                    "rights_note": "Original project writing; public wording not approved.",
                },
            ],
        }))
        return spec, [guitar, voices, lyrics]

    def test_captures_prompt_raw_recordings_and_frozen_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request Intake")
            spec, sources = self._fixture(root, song)
            digests = [sha256(path) for path in sources]

            manifest_path = create_production_request(spec, song)
            path, request = load_production_request(song, manifest_path.parent.name)
            self.assertEqual(path, manifest_path.resolve())
            self.assertEqual(request["schema"], "eprs.production-request-record/v1")
            self.assertEqual(request["status"], "captured")
            self.assertIn("not authorization", request["authority"]["statement"])
            self.assertEqual(set(request["provided"]), {"guitar-one", "family-answer", "lyric-fragments"})
            guitar = request["provided"]["guitar-one"]
            family = request["provided"]["family-answer"]
            lyrics = request["provided"]["lyric-fragments"]
            self.assertEqual(guitar["storage"], "song-reference")
            self.assertEqual(family["storage"], "song-reference")
            self.assertEqual(lyrics["storage"], "request-copy")
            self.assertTrue((song / guitar["path"]).is_file())
            self.assertTrue((song / family["path"]).is_file())
            frozen_lyrics = manifest_path.parent / lyrics["path"]
            self.assertEqual(frozen_lyrics.read_text(), sources[2].read_text())
            family_sidecar = json.loads((song / family["provenance_path"]).read_text())
            self.assertIn("Private family recording", family_sidecar["rights"])
            self.assertEqual([sha256(path) for path in sources], digests)
            self.assertIn("performance comparison", " ".join(request["suggested_next_actions"]))
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["production_requests"], {
                "total": 1, "invalid": 0, "recordings": 2, "evidence": 1,
            })
            self.assertEqual(status["attention"], [])
            packet = build_agent_context(
                song,
                purpose="Start from the supplied family session.",
                request=manifest_path.parent.name,
                verify=True,
            )
            focused = packet["focus"]["production_request"]["record"]
            self.assertIn("keeping the room", focused["prompt"])
            self.assertIn("Automatic tuning", focused["avoid"])
            self.assertEqual(len(packet["evidence"]), 3)
            self.assertTrue(all(item.get("checksum_matches") for item in packet["evidence"]))
            self.assertEqual(packet["recent_production_requests"][0]["id"], request["id"])
            self.assertFalse(packet["limits"]["binary_media_embedded"])

    def test_validates_all_items_before_creating_request_or_raw_intake(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request Validation")
            spec, _ = self._fixture(root, song)
            score = json.loads(spec.read_text())
            score["provided"][1]["id"] = "guitar one"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "duplicated"):
                create_production_request(spec, song)
            self.assertFalse((song / "notes" / "requests").exists())
            self.assertEqual(list((song / "recordings" / "raw").rglob("*")), [])

    def test_failed_evidence_copy_leaves_no_visible_partial_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Request Atomicity")
            spec, _ = self._fixture(root, song)
            with patch("eprs.request.shutil.copy2", side_effect=OSError("simulated copy failure")):
                with self.assertRaisesRegex(OSError, "simulated"):
                    create_production_request(spec, song)
            request_root = song / "notes" / "requests"
            self.assertEqual(list(request_root.iterdir()) if request_root.exists() else [], [])

    def test_context_budget_caps_large_permission_notes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Bounded Request")
            spec, _ = self._fixture(root, song)
            score = json.loads(spec.read_text())
            large_note = "private-permission-note " * 300
            score["provided"][0]["rights_note"] = large_note
            spec.write_text(json.dumps(score))
            manifest = create_production_request(spec, song)
            packet = build_agent_context(
                song,
                request=manifest.parent.name,
                max_text_bytes=1024,
            )
            self.assertLessEqual(packet["limits"]["text_bytes_used"], 1024)
            self.assertNotIn(large_note, json.dumps(packet))
            clipped = packet["focus"]["production_request"]["record"]["provided"]["guitar-one"]
            self.assertTrue(clipped["rights_note_truncated"])


if __name__ == "__main__":
    unittest.main()
