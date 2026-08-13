"""Fetch and freeze licensed iNaturalist photo evidence for visual production."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .system import load_song_manifest, sha256, slugify, utc_now


INATURALIST_API = "https://api.inaturalist.org/v1"
INATURALIST_PHOTO_SCHEMA = "eprs.inaturalist-photo/v1"
DEFAULT_USER_AGENT = "eprs-inaturalist-photo/1.0 (read-only visual reference)"
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
PHOTO_SIZES = {"small", "medium", "large", "original"}
REUSABLE_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
}
PUBLICATION_COMPATIBLE_LICENSES = {"cc0", "cc-by"}
PHOTO_HOSTS = {"inaturalist-open-data.s3.amazonaws.com"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}


def publication_status_for_photo_license(license_code: str | None) -> str:
    if license_code in PUBLICATION_COMPATIBLE_LICENSES:
        return "commercial-compatible-subject-to-attribution"
    if license_code in {"cc-by-sa", "cc-by-nc-sa"}:
        return "share-alike-review-required"
    if license_code in {"cc-by-nd", "cc-by-nc-nd"}:
        return "no-derivatives-review-required"
    if license_code and license_code.startswith("cc-by-nc"):
        return "noncommercial-only"
    if license_code:
        return "manual-review-required"
    return "permission-required"


def _rights(license_code: str | None) -> dict:
    status = publication_status_for_photo_license(license_code)
    return {
        "license_code": license_code,
        "publication_status": status,
        "visual_release_ready": status == "commercial-compatible-subject-to-attribution",
        "attribution_required": license_code != "cc0",
    }


def _request(url: str, user_agent: str, timeout: float, accept: str) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": accept})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"iNaturalist request failed for {url}: {exc}") from exc


def _observation(observation_id: int, user_agent: str, timeout: float) -> dict:
    if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id <= 0:
        raise ValueError("iNaturalist observation id must be a positive integer")
    url = f"{INATURALIST_API}/observations/{observation_id}"
    try:
        payload = json.loads(_request(url, user_agent, timeout, "application/json"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"iNaturalist returned invalid JSON for observation {observation_id}") from exc
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError(f"iNaturalist observation was not found: {observation_id}")
    return results[0]


def _photo_url(photo: dict, size: str) -> tuple[str, str]:
    value = photo.get("url")
    if not isinstance(value, str):
        raise ValueError("iNaturalist photo has no URL")
    parsed = urlparse(value)
    parts = Path(parsed.path).parts
    declared_id = photo.get("id")
    if (
        parsed.scheme != "https"
        or parsed.hostname not in PHOTO_HOSTS
        or len(parts) != 4
        or parts[1] != "photos"
        or not parts[2].isdigit()
        or parts[3].count(".") != 1
        or int(parts[2]) != declared_id
        or Path(parts[3]).stem not in {"square", "thumb", "small", "medium", "large", "original"}
    ):
        raise ValueError("iNaturalist photo has no safe open-data URL")
    _, suffix = Path(parts[3]).stem, Path(parts[3]).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError("iNaturalist photo format is unsupported")
    return f"https://{parsed.hostname}/photos/{declared_id}/{size}{suffix}", suffix


def _photo_record(observation: dict, photo_id: int | None, size: str) -> tuple[dict, dict]:
    photos = observation.get("photos")
    if not isinstance(photos, list) or not photos:
        raise ValueError("iNaturalist observation has no attached photos")
    candidates = [
        photo for photo in photos
        if isinstance(photo, dict)
        and not photo.get("hidden")
        and (photo_id is None or photo.get("id") == photo_id)
    ]
    if photo_id is not None and not candidates:
        raise ValueError(f"iNaturalist observation has no visible photo {photo_id}")
    if photo_id is None and len(candidates) != 1:
        raise ValueError("observation has multiple photos; pass --photo-id explicitly")
    photo = candidates[0]
    declared_id = photo.get("id")
    if isinstance(declared_id, bool) or not isinstance(declared_id, int) or declared_id <= 0:
        raise ValueError("iNaturalist photo has an invalid id")
    license_code = photo.get("license_code")
    if license_code is not None and not isinstance(license_code, str):
        raise ValueError("iNaturalist photo license code is invalid")
    license_code = (license_code or "").strip().lower() or None
    if license_code not in REUSABLE_LICENSES:
        raise ValueError("iNaturalist photo is not published under a reusable Creative Commons license")
    attribution = photo.get("attribution")
    if attribution is not None and not isinstance(attribution, str):
        raise ValueError("iNaturalist photo attribution is invalid")
    download_url, suffix = _photo_url(photo, size)
    dimensions = photo.get("original_dimensions")
    if not isinstance(dimensions, dict):
        dimensions = {}
    width, height = dimensions.get("width"), dimensions.get("height")
    normalized_dimensions = {
        "width": width if isinstance(width, int) and width > 0 else None,
        "height": height if isinstance(height, int) and height > 0 else None,
    }
    observation_id = observation.get("id")
    if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id <= 0:
        raise ValueError("iNaturalist observation has an invalid id")
    observation_url = observation.get("uri") or f"https://www.inaturalist.org/observations/{observation_id}"
    parsed_observation = urlparse(observation_url) if isinstance(observation_url, str) else None
    if (
        parsed_observation is None
        or parsed_observation.scheme != "https"
        or parsed_observation.hostname not in {"www.inaturalist.org", "inaturalist.org"}
        or parsed_observation.path != f"/observations/{observation_id}"
    ):
        raise ValueError("iNaturalist observation has no safe public URL")
    normalized_photo = {
        "id": declared_id,
        "url": download_url,
        "source_url": observation_url,
        "download_size": size,
        "format": suffix.lstrip("."),
        "original_dimensions": normalized_dimensions,
        "license_code": license_code,
        "attribution": attribution.strip() if attribution and attribution.strip() else f"Photo licensed {license_code.upper()}",
    }
    taxon_value = observation.get("taxon")
    taxon: dict[str, object] = dict(taxon_value) if isinstance(taxon_value, dict) else {}
    normalized_observation = {
        "id": observation_id,
        "url": observation_url,
        "observed_on": observation.get("observed_on"),
        "contributor": (observation.get("user") or {}).get("login")
        if isinstance(observation.get("user"), dict) else None,
        "taxon": {
            "id": taxon.get("id"),
            "scientific_name": taxon.get("name"),
            "common_name": taxon.get("preferred_common_name"),
            "iconic_taxon_name": taxon.get("iconic_taxon_name"),
        },
    }
    return normalized_observation, normalized_photo


def _download_file(
    url: str,
    destination: Path,
    user_agent: str,
    timeout: float,
    suffix: str,
) -> None:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "image/*"})
    try:
        with urlopen(request, timeout=timeout) as response, destination.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("iNaturalist photo exceeds the 64 MiB download limit")
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"iNaturalist photo download failed for {url}: {exc}") from exc
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("iNaturalist photo download produced an empty file")
    with destination.open("rb") as source:
        header = source.read(12)
    signatures = {
        ".jpg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
        ".png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": lambda value: value.startswith((b"GIF87a", b"GIF89a")),
    }
    if not signatures[suffix](header):
        raise ValueError("iNaturalist photo bytes do not match the declared image format")


def verify_inaturalist_photo(
    value: str | Path,
    *,
    require_publication_compatible: bool = False,
) -> tuple[Path, Path, dict]:
    path = Path(value).resolve()
    sidecar = path.with_suffix(path.suffix + ".json")
    if not path.is_file() or not sidecar.is_file():
        raise FileNotFoundError(path if not path.is_file() else sidecar)
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid iNaturalist photo metadata: {sidecar}: {exc.msg}") from exc
    if not isinstance(record, dict) or record.get("schema") != INATURALIST_PHOTO_SCHEMA:
        raise ValueError("unsupported iNaturalist photo metadata schema")
    photo = record.get("photo")
    rights = record.get("rights")
    output = record.get("output")
    if not isinstance(photo, dict) or not isinstance(rights, dict) or not isinstance(output, dict):
        raise ValueError("iNaturalist photo metadata is incomplete")
    if output.get("sha256") != sha256(path):
        raise ValueError("iNaturalist photo checksum has changed")
    if rights != _rights(photo.get("license_code")):
        raise ValueError("iNaturalist photo rights record is invalid")
    if require_publication_compatible and not rights["visual_release_ready"]:
        raise ValueError(
            "iNaturalist photo is not cleared for flexible public/commercial visual reuse: "
            f"{rights['publication_status']}"
        )
    return path, sidecar, record


def download_inaturalist_photo(
    observation_id: int,
    song: str | Path,
    role: str,
    *,
    photo_id: int | None = None,
    size: str = "large",
    note: str = "",
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
) -> tuple[Path, Path, dict]:
    """Freeze one reusable observation photo with attribution and rights evidence."""
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("iNaturalist photo role must contain a letter or number")
    if size not in PHOTO_SIZES:
        raise ValueError("iNaturalist photo size must be small, medium, large, or original")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("iNaturalist photo user agent is required")
    if timeout <= 0:
        raise ValueError("iNaturalist photo timeout must be greater than zero")

    observation = _observation(observation_id, user_agent, timeout)
    normalized_observation, photo = _photo_record(observation, photo_id, size)
    observation_id = normalized_observation["id"]
    photo_id = photo["id"]
    suffix = f".{photo['format']}"
    destination_dir = song_path / "references" / "inaturalist-photos" / role_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"observation-{observation_id}-photo-{photo_id}-{size}{suffix}"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists() or sidecar.exists():
        path, existing_sidecar, existing = verify_inaturalist_photo(destination)
        if (
            existing.get("photo") == photo
            and existing.get("source", {}).get("observation_id") == observation_id
            and existing.get("source", {}).get("url") == normalized_observation["url"]
        ):
            return path, existing_sidecar, existing
        raise FileExistsError(f"iNaturalist photo reference has conflicting provenance: {destination}")

    partial = destination.with_name(f".{destination.name}.partial")
    if partial.exists():
        raise FileExistsError(f"incomplete iNaturalist photo download exists: {partial}")
    try:
        _download_file(photo["url"], partial, user_agent, timeout, suffix)
        partial.replace(destination)
        retrieved_at = utc_now()
        metadata = {
            "schema": INATURALIST_PHOTO_SCHEMA,
            "created_at": retrieved_at,
            "retrieved_at": retrieved_at,
            "source": {
                "provider": "iNaturalist",
                "api_url": f"{INATURALIST_API}/observations/{observation_id}",
                "observation_id": observation_id,
                **normalized_observation,
            },
            "photo": photo,
            "role": role,
            "note": note,
            "rights": _rights(photo["license_code"]),
            "output": {
                "path": str(destination.relative_to(song_path)),
                "sha256": sha256(destination),
                "size_bytes": destination.stat().st_size,
            },
            "authority": {
                "statement": (
                    "This is downloaded community-science photo evidence. It is not a "
                    "live-sighting claim; publication must preserve the recorded license and attribution."
                )
            },
        }
        sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return destination, sidecar, metadata
    except Exception:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise
