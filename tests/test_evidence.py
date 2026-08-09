import json
from pathlib import Path
import tempfile
import unittest

from eprs.evidence import bind_song_evidence, verify_evidence_bindings
from eprs.system import new_song


class EvidenceBindingTests(unittest.TestCase):
    def test_bindings_are_deterministic_bounded_and_song_local(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Evidence Contract")
            note = song / "notes" / "decision.md"
            note.write_text("Keep the family breath before the chime.\n")
            values = [{
                "id": "breath note",
                "role": "listening decision",
                "path": "notes/decision.md",
                "use": "Keep the breath as an arrangement landmark.",
            }]

            first = bind_song_evidence(song, values, "test")
            second = bind_song_evidence(song, values, "test")
            self.assertEqual(first, second)
            self.assertEqual(first[0]["schema"], "eprs.evidence-binding/v1")
            self.assertEqual(verify_evidence_bindings(song, first, "test"), [note.resolve()])

            with self.assertRaisesRegex(ValueError, "duplicate"):
                bind_song_evidence(song, [values[0], {**values[0], "id": "breath-note"}], "test")
            outside = root / "outside.md"
            outside.write_text("outside\n")
            with self.assertRaisesRegex(ValueError, "relative to the song"):
                bind_song_evidence(song, [{**values[0], "path": str(outside)}], "test")
            with self.assertRaisesRegex(ValueError, "escapes"):
                bind_song_evidence(song, [{**values[0], "path": "../outside.md"}], "test")

    def test_binding_verification_can_check_structure_without_hashing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Evidence Status")
            note = song / "notes" / "decision.json"
            note.write_text(json.dumps({"schema": "example/v1"}))
            binding = bind_song_evidence(song, [{
                "id": "decision", "role": "decision", "path": "notes/decision.json",
                "use": "Carry the decision into the next reversible render.",
            }], "test")
            note.write_text(json.dumps({"schema": "example/v2"}))
            self.assertEqual(
                verify_evidence_bindings(song, binding, "test", verify_checksums=False),
                [note.resolve()],
            )
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                verify_evidence_bindings(song, binding, "test")


if __name__ == "__main__":
    unittest.main()
