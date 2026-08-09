import json
from pathlib import Path
import tempfile
import unittest

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.lyrics import (
    create_lyric_development,
    load_lyric_development,
    review_lyric_variant,
)
from eprs.system import ingest, new_song, sha256, song_status
from eprs.work import create_work_item, finish_work_item, start_work_item


def lyrics_score(source: Path | None = None) -> dict:
    sources = [] if source is None else [{
        "id": "seed-fragments",
        "role": "original lyric fragments",
        "path": str(source),
        "note": "Keep meaningful wording alternatives and the space after the last image.",
        "rights_note": "Original private project writing; public wording is not approved.",
    }]
    source_ids = ["seed-fragments"] if source is not None else []
    return {
        "schema": "eprs.lyrics/v1",
        "title": "Porch-light answer variants",
        "intent": "Find words a family can answer together without making the room feel scripted.",
        "language": "English",
        "voice_note": "Plainspoken first-person plural; leave room for breath and overlap.",
        "preserve": ["Porch light image", "A released ending", "Meaningful variants"],
        "avoid": ["Forced rhyme", "Copying reference lyrics", "Silently choosing a final version"],
        "sources": sources,
        "variants": [{
            "id": "Open Door",
            "role": "family refrain candidate",
            "text": "Leave the porch light on\nwe are still coming home",
            "intent": "A direct shared answer with an open final vowel.",
            "source_ids": source_ids,
            "singability_note": "Test whether the first line fits one breath without tightening the family entrance.",
            "unresolved": ["Whether 'still' feels hopeful or delayed"],
        }, {
            "id": "Room Answers",
            "role": "family refrain alternate",
            "text": "Porch light in the window\nlet the whole room answer",
            "intent": "Name the room as part of the response.",
            "source_ids": source_ids,
            "singability_note": "The consonants may crowd a loose group entrance; hear it before revising.",
            "unresolved": ["Whether the second line is too explanatory"],
        }],
    }


