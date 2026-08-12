from io import BytesIO
import json
import math
from array import array
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
from unittest.mock import patch

from eprs.inaturalist_audio import download_inaturalist_sound
from eprs.bioacoustic_models import MODEL_CATALOG_SCHEMA, bioacoustic_model_catalog
from eprs.inaturalist_study import STUDY_SCHEMA, study_inaturalist_sound
from eprs.system import new_song


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


def tone_bytes(seconds: float = 0.6, rate: int = 48_000) -> bytes:
    samples = array("h")
    for frame in range(round(seconds * rate)):
        # Three separated bursts make the measured spacing useful to a beat
        # study while remaining a deterministic synthetic test fixture.
        burst = (frame % round(rate * 0.2)) < round(rate * 0.06)
        value = math.sin(2 * math.pi * 330 * frame / rate) * 7000 if burst else 0
        samples.append(round(value))
    stream = BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples.tobytes())
    return stream.getvalue()


def observation_payload() -> bytes:
    return json.dumps({
        "results": [{
            "id": 390334715,
            "uri": "https://www.inaturalist.org/observations/390334715",
            "place_guess": "Test habitat",
            "taxon": {
                "name": "Melopsittacus undulatus",
                "preferred_common_name": "Budgerigar",
                "iconic_taxon_name": "Aves",
            },
            "sounds": [{
                "id": 2114662,
                "file_url": "https://static.inaturalist.org/sounds/2114662.mp3",
                "file_content_type": "audio/mpeg",
                "license_code": "cc0",
                "attribution": "Test contributor",
                "hidden": False,
            }],
        }]
    }).encode()


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class INaturalistStudyTests(unittest.TestCase):
    def test_model_catalog_marks_open_tools_and_frontier_boundaries(self):
        catalog = bioacoustic_model_catalog()
        self.assertEqual(catalog["schema"], MODEL_CATALOG_SCHEMA)
        ids = {model["id"] for model in catalog["models"]}
        self.assertTrue({"naturelm-audio", "perch-2", "birdnet", "dolphingemma"} <= ids)
        self.assertIn("not proof of animal intent", catalog["interpretation_boundary"])

    def test_study_maps_one_sound_to_five_creative_domains(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Study Sound")
            with patch(
                "eprs.inaturalist_audio.urlopen",
                side_effect=[FakeResponse(observation_payload()), FakeResponse(tone_bytes())],
            ):
                reference, _, _ = download_inaturalist_sound(
                    390334715, song, "budgerigar reference", sound_id=2114662,
                )
            manifest, record = study_inaturalist_sound(
                reference, song, "budgerigar rhythm", key="C", scale="minor-pentatonic",
            )
            self.assertTrue(manifest.is_file())
            self.assertEqual(record["schema"], STUDY_SCHEMA)
            self.assertEqual(record["source"]["iNaturalist"]["sound_id"], 2114662)
            self.assertEqual(record["creative_map"]["lyrics"]["subject"], "Budgerigar")
            self.assertEqual(record["bioacoustic_ai"]["schema"], MODEL_CATALOG_SCHEMA)
            self.assertEqual(
                sorted(record["creative_map"]),
                ["beats", "lyrics", "noises", "tones", "vocals"],
            )
            self.assertFalse(record["interpretation_limits"]["animal_language_translation"])
            repeated_manifest, repeated = study_inaturalist_sound(
                reference, song, "budgerigar rhythm", key="C", scale="minor-pentatonic",
            )
            self.assertEqual(repeated_manifest, manifest)
            self.assertEqual(repeated["study_id"], record["study_id"])


if __name__ == "__main__":
    unittest.main()
