"""Build and render editable, original-media Shotcut/MLT projects."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from xml.etree import ElementTree as ET

from .system import PROJECT_ROOT, sha256, utc_now


SHOTCUT_PROJECT_SCHEMA = "eprs.shotcut-project/v1"
SHOTCUT_PACKAGE_SCHEMA = "eprs.shotcut-project-package/v1"
SHOTCUT_RENDER_SCHEMA = "eprs.shotcut-render/v1"
SHOTCUT_APP = Path("/Applications/Shotcut.app/Contents/MacOS/Shotcut")
SHOTCUT_MELT = Path("/Applications/Shotcut.app/Contents/MacOS/melt")


def _song_path(value: str | Path) -> Path:
    song = Path(value).expanduser().resolve()
    if (
        not song.is_dir()
        or not song.is_relative_to(PROJECT_ROOT)
    ):
        raise ValueError(f"Shotcut requires a song workspace inside the EPRS repository: {song}")
    return song


def _song_file(song: Path, value: str | Path, label: str, *, suffix: str | None = None) -> Path:
    candidate = Path(value).expanduser()
    candidates = [candidate] if candidate.is_absolute() else [song / candidate, PROJECT_ROOT / candidate]
    resolved = next((path.resolve() for path in candidates if path.is_file()), None)
    if resolved is None:
        raise FileNotFoundError(candidate)
    try:
        relative = resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Shotcut {label} must remain inside the EPRS repository") from exc
    if "raw" in {part.lower() for part in relative.parts}:
        raise ValueError(f"Shotcut refuses immutable raw material: {relative}")
    candidate = resolved
    if suffix and candidate.suffix.lower() != suffix:
        raise ValueError(f"Shotcut {label} must use {suffix}")
    return candidate


def _song_output(song: Path, value: str | Path, label: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = song / candidate
    candidate = candidate.resolve()
    try:
        relative = candidate.relative_to(song)
    except ValueError as exc:
        raise ValueError(f"Shotcut {label} must remain inside the song workspace") from exc
    if "raw" in {part.lower() for part in relative.parts}:
        raise ValueError(f"Shotcut refuses immutable raw output paths: {relative}")
    return candidate


def _link_asset(destination: Path, source: Path, label: str) -> Path:
    assets = destination / "assets"
    assets.mkdir(exist_ok=True)
    link = assets / f"{_slug(label)}-{source.name}"
    link.symlink_to(os.path.relpath(source, link.parent))
    return link


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, env=env
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"Shotcut/MLT command failed: {detail or 'unknown error'}")
    return completed


def _tool_version(path: Path, name: str) -> str:
    if not path.is_file():
        return "unavailable"
    completed = _run([str(path), "--version"] if name == "shotcut" else [str(path), "-version"])
    return (completed.stdout or completed.stderr).splitlines()[0].strip()


def _melt_path() -> Path:
    if SHOTCUT_MELT.is_file():
        return SHOTCUT_MELT
    located = shutil.which("melt")
    if located:
        return Path(located)
    raise RuntimeError("Shotcut rendering requires bundled melt or a melt command")


def _probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("Shotcut integration requires ffprobe")
    completed = _run([
        ffprobe, "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_name,codec_type,width,height,pix_fmt,"
        "r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ])
    return json.loads(completed.stdout)


def _slug(value: str) -> str:
    result = "-".join(
        part for part in "".join(
            character.lower() if character.isalnum() else " " for character in value
        ).split() if part
    )
    return result or "shotcut-project"


def _property(parent: ET.Element, name: str, value: object) -> None:
    node = ET.SubElement(parent, "property", {"name": name})
    node.text = str(value)


def _frames(seconds: float, fps: int) -> int:
    return round(seconds * fps)


def _validate_number(value: object, label: str, low: float, high: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Shotcut {label} must be numeric")
    result = float(value)
    if not low <= result <= high:
        raise ValueError(f"Shotcut {label} must be between {low} and {high}")
    return result


def _filter(parent: ET.Element, service: str, shotcut_id: str, values: dict[str, object]) -> None:
    node = ET.SubElement(parent, "filter")
    _property(node, "mlt_service", service)
    _property(node, "shotcut:filter", shotcut_id)
    for name, value in values.items():
        _property(node, name, value)


def _add_section_filters(chain: ET.Element, section: dict, frames: int) -> list[str]:
    services: list[str] = []
    look = section.get("look", {})
    if not isinstance(look, dict):
        raise ValueError("Shotcut section look must be an object")
    eq: dict[str, object] = {
        "av.contrast": _validate_number(look.get("contrast", 1.0), "contrast", -2, 2),
        "av.brightness": _validate_number(look.get("brightness", 0.0), "brightness", -1, 1),
        "av.saturation": _validate_number(look.get("saturation", 1.0), "saturation", 0, 3),
        "av.gamma": _validate_number(look.get("gamma", 1.0), "gamma", 0.1, 10),
        "av.eval": "frame",
    }
    if any(eq[key] != default for key, default in (
        ("av.contrast", 1.0), ("av.brightness", 0.0),
        ("av.saturation", 1.0), ("av.gamma", 1.0),
    )):
        _filter(chain, "avfilter.eq", "avfilterEq", eq)
        services.append("avfilter.eq")

    transform = section.get("transform")
    if transform is not None:
        if not isinstance(transform, dict):
            raise ValueError("Shotcut section transform must be an object")
        start_rect = str(transform.get("start_rect", "0%/0%:100%x100%:100%"))
        end_rect = str(transform.get("end_rect", start_rect))
        rotate_start = _validate_number(transform.get("rotate_start", 0), "rotation", -360, 360)
        rotate_end = _validate_number(transform.get("rotate_end", rotate_start), "rotation", -360, 360)
        last = max(0, frames - 1)
        _filter(chain, "affine", "affineSizePosition", {
            "transition.rect": f"0~={start_rect};{last}~={end_rect}",
            "transition.fix_rotate_z": f"0~={rotate_start};{last}~={rotate_end}",
            "transition.fill": 1,
            "transition.distort": 0,
        })
        services.append("affine")

    glow = section.get("glow")
    if glow is not None:
        amount = _validate_number(glow, "glow", 0, 1)
        _filter(chain, "frei0r.glow", "frei0r_glow", {"0": amount})
        services.append("frei0r.glow")

    rgb_shift = section.get("rgb_shift")
    if rgb_shift is not None:
        amount = round(_validate_number(rgb_shift, "RGB shift", 0, 255))
        _filter(chain, "avfilter.rgbashift", "avfilterRgbashift", {
            "av.rh": amount,
            "av.bh": -amount,
            "av.edge": "wrap",
        })
        services.append("avfilter.rgbashift")

    text = section.get("text")
    if text is not None:
        if not isinstance(text, dict) or not str(text.get("value", "")).strip():
            raise ValueError("Shotcut section text needs a non-blank value")
        _filter(chain, "qtext", "dynamicText", {
            "argument": str(text["value"]),
            "geometry": str(text.get("geometry", "5%/5%:90%x90%:100%")),
            "family": str(text.get("family", "Helvetica Neue")),
            "size": round(_validate_number(text.get("size", 96), "text size", 8, 400)),
            "weight": round(_validate_number(text.get("weight", 700), "text weight", 100, 1000)),
            "fgcolour": str(text.get("color", "#ffffffff")),
            "bgcolour": str(text.get("background", "#00000000")),
            "halign": str(text.get("halign", "center")),
            "valign": str(text.get("valign", "middle")),
            "opacity": _validate_number(text.get("opacity", 1), "text opacity", 0, 1),
            "typewriter": 1 if text.get("typewriter", False) else 0,
            "typewriter.step_length": round(_validate_number(
                text.get("step_frames", 2), "typewriter step", 1, 200
            )),
            "typewriter.cursor": 0,
        })
        services.append("qtext")
    return services


def _source_chain(
    root: ET.Element,
    chain_id: str,
    resource: str,
    caption: str,
    *,
    audio: bool,
) -> ET.Element:
    chain = ET.SubElement(root, "chain", {"id": chain_id})
    _property(chain, "mlt_service", "avformat-novalidate")
    _property(chain, "resource", resource)
    _property(chain, "shotcut:resource", resource)
    _property(chain, "shotcut:caption", caption)
    _property(chain, "shotcut:disableProxy", 1)
    _property(chain, "audio_index", 0 if audio else -1)
    _property(chain, "video_index", -1 if audio else 0)
    return chain


def _transition(
    tractor: ET.Element,
    transition_id: str,
    service: str,
    a_track: int,
    b_track: int,
    *,
    shotcut_id: str | None = None,
    values: dict[str, object] | None = None,
) -> None:
    node = ET.SubElement(tractor, "transition", {"id": transition_id})
    _property(node, "a_track", a_track)
    _property(node, "b_track", b_track)
    _property(node, "mlt_service", service)
    _property(node, "always_active", 1)
    if shotcut_id:
        _property(node, "shotcut:transition", shotcut_id)
    for name, value in (values or {}).items():
        _property(node, name, value)


def _blend_name(value: object) -> str:
    names = {
        0: "normal", 13: "multiply", 14: "screen", 15: "overlay",
        16: "darken", 17: "lighten", 20: "hardlight", 21: "softlight",
        22: "difference", 23: "exclusion",
    }
    if isinstance(value, str) and value in set(names.values()):
        return value
    if isinstance(value, int) and value in names:
        return names[value]
    raise ValueError("Shotcut overlay blend mode is unsupported")


def compile_shotcut_project(spec: str | Path, song: str | Path) -> dict:
    """Compile an EPRS Shotcut score into editable MLT XML and a manifest."""
    song_path = _song_path(song)
    spec_path = _song_file(song_path, spec, "score", suffix=".json")
    score = json.loads(spec_path.read_text())
    if score.get("schema") != SHOTCUT_PROJECT_SCHEMA:
        raise ValueError(f"Shotcut spec schema must be {SHOTCUT_PROJECT_SCHEMA}")
    title = str(score.get("title", "")).strip()
    intent = str(score.get("intent", "")).strip()
    if not title or not intent:
        raise ValueError("Shotcut spec needs title and intent")
    source_paths: dict[str, Path] = {
        "main": _song_file(song_path, score.get("source_video", ""), "source video")
    }
    sources = score.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Shotcut sources must be an object mapping ids to media paths")
    for source_id, value in sources.items():
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("Shotcut source ids must be non-empty strings")
        source_paths[source_id] = _song_file(song_path, value, f"source {source_id}")
    master = _song_file(song_path, score.get("master", ""), "master")
    width = round(_validate_number(score.get("width", 1920), "width", 320, 7680))
    height = round(_validate_number(score.get("height", 1080), "height", 180, 4320))
    fps = round(_validate_number(score.get("fps", 30), "fps", 1, 120))
    sections = score.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Shotcut spec needs at least one section")

    normalized: list[dict] = []
    cursor = 0.0
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ValueError("Shotcut sections must be objects")
        start = _validate_number(section.get("start_seconds"), "section start", 0, 86_400)
        end = _validate_number(section.get("end_seconds"), "section end", 0, 86_400)
        if abs(start - cursor) > 1 / fps:
            raise ValueError("Shotcut sections must be contiguous and start at zero")
        if end <= start:
            raise ValueError("Shotcut section end must be after start")
        source_start = _validate_number(
            section.get("source_start_seconds", start), "source start", 0, 86_400
        )
        normalized.append({**section, "start_seconds": start, "end_seconds": end,
                           "source_start_seconds": source_start, "index": index})
        cursor = end
    total_frames = _frames(cursor, fps)
    if total_frames < 1:
        raise ValueError("Shotcut project duration must be positive")

    source_probes = {source_id: _probe(path) for source_id, path in source_paths.items()}
    master_probe = _probe(master)
    master_duration = float(master_probe["format"]["duration"])
    for section in normalized:
        duration = section["end_seconds"] - section["start_seconds"]
        source_id = str(section.get("source", "main"))
        if source_id not in source_paths:
            raise ValueError(f"Shotcut section references unknown source: {source_id}")
        source_duration = float(source_probes[source_id]["format"]["duration"])
        if section["source_start_seconds"] + duration > source_duration + 1 / fps:
            raise ValueError("Shotcut section exceeds source video duration")
    if cursor > master_duration + 1 / fps:
        raise ValueError("Shotcut timeline exceeds master duration")

    fingerprint = {
        "score": score,
        "source_sha256": {source_id: sha256(path) for source_id, path in source_paths.items()},
        "master_sha256": sha256(master),
    }
    package_id = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    destination = song_path / "shotcut" / f"{_slug(title)}-{package_id[:10]}"
    if destination.exists():
        raise FileExistsError(f"Shotcut project already exists: {destination}")
    destination.mkdir(parents=True)
    project = destination / f"{_slug(title)}.mlt"
    manifest = destination / "project.json"

    linked_sources = {
        source_id: _link_asset(destination, path, source_id)
        for source_id, path in source_paths.items()
    }
    linked_master = _link_asset(destination, master, "master")
    source_resources = {
        source_id: os.path.relpath(path, destination)
        for source_id, path in linked_sources.items()
    }
    master_resource = os.path.relpath(linked_master, destination)
    root = ET.Element("mlt", {
        "LC_NUMERIC": "C",
        "version": "7.41.0",
        "title": "Shotcut project generated by EPRS",
        "producer": "tractor0",
        "root": str(destination),
    })
    ET.SubElement(root, "profile", {
        "description": f"EPRS {width}x{height} {fps} fps",
        "width": str(width), "height": str(height),
        "progressive": "1", "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "frame_rate_num": str(fps), "frame_rate_den": "1", "colorspace": "709",
    })
    black = ET.SubElement(root, "producer", {"id": "black", "out": str(total_frames - 1)})
    _property(black, "mlt_service", "color")
    _property(black, "resource", "#000000")
    audio_chain = _source_chain(root, "master_audio", master_resource, master.name, audio=True)
    _property(audio_chain, "shotcut:comment", "Approved EPRS master used as local Shotcut guide audio")

    base_playlist = ET.Element("playlist", {"id": "video_base"})
    _property(base_playlist, "shotcut:name", "V1 • Structured cut")
    _property(base_playlist, "shotcut:video", 1)
    used_services: set[str] = {"avformat-novalidate", "color", "qtblend"}
    bin_entries: list[tuple[str, int]] = []
    for section in normalized:
        duration_frames = _frames(section["end_seconds"] - section["start_seconds"], fps)
        chain_id = f"section_{section['index']:02d}"
        source_id = str(section.get("source", "main"))
        chain = _source_chain(
            root, chain_id, source_resources[source_id],
            str(section.get("label") or f"Section {section['index'] + 1}"), audio=False,
        )
        used_services.update(_add_section_filters(chain, section, duration_frames))
        source_in = _frames(section["source_start_seconds"], fps)
        ET.SubElement(base_playlist, "entry", {
            "producer": chain_id,
            "in": str(source_in),
            "out": str(source_in + duration_frames - 1),
        })
        bin_entries.append((chain_id, source_in + duration_frames - 1))

    overlay_playlist = ET.Element("playlist", {"id": "video_accents"})
    _property(overlay_playlist, "shotcut:name", "V2 • Difference accents")
    _property(overlay_playlist, "shotcut:video", 1)
    overlays = score.get("overlays", [])
    if not isinstance(overlays, list):
        raise ValueError("Shotcut overlays must be a list")
    overlay_cursor = 0
    for index, overlay in enumerate(overlays):
        if not isinstance(overlay, dict):
            raise ValueError("Shotcut overlays must be objects")
        start = _validate_number(overlay.get("start_seconds"), "overlay start", 0, cursor)
        end = _validate_number(overlay.get("end_seconds"), "overlay end", 0, cursor)
        if end <= start:
            raise ValueError("Shotcut overlay end must be after start")
        start_frame = _frames(start, fps)
        end_frame = _frames(end, fps)
        if start_frame < overlay_cursor:
            raise ValueError("Shotcut overlays may not overlap each other")
        if start_frame > overlay_cursor:
            ET.SubElement(overlay_playlist, "blank", {"length": str(start_frame - overlay_cursor)})
        duration_frames = end_frame - start_frame
        source_id = str(overlay.get("source", "main"))
        if source_id not in source_paths:
            raise ValueError(f"Shotcut overlay references unknown source: {source_id}")
        source_duration = float(source_probes[source_id]["format"]["duration"])
        source_start = _validate_number(
            overlay.get("source_start_seconds", start), "overlay source start", 0, source_duration
        )
        if source_start + (end - start) > source_duration + 1 / fps:
            raise ValueError("Shotcut overlay exceeds source video duration")
        chain_id = f"overlay_{index:02d}"
        chain = _source_chain(
            root, chain_id, source_resources[source_id],
            str(overlay.get("label") or f"Accent {index + 1}"), audio=False,
        )
        used_services.update(_add_section_filters(chain, overlay, duration_frames))
        source_in = _frames(source_start, fps)
        ET.SubElement(overlay_playlist, "entry", {
            "producer": chain_id,
            "in": str(source_in),
            "out": str(source_in + duration_frames - 1),
        })
        overlay_cursor = end_frame
        bin_entries.append((chain_id, source_in + duration_frames - 1))
    if overlay_cursor < total_frames:
        ET.SubElement(overlay_playlist, "blank", {"length": str(total_frames - overlay_cursor)})

    background = ET.SubElement(root, "playlist", {"id": "background"})
    ET.SubElement(background, "entry", {"producer": "black", "in": "0", "out": str(total_frames - 1)})
    root.append(base_playlist)
    root.append(overlay_playlist)
    audio_playlist = ET.SubElement(root, "playlist", {"id": "audio_master"})
    _property(audio_playlist, "shotcut:name", "A1 • Approved master guide")
    _property(audio_playlist, "shotcut:audio", 1)
    ET.SubElement(audio_playlist, "entry", {
        "producer": "master_audio", "in": "0", "out": str(total_frames - 1)
    })

    main_bin = ET.SubElement(root, "playlist", {"id": "main bin"})
    _property(main_bin, "shotcut:projectFolder", 1)
    for chain_id, out_frame in bin_entries:
        ET.SubElement(main_bin, "entry", {"producer": chain_id, "in": "0", "out": str(out_frame)})

    tractor = ET.SubElement(root, "tractor", {"id": "tractor0", "in": "0", "out": str(total_frames - 1)})
    _property(tractor, "shotcut", 1)
    _property(tractor, "shotcut:projectAudioChannels", 2)
    _property(tractor, "shotcut:projectFolder", 1)
    _property(tractor, "shotcut:trackHeight", 50)
    _property(tractor, "shotcut:scaleFactor", 4)
    _property(tractor, "shotcut:projectNote", intent)
    markers = score.get("markers", [])
    if not isinstance(markers, list):
        raise ValueError("Shotcut markers must be a list")
    _property(tractor, "shotcut:markers", json.dumps(markers, separators=(",", ":")))
    ET.SubElement(tractor, "track", {"producer": "background"})
    ET.SubElement(tractor, "track", {"producer": "video_base"})
    ET.SubElement(tractor, "track", {"producer": "video_accents"})
    ET.SubElement(tractor, "track", {"producer": "audio_master", "hide": "video"})
    _transition(
        tractor, "composite_base", "qtblend", 0, 1,
        shotcut_id="qtblend", values={"compositing": 0},
    )
    blend_name = _blend_name(score.get("overlay_blend_mode", "normal"))
    blend_service = "qtblend" if blend_name == "normal" else f"frei0r.{blend_name}"
    used_services.add(blend_service)
    _transition(
        tractor, "composite_accents", blend_service, 1, 2,
        shotcut_id="qtblend" if blend_name == "normal" else blend_service,
        values={"compositing": 0} if blend_name == "normal" else None,
    )
    # A single audio track does not need an explicit ``mix`` transition. In
    # MLT it can keep the avformat consumer alive during finalization, leaving
    # an MP4 without its moov atom even after the last video frame renders.

    ET.indent(root, space="  ")
    project.write_text(ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n")
    melt = _melt_path()
    _run([str(melt), "-progress2", str(project), "-consumer", "null"])
    record = {
        "schema": SHOTCUT_PACKAGE_SCHEMA,
        "package_id": package_id,
        "created_at": utc_now(),
        "recipe": score,
        "project": {
            "path": str(project.relative_to(song_path)),
            "sha256": sha256(project),
            "format": "MLT XML editable by Shotcut",
            "duration_seconds": cursor,
            "frames": total_frames,
            "profile": {"width": width, "height": height, "fps": fps, "colorspace": "BT.709"},
        },
        "inputs": {
            "sources": {
                source_id: {
                    "path": str(path.relative_to(PROJECT_ROOT)),
                    "sha256": sha256(path),
                }
                for source_id, path in source_paths.items()
            },
            "master": {
                "path": str(master.relative_to(PROJECT_ROOT)),
                "sha256": sha256(master),
            },
        },
        "tool": {
            "shotcut": _tool_version(SHOTCUT_APP, "shotcut"),
            "melt": _tool_version(melt, "melt"),
            "melt_path": str(melt),
            "services": sorted(used_services),
        },
        "verification": {
            "mlt_parse_and_null_render": True,
            "original_media_only": True,
            "editable_annotations": True,
            "gui_opened": False,
            "creative_review": False,
        },
        "authority": {
            "network_access": False,
            "upload": False,
            "publication": False,
        },
    }
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    return {"package": str(destination), "project": str(project), "manifest": str(manifest),
            "package_id": package_id, "duration_seconds": cursor}


def prepare_shotcut_project(
    song: str | Path,
    *,
    title: str,
    video_segments: list[dict],
    audio: str | Path,
    title_cues: list[dict] | None = None,
    markers: list[dict] | None = None,
    out: str | Path | None = None,
) -> dict:
    """Compatibility builder for the original repeatable-segment CLI.

    The structured score is preserved inside the song and then passed through
    the same strict spec-to-MLT compiler used by ``shotcut compile``.
    """
    song_path = _song_path(song)
    if not isinstance(video_segments, list) or not video_segments:
        raise ValueError("Shotcut prepare needs at least one video segment")
    sections: list[dict] = []
    cursor = 0.0
    source_ids: dict[str, str] = {}
    source_values: dict[str, str] = {}
    for index, segment in enumerate(video_segments):
        if not isinstance(segment, dict):
            raise ValueError("Shotcut video segments must be objects")
        video = str(segment.get("video", ""))
        source_key = str(Path(video).expanduser().resolve())
        proposed_id = "main" if not source_ids else f"source_{len(source_ids) + 1:02d}"
        source_id = source_ids.setdefault(source_key, proposed_id)
        source_values.setdefault(source_id, video)
        duration = _validate_number(
            segment.get("duration_seconds"), "segment duration", 1 / 120, 86_400
        )
        sections.append({
            "id": str(segment.get("id") or f"segment-{index + 1}"),
            "label": str(segment.get("label") or f"Segment {index + 1}"),
            "start_seconds": cursor,
            "end_seconds": cursor + duration,
            "source_start_seconds": _validate_number(
                segment.get("start_seconds", 0), "segment source start", 0, 86_400
            ),
            "source": source_id,
            **({"look": segment["look"]} if "look" in segment else {}),
            **({"transform": segment["transform"]} if "transform" in segment else {}),
            **({"glow": segment["glow"]} if "glow" in segment else {}),
            **({"rgb_shift": segment["rgb_shift"]} if "rgb_shift" in segment else {}),
        })
        cursor += duration
    overlays: list[dict] = []
    for index, cue in enumerate(title_cues or []):
        if not isinstance(cue, dict):
            raise ValueError("Shotcut title cues must be objects")
        start = _validate_number(cue.get("start_seconds"), "title cue start", 0, cursor)
        duration = _validate_number(cue.get("duration_seconds"), "title cue duration", 1 / 120, cursor)
        overlays.append({
            "id": f"title-{index + 1}",
            "label": str(cue.get("text") or f"Title {index + 1}"),
            "start_seconds": start,
            "end_seconds": min(cursor, start + duration),
            "source_start_seconds": start,
            "text": {
                "value": str(cue.get("text", "")),
                "size": cue.get("size", 112),
                "color": cue.get("color", "#ffffffff"),
                "background": cue.get("background", "#00000060"),
                "typewriter": cue.get("typewriter", False),
            },
        })
    score = {
        "schema": SHOTCUT_PROJECT_SCHEMA,
        "title": title,
        "intent": "Editable beat-mapped Shotcut timeline prepared from repeatable CLI segments.",
        "source_video": next(iter(source_values.values())),
        "master": str(audio),
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "sections": sections,
        "sources": {
            source_id: value
            for source_id, value in source_values.items()
            if value != next(iter(source_values.values()))
        },
        "overlays": sorted(overlays, key=lambda item: item["start_seconds"]),
        "overlay_blend_mode": 0,
        "markers": sorted(markers or [], key=lambda item: item.get("time_seconds", 0)),
    }
    digest = hashlib.sha256(
        json.dumps(score, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:10]
    if out:
        score_path = _song_output(song_path, out, "score output")
        if score_path.suffix.lower() != ".json":
            score_path = score_path / f"{_slug(title)}-{digest}.json"
    else:
        score_path = song_path / "shotcut-specs" / f"{_slug(title)}-{digest}.json"
    if score_path.exists():
        raise FileExistsError(f"Shotcut score already exists: {score_path}")
    score_path.parent.mkdir(parents=True, exist_ok=True)
    score_path.write_text(json.dumps(score, indent=2) + "\n")
    result = compile_shotcut_project(score_path, song_path)
    record = json.loads(Path(result["manifest"]).read_text())
    record["recipe"]["markers"] = score["markers"]
    Path(result["manifest"]).write_text(json.dumps(record, indent=2) + "\n")
    return {
        **result,
        "score": str(score_path),
        "markers": score["markers"],
        "title_cues": [item["text"] for item in overlays],
    }


def render_shotcut_project(
    project: str | Path,
    song: str | Path,
    *,
    out: str | Path,
    quality: str = "full",
) -> dict:
    """Render a prepared project through Shotcut's bundled melt without overwriting."""
    song_path = _song_path(song)
    project_path = _song_file(song_path, project, "project", suffix=".mlt")
    output = _song_output(song_path, out, "render output")
    if output.exists() or output.with_suffix(output.suffix + ".json").exists():
        raise FileExistsError(f"Shotcut render output already exists: {output}")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Shotcut render output must use .mp4")
    output.parent.mkdir(parents=True, exist_ok=True)
    melt = _melt_path()
    if quality not in {"draft", "full"}:
        raise ValueError("Shotcut render quality must be draft or full")
    # Keep the consumer invocation intentionally small. On the bundled macOS
    # MLT, adding ffmpeg-style overrides to an XML project can make export
    # reach 99% but never finalize the MP4 moov atom. Shotcut's project profile
    # already carries the intended frame size and rate; use its defaults for
    # the reliable path and record quality as review intent.
    command = [
        str(melt), "-progress2", str(project_path),
        "-consumer", f"avformat:{output}",
    ]
    env = {**os.environ, "LC_NUMERIC": "C"}
    completed = _run(command, env=env)
    media = _probe(output)
    record = {
        "schema": SHOTCUT_RENDER_SCHEMA,
        "rendered_at": utc_now(),
        "project": {"path": str(project_path.relative_to(song_path)), "sha256": sha256(project_path)},
        "output": {"path": str(output.relative_to(song_path)), "sha256": sha256(output), "media": media},
        "tool": {"melt": _tool_version(melt, "melt"), "path": str(melt)},
        "quality": quality,
        "audio_policy": (
            "Any Shotcut-exported audio is a lossy guide only; EPRS discards it and "
            "pairs the reviewed picture with the separately approved master during final delivery."
        ),
        "command": command,
        "progress_tail": (completed.stderr or completed.stdout).splitlines()[-8:],
        "review": {"technical_render": "passed", "creative_review": "not recorded"},
        "authority": {"upload": False, "publication": False},
    }
    sidecar = output.with_suffix(output.suffix + ".json")
    sidecar.write_text(json.dumps(record, indent=2) + "\n")
    return {"video": str(output), "metadata": str(sidecar), "sha256": sha256(output),
            "media": media, "quality": quality}


def open_shotcut_project(project: str | Path, song: str | Path) -> dict:
    """Open one prepared MLT project in isolated local Shotcut app data."""
    song_path = _song_path(song)
    project_path = _song_file(song_path, project, "project", suffix=".mlt")
    if not SHOTCUT_APP.is_file():
        raise RuntimeError(f"Shotcut application is unavailable: {SHOTCUT_APP}")
    appdata = project_path.parent / "appdata"
    appdata.mkdir(exist_ok=True)
    process = subprocess.Popen(
        [str(SHOTCUT_APP), "--appdata", str(appdata), str(project_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    manifest_path = project_path.parent / "project.json"
    if manifest_path.is_file():
        record = json.loads(manifest_path.read_text())
        record["verification"]["gui_opened"] = True
        record["verification"]["gui_opened_at"] = utc_now()
        record["verification"]["gui_pid"] = process.pid
        manifest_path.write_text(json.dumps(record, indent=2) + "\n")
    return {
        "project": str(project_path),
        "application": str(SHOTCUT_APP),
        "version": _tool_version(SHOTCUT_APP, "shotcut"),
        "appdata": str(appdata),
        "pid": process.pid,
        "network_access": False,
    }
