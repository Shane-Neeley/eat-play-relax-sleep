import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eprs.inaturalist_photo import (
    download_inaturalist_photo,
    verify_inaturalist_photo,
)
from eprs.system import new_song, sha256
from eprs.visuals import _stage_inaturalist_photographs, compile_prompt, validate_spec
from eprs.youtube_assets import _thumbnail


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.position = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self.payload) - self.position
        chunk = self.payload[self.position:self.position + size]
        self.position += len(chunk)
        return chunk


def observation_payload(license_code: str = "cc-by", photo_count: int = 1) -> bytes:
    photos = [
        {
            "id": 715632441 + index,
            "license_code": license_code,
            "original_dimensions": {"width": 1542, "height": 2048},
            "url": (
                "https://inaturalist-open-data.s3.amazonaws.com/photos/"
                f"{715632441 + index}/square.jpg"
            ),
            "attribution": f"(c) Field Photographer, some rights reserved ({license_code.upper()})",
            "hidden": False,
        }
        for index in range(photo_count)
    ]
    return json.dumps({
        "results": [{
            "id": 390608319,
            "uri": "https://www.inaturalist.org/observations/390608319",
            "observed_on": "2026-08-12",
            "place_guess": "A precise place that should not be copied into visual metadata",
            "user": {"login": "field-photographer"},
            "taxon": {
                "id": 75765,
                "name": "Bidens cernua",
                "preferred_common_name": "Nodding Beggarticks",
                "iconic_taxon_name": "Plantae",
            },
            "photos": photos,
        }]
    }).encode()


class INaturalistPhotoTests(unittest.TestCase):
    def test_freezes_attributed_photo_and_stages_it_for_visuals(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Photo Reference")
            image_bytes = b"\xff\xd8\xff\xe0" + b"licensed-photo-fixture"
            responses = [
                FakeResponse(observation_payload()),
                FakeResponse(image_bytes),
                FakeResponse(observation_payload()),
            ]
            with patch("eprs.inaturalist_photo.urlopen", side_effect=responses):
                reference, sidecar, record = download_inaturalist_photo(
                    390608319,
                    song,
                    "marsh texture",
                    photo_id=715632441,
                    note="Let the real plant texture sit behind the signal world.",
                )
                repeated, repeated_sidecar, _ = download_inaturalist_photo(
                    390608319,
                    song,
                    "marsh texture",
                    photo_id=715632441,
                )

            self.assertEqual(repeated, reference)
            self.assertEqual(repeated_sidecar, sidecar)
            self.assertEqual(record["photo"]["license_code"], "cc-by")
            self.assertTrue(record["rights"]["visual_release_ready"])
            self.assertNotIn("place_guess", record["source"])
            self.assertEqual(record["output"]["sha256"], sha256(reference))
            verify_inaturalist_photo(reference, require_publication_compatible=True)

            score_dir = song / "visuals"
            score_dir.mkdir(exist_ok=True)
            score_path = score_dir / "visual.json"
            score = compile_prompt("slow constellation with a field photograph", "Field Signal", 18)
            score["photographs"] = [{
                "path": str(Path("..") / reference.relative_to(song.resolve())),
                "opacity": 0.3,
                "treatment": "soft-light",
            }]
            score_path.write_text(json.dumps(score))
            validate_spec(score)
            media_dir = root / "media"
            media_dir.mkdir()
            render_spec, provenance = _stage_inaturalist_photographs(
                score, score_path, media_dir
            )
            self.assertEqual(render_spec["photographs"][0]["label"], "Nodding Beggarticks")
            self.assertEqual(render_spec["photographs"][0]["licenseCode"], "CC-BY")
            self.assertEqual(provenance[0]["observation_id"], 390608319)
            self.assertTrue((media_dir / Path(render_spec["photographs"][0]["file"]).name).is_file())

            with patch("eprs.youtube_assets.probe", return_value={
                "streams": [{"codec_type": "video", "width": 1280, "height": 720}]
            }):
                thumbnail, _, _ = _thumbnail(song, {
                    "path": str(reference.relative_to(song.resolve())),
                    "alt_text": "Nodding beggarticks from an attributed iNaturalist observation.",
                    "review_question": "Does the crop remain truthful and legible?",
                })
            self.assertEqual(thumbnail["iNaturalist_source"]["photo_id"], 715632441)
            self.assertEqual(thumbnail["iNaturalist_source"]["license_code"], "cc-by")

    def test_reference_only_license_cannot_enter_visual_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Reference Only Photo")
            with patch("eprs.inaturalist_photo.urlopen", side_effect=[
                FakeResponse(observation_payload("cc-by-nc")),
                FakeResponse(b"\xff\xd8\xff\xe0reference-only"),
            ]):
                reference, _, record = download_inaturalist_photo(
                    390608319, song, "private study", photo_id=715632441
                )
            self.assertEqual(record["rights"]["publication_status"], "noncommercial-only")
            with self.assertRaisesRegex(ValueError, "not cleared"):
                verify_inaturalist_photo(reference, require_publication_compatible=True)

    def test_multiple_photos_require_an_explicit_photo_id(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder) / "songs", "Multiple Photos")
            with patch(
                "eprs.inaturalist_photo.urlopen",
                return_value=FakeResponse(observation_payload(photo_count=2)),
            ):
                with self.assertRaisesRegex(ValueError, "multiple photos"):
                    download_inaturalist_photo(390608319, song, "visual reference")

    def test_unlicensed_photo_is_not_downloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            song = new_song(Path(folder) / "songs", "Unlicensed Photo")
            with patch(
                "eprs.inaturalist_photo.urlopen",
                return_value=FakeResponse(observation_payload("")),
            ):
                with self.assertRaisesRegex(ValueError, "reusable Creative Commons"):
                    download_inaturalist_photo(
                        390608319, song, "visual reference", photo_id=715632441
                    )


if __name__ == "__main__":
    unittest.main()
