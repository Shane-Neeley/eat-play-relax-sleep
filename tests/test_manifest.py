from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from eprs.cli import main, parser
from eprs.manifest import (
    EVENT_SCHEMA,
    _portable_value,
    add_manifest_note,
    add_method_record,
    build_song_method_manifest,
    command_catalog,
    compare_song_method_manifests,
    verify_song_method_manifest,
)
from eprs.system import new_song


class SongMethodManifestTests(unittest.TestCase):
    def test_catalog_captures_commands_choices_defaults_and_adapters(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(folder, "Catalog Song")
            output = song / "code" / "candidate.beat"
            output.write_text(
                "title Catalog Song\ntempo 92\nmeter 4/4\nbars 1\nresolution 4\n",
                encoding="utf-8",
            )
            add_method_record(
                song,
                "Sonic Pi",
                "A live-coded groove was considered as an orthogonal rhythmic route.",
                kind="composition",
                status="considered",
                software_version="4.x unknown patch",
                prompt="Let the room answer after every second kick.",
                settings=[{"seed": 23}, {"swing": 0.54}],
                outputs=[("score candidate", "code/candidate.beat")],
                alternatives=["BeatScript", "live percussion"],
                tags=["groove", "orthogonal-candidate"],
            )
            add_manifest_note(
                song,
                "thoughts and loose ends",
                "Try silence as an instrument next time.",
            )

            path = build_song_method_manifest(
                song,
                parser(),
                tool_report={
                    "tools": [
                        {
                            "id": "ffmpeg",
                            "available": True,
                            "versions": {"ffmpeg": "fixture 1.0"},
                        }
                    ],
                },
            )
            # Automatic portable rebuilds retain the last explicit probe snapshot.
            path = build_song_method_manifest(song, parser())
            record = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(record["schema"], "eprs.song-method-manifest/v1")
            self.assertEqual(record["manual_records"][0]["method"], "Sonic Pi")
            self.assertEqual(record["notes"][0]["section"], "thoughts and loose ends")
            self.assertIn(
                "ffmpeg", {item["id"] for item in record["method_space"]["software"]}
            )
            ffmpeg = next(
                item
                for item in record["method_space"]["software"]
                if item["id"] == "ffmpeg"
            )
            self.assertEqual(
                ffmpeg["availability"]["versions"]["ffmpeg"], "fixture 1.0"
            )
            self.assertIn(
                "sonic-pi-live-code",
                {item["id"] for item in record["method_space"]["adapters"]},
            )

            methods = {item["id"]: item for item in record["method_space"]["eprs_cli"]}
            self.assertIn("manifest record", methods)
            render = methods["visual-render"]
            renderer = next(
                item for item in render["parameters"] if item["name"] == "renderer"
            )
            self.assertEqual(renderer["choices"], ["remotion", "vgpu"])
            self.assertEqual(renderer["default"], "remotion")
            self.assertTrue(render["summary"])
            self.assertTrue(verify_song_method_manifest(song)["valid"])

            detector = song / "notes" / "detection.json"
            detector.write_text(
                json.dumps({"schema": "eprs.bioacoustic-detection/v1"}),
                encoding="utf-8",
            )
            indexed = json.loads(
                build_song_method_manifest(song, parser()).read_text(encoding="utf-8")
            )
            indexed_methods = {
                item["id"]: item for item in indexed["method_space"]["eprs_cli"]
            }
            self.assertEqual(
                indexed_methods["bioacoustic detect"]["status"], "artifact-evidenced"
            )

            output.write_text(
                output.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
            )
            verification = verify_song_method_manifest(song)
            self.assertFalse(verification["valid"])
            self.assertEqual(verification["invalid"][0]["reason"], "checksum changed")

            escaped = json.loads(path.read_text(encoding="utf-8"))
            escaped["artifacts"][0]["path"] = "../../outside"
            path.write_text(json.dumps(escaped), encoding="utf-8")
            reasons = {
                item["reason"] for item in verify_song_method_manifest(song)["invalid"]
            }
            self.assertIn("path escapes song workspace", reasons)

            # A cleanly added binary still makes the generated snapshot stale.
            path = build_song_method_manifest(song, parser())
            (song / "new-render.wav").write_bytes(b"new")
            reasons = {
                item["reason"] for item in verify_song_method_manifest(song)["invalid"]
            }
            self.assertIn("asset is not indexed; rebuild manifest", reasons)

    def test_successful_song_mutation_is_recorded_automatically(self):
        with tempfile.TemporaryDirectory() as folder:
            with redirect_stdout(io.StringIO()):
                result = main(["new", "Ledger Song", "--root", folder])
            self.assertEqual(result, 0)
            song = Path(folder) / "ledger-song"
            manifest = json.loads(
                (song / "song-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["summary"]["recorded_methods"], {"new": 1})
            event = manifest["events"][0]
            self.assertEqual(event["method"], "new")
            self.assertEqual(event["outcome"], "completed")
            self.assertIn("song.json", {item["path"] for item in event["artifacts"]})
            self.assertNotIn(str(Path.home()), json.dumps(event))

            # Status surfaces the ledger without mutating it.
            with (
                patch("eprs.cli.snapshot_song") as snapshot,
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(main(["status", str(song), "--json"]), 0)
            snapshot.assert_not_called()
            unchanged = json.loads(
                (song / "song-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(unchanged["events"]), 1)

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "ingest",
                            str(song / "missing.wav"),
                            "--song",
                            str(song),
                            "--role",
                            "missing take",
                        ]
                    ),
                    2,
                )
            attempted = json.loads(
                (song / "song-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(attempted["events"][-1]["outcome"], "nonzero")
            methods = {
                item["id"]: item for item in attempted["method_space"]["eprs_cli"]
            }
            self.assertEqual(methods["ingest"]["status"], "attempted-nonzero")

    def test_command_catalog_has_one_record_per_leaf(self):
        catalog = command_catalog(parser())
        ids = [item["id"] for item in catalog]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("mix-review", ids)
        self.assertIn("work finish", ids)
        self.assertGreater(len(ids), 50)

    def test_compare_surfaces_shared_and_exclusive_method_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            first = new_song(folder, "Pulse Study")
            second = new_song(folder, "Drift Study")
            add_method_record(
                first, "live percussion", "A performed pulse carries the form."
            )
            add_method_record(
                second, "free-time synthesis", "An evolving spectrum carries the form."
            )
            build_song_method_manifest(first, parser())
            build_song_method_manifest(second, parser())

            comparison = compare_song_method_manifests([first, second])
            pair = comparison["pairs"][0]
            self.assertIn("new", pair["shared"])
            self.assertIn("live percussion", pair["only"]["pulse-study"])
            self.assertIn("free-time synthesis", pair["only"]["drift-study"])
            self.assertLess(pair["jaccard"], 1.0)

            with self.assertRaisesRegex(ValueError, "at least two"):
                compare_song_method_manifests([first])

            ledger = first / "notes" / "manifest" / "events" / "bad.json"
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps({"schema": EVENT_SCHEMA}), encoding="utf-8")
            build_song_method_manifest(first, parser())
            self.assertFalse(verify_song_method_manifest(first)["valid"])
            with self.assertRaisesRegex(ValueError, "invalid or stale"):
                compare_song_method_manifests([first, second])

    def test_status_reports_non_object_manifest_as_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(folder, "Malformed Ledger")
            (song / "song-manifest.json").write_text("[]\n", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(["status", str(song), "--verify", "--json"]), 0)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["inventory"]["method_manifest"]["valid"])
            self.assertTrue(
                any(
                    "Invalid song method manifest" in item
                    for item in report["attention"]
                )
            )

            malformed = {
                "schema": "eprs.song-method-manifest/v1",
                "summary": {},
                "events": None,
                "manual_records": [],
                "notes": [],
            }
            (song / "song-manifest.json").write_text(
                json.dumps(malformed), encoding="utf-8"
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(["status", str(song), "--verify", "--json"]), 0)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["inventory"]["method_manifest"]["valid"])

    def test_long_free_form_prompt_is_not_treated_as_a_filesystem_path(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(folder, "Long Prompt")
            output = song / "visuals" / "long-prompt.json"
            prompt = "slow amber geometry " * 40
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "visual-prompt",
                            prompt,
                            "--title",
                            "Long Prompt",
                            "--out",
                            str(output),
                        ]
                    ),
                    0,
                )
            manifest = json.loads(
                (song / "song-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["events"][0]["parameters"]["prompt"], prompt)

    def test_external_absolute_paths_are_redacted_without_changing_prose_or_urls(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(folder, "Portable Paths")
            self.assertEqual(
                _portable_value("/Volumes/ClientName/private/take.wav", song),
                "<external>/take.wav",
            )
            self.assertEqual(
                _portable_value("https://example.com/a/b", song),
                "https://example.com/a/b",
            )
            prose = "try / fewer hits / and longer spaces"
            self.assertEqual(_portable_value(prose, song), prose)

    def test_event_output_hash_detects_same_size_binary_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["new", "Hash State", "--root", folder]), 0)
            song = Path(folder) / "hash-state"
            song_file = song / "song.json"
            original = song_file.read_bytes()
            song_file.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            verification = verify_song_method_manifest(song)
            self.assertFalse(verification["valid"])
            self.assertIn(
                "checksum changed", {item["reason"] for item in verification["invalid"]}
            )


if __name__ == "__main__":
    unittest.main()
