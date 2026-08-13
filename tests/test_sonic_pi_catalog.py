import json
from pathlib import Path
import tempfile
import unittest

from eprs.sonic_pi_catalog import find_entry, load_catalog, search_entries, summarize


class SonicPiCatalogTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        (root / "synths.json").write_text(json.dumps({"pages": [{
            "key": "beep",
            "title": "Sine Wave",
            "doc_html": "<p>A pure tone.</p>",
            "opts": [{"name": "phase_offset", "default": 0, "slidable": True}],
        }]}))
        (root / "fx.json").write_text(json.dumps({"pages": [{
            "key": "echo", "title": "Echo", "doc_html": "<p>Repeating delay.</p>"
        }]}))
        (root / "samples.json").write_text(json.dumps({"groups": [{
            "title": "Animal-adjacent", "samples": ["misc_crow"]
        }]}))
        (root / "lang.json").write_text(json.dumps({"pages": [{
            "key": "spread", "summary": "Euclidean rhythm", "usage": "spread hits, size"
        }]}))

    def test_catalog_normalizes_all_reference_kinds(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            catalog = load_catalog(root)
            self.assertEqual(
                summarize(catalog)["counts"],
                {"synth": 1, "fx": 1, "sample": 1, "function": 1},
            )
            self.assertEqual(find_entry(catalog, "sample", ":misc_crow")["group"], "Animal-adjacent")

    def test_search_reads_docs_and_option_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            catalog = load_catalog(root)
            self.assertEqual(search_entries(catalog, "phase offset")[0]["name"], "beep")
            self.assertEqual(search_entries(catalog, "euclidean", ["function"])[0]["name"], "spread")


if __name__ == "__main__":
    unittest.main()
