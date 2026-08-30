import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "youtube_analytics_report.py"
SPEC = importlib.util.spec_from_file_location("youtube_analytics_report", MODULE_PATH)
assert SPEC and SPEC.loader
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class YouTubeAnalyticsReportTests(unittest.TestCase):
    def test_summary_query_is_channel_owner_readback(self):
        query = REPORT.query_parameters(
            "2026-08-01",
            "2026-08-28",
            REPORT.SUMMARY_METRICS,
        )
        self.assertEqual(query["ids"], "channel==MINE")
        self.assertEqual(query["startDate"], "2026-08-01")
        self.assertIn("engagedViews", query["metrics"])
        self.assertNotIn("dimensions", query)

    def test_video_query_is_sorted_and_bounded(self):
        query = REPORT.query_parameters(
            "2026-08-01",
            "2026-08-28",
            REPORT.VIDEO_METRICS,
            dimensions="video",
            sort="-views",
            max_results=50,
        )
        self.assertEqual(query["dimensions"], "video")
        self.assertEqual(query["sort"], "-views")
        self.assertEqual(query["maxResults"], 50)
        self.assertIn("averageViewPercentage", query["metrics"])

    def test_invalid_date_is_rejected(self):
        with self.assertRaises(Exception):
            REPORT._iso_date("2026-02-30")


if __name__ == "__main__":
    unittest.main()
