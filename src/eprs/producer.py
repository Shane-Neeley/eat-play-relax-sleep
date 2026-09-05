"""A small shared front door for daily and on-demand agent production.

This coordinates creative work; it does not impersonate a music model, listener,
or publisher. Native sessions and the existing EPRS artifact contracts survive.
"""

from __future__ import annotations

from collections import Counter
from array import array
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

from .system import sha256


AXES = ("engine", "composition", "groove", "sound_world", "form", "visual")
MUSICAL_AXES = ("composition", "groove", "sound_world", "form")
TERMINAL = {"complete", "hold"}
STAGES = ("sketch", "arrange", "mix", "picture", "package", "complete")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object: {path.name}")
    return value


def _write(path: Path, record: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(path)


def _inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes the production root")
    return path


def catalog(root: str | Path) -> dict:
    """Discover actual favorites, including nested album handoffs, read-only."""
    root = Path(root).resolve()
    songs = {p.parent.name: p.parent for p in (root / "songs").glob("*/song.json")}
    favorites = []
    warnings = []
    for album in sorted((root / "albums").glob("*/album.json")):
        album_root = album.parent
        try:
            index = _read(album)
        except (ValueError, OSError) as exc:
            warnings.append(str(exc))
            continue
        indexed = {t.get("slug") for t in index.get("tracks", []) if isinstance(t, dict)}
        for folder in sorted(p for p in album_root.iterdir() if p.is_dir()):
            if not folder.resolve().is_relative_to(root):
                warnings.append(f"Skipped external favorite: {folder.name}")
                continue
            metadata = next(iter(sorted(folder.glob("metadata.json"))), None)
            metadata = metadata or next(iter(sorted(folder.glob("*/metadata.json"))), None)
            try:
                detail = _read(metadata) if metadata else {}
            except (ValueError, OSError) as exc:
                warnings.append(str(exc))
                detail = {}
            favorites.append({
                "slug": folder.name, "title": detail.get("title", folder.name),
                "album": index.get("title", album_root.name),
                "path": str(folder.relative_to(root)),
                "song": str(songs[folder.name].relative_to(root)) if folder.name in songs else None,
                "indexed": folder.name in indexed,
                "metadata": str(metadata.relative_to(root)) if metadata else None,
            })
    return {"schema": "eprs.producer-catalog/v1", "song_count": len(songs),
            "favorites": favorites, "warnings": warnings,
            "boundary": "Folder inclusion expresses preference, never rights or publication approval."}


def history(root: str | Path) -> list[dict]:
    directory = Path(root).resolve() / ".eprs-local" / "producer" / "runs"
    return sorted((_read(p) for p in directory.glob("*.json")), key=lambda r: r["created_at"])


def compare(candidate: dict, previous: list[dict]) -> dict:
    """Compare real production axes; titles, palettes and taxa cannot buy novelty."""
    for axis in AXES:
        if not isinstance(candidate.get(axis), str) or not candidate[axis].strip():
            raise ValueError(f"Concept requires {axis}")
    recent = [r["concept"] for r in previous if r.get("stage") == "complete"][-7:]
    normalized = {k: candidate[k].strip().casefold() for k in AXES}
    distances = [sum(normalized[k] != r[k].strip().casefold() for k in AXES) for r in recent]
    changed = [k for k in AXES if not recent or normalized[k] != recent[-1][k].strip().casefold()]
    musical_changes = [k for k in changed if k in MUSICAL_AXES]
    triple = ("engine", "composition", "groove")
    collisions = sum(all(normalized[k] == r[k].strip().casefold() for k in triple) for r in recent)
    return {"history_size": len(recent), "changed_axes": changed,
            "nearest_distance": min(distances) if distances else None,
            "method_collisions": collisions, "changed_musical_axes": musical_changes,
            "decision": "rework" if recent and (len(musical_changes) < 3 or collisions) else "explore",
            "boundary": "Declared differences need audible evidence; this is not a taste score."}


def brief(root: str | Path, key: str) -> dict:
    root = Path(root).resolve()
    policy = _read(root / "config" / "producer.json")
    prior = history(root)
    counts = Counter(r.get("concept", {}).get("engine") for r in prior if r.get("stage") == "complete")
    lanes = sorted(policy["lanes"], key=lambda lane: (
        counts[lane["engine"]], hashlib.sha256(f'{key}:{lane["id"]}'.encode()).hexdigest()))
    return {"schema": "eprs.producer-brief/v1", "key": key,
            "catalog": catalog(root), "candidate_lanes": lanes[:3],
            "recent_runs": prior[-7:], "quality": policy["quality"],
            "instruction": "Author and render two contrasting short sketches. Choose by musical effect, not the lane ranking. Preserve the losing sketch. Missing legacy method history is unknown, so inspect recent song manifests too."}


@contextmanager
def _lock(root: Path):
    import fcntl

    directory = root / ".eprs-local" / "producer"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "state.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield directory
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def start(root: str | Path, key: str, owner: str, song: str, concept: dict) -> dict:
    root = Path(root).resolve()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}", key):
        raise ValueError("Use a short alphanumeric run key with hyphens/underscores")
    if not owner.strip():
        raise ValueError("Run owner is required")
    destination = _inside(root, song)
    if not (destination / "song.json").is_file():
        raise ValueError("Create the EPRS song workspace before claiming production")
    with _lock(root) as directory:
        runs = directory / "runs"
        runs.mkdir(exist_ok=True)
        if (runs / f"{key}.json").exists():
            raise ValueError("Run key already exists; resume it instead of producing a duplicate")
        prior = history(root)
        active = [r for r in prior if r["stage"] not in TERMINAL]
        if active:
            raise ValueError(f'Production already owned by {active[0]["owner"]}: {active[0]["key"]}. Resume or explicitly hold it; leases never expire silently.')
        novelty = compare(concept, prior)
        if novelty["decision"] == "rework" and not concept.get("repair_of"):
            raise ValueError("Concept repeats recent production methods; change it or declare repair_of")
        record = {"schema": "eprs.producer-run/v1", "key": key, "owner": owner,
                  "token": uuid.uuid4().hex, "song": str(destination.relative_to(root)),
                  "created_at": _now(), "stage": "sketch", "concept": concept,
                  "diversity": novelty, "events": []}
        _write(runs / f"{key}.json", record)
        return record


