import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from eprs.context import build_agent_context, render_agent_context_markdown
from eprs.publication import (
    prepare_publication_handoff,
    record_publication_receipt,
    verify_publication_handoff,
)
from eprs.system import new_song, sha256, song_status


def release_package(song: Path, visibility: str = "private") -> tuple[Path, Path, Path]:
    recipe = {
        "schema": "eprs.release/v1",
        "title": "Publication fixture",
        "youtube": {"visibility_intent": visibility},
        "fixture": "Checksum-bound offline uploader contract.",
    }
    release_id = hashlib.sha256(
        json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    root = song / "FINAL" / f"publication-fixture-{release_id[:10]}"
    root.mkdir()
    video = root / "publication-fixture-youtube.mp4"
    video.write_bytes(b"fixture YouTube upload bytes\n")
    metadata = root / "youtube-metadata.json"
    metadata.write_text(json.dumps({
        "title": "Publication Fixture",
        "description": "An exact offline uploader fixture.",
        "tags": ["original music", "fixture"],
        "visibility_intent": visibility,
        "uploaded": False,
        "published": False,
    }, indent=2) + "\n")
    manifest = root / "release.json"
    manifest.write_text(json.dumps({
        "schema": "eprs.release-package/v1",
        "release_id": release_id,
        "packaged_at": "2026-08-03T12:00:00Z",
        "recipe": recipe,
        "artifacts": [{
            "role": "approved YouTube video",
            "path": str(video.relative_to(song)),
            "sha256": sha256(video),
        }, {
            "role": "YouTube metadata",
            "path": str(metadata.relative_to(song)),
            "sha256": sha256(metadata),
        }],
        "verification": {"approved_video": True, "copies_match": True},
        "publication": {"uploaded": False, "published": False, "platform_id": None},
    }, indent=2) + "\n")
    return manifest, video, metadata


def receipt_spec(
    root: Path,
    song: Path,
    handoff: Path,
    *,
    platform_id: str = "abcDEF_1234",
    visibility: str = "private",
    published_at: str | None = None,
) -> Path:
    spec = root / f"receipt-{platform_id}-{visibility}.json"
    spec.write_text(json.dumps({
        "schema": "eprs.youtube-publication-receipt/v1",
        "handoff": str(handoff.resolve().relative_to(song.resolve())),
        "platform_id": platform_id,
        "canonical_url": f"https://www.youtube.com/watch?v={platform_id}",
        "visibility": visibility,
        "uploaded_at": "2026-08-03T12:30:00-07:00",
        "published_at": published_at,
        "performed_by": "authorized fixture uploader",
        "authorization_note": "The fixture user explicitly authorized this exact upload and visibility.",
    }))
    return spec


class PublicationHandoffTests(unittest.TestCase):
    def test_legacy_v1_handoff_without_upload_assets_remains_valid_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Legacy Offline Publication")
            release, _, _ = release_package(song)
            handoff = prepare_publication_handoff(song, release)
            record = json.loads(handoff.read_text())
            record["recipe"].pop("upload_assets")
            record["handoff_id"] = hashlib.sha256(
                json.dumps(
                    record["recipe"], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
            handoff.write_text(json.dumps(record, indent=2) + "\n")

            self.assertEqual(verify_publication_handoff(song, handoff)[0], handoff)
            self.assertEqual(prepare_publication_handoff(song, release), handoff)

    def test_handoff_binds_exact_final_inputs_without_authorizing_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Offline Publication")
            release, video, metadata = release_package(song)

            handoff = prepare_publication_handoff(song, release)
            handoff_path, record = verify_publication_handoff(song, handoff)

            self.assertEqual(handoff_path, handoff)
            self.assertEqual(record["schema"], "eprs.youtube-publication-handoff/v1")
            self.assertFalse(record["authorization"]["upload_authorized"])
            self.assertFalse(record["authorization"]["publication_authorized"])
            self.assertIn("does not authorize", record["authorization"]["statement"])
            self.assertEqual(record["recipe"]["video"]["sha256"], sha256(video))
            self.assertEqual(record["recipe"]["metadata_artifact"]["sha256"], sha256(metadata))
            self.assertEqual(record["recipe"]["metadata"]["visibility_intent"], "private")
            self.assertEqual(prepare_publication_handoff(song, release), handoff)

            video.write_bytes(b"changed upload bytes\n")
            with self.assertRaisesRegex(ValueError, "artifact checksum has changed"):
                verify_publication_handoff(song, handoff)

    def test_receipt_is_idempotent_visibility_limited_and_refuses_duplicate_upload_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Private Receipt")
            release, _, _ = release_package(song, "private")
            handoff = prepare_publication_handoff(song, release)
            spec = receipt_spec(root, song, handoff)

            receipt = record_publication_receipt(spec, song)
            record = json.loads(receipt.read_text())
            self.assertEqual(record["schema"], "eprs.youtube-publication-receipt-record/v1")
            self.assertTrue(record["external_state"]["uploaded"])
            self.assertFalse(record["external_state"]["published"])
            self.assertEqual(record["external_state"]["visibility"], "private")
            self.assertEqual(record["recipe"]["uploaded_at"], "2026-08-03T19:30:00Z")
            self.assertIn("independently prove", record["authority"]["statement"])
            self.assertEqual(record_publication_receipt(spec, song), receipt)
            status = song_status(song, verify=True)
            self.assertEqual(status["inventory"]["publication_handoffs"], 1)
            self.assertEqual(status["inventory"]["publication_receipts"], 1)
            self.assertEqual(status["inventory"]["invalid_publications"], 0)
            self.assertEqual(status["attention"], [])
            packet = build_agent_context(song, verify=True)
            self.assertEqual(packet["recent_publications"][0]["receipts"][0]["platform_id"], "abcDEF_1234")
            self.assertFalse(packet["recent_publications"][0]["upload_authorized"])
            self.assertIn("## Publication handoffs and receipts", render_agent_context_markdown(packet))

            broader = receipt_spec(root, song, handoff, visibility="public", published_at="2026-08-03T19:31:00Z")
            with self.assertRaisesRegex(ValueError, "broader than release intent"):
                record_publication_receipt(broader, song)

            duplicate = receipt_spec(root, song, handoff, platform_id="otherID_789")
            with self.assertRaisesRegex(ValueError, "different platform_id"):
                record_publication_receipt(duplicate, song)

    def test_public_visibility_updates_are_append_only_and_validate_url_and_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            song = new_song(root, "Public Receipt")
            release, _, _ = release_package(song, "public")
            handoff = prepare_publication_handoff(song, release)
            private_spec = receipt_spec(root, song, handoff)
            private_receipt = record_publication_receipt(private_spec, song)

            public_spec = receipt_spec(
                root,
                song,
                handoff,
                visibility="public",
                published_at="2026-08-03T19:45:00Z",
            )
            public_receipt = record_publication_receipt(public_spec, song)
            self.assertNotEqual(private_receipt, public_receipt)
            self.assertEqual(len(list(public_receipt.parent.glob("*.json"))), 2)
            public = json.loads(public_receipt.read_text())
            self.assertTrue(public["external_state"]["published"])
            self.assertEqual(public["recipe"]["published_at"], "2026-08-03T19:45:00Z")

            invalid_url = json.loads(public_spec.read_text())
            invalid_url["canonical_url"] = "https://example.com/watch?v=abcDEF_1234"
            public_spec.write_text(json.dumps(invalid_url))
            with self.assertRaisesRegex(ValueError, "HTTPS YouTube URL"):
                record_publication_receipt(public_spec, song)

            too_early = receipt_spec(
                root,
                song,
                handoff,
                visibility="public",
                published_at="2026-08-03T19:00:00Z",
            )
            with self.assertRaisesRegex(ValueError, "cannot be before"):
                record_publication_receipt(too_early, song)


if __name__ == "__main__":
    unittest.main()
