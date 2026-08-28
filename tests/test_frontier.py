import json
from pathlib import Path
import tempfile
import unittest

from eprs.frontier import validate_frontier_watch


ROOT = Path(__file__).resolve().parents[1]


class FrontierWatchTests(unittest.TestCase):
    def test_public_template_is_portable_and_requires_both_oracles(self):
        path = ROOT / "templates" / "frontier-watch.json"
        source_path, record = validate_frontier_watch(path)

        self.assertEqual(source_path, path.resolve())
        self.assertEqual(record["schema"], "eprs.frontier-watch/v1")
        candidate = record["candidates"][0]
        self.assertEqual(candidate["status"]["stage"], "lead")
        self.assertIn("oracle", candidate["capability_test"])
        self.assertIn("oracle", candidate["creative_test"])
        self.assertEqual(candidate["empirical_boundary"]["mode"], "compute-closed")
        self.assertIn("thought_experiment", candidate["human_direction"])
        self.assertIn("counterexample_search", candidate["formal_pressure"])
        serialized = json.dumps(record)
        self.assertNotIn("shaneneeley.com", serialized)
        self.assertNotIn("CashForClankers", serialized)

    def test_frontier_watch_rejects_missing_independent_test_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "frontier.json"
            payload = json.loads((ROOT / "templates" / "frontier-watch.json").read_text())
            payload["candidates"][0]["capability_test"].pop("oracle")
            path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(ValueError, "capability_test oracle"):
                validate_frontier_watch(path)

    def test_frontier_watch_rejects_unknown_source_reference(self):
        payload = json.loads((ROOT / "templates" / "frontier-watch.json").read_text())
        payload["candidates"][0]["source_ids"] = ["does-not-exist"]

        with self.assertRaisesRegex(ValueError, "unknown ids"):
            validate_frontier_watch(payload)

    def test_frontier_watch_keeps_old_packets_backward_compatible(self):
        payload = json.loads((ROOT / "templates" / "frontier-watch.json").read_text())
        payload["candidates"][0].pop("human_direction")
        payload["candidates"][0].pop("formal_pressure")
        payload["candidates"][0].pop("empirical_boundary")

        _, record = validate_frontier_watch(payload)

        candidate = record["candidates"][0]
        self.assertEqual(candidate["empirical_boundary"]["mode"], "unspecified")
        self.assertEqual(candidate["human_direction"]["thought_experiment"], "")

    def test_frontier_watch_rejects_unknown_empirical_boundary_mode(self):
        payload = json.loads((ROOT / "templates" / "frontier-watch.json").read_text())
        payload["candidates"][0]["empirical_boundary"]["mode"] = "all-compute-proves-reality"

        with self.assertRaisesRegex(ValueError, "empirical_boundary mode"):
            validate_frontier_watch(payload)


if __name__ == "__main__":
    unittest.main()
