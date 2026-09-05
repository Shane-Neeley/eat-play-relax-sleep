import unittest

from eprs.singing_score import phrase_placements, validate_score


def phrase():
    return {
        "time": [0, 1500],
        "duration": "0.2 0.8 0.5",
        "text": "<SP> storm <SP>",
        "phoneme": "<SP> en_S-T-AO1-R-M <SP>",
        "note_pitch": "0 52 0",
        "note_type": "1 2 1",
    }


class SingingScoreTests(unittest.TestCase):
    def test_complete_word(self):
        validate_score([phrase()])

    def test_orphan_continuation_rejected(self):
        s = phrase()
        s["note_type"] = "1 3 1"
        with self.assertRaisesRegex(ValueError, "Continuation"):
            validate_score([s])

    def test_real_melisma(self):
        s = {
            "time": [0, 1500],
            "duration": "0.5 0.5 0.5",
            "text": "storm storm <SP>",
            "phoneme": "en_S-T-AO1-R-M en_S-T-AO1-R-M <SP>",
            "note_pitch": "55 52 0",
            "note_type": "2 3 1",
        }
        validate_score([s])

    def test_short_window_rejected(self):
        s = phrase()
        s["time"] = [0, 1300]
        with self.assertRaisesRegex(ValueError, "window"):
            validate_score([s])

    def test_tail_not_cropped(self):
        self.assertEqual(phrase_placements([phrase()], [40000], 24000), ([0], 40000))

    def test_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            validate_score([phrase(), phrase()])

    def test_nan_rejected(self):
        s = phrase()
        s["duration"] = "0.2 nan 0.5"
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_score([s])

    def test_parallel_arrays_rejected(self):
        s = phrase()
        s["text"] = "storm"
        with self.assertRaisesRegex(ValueError, "counts"):
            validate_score([s])
