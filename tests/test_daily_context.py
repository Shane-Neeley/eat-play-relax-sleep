import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DailyContextTemplateTests(unittest.TestCase):
    def test_public_template_is_site_agnostic_and_contract_shaped(self):
        path = ROOT / "templates" / "daily-context.json"
        payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["schema"], "eprs.daily-context/v1")
        self.assertEqual(payload["date"], "2026-01-01")
        self.assertGreaterEqual(len(payload["passages"]), 1)
        self.assertEqual(payload["selection"]["mode"], "date-stable")
        self.assertIn("public_metadata", payload["privacy"])

        for passage in payload["passages"]:
            self.assertTrue(passage["id"])
            self.assertTrue(passage["kind"])
            self.assertTrue(passage["text"])
            self.assertIn("source", passage)
            self.assertIn("rights", passage["source"])
            self.assertIn("handling", passage)

if __name__ == "__main__":
    unittest.main()
