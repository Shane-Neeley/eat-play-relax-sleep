import json
from pathlib import Path
import tempfile
import unittest

from eprs.runtime import format_performance_report, performance_report
from eprs.system import new_song


PS_FIXTURE = """
 101 1 06-00:00:00 S 7.5 0.2 20480 /repo/visuals/node_modules/.remotion/chrome-headless-shell/mac/chrome-headless-shell about:blank
 102 101 06-00:00:00 S 2.0 0.1 10240 /repo/visuals/node_modules/.remotion/chrome-headless-shell/mac/chrome-headless-shell --type=renderer
 201 200 02:30 R 10.0 0.3 30720 /repo/visuals/node_modules/.bin/remotion render src/index.ts PromptVisual
 301 1 20:00 S 0.0 0.1 4096 /Applications/Some Other Browser.app/browser
"""


class PerformanceReportTests(unittest.TestCase):
    def _fixture(self) -> str:
        from eprs.system import PROJECT_ROOT

        return PS_FIXTURE.replace("/repo", str(PROJECT_ROOT.resolve()))

    def test_reports_stale_orphans_separately_from_active_work(self):
        report = performance_report(stale_seconds=900, ps_output=self._fixture())
        self.assertEqual(report["schema"], "eprs.performance/v1")
        self.assertTrue(report["read_only"])
        self.assertEqual(report["summary"]["status"], "attention")
        self.assertEqual(report["summary"]["matching_processes"], 3)
        self.assertEqual(report["summary"]["orphaned_browser_roots"], 1)
        self.assertEqual(report["summary"]["stale_browser_roots"], 1)
        self.assertEqual(report["summary"]["active_processes"], 2)
        self.assertIn("STALE", format_performance_report(report))

    def test_song_report_surfaces_new_render_timing_and_legacy_sidecars(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder), "Timing Study")
            video = song / "video" / "timed.mp4.json"
            video.write_text(json.dumps({
                "schema": "eprs.visual-render/v1",
                "rendered_at": "2026-08-09T12:00:00Z",
                "duration_seconds": 8.0,
                "quality": "draft",
                "performance": {
                    "elapsed_seconds": 12.0,
                    "concurrency": 4,
                    "timeout_seconds": 600,
                },
            }))
            report = performance_report(song, ps_output="")
            timing = report["recent_visual_renders"][0]
            self.assertEqual(timing["render_to_media_ratio"], 1.5)
            self.assertEqual(timing["concurrency"], 4)
            self.assertEqual(report["summary"]["status"], "healthy")
            self.assertIn("12.0s render / 8.0s media", format_performance_report(report))

    def test_rejects_invalid_stale_threshold(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            performance_report(stale_seconds=0, ps_output="")


if __name__ == "__main__":
    unittest.main()
