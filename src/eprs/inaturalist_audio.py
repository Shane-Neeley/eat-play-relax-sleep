"""Fetch and freeze iNaturalist sound evidence for a song workspace."""

from __future__ import annotations

import json
from pathlib import Path
import mimetypes
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .system import load_song_manifest, probe, sha256, slugify, utc_now


INATURALIST_API = "https://api.inaturalist.org/v1"
INATURALIST_SOUND_SCHEMA = "eprs.inaturalist-audio/v1"
DEFAULT_USER_AGENT = "eprs-inaturalist-audio/1.0 (read-only sound reference)"
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
COMMERCIAL_COMPATIBLE_LICENSES = {"cc0", "cc-by"}


def _sound_request(url: str, user_agent: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
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
        payload = json.loads(_sound_request(url, user_agent, timeout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"iNaturalist returned invalid JSON for observation {observation_id}") from exc
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError(f"iNaturalist observation was not found: {observation_id}")
    return results[0]


def _sound_record(observation: dict, sound_id: int | None) -> tuple[dict, dict]:
    sounds = observation.get("sounds")
    if not isinstance(sounds, list) or not sounds:
        raise ValueError("iNaturalist observation has no attached sounds")
    candidates = [
        sound for sound in sounds
        if isinstance(sound, dict) and not sound.get("hidden")
        and (sound_id is None or sound.get("id") == sound_id)
    ]
    if sound_id is not None and not candidates:
        raise ValueError(f"iNaturalist observation has no visible sound {sound_id}")
    if sound_id is None and len(candidates) != 1:
        raise ValueError("observation has multiple sounds; pass --sound-id explicitly")
    sound = candidates[0]
    file_url = sound.get("file_url")
    if not isinstance(file_url, str) or urlparse(file_url).scheme != "https":
        raise ValueError("iNaturalist sound has no safe HTTPS file URL")
    content_type = sound.get("file_content_type")
    if not isinstance(content_type, str) or not content_type.startswith("audio/"):
        raise ValueError("iNaturalist sound does not declare an audio content type")
    declared_id = sound.get("id")
    if isinstance(declared_id, bool) or not isinstance(declared_id, int) or declared_id <= 0:
        raise ValueError("iNaturalist sound has an invalid id")
    license_code = sound.get("license_code")
    if license_code is not None and not isinstance(license_code, str):
        raise ValueError("iNaturalist sound license code is invalid")
    license_code = (license_code or "").strip().lower() or None
    attribution = sound.get("attribution")
    if attribution is not None and not isinstance(attribution, str):
        raise ValueError("iNaturalist sound attribution is invalid")
    observation_id = observation.get("id")
    if isinstance(observation_id, bool) or not isinstance(observation_id, int) or observation_id <= 0:
        raise ValueError("iNaturalist observation has an invalid id")
    observation_url = observation.get("uri") or f"https://www.inaturalist.org/observations/{observation_id}"
    if not isinstance(observation_url, str) or urlparse(observation_url).scheme != "https":
        raise ValueError("iNaturalist observation has no safe public URL")
    normalized_sound = {
        "id": declared_id,
        "url": file_url,
        "content_type": content_type,
        "license_code": license_code,
        "attribution": attribution or "Attribution not supplied by iNaturalist",
    }
    normalized_observation = {
        "id": observation_id,
        "url": observation_url,
        "observed_on": observation.get("observed_on"),
        "place_guess": observation.get("place_guess"),
        "contributor": (observation.get("user") or {}).get("login")
        if isinstance(observation.get("user"), dict) else None,
        "taxon": {
            key: observation.get("taxon", {}).get(source_key)
            for key, source_key in (
                ("scientific_name", "name"),
                ("common_name", "preferred_common_name"),
                ("iconic_taxon_name", "iconic_taxon_name"),
            )
        } if isinstance(observation.get("taxon"), dict) else {},
    }
    return normalized_observation, normalized_sound


def _rights(license_code: str | None) -> dict:
    status = publication_status_for_license(license_code)
    return {
        "license_code": license_code,
        "publication_status": status,
        "reference_only_until_cleared": status != "commercial-compatible-subject-to-attribution",
    }


def publication_status_for_license(license_code: str | None) -> str:
    if license_code in COMMERCIAL_COMPATIBLE_LICENSES:
        status = "commercial-compatible-subject-to-attribution"
    elif license_code and license_code.startswith("cc-by-nc"):
        status = "noncommercial-only"
    elif license_code:
        status = "manual-review-required"
    else:
        status = "permission-required"
    return status


def _extension(content_type: str, file_url: str) -> str:
    extension = Path(urlparse(file_url).path).suffix.lower()
    if extension in {".aac", ".aif", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}:
        return extension
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    if guessed in {".aac", ".aif", ".aiff", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}:
        return guessed
    return ".audio"


def _download_file(url: str, destination: Path, user_agent: str, timeout: float) -> None:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "audio/*"})
    try:
        with urlopen(request, timeout=timeout) as response, destination.open("wb") as output:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("iNaturalist sound exceeds the 256 MiB download limit")
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"iNaturalist sound download failed for {url}: {exc}") from exc
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("iNaturalist sound download produced an empty file")