def advance(root: str | Path, key: str, token: str, stage: str, note: str,
            artifacts: list[str]) -> dict:
    root = Path(root).resolve()
    if stage not in {*STAGES, "hold"} or len(note.strip()) < 20:
        raise ValueError("A known stage and specific decision note are required")
    with _lock(root) as directory:
        path = _inside(directory / "runs", f"{key}.json")
        record = _read(path)
        if record["token"] != token:
            raise ValueError("Run token does not match its owner")
        current = record["stage"]
        if current in TERMINAL:
            raise ValueError("Terminal run is immutable; start a new named revision")
        if stage != "hold" and STAGES.index(stage) != STAGES.index(current) + 1:
            raise ValueError("Advance exactly one stage; do not skip production evidence")
        song = _inside(root, record["song"])
        if stage == "package":
            validate_vocals(song, record["concept"].get("vocals", {"mode": "instrumental"}))
        evidence = []
        for item in artifacts:
            file = _inside(song, item)
            if not file.is_file() or not file.stat().st_size:
                raise ValueError(f"Missing or empty stage evidence: {item}")
            evidence.append({"path": str(file.relative_to(song)), "sha256": sha256(file)})
        if stage != "hold" and not evidence:
            raise ValueError("Stage transition requires actual artifact evidence")
        # Existing evidence cannot drift unnoticed between production stages.
        for event in record["events"]:
            for item in event["artifacts"]:
                file = _inside(song, item["path"])
                if not file.is_file() or sha256(file) != item["sha256"]:
                    if stage != "hold":
                        raise ValueError("Prior stage evidence changed; preserve a new revision")
        record["events"].append({"at": _now(), "from": current, "to": stage,
                                 "note": note, "artifacts": evidence})
        record["stage"] = stage
        _write(path, record)
        return record


def validate_vocals(song: Path, vocals: dict) -> None:
    """Refuse the common silent fallback from singing to untreated speech.

    The review remains an attributed assessment, not a machine proof of taste.
    Source/output/context checksums make forgotten or stale processing visible.
    """
    mode = vocals.get("mode")
    if mode == "instrumental":
        return
    if mode not in {"human-performance", "synthetic-singing", "processed-synthetic", "spoken-requested"}:
        raise ValueError("Untreated TTS is not a vocal delivery mode; sing/process it or use an instrumental")
    if mode == "spoken-requested":
        request = _inside(song, vocals.get("request_evidence", ""))
        if not request.is_file() or not request.read_text().strip():
            raise ValueError("Spoken delivery requires preserved explicit user request evidence")
    review_path = _inside(song, vocals.get("review", ""))
    if not review_path.is_file():
        raise ValueError("Vocal delivery requires an in-context review")
    review = _read(review_path)
    if review.get("decision") != "keep" or not all(review.get(k) for k in ("reviewer", "method", "delivery_note")):
        raise ValueError("Vocal review must name the reviewer, method, delivery assessment and keep decision")
    for key in ("vocal", "context"):
        item = review.get(key, {})
        path = _inside(song, item.get("path", ""))
        if not path.is_file() or item.get("sha256") != sha256(path):
            raise ValueError(f"Vocal review {key} evidence is missing or changed")
    if mode == "processed-synthetic":
        provenance = _read(_inside(song, vocals.get("processing", "")))
        if provenance.get("schema") != "eprs.autotune-render/v1":
            raise ValueError("Processed synthetic speech requires actual autotune render provenance")
        for key in ("source", "output"):
            item = provenance.get(key, {})
            path = _inside(song, item.get("path", ""))
            if not path.is_file() or item.get("sha256") != sha256(path):
                raise ValueError("Vocal processing source/output is missing or changed")
        if provenance["source"]["sha256"] == provenance["output"]["sha256"]:
            raise ValueError("Vocal processing cannot point at unchanged raw speech")
        if provenance["output"]["sha256"] != review["vocal"]["sha256"]:
            raise ValueError("Review must cover the processed vocal, not the raw TTS")


