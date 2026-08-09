"""Checksum-verified audio lineage traversal for delivery and handoff gates."""

from __future__ import annotations

import json
from pathlib import Path

from .system import load_song_manifest, sha256


SOURCE_FIELDS = {
    "eprs.audio-selection/v1": ("source",),
    "eprs.process-render/v1": ("source",),
    "eprs.comp-render/v1": ("sources",),
    "eprs.mix-render/v1": ("sources",),
    "eprs.daw-return-mix/v1": ("sources",),
    "eprs.master-render/v1": ("source",),
}


def _safe_song_path(song: Path, value: object, description: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{description} has no valid path")
    path = (song / value).resolve()
    try:
        path.relative_to(song)
    except ValueError as exc:
        raise ValueError(f"{description} escapes the song workspace") from exc
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def trace_audio_lineage(song: str | Path, artifact: str | Path) -> dict:
    """Trace known derived-audio schemas to immutable raw recordings.

    Unknown leaves are retained as explicit evidence rather than guessed to be
    performances or synthesis.
    """
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    requested = Path(artifact)
    root = requested.resolve() if requested.is_absolute() else (song_path / requested).resolve()
    try:
        root.relative_to(song_path)
    except ValueError as exc:
        raise ValueError("audio lineage root must be inside the song workspace") from exc
    if not root.is_file():
        raise FileNotFoundError(root)

    raw_root = (song_path / "recordings" / "raw").resolve()
    visited: set[Path] = set()
    artifacts: list[dict] = []
    raw: dict[str, dict] = {}
    unknown: dict[str, dict] = {}

    def walk(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited:
            return
        visited.add(resolved)
        try:
            resolved.relative_to(song_path)
        except ValueError as exc:
            raise ValueError("audio lineage source escapes the song workspace") from exc
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        relative = str(resolved.relative_to(song_path))
        digest = sha256(resolved)
        try:
            resolved.relative_to(raw_root)
        except ValueError:
            pass
        else:
            sidecar = resolved.with_suffix(resolved.suffix + ".json")
            if not sidecar.is_file():
                raise ValueError(f"raw lineage source lacks provenance: {relative}")
            try:
                metadata = json.loads(sidecar.read_text())
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid raw lineage provenance {sidecar}: {exc.msg}") from exc
            if metadata.get("schema") != "eprs.recording/v1" or metadata.get("sha256") != digest:
                raise ValueError(f"raw lineage source provenance is invalid or changed: {relative}")
            raw[relative] = {
                "path": relative,
                "sha256": digest,
                "provenance_path": str(sidecar.relative_to(song_path)),
                "provenance_sha256": sha256(sidecar),
            }
            return

        sidecar = resolved.with_suffix(resolved.suffix + ".json")
        if not sidecar.is_file():
            unknown[relative] = {"path": relative, "sha256": digest, "reason": "no supported adjacent provenance"}
            return
        try:
            metadata = json.loads(sidecar.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid audio lineage provenance {sidecar}: {exc.msg}") from exc
        schema = metadata.get("schema")
        fields = SOURCE_FIELDS.get(schema)
        if fields is None:
            unknown[relative] = {
                "path": relative,
                "sha256": digest,
                "provenance_path": str(sidecar.relative_to(song_path)),
                "provenance_sha256": sha256(sidecar),
                "reason": f"unsupported provenance schema: {schema}",
            }
            return
        output = metadata.get("output")
        if not isinstance(output, dict) or output.get("path") != relative or output.get("sha256") != digest:
            raise ValueError(f"audio lineage output provenance is invalid or changed: {relative}")
        artifacts.append({
            "path": relative,
            "sha256": digest,
            "schema": schema,
            "provenance_path": str(sidecar.relative_to(song_path)),
            "provenance_sha256": sha256(sidecar),
        })
        records = []
        for field in fields:
            value = metadata.get(field)
            if field == "sources":
                if not isinstance(value, list) or not value:
                    raise ValueError(f"audio lineage {schema} sources are invalid: {relative}")
                records.extend(value)
            else:
                if not isinstance(value, dict):
                    raise ValueError(f"audio lineage {schema} source is invalid: {relative}")
                records.append(value)
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise ValueError(f"audio lineage source record is invalid: {relative} #{index}")
            source = _safe_song_path(song_path, record.get("path"), f"audio lineage source {relative} #{index}")
            if record.get("sha256") != sha256(source):
                raise ValueError(f"audio lineage source checksum is invalid or changed: {source.relative_to(song_path)}")
            walk(source)

    walk(root)
    return {
        "schema": "eprs.audio-lineage/v1",
        "root": str(root.relative_to(song_path)),
        "artifacts": sorted(artifacts, key=lambda record: record["path"]),
        "raw_recordings": sorted(raw.values(), key=lambda record: record["path"]),
        "untraced_leaves": sorted(unknown.values(), key=lambda record: record["path"]),
    }
