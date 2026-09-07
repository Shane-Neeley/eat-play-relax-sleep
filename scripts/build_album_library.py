#!/usr/bin/env python3
"""Snapshot the song pool and deduplicated field references without moving media.

Run with PYTHONPATH=src. Output is a new directory; human curation belongs in
a separate document so rescanning cannot erase decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from eprs.inaturalist_audio import INATURALIST_SOUND_SCHEMA, publication_status_for_license
from eprs.producer import catalog


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def snapshot(root: Path, album: str, libraries: list[Path]) -> dict:
    root = root.resolve()
    if not album or Path(album).name != album or album in {".", ".."}:
        raise ValueError("album must be a single folder name")
    if not (root / "albums" / album / "album.json").is_file():
        raise ValueError(f"Album manifest missing: {album}")
    discovered = catalog(root)
    favorites = {x["slug"]: x for x in discovered["favorites"]
                 if Path(x["path"]).parent.name == album}
    warnings = list(discovered["warnings"])
    songs = {}
    workspaces = []
    for manifest in sorted((root / "songs").glob("*/song.json")):
        if not manifest.resolve().is_relative_to(root):
            warnings.append(f"Skipped external song: {manifest.parent.name}")
            continue
        detail = read_object(manifest)
        slug = manifest.parent.name
        workspaces.append(manifest.parent)
        songs[slug] = {
            "id": f"song:{slug}", "slug": slug, "title": detail.get("title", slug),
            "workspace": str(manifest.parent.relative_to(root)),
            "manifest_status": detail.get("status"),
            "album_candidate": slug in favorites, "handoff": favorites.get(slug),
            "curation_status": "unreviewed", "final_track_number": None,
        }
    for slug, favorite in favorites.items():
        if slug not in songs:
            songs[slug] = {"id": f"song:{slug}", "slug": slug, "title": favorite["title"],
                           "workspace": None, "manifest_status": None,
                           "album_candidate": True, "handoff": favorite,
                           "curation_status": "unreviewed", "final_track_number": None}
            warnings.append(f"No matching canonical song manifest for handoff: {slug}")
    for library in libraries:
        path = (root / library).resolve()
        if not path.is_relative_to(root) or not (path / "song.json").is_file():
            raise ValueError(f"Library must be an EPRS workspace inside root: {library}")
        workspaces.append(path)
    sounds = {}
    for workspace in sorted(set(workspaces)):
        sidecars = [p for folder in ("inaturalist-audio", "external-audio")
                    for p in (workspace / "references" / folder).glob("**/*.json")]
        for sidecar in sorted(sidecars):
            if not sidecar.resolve().is_relative_to(root):
                warnings.append(f"Skipped external sidecar: {sidecar.name}")
                continue
            data = read_object(sidecar)
            if data.get("schema") not in {INATURALIST_SOUND_SCHEMA, "eprs.external-audio/v1"}:
                continue
            sound, source, output = data["sound"], data["source"], data["output"]
            provider = "inaturalist" if data["schema"] == INATURALIST_SOUND_SCHEMA else source["provider"].lower()
            key = f"{provider}:{sound['id']}"
            media = (workspace / output["path"]).resolve()
            if not media.is_relative_to(workspace.resolve()):
                warnings.append(f"Skipped escaping media path: {sidecar.relative_to(root)}")
                continue
            digest = None
            if media.is_file():
                with media.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
            # Record integrity per copy; a second copy must never hide drift.
            copy = {"path": str(media.relative_to(root)), "sidecar": str(sidecar.relative_to(root)),
                    "expected_sha256": output.get("sha256"), "actual_sha256": digest,
                    "integrity": "verified" if digest and digest == output.get("sha256") else "missing-or-mismatch",
                    "role": data.get("role"), "retrieved_at": data.get("retrieved_at")}
            entry = sounds.setdefault(key, {
                "id": key, "observation_url": source.get("url"), "taxon": source.get("taxon"),
                "sound": sound, "rights_status": publication_status_for_license(sound.get("license_code")),
                "copies": [], "provenance_conflict": False, "provider": provider,
                "source_kind": source.get("kind", "community field recording"),
                "window_review": "consult song audits; not inferred by inventory",
                "source_use_eligible": False,
            })
            if entry["sound"] != sound or entry["observation_url"] != source.get("url"):
                entry["provenance_conflict"] = True
                warnings.append(f"Conflicting sound provenance: {key}")
            entry["copies"].append(copy)
            if copy["integrity"] != "verified":
                warnings.append(f"Missing or changed source: {copy['path']}")
    return {"schema": "eprs.album-library-snapshot/v1",
            "created_at": datetime.now(timezone.utc).isoformat(), "album": album,
            "boundary": "Inventory only. Status, taste, audible identity and release clearance are not inferred.",
            "songs": sorted(songs.values(), key=lambda x: (not x["album_candidate"], x["slug"])),
            "sounds": sorted(sounds.values(), key=lambda x: x["id"]), "warnings": warnings}


def cell(value: object) -> str:
    return str(value if value is not None else "unknown").replace("|", "\\|").replace("\n", " ")


def write_snapshot(data: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    (out / "catalog.json").write_text(json.dumps(data, indent=2) + "\n")
    lines = ["# Song pool", "", data["boundary"], "",
             "Canonical manifest statuses can be stale; they are reproduced as evidence, not reconciled approval.", "",
             "| Candidate ID | Title | In album folder | Manifest status | Workspace |",
             "| --- | --- | --- | --- | --- |"]
    for song in data["songs"]:
        lines.append("| " + " | ".join(cell(song[k]) for k in
                     ("id", "title", "album_candidate", "manifest_status", "workspace")) + " |")
    (out / "SONG_POOL.md").write_text("\n".join(lines) + "\n")
    lines = ["# Sound inventory", "", "One row per provider/sound ID; all copies and hashes are in catalog.json.",
             "No row is an audible-window approval. Preserve source credits when making derivatives.", "",
             "| Sound ID | Taxon label | License | Copies | Integrity | Observation |",
             "| --- | --- | --- | --- | --- | --- |"]
    for sound in data["sounds"]:
        integrity = "verified" if all(x["integrity"] == "verified" for x in sound["copies"]) else "CHECK"
        if sound["provenance_conflict"]:
            integrity += "; provenance conflict"
        values = (sound["id"], (sound["taxon"] or {}).get("scientific_name"),
                  sound["sound"].get("license_code"), len(sound["copies"]), integrity, sound["observation_url"])
        lines.append("| " + " | ".join(cell(x) for x in values) + " |")
    (out / "SOUND_INVENTORY.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--album", required=True)
    parser.add_argument("--library", type=Path, action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = snapshot(args.root, args.album, args.library)
    write_snapshot(data, args.out)
    print(json.dumps({"songs": len(data["songs"]), "sounds": len(data["sounds"]),
                      "warnings": data["warnings"], "output": str(args.out)}))


if __name__ == "__main__":
    main()