def package(root: str | Path, key: str, token: str, review: str) -> Path:
    """Freeze honestly attributed agent/human review without fabricating old approvals.

    This prepares a local package only. Publication still requires the current
    user's authorization and a separate, verified platform receipt.
    """
    root = Path(root).resolve()
    with _lock(root) as directory:
        record = _read(_inside(directory / "runs", f"{key}.json"))
        if record["token"] != token or record["stage"] != "package":
            raise ValueError("Package requires the owner token and package stage")
        song = _inside(root, record["song"])
        for event in record["events"]:
            for item in event["artifacts"]:
                file = _inside(song, item["path"])
                if not file.is_file() or sha256(file) != item["sha256"]:
                    raise ValueError("Prior stage evidence changed before packaging")
        review_path = _inside(song, review)
        assessment = _read(review_path)
        if assessment.get("schema") != "eprs.producer-review/v1":
            raise ValueError("Expected eprs.producer-review/v1")
        if assessment.get("reviewer_type") not in {"agent", "human", "model-assisted"}:
            raise ValueError("Name the actual reviewer type")
        for field in ("reviewer", "method", "decision_note", "rights_note", "limitations"):
            if not isinstance(assessment.get(field), str) or not assessment[field].strip():
                raise ValueError(f"Review requires {field}")
        if assessment.get("decision") != "keep":
            raise ValueError("Review has not kept this production")
        validate_vocals(song, record["concept"].get("vocals", {"mode": "instrumental"}))
        media = {}
        for role in ("master", "video"):
            item = assessment.get(role, {})
            file = _inside(song, item.get("path", ""))
            if not file.is_file() or sha256(file) != item.get("sha256"):
                raise ValueError(f"Reviewed {role} is missing or changed")
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(file),
                            "-f", "null", "-"], check=True, capture_output=True, timeout=180)
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file)
            ], timeout=20))
            if role == "master" and not any(s.get("codec_name") == "pcm_s24le" for s in probe["streams"]):
                raise ValueError("Package requires a 24-bit PCM WAV master")
            if role == "video" and not {"audio", "video"}.issubset({s["codec_type"] for s in probe["streams"]}):
                raise ValueError("Package video must contain both picture and audio")
            media[role] = {"file": file, "probe": probe, "sha256": item["sha256"]}
        durations = [float(item["probe"]["format"]["duration"]) for item in media.values()]
        if abs(durations[0] - durations[1]) > 0.15:
            raise ValueError("Master/video durations do not match")
        correlation = soundtrack_correlation(media["master"]["file"], media["video"]["file"])
        if correlation < 0.97:
            raise ValueError("Video soundtrack does not match the reviewed master at time zero")
        final = song / "FINAL" / key
        if final.exists():
            raise FileExistsError(final)
        final.parent.mkdir(exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".package-", dir=final.parent))
        try:
            outputs = {}
            for role, item in media.items():
                name = "master.wav" if role == "master" else "video.mp4"
                shutil.copy2(item["file"], temporary / name)
                outputs[role] = {"path": name, "sha256": sha256(temporary / name), "probe": item["probe"]}
            shutil.copy2(review_path, temporary / "review.json")
            _write(temporary / "release.json", {
                "schema": "eprs.producer-package/v1", "created_at": _now(),
                "key": key, "concept": record["concept"], "outputs": outputs,
                "soundtrack_correlation": correlation,
                "review": {"path": "review.json", "sha256": sha256(temporary / "review.json"),
                           "reviewer_type": assessment["reviewer_type"], "method": assessment["method"]},
                "publication": {"performed": False, "authorization_inferred": False},
            })
            temporary.rename(final)
        except BaseException:
            shutil.rmtree(temporary)
            raise
        return final