class LyricDevelopmentTests(unittest.TestCase):
    def test_lyrics_preserve_sources_variants_and_explicit_review_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lyric Variants")
            source = root / "fragments.txt"
            source.write_text("porch light / everybody answers / coming home\n")
            before = sha256(source)
            spec = root / "lyrics.json"
            spec.write_text(json.dumps(lyrics_score(source)))

            path = create_lyric_development(spec, song)
            _, record = load_lyric_development(song, path)
            self.assertEqual(record["schema"], "eprs.lyric-development/v1")
            self.assertEqual([variant["id"] for variant in record["recipe"]["variants"]], [
                "open-door", "room-answers",
            ])
            frozen = path.parent / record["sources"]["seed-fragments"]["path"]
            self.assertEqual(sha256(frozen), before)
            self.assertEqual(sha256(source), before)
            self.assertEqual(create_lyric_development(spec, song).resolve(), path.resolve())
            self.assertEqual(record["review_state"], "pending")

            review_lyric_variant(
                song, path, "Open Door", "keep",
                "Read and sang the full refrain; the shared vowel leaves breath for the room.",
            )
            review_lyric_variant(
                song, path, "Room Answers", "alternate",
                "Keep this language available; the consonants currently crowd the group entrance.",
            )
            _, reviewed = load_lyric_development(song, path)
            self.assertEqual(reviewed["review_state"], "complete")
            self.assertEqual(reviewed["reviews"]["open-door"]["decision"], "keep")
            self.assertEqual(reviewed["reviews"]["room-answers"]["decision"], "alternate")
            self.assertEqual(reviewed["recipe"]["variants"][1]["text"], lyrics_score(source)["variants"][1]["text"])

            status = song_status(song, verify=True)
            counts = status["inventory"]["lyric_developments"]
            self.assertEqual(counts["total"], 1)
            self.assertEqual(counts["variants"], 2)
            self.assertEqual(counts["keep"], 1)
            self.assertEqual(counts["alternate"], 1)
            self.assertEqual(counts["complete_records"], 1)
            self.assertEqual(counts["invalid"], 0)
            packet = build_agent_context(song, verify=True)
            summary = packet["recent_lyrics"][0]
            self.assertEqual(summary["variants"][0]["decision"], "keep")
            self.assertIn("Leave the porch light on", summary["variants"][0]["text"])
            self.assertNotIn("content", summary["sources"][0])
            self.assertIn("## Recent lyric variants", render_agent_context_markdown(packet))
            self.assertEqual(packet["attention"], [])

            review_lyric_variant(
                song, path, "Open Door", "alternate",
                "After singing beside guitar, retain it as an alternate while the cadence changes.",
            )
            _, revised_review = load_lyric_development(song, path)
            self.assertEqual(len(revised_review["reviews"]["open-door"]["listening_notes"]), 2)
            self.assertEqual(revised_review["reviews"]["open-door"]["decision"], "alternate")

    def test_lyrics_can_reference_immutable_raw_and_refuse_source_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Sung Fragments")
            take = root / "sung-idea.raw"
            take.write_bytes(b"private sung lyric idea")
            raw, _ = ingest(take, song, "sung lyric idea", rights_note="Private; do not publish.")
            spec = root / "lyrics.json"
            spec.write_text(json.dumps(lyrics_score(raw)))
            path = create_lyric_development(spec, song)
            _, record = load_lyric_development(song, path)
            source = record["sources"]["seed-fragments"]
            self.assertEqual(source["storage"], "song-reference")
            self.assertEqual(source["base"], "song")
            self.assertFalse((path.parent / "sources").exists())

            raw.write_bytes(b"changed raw evidence")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                load_lyric_development(song, path)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["lyric_developments"]["invalid"], 1)
            self.assertIn("Lyrics verification failed", " ".join(status["attention"]))

    def test_lyrics_validate_attribution_and_optional_completed_work_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lyric Work")
            score = lyrics_score()
            spec = root / "lyrics.json"
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "source or a completed work origin"):
                create_lyric_development(spec, song)

            source = root / "fragments.txt"
            source.write_text("one private fragment\n")
            score = lyrics_score(source)
            score["variants"][0]["source_ids"] = ["missing-source"]
            spec.write_text(json.dumps(score))
            with self.assertRaisesRegex(ValueError, "unknown sources"):
                create_lyric_development(spec, song)

            item_path = create_work_item(
                song,
                "Develop lyric variants",
                "lyrics",
                "Preserve alternatives and do not silently choose a final lyric.",
            )
            item_id = json.loads(item_path.read_text())["id"]
            start_work_item(song, item_id, "lyrics-agent")
            result = root / "work-result.md"
            result.write_text("Two lyric alternatives were retained.\n")
            finish_work_item(
                song, item_id, "Preserved two alternatives.", "complete", [("lyric note", result)]
            )
            score = lyrics_score()
            score["work"] = {"item": item_id, "run": 1}
            spec.write_text(json.dumps(score))
            path = create_lyric_development(spec, song)
            _, record = load_lyric_development(song, path)
            self.assertEqual(record["recipe"]["work_origin"]["item_id"], item_id)

            frozen_result = song / record["recipe"]["work_origin"]["results"][0]["path"]
            frozen_result.write_text("changed work result\n")
            with self.assertRaisesRegex(ValueError, "work origin result is missing or changed"):
                load_lyric_development(song, path)

    def test_lyrics_resolution_stays_inside_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lyric Boundary")
            outside = root / "outside" / "lyrics.json"
            outside.parent.mkdir()
            outside.write_text("{}")
            with self.assertRaisesRegex(ValueError, "inside the song"):
                load_lyric_development(song, outside)

    def test_lyrics_review_lock_prevents_concurrent_last_writer_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root / "songs", "Lyric Review Lock")
            source = root / "fragments.txt"
            source.write_text("one line\n")
            spec = root / "lyrics.json"
            spec.write_text(json.dumps(lyrics_score(source)))
            path = create_lyric_development(spec, song)
            lock = path.parent / ".lyrics-review.lock"
            lock.write_text("simulated concurrent review\n")
            with self.assertRaisesRegex(FileExistsError, "locked by another process"):
                review_lyric_variant(song, path, "open-door", "keep", "A real review note.")
            self.assertIn("Lyrics review lock requires inspection", " ".join(song_status(song)["attention"]))
            self.assertEqual(
                load_lyric_development(song, path)[1]["reviews"]["open-door"]["decision"],
                "not-reviewed",
            )


if __name__ == "__main__":
    unittest.main()
