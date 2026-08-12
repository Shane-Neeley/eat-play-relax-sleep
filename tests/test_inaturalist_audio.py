from array import array
from io import BytesIO
import json
from pathlib import Path
import math
import tempfile
import unittest
import wave
from unittest.mock import patch

from eprs.inaturalist_audio import download_inaturalist_sound
from eprs.lineage import trace_audio_lineage, validate_external_audio_visibility
from eprs.selection import select_audio
from eprs.system import new_song, sha256


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


def tone_bytes(seconds: float = 0.08, rate: int = 48_000) -> bytes:
    samples = array("h", (
        round(math.sin(2 * math.pi * 220 * frame / rate) * 6000)
        for frame in range(round(seconds * rate))
    ))
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
            "id": 168281317,
            "uri": "https://www.inaturalist.org/observations/168281317",
            "observed_on": "2023-06-15",
            "place_guess": "Gabon",
            "user": {"login": "bureaubenjamin"},
            "taxon": {
                "name": "Gorilla gorilla gorilla",
                "preferred_common_name": "Western Lowland Gorilla",
                "iconic_taxon_name": "Mammalia",
            },
            "sounds": [{
                "id": 744247,
                "file_url": "https://static.inaturalist.org/sounds/744247.mp3",
                "file_content_type": "audio/mpeg",
                "license_code": "cc-by-nc",
                "attribution": "(c) bureaubenjamin, some rights reserved (CC BY-NC)",
                "hidden": False,
            }],
        }]
    }).encode()


class INaturalistAudioTests(unittest.TestCase):
    def test_freezes_attributed_reference_and_traces_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Sound Reference")
            audio = tone_bytes()
            responses = [
                FakeResponse(observation_payload()),
                FakeResponse(audio),
                FakeResponse(observation_payload()),
                FakeResponse(audio),
            ]
            with patch("eprs.inaturalist_audio.urlopen", side_effect=responses):
                reference, sidecar, record = download_inaturalist_sound(
                    168281317,
                    song,
                    "gorilla call reference",
                    sound_id=744247,
                    note="Study spacing; invent the musical response.",
                )
                repeated, repeated_sidecar, _ = download_inaturalist_sound(
                    168281317,
                    song,
                    "gorilla call reference",
                    sound_id=744247,
                    note="Study spacing; invent the musical response.",
                )

            self.assertEqual(repeated, reference)
            self.assertEqual(repeated_sidecar, sidecar)
            self.assertEqual(record["rights"]["publication_status"], "noncommercial-only")
            self.assertEqual(record["sound"]["license_code"], "cc-by-nc")
            self.assertEqual(record["source"]["url"], "https://www.inaturalist.org/observations/168281317")
            self.assertEqual(record["output"]["sha256"], sha256(reference))

            lineage = trace_audio_lineage(song, reference)
            self.assertEqual(len(lineage["external_audio"]), 1)
            self.assertEqual(lineage["external_audio"][0]["sound_id"], 744247)
            self.assertEqual(lineage["untraced_leaves"], [])
            with self.assertRaisesRegex(ValueError, "noncommercial-only"):
                validate_external_audio_visibility(lineage, "public", "release")
            validate_external_audio_visibility(lineage, "private", "release")

            selected, selection_sidecar = select_audio(
                reference,
                song,
                "gorilla call phrase",
                start=0,
                duration=0.04,
                note="Keep the attack and decay as a found-sound texture.",
            )
            self.assertTrue(selection_sidecar.is_file())
            selected_lineage = trace_audio_lineage(song, selected)
            self.assertEqual(len(selected_lineage["external_audio"]), 1)
            self.assertEqual(selected_lineage["external_audio"][0]["observation_id"], 168281317)

    def test_multiple_sounds_require_an_explicit_sound_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Multiple Sounds")
            payload = json.loads(observation_payload())
            payload["results"][0]["sounds"].append({
                **payload["results"][0]["sounds"][0],
                "id": 744248,
            })
            with patch(
                "eprs.inaturalist_audio.urlopen",
                return_value=FakeResponse(json.dumps(payload).encode()),
            ):
                with self.assertRaisesRegex(ValueError, "multiple sounds"):
                    download_inaturalist_sound(168281317, song, "animal call")


if __name__ == "__main__":
    unittest.main()
