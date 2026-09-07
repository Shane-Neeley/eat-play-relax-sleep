import argparse
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest

_spec = spec_from_file_location('bird_windows', Path(__file__).resolve().parents[1] / 'scripts/classify_bird_windows.py')
assert _spec and _spec.loader
review = module_from_spec(_spec)
_spec.loader.exec_module(review)


class BirdWindowReviewTests(unittest.TestCase):
    def test_windows_are_finite_positive_and_model_bounded(self):
        self.assertEqual(review.window('2:7'), (2, 7))
        for invalid in ['0:6', '-1:2', '2:2', '3:1', 'nan:2', '0:inf', 'all', '0:1:2']:
            with self.subTest(invalid=invalid), self.assertRaises(argparse.ArgumentTypeError):
                review.window(invalid)

    def test_output_cannot_replace_input_or_immutable_lanes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'call.wav'
            source.write_bytes(b'original')
            for output in [source, root / 'FINAL/review.json', root / 'recordings/raw/review.json']:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    review.validate_output(output, [source])
            existing = root / 'review.json'
            existing.write_text('prior review')
            with self.assertRaises(FileExistsError):
                review.validate_output(existing, [source])
            review.validate_output(root / 'notes/new-review.json', [source])
            self.assertEqual(source.read_bytes(), b'original')
            self.assertEqual(existing.read_text(), 'prior review')

    def test_symlink_cannot_hide_source_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'call.wav'
            source.write_bytes(b'original')
            alias = root / 'result.json'
            alias.symlink_to(source)
            with self.assertRaises(ValueError):
                review.validate_output(alias, [source])