def download_inaturalist_sound(
    observation_id: int,
    song: str | Path,
    role: str,
    *,
    sound_id: int | None = None,
    note: str = "",
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: float = 30.0,
) -> tuple[Path, Path, dict]:
    """Download one iNaturalist sound into song-local reference storage.

    The media is kept outside ``recordings/raw`` because it is external
    evidence, not a human performance. The sidecar records rights and
    attribution so downstream lineage and release checks cannot mistake it
    for an owned recording.
    """
    song_path = Path(song).resolve()
    load_song_manifest(song_path)
    role_slug = slugify(role)
    if not role_slug:
        raise ValueError("iNaturalist audio role must contain a letter or number")
    if not isinstance(user_agent, str) or not user_agent.strip():
        raise ValueError("iNaturalist audio user agent is required")
    if timeout <= 0:
        raise ValueError("iNaturalist audio timeout must be greater than zero")

    observation = _observation(observation_id, user_agent, timeout)
    normalized_observation, sound = _sound_record(observation, sound_id)
    observation_id = normalized_observation["id"]
    sound_id = sound["id"]
    extension = _extension(sound["content_type"], sound["url"])
    destination_dir = song_path / "references" / "inaturalist-audio" / role_slug
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"observation-{observation_id}-sound-{sound_id}{extension}"
    sidecar = destination.with_suffix(destination.suffix + ".json")
    if destination.exists() or sidecar.exists():
        if not destination.is_file() or not sidecar.is_file():
            raise FileExistsError(f"incomplete iNaturalist audio reference exists: {destination}")
        existing = json.loads(sidecar.read_text(encoding="utf-8"))
        if (
            existing.get("schema") == INATURALIST_SOUND_SCHEMA
            and existing.get("sound", {}).get("id") == sound_id
            and existing.get("sound") == sound
            and existing.get("source", {}).get("observation_id") == observation_id
            and existing.get("source", {}).get("url") == normalized_observation["url"]
            and existing.get("rights") == _rights(sound["license_code"])
            and existing.get("output", {}).get("sha256") == sha256(destination)
        ):
            return destination, sidecar, existing
        raise FileExistsError(f"iNaturalist audio reference has conflicting provenance: {destination}")

    partial = destination.with_name(f".{destination.name}.partial")
    if partial.exists():
        raise FileExistsError(f"incomplete iNaturalist audio download exists: {partial}")
    try:
        _download_file(sound["url"], partial, user_agent, timeout)
        partial.replace(destination)
        digest = sha256(destination)
        retrieved_at = utc_now()
        metadata = {
            "schema": INATURALIST_SOUND_SCHEMA,
            "created_at": retrieved_at,
            "retrieved_at": retrieved_at,
            "source": {
                "provider": "iNaturalist",
                "api_url": f"{INATURALIST_API}/observations/{observation_id}",
                "observation_id": observation_id,
                **normalized_observation,
            },
            "sound": sound,
            "role": role,
            "note": note,
            "rights": _rights(sound["license_code"]),
            "output": {
                "path": str(destination.relative_to(song_path)),
                "sha256": digest,
                "probe": probe(destination),
            },
            "authority": {
                "statement": "This is downloaded community-science sound evidence, not permission to publish or a live-sighting claim."
            },
        }
        sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return destination, sidecar, metadata
    except Exception:
        partial.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        raise
