import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.cli import parser
from eprs.video_quality import (
    analyze_video,
    crop_geometry,
    sample_indices,
    write_video_quality_report,
)


OPENCV_AVAILABLE = importlib.util.find_spec("cv2") is not None


class VideoQualityTests(unittest.TestCase):
    def test_sample_indices_are_bounded_and_evenly_spaced(self):
        self.assertEqual(sample_indices(1, 18), [0])
        self.assertEqual(sample_indices(10, 3), [0, 4, 9])
        with self.assertRaisesRegex(ValueError, "between 1 and 240"):
            sample_indices(10, 0)

    def test_crop_geometry_reports_budget_without_claiming_subject_safety(self):
        result = crop_geometry(1920, 1080, 9 / 16, max_crop_fraction=0.40)
        self.assertEqual(result["method"], "center_crop_width")
        self.assertGreater(result["crop_fraction"], 0.40)
        self.assertFalse(result["within_budget"])

        untouched = crop_geometry(1920, 1080, None)
        self.assertFalse(untouched["evaluated"])
        self.assertTrue(untouched["within_budget"])

    def test_missing_optional_dependency_has_an_actionable_error(self):
        with patch("eprs.video_quality.importlib.import_module", side_effect=ImportError):
            with self.assertRaisesRegex(RuntimeError, "make opencv-install"):
                analyze_video(Path(__file__))

    def test_report_cannot_overwrite_source_video(self):
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "candidate.mp4"
            video.write_bytes(b"not a video, but it is still precious")
            with self.assertRaisesRegex(ValueError, "must differ"):
                write_video_quality_report(video, video)
            self.assertEqual(video.read_bytes(), b"not a video, but it is still precious")

    @unittest.skipUnless(OPENCV_AVAILABLE, "optional OpenCV extra is not installed")
    def test_sampling_rejects_excessive_dimensions_before_decode(self):
        import cv2

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "fixture.mp4"
            video.write_bytes(b"fixture")

            class HugeCapture:
                def isOpened(self):
                    return True

                def get(self, prop):
                    return {
                        cv2.CAP_PROP_FPS: 24.0,
                        cv2.CAP_PROP_FRAME_COUNT: 1.0,
                        cv2.CAP_PROP_FRAME_WIDTH: 8192.0,
                        cv2.CAP_PROP_FRAME_HEIGHT: 4320.0,
                    }.get(prop, 0.0)

                def release(self):
                    pass

            with patch.object(cv2, "VideoCapture", lambda _path: HugeCapture()):
                with self.assertRaisesRegex(ValueError, "4096px/16-megapixel"):
                    analyze_video(video, max_frames=1)

    def test_cli_exposes_delivery_aspect_and_threshold_controls(self):
        args = parser().parse_args([
            "video-quality", "candidate.mp4", "--out", "report.json",
            "--target-width", "1280", "--target-height", "720",
            "--max-frames", "12", "--min-sharpness", "3.5",
        ])
        self.assertEqual(args.command, "video-quality")
        self.assertEqual(args.max_frames, 12)
        self.assertEqual(args.min_sharpness, 3.5)
        self.assertEqual((args.target_width, args.target_height), (1280, 720))

    @unittest.skipUnless(OPENCV_AVAILABLE, "optional OpenCV extra is not installed")
    def test_real_video_sampling_reports_metrics_and_preserves_source(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "fixture.mp4"
            writer = cv2.VideoWriter(
                str(video),
                cv2.VideoWriter_fourcc(*"mp4v"),
                12.0,
                (640, 360),
            )
            if not writer.isOpened():
                self.skipTest("OpenCV mp4v writer is unavailable")
            for index in range(12):
                frame = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.rectangle(frame, (40 + index * 8, 80), (300 + index * 8, 280), (30, 220, 245), -1)
                cv2.putText(frame, f"EPRS {index}", (180, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                writer.write(frame)
            writer.release()
            before = video.read_bytes()

            report = analyze_video(video, max_frames=6, min_sharpness=1, min_contrast=3)

            self.assertEqual(report["schema"], "eprs.video-quality/v1")
            self.assertEqual(report["source"]["path"], video.name)
            self.assertEqual(report["source"]["path_kind"], "basename_redacted")
            self.assertEqual(len(report["source"]["sha256"]), 64)
            self.assertEqual(report["video"]["width"], 640)
            self.assertEqual(report["sampling"]["sampled_frames"], 6)
            self.assertGreater(report["metrics"]["edge_density_mean"], 0)
            self.assertIn(report["decision"], {"pass", "hold"})
            self.assertEqual(video.read_bytes(), before)

    @unittest.skipUnless(OPENCV_AVAILABLE, "optional OpenCV extra is not installed")
    def test_partial_sample_decode_is_held_even_when_remaining_frames_are_good(self):
        import cv2
        import numpy as np

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "fixture.mp4"
            video.write_bytes(b"fixture")
            class PartialCapture:
                def __init__(self, _path):
                    self.index = 0

                def isOpened(self):
                    return True

                def get(self, prop):
                    return {
                        cv2.CAP_PROP_FPS: 12.0,
                        cv2.CAP_PROP_FRAME_COUNT: 18.0,
                        cv2.CAP_PROP_FRAME_WIDTH: 640.0,
                        cv2.CAP_PROP_FRAME_HEIGHT: 360.0,
                    }.get(prop, 0.0)

                def set(self, _prop, value):
                    self.index = int(value)

                def read(self):
                    if self.index == 9:
                        return False, None
                    return True, np.zeros((360, 640, 3), dtype=np.uint8)

                def release(self):
                    pass

            with patch.object(cv2, "VideoCapture", PartialCapture):
                report = analyze_video(video, max_frames=18, min_sharpness=0, min_contrast=0)
            self.assertFalse(report["checks"]["sample_decode"])
            self.assertEqual(report["decision"], "hold")


if __name__ == "__main__":
    unittest.main()
