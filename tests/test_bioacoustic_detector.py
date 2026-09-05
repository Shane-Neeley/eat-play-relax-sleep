import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from eprs.bioacoustic_detector import (
    DETECTION_SCHEMA,
    detect_audio,
    load_species_selection_table,
    write_detection_report,
)
from eprs.cli import parser


class BioacousticDetectorTests(unittest.TestCase):
    def test_reads_birdcode_selection_table_as_soft_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            table = Path(folder) / "predictions.txt"
            table.write_text(
                "Begin Time\tEnd Time\tSpecies\tScore\n"
                "1.25\t1.75\tDryocopus pileatus\t0.81\n"
                "2.00\t2.50\tTurdus migratorius\t0.92\n",
                encoding="utf-8",
            )
            rows = load_species_selection_table(table)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["species"], "Dryocopus pileatus")
        self.assertEqual(rows[0]["score"], 0.81)

    def test_reads_birdcode_headers_with_seconds_units(self):
        with tempfile.TemporaryDirectory() as folder:
            table = Path(folder) / "predictions.txt"
            table.write_text(
                "Begin Time (s)\tEnd Time (s)\tSpecies\tScore\n"
                "1.25\t1.75\tDryocopus pileatus\t0.81\n",
                encoding="utf-8",
            )
            rows = load_species_selection_table(table)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["begin_seconds"], 1.25)

    def test_reads_generic_taxon_classifier_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            table = Path(folder) / "predictions.csv"
            table.write_text(
                "Start,End,Taxon,Confidence\n0.5,2.5,Megaptera novaeangliae,0.88\n",
                encoding="utf-8",
            )
            rows = load_species_selection_table(
                table,
                species="Megaptera novaeangliae",
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["species"], "Megaptera novaeangliae")
        self.assertEqual(rows[0]["score"], 0.88)

    def test_cli_exposes_reviewable_detection(self):
        args = parser().parse_args(
            [
                "bioacoustic",
                "detect",
                "source.wav",
                "--species-table",
                "predictions.txt",
                "--reference",
                "known-good.wav",
                "--pulse-max-gap",
                "0.5",
            ]
        )
        self.assertEqual(args.bioacoustic_command, "detect")
        self.assertEqual(args.species, "Dryocopus pileatus")
        self.assertEqual(args.reference, "known-good.wav")
        self.assertEqual(args.behavior, "transient")
        self.assertEqual(args.pulse_max_gap, 0.5)
        self.assertEqual(args.max_duration_seconds, 120.0)

    def test_report_cannot_overwrite_source_or_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.wav"
            source.write_bytes(b"immutable-audio")
            report = {
                "source": {"path": str(source.resolve())},
                "reference": {"path": None},
                "species_evidence": {"selection_table": None},
            }

            with self.assertRaisesRegex(ValueError, "must not overwrite"):
                write_detection_report(report, source)

            self.assertEqual(source.read_bytes(), b"immutable-audio")

    def test_report_is_portable_atomic_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "report.json"
            report = {
                "source": {"path": "<external>/source.wav", "sha256": "abc"},
                "reference": {"path": None},
                "species_evidence": {"selection_table": None},
            }
            write_detection_report(report, destination)
            saved = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(saved["report_path"], "<external>/report.json")
            self.assertNotIn(str(Path(folder)), json.dumps(saved))
            with self.assertRaises(FileExistsError):
                write_detection_report(report, destination)

    def test_selection_table_rejects_malformed_and_nonfinite_evidence(self):
        bad_rows = (
            "0.0,,Dryocopus pileatus,0.9",
            "nan,1.0,Dryocopus pileatus,0.9",
            "0.0,1.0,Dryocopus pileatus,inf",
            "0.0,1.0,Dryocopus pileatus,1.1",
            "-1.0,1.0,Dryocopus pileatus,0.9",
        )
        with tempfile.TemporaryDirectory() as folder:
            table = Path(folder) / "predictions.csv"
            for row in bad_rows:
                with self.subTest(row=row):
                    table.write_text(
                        "Start,End,Taxon,Confidence\n" + row + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError):
                        load_species_selection_table(table)

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_detects_a_broadband_transient_without_approving_a_clip(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample_rate = 8_000
            times = np.arange(sample_rate * 2) / sample_rate
            background = 0.025 * np.sin(2 * np.pi * 440 * times)
            transient = np.zeros_like(times)
            transient[int(0.7 * sample_rate) : int(0.72 * sample_rate)] = np.hanning(
                int(0.02 * sample_rate)
            )
            source = root / "source.wav"
            sf.write(source, background + transient, sample_rate)

            report = detect_audio(source, max_events=20)

        self.assertEqual(report["schema"], DETECTION_SCHEMA)
        self.assertFalse(report["review"]["automatic_clipping"])
        self.assertEqual(report["review"]["status"], "review-required")
        self.assertTrue(report["events"])
        self.assertLess(abs(report["events"][0]["peak_seconds"] - 0.7), 0.12)

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_rejects_nonfinite_audio_and_unbounded_sample_counts(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            corrupt = root / "nan.wav"
            sf.write(
                corrupt, np.full(1000, np.nan, dtype=np.float32), 8_000, subtype="FLOAT"
            )
            with self.assertRaisesRegex(ValueError, "NaN or infinite"):
                detect_audio(corrupt)

            too_many = root / "too-many.wav"
            sf.write(too_many, np.zeros(1_500_001, dtype=np.float32), 16_000)
            with self.assertRaisesRegex(ValueError, "1500000"):
                detect_audio(too_many)

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_species_table_is_a_gate_not_an_optional_bonus(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample_rate = 8_000
            samples = np.zeros(sample_rate * 2)
            loud = np.hanning(160)
            quieter = 0.65 * np.hanning(160)
            samples[4_000:4_160] = loud
            samples[12_000:12_160] = quieter
            source = root / "source.wav"
            sf.write(source, samples, sample_rate)
            original = source.read_bytes()
            table = root / "predictions.txt"
            table.write_text(
                "Begin Time\tEnd Time\tSpecies\tScore\n"
                "1.40\t1.70\tDryocopus pileatus\t0.8\n",
                encoding="utf-8",
            )

            report = detect_audio(source, species_selection_table=table, max_events=20)

            self.assertEqual(source.read_bytes(), original)

        self.assertTrue(report["events"][0]["target_gate_passed"])
        self.assertLess(abs(report["events"][0]["peak_seconds"] - 1.5), 0.12)
        rejected = next(
            event
            for event in report["events"]
            if abs(event["peak_seconds"] - 0.5) < 0.12
        )
        self.assertFalse(rejected["target_gate_passed"])
        self.assertIn("outside-target-species-interval", rejected["rejection_reasons"])

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_pulse_train_gate_rejects_an_isolated_louder_noise(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample_rate = 8_000
            samples = np.zeros(sample_rate * 2)
            samples[3_200:3_280] = np.hanning(80)
            for start_seconds in (1.0, 1.1, 1.2, 1.3):
                start = int(start_seconds * sample_rate)
                samples[start : start + 80] = 0.65 * np.hanning(80)
            source = root / "source.wav"
            sf.write(source, samples, sample_rate)

            report = detect_audio(source, behavior="pulse-train", max_events=20)

        candidates = [
            event for event in report["events"] if event["target_gate_passed"]
        ]
        self.assertGreaterEqual(len(candidates), 4)
        self.assertTrue(all(event["pulse_train"]["count"] >= 4 for event in candidates))
        self.assertEqual(len(report["target_segments"]), 1)
        self.assertEqual(report["review"]["target_candidates"], 1)
        self.assertGreaterEqual(report["target_segments"][0]["event_count"], 4)
        isolated = next(
            event
            for event in report["events"]
            if abs(event["peak_seconds"] - 0.4) < 0.12
        )
        self.assertFalse(isolated["target_gate_passed"])

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_sustained_call_segments_low_whale_and_canid_howl_frequencies(self):
        import numpy as np
        import soundfile as sf

        cases = (
            ("whale", "Megaptera novaeangliae", 80.0, 4_000, 0.8, 2.4),
            ("canid", "Canis lupus", 420.0, 8_000, 0.7, 2.5),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for (
                name,
                species,
                frequency,
                sample_rate,
                expected_start,
                expected_end,
            ) in cases:
                with self.subTest(animal=name):
                    times = np.arange(sample_rate * 3) / sample_rate
                    samples = 0.002 * np.random.default_rng(2).normal(size=times.size)
                    active = (times >= expected_start) & (times <= expected_end)
                    phase = np.clip(
                        (times - expected_start) / (expected_end - expected_start),
                        0.0,
                        1.0,
                    )
                    envelope = np.sin(np.pi * phase) ** 2
                    samples += (
                        0.25 * np.sin(2 * np.pi * frequency * times) * envelope * active
                    )
                    source = root / f"{name}.wav"
                    sf.write(source, samples, sample_rate)
                    original = source.read_bytes()
                    table = root / f"{name}.csv"
                    table.write_text(
                        f"Start,End,Taxon,Confidence\n0.5,2.7,{species},0.9\n",
                        encoding="utf-8",
                    )

                    report = detect_audio(
                        source,
                        behavior="sustained-call",
                        species_selection_table=table,
                        species=species,
                    )

                    self.assertEqual(source.read_bytes(), original)
                    self.assertEqual(report["review"]["target_candidates"], 1)
                    segment = report["target_segments"][0]
                    self.assertLessEqual(
                        abs(segment["start_seconds"] - expected_start), 0.15
                    )
                    self.assertLessEqual(
                        abs(segment["end_seconds"] - expected_end), 0.15
                    )
                    self.assertLess(
                        abs(
                            report["events"][0]["features"]["spectral_centroid_hz"]
                            - frequency
                        ),
                        frequency * 0.30 + 20.0,
                    )

    @unittest.skipUnless(
        shutil.which("ffmpeg")
        and shutil.which("ffprobe")
        and all(
            importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")
        ),
        "compressed-audio test needs ffmpeg and bioacoustic dependencies",
    )
    def test_m4a_field_recording_is_decoded_without_modifying_source(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample_rate = 16_000
            times = np.arange(sample_rate * 2) / sample_rate
            active = (times >= 0.5) & (times <= 1.5)
            samples = 0.001 * np.random.default_rng(8).normal(size=times.size)
            samples += 0.3 * np.sin(2 * np.pi * 180 * times) * active
            wav = root / "source.wav"
            source = root / "field-recording.m4a"
            sf.write(wav, samples, sample_rate)
            subprocess.run(
                [
                    shutil.which("ffmpeg"),
                    "-v",
                    "error",
                    "-i",
                    str(wav),
                    "-c:a",
                    "aac",
                    str(source),
                ],
                check=True,
            )
            original = source.read_bytes()

            report = detect_audio(source, behavior="sustained-call")

            self.assertEqual(source.read_bytes(), original)

        self.assertEqual(report["source"]["sample_rate_hz"], sample_rate)
        self.assertEqual(report["review"]["status"], "review-required")

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_insect_chirp_timing_is_configurable_without_weakening_default(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sample_rate = 16_000
            samples = 0.001 * np.random.default_rng(4).normal(size=sample_rate * 2)
            pulse_size = int(0.018 * sample_rate)
            pulse_times = (0.4, 0.7, 1.0, 1.3, 1.6)
            pulse = (
                0.8
                * np.sin(2 * np.pi * 5_000 * np.arange(pulse_size) / sample_rate)
                * np.hanning(pulse_size)
            )
            for pulse_seconds in pulse_times:
                start = int(pulse_seconds * sample_rate)
                samples[start : start + pulse_size] += pulse
            source = root / "insect.wav"
            sf.write(source, samples, sample_rate)

            default_report = detect_audio(source, behavior="pulse-train")
            insect_report = detect_audio(
                source,
                behavior="pulse-train",
                pulse_maximum_gap_seconds=0.35,
            )

        self.assertEqual(default_report["review"]["status"], "no-target-candidates")
        self.assertEqual(insect_report["review"]["target_candidates"], 1)
        pulse_train = insect_report["target_segments"][0]["pulse_train"]
        self.assertEqual(pulse_train["count"], 5)
        self.assertAlmostEqual(pulse_train["mean_gap_seconds"], 0.3, delta=0.03)

    def test_rejects_invalid_cross_taxon_timing_configuration(self):
        with self.assertRaisesRegex(ValueError, "at least 2"):
            detect_audio("not-read.wav", pulse_minimum_count=1)
        with self.assertRaisesRegex(ValueError, "exceed the minimum"):
            detect_audio(
                "not-read.wav",
                pulse_minimum_gap_seconds=0.5,
                pulse_maximum_gap_seconds=0.2,
            )

    @unittest.skipUnless(
        all(importlib.util.find_spec(name) for name in ("numpy", "scipy", "soundfile")),
        "bioacoustic optional dependencies are not installed",
    )
    def test_target_species_missing_from_table_fails_loudly(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.wav"
            sf.write(source, np.zeros(8_000), 8_000)
            table = root / "predictions.txt"
            table.write_text(
                "Begin Time\tEnd Time\tSpecies\tScore\n"
                "0.0\t1.0\tTurdus migratorius\t0.9\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "no rows for target species"):
                detect_audio(source, species_selection_table=table)


if __name__ == "__main__":
    unittest.main()