def soundtrack_correlation(master: Path, video: Path) -> float:
    """Compare a bounded low-band decode; catch wrong masters and sync offsets."""
    signals = []
    for path in (master, video):
        data = subprocess.check_output([
            "ffmpeg", "-v", "error", "-i", str(path), "-t", "600", "-vn",
            "-af", "lowpass=f=3000", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"
        ], timeout=60)
        signal = array("h")
        signal.frombytes(data)
        import sys
        if sys.byteorder != "little":
            signal.byteswap()
        signals.append(signal)
    size = min(map(len, signals))
    if not size:
        return 0.0
    x, y = (signal[:size] for signal in signals)
    mx, my = sum(x) / size, sum(y) / size
    xx = sum((v - mx) ** 2 for v in x)
    yy = sum((v - my) ** 2 for v in y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(xx * yy) if xx and yy else 0.0


def verify_package(directory: Path, *, verify: bool = True) -> dict:
    directory = directory.resolve()
    record = _read(directory / "release.json")
    if record.get("schema") != "eprs.producer-package/v1":
        raise ValueError("Unsupported producer package")
    for role in ("master", "video"):
        item = record.get("outputs", {}).get(role, {})
        file = _inside(directory, item.get("path", ""))
        if not file.is_file() or (verify and sha256(file) != item.get("sha256")):
            raise ValueError(f"Producer package {role} is missing or changed")
    item = record.get("review", {})
    path = _inside(directory, item.get("path", ""))
    if not path.is_file() or (verify and sha256(path) != item.get("sha256")):
        raise ValueError("Producer package review is missing or changed")
    assessment = _read(path)
    if assessment.get("decision") != "keep" or assessment.get("reviewer_type") != item.get("reviewer_type"):
        raise ValueError("Producer package review identity changed")
    for role in ("master", "video"):
        if assessment.get(role, {}).get("sha256") != record["outputs"][role]["sha256"]:
            raise ValueError("Producer package review does not bind its output")
    return record


def publication_summary(song: Path, *, verify: bool = True) -> dict:
    """Read the new producer's receipt without altering legacy publication state."""
    receipt = song / "notes" / "publication-receipt.json"
    result = {"receipts": 0, "public": 0, "url": None, "error": None}
    if not receipt.is_file():
        return result
    try:
        data = _read(receipt)
        if data.get("schema") != "eprs.producer-publication/v1":
            return result
        file = _inside(song / "FINAL", str(Path(data["release"]["path"]).relative_to("FINAL")))
        if verify and sha256(file) != data["release"]["sha256"]:
            raise ValueError("Producer publication package changed")
        record = verify_package(file.parent, verify=verify)
        if data.get("video_sha256") != record["outputs"]["video"]["sha256"]:
            raise ValueError("Producer publication video changed")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", data.get("video_id", "")):
            raise ValueError("Invalid platform video id")
        if data.get("url") != "https://youtu.be/" + data["video_id"]:
            raise ValueError("Platform URL does not match its video id")
        result.update(receipts=1, public=int(data.get("visibility") == "public"), url=data["url"])
    except (ValueError, KeyError, OSError) as exc:
        result["error"] = str(exc)
    return result


def add_parser(commands) -> None:
    parser = commands.add_parser("produce", help="Coordinate daily or on-demand music production")
    parser.add_argument("action", choices=["catalog", "brief", "status", "start", "advance", "package"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--key")
    parser.add_argument("--owner")
    parser.add_argument("--song")
    parser.add_argument("--concept", help="JSON file with six authored method axes")
    parser.add_argument("--token")
    parser.add_argument("--stage", choices=[*STAGES, "hold"])
    parser.add_argument("--note")
    parser.add_argument("--review", help="Song-relative eprs.producer-review/v1 file")
    parser.add_argument("--artifact", action="append", default=[], help="Song-relative evidence path")


def run(args) -> dict | list:
    if args.action == "catalog":
        return catalog(args.root)
    if args.action == "status":
        return history(args.root)
    if not args.key:
        raise ValueError("--key is required")
    if args.action == "brief":
        return brief(args.root, args.key)
    if args.action == "start":
        if not all((args.owner, args.song, args.concept)):
            raise ValueError("start requires --owner, --song and --concept")
        return start(args.root, args.key, args.owner, args.song, _read(Path(args.concept)))
    if args.action == "package":
        if not args.token or not args.review:
            raise ValueError("package requires --token and --review")
        return {"package": str(package(args.root, args.key, args.token, args.review))}
    if not all((args.token, args.stage, args.note)):
        raise ValueError("advance requires --token, --stage and --note")
    return advance(args.root, args.key, args.token, args.stage, args.note, args.artifact)
