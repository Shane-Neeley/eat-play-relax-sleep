#!/usr/bin/env python3
"""Generate bounded synthetic voice cues through the FireRedTTS3 Space.

The default path uses reference-free Voice Design. It sends only the declared
instruction and cue text, downloads each generated WAV, and records the exact
request, Space revision, checksums, and optional EPRS autotune treatment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import wave


DEFAULT_SPACE_ID = "hugging-apps/firered-tts3"
DEFAULT_BASE_URL = "https://hugging-apps-firered-tts3.hf.space"
MODEL_ID = "FireRedTeam/FireRedTTS3"
MODEL_LICENSE = "Apache-2.0"
AUTOTUNE_PRESETS = ("none", "transparent", "tight", "hard-step", "gloopy")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--space-id", default=DEFAULT_SPACE_ID)
    command.add_argument("--base-url", default=DEFAULT_BASE_URL)
    command.add_argument(
        "--space-revision",
        help="Known Space git revision; otherwise retrieve it from the Hugging Face API",
    )
    command.add_argument(
        "--instruct",
        required=True,
        help="Describe an original synthetic voice; do not request a real-person imitation",
    )
    command.add_argument(
        "--text", action="append", required=True,
        help="One cue to synthesize; repeat for a bounded cue batch",
    )
    command.add_argument("--out-dir", type=Path, required=True)
    command.add_argument("--prefix", default="firered-cue")
    command.add_argument("--seed", type=int, default=20260814)
    command.add_argument("--inference-cfg", type=float, default=1.2)
    command.add_argument("--timesteps", type=int, default=10)
    command.add_argument("--no-text-normalization", action="store_true")
    command.add_argument("--timeout", type=float, default=180.0)
    command.add_argument(
        "--autotune-preset", choices=AUTOTUNE_PRESETS, default="none",
        help="Optionally preserve each raw cue and render a declared EPRS tuning treatment",
    )
    command.add_argument("--autotune-key", default="C")
    command.add_argument("--autotune-scale", default="chromatic")
    command.add_argument(
        "--version", action="version", version="firered-tts3-voice 0.1",
    )
    return command


def _headers(*, json_body: bool = False) -> dict[str, str]:
    headers = {"Accept": "application/json, text/event-stream, audio/wav"}
    if json_body:
        headers["Content-Type"] = "application/json"
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _open(request: urllib.request.Request, timeout: float):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read(2048).decode("utf-8", errors="replace")
        if exc.code == 429:
            raise RuntimeError(
                f"FireRedTTS3 Space rate limited the request (HTTP 429): {detail}"
            ) from exc
        raise RuntimeError(
            f"FireRedTTS3 Space returned HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"FireRedTTS3 Space is unavailable: {exc}") from exc


def _space_revision(space_id: str, timeout: float) -> str | None:
    url = "https://huggingface.co/api/spaces/" + urllib.parse.quote(
        space_id, safe="/"
    )
    request = urllib.request.Request(url, headers=_headers())
    try:
        with _open(request, timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (RuntimeError, ValueError):
        return None
    revision = value.get("sha") if isinstance(value, dict) else None
    return revision if isinstance(revision, str) and revision else None


def _submit_voice_design(
    base_url: str, payload: dict[str, Any], timeout: float
) -> str:
    url = base_url.rstrip("/") + "/gradio_api/call/v2/voice_design"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(json_body=True),
        method="POST",
    )
    with _open(request, timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    event_id = value.get("event_id") if isinstance(value, dict) else None
    if not isinstance(event_id, str) or not event_id:
        raise RuntimeError("FireRedTTS3 Space did not return an event id")
    return event_id


def _wait_for_result(base_url: str, event_id: str, timeout: float) -> list[Any]:
    quoted = urllib.parse.quote(event_id, safe="")
    url = base_url.rstrip("/") + f"/gradio_api/call/voice_design/{quoted}"
    request = urllib.request.Request(url, headers=_headers())
    event = ""
    with _open(request, timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line.partition(":")[2].strip()
                continue
            if not line.startswith("data:"):
                continue
            data = line.partition(":")[2].strip()
            if event == "error":
                raise RuntimeError(f"FireRedTTS3 generation failed: {data}")
            if event == "complete":
                value = json.loads(data)
                if not isinstance(value, list) or not value:
                    raise RuntimeError("FireRedTTS3 returned an invalid completion payload")
                return value
    raise RuntimeError("FireRedTTS3 Space closed before completing generation")


def _download_url(base_url: str, output: Any) -> str:
    if not isinstance(output, dict):
        raise RuntimeError("FireRedTTS3 completion did not include an audio object")
    candidate = output.get("url")
    if not isinstance(candidate, str) or not candidate:
        path = output.get("path")
        if isinstance(path, str) and path:
            candidate = "/gradio_api/file=" + urllib.parse.quote(path, safe="/")
    if not isinstance(candidate, str) or not candidate:
        raise RuntimeError("FireRedTTS3 completion did not include an audio URL")
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", candidate)
    base = urllib.parse.urlparse(base_url)
    parsed = urllib.parse.urlparse(url)
    local_test = parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.netloc != base.netloc or (parsed.scheme != "https" and not local_test):
        raise RuntimeError("FireRedTTS3 returned an unexpected audio download origin")
    return url


def _download_wav(url: str, destination: Path, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_headers())
    with _open(request, timeout) as response:
        body = response.read()
    destination.write_bytes(body)
    try:
        with wave.open(str(destination), "rb") as audio:
            frames = audio.getnframes()
            sample_rate = audio.getframerate()
            if frames <= 0 or sample_rate <= 0:
                raise ValueError("empty audio")
            return {
                "sample_rate": sample_rate,
                "channels": audio.getnchannels(),
                "sample_width_bytes": audio.getsampwidth(),
                "frames": frames,
                "duration_seconds": frames / sample_rate,
            }
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "FireRedTTS3 response was not a non-empty PCM WAV"
        ) from exc


def _payload(args: argparse.Namespace, text: str, seed: int) -> dict[str, Any]:
    if not 0.0 <= args.inference_cfg <= 4.0:
        raise ValueError("--inference-cfg must be between 0 and 4")
    if not 4 <= args.timesteps <= 30:
        raise ValueError("--timesteps must be between 4 and 30")
    if not text.strip() or len(text) > 400:
        raise ValueError("each --text cue must contain 1 to 400 characters")
    if not args.instruct.strip() or len(args.instruct) > 400:
        raise ValueError("--instruct must contain 1 to 400 characters")
    return {
        "instruction": args.instruct,
        "text": text,
        "inference_cfg": args.inference_cfg,
        "n_timesteps": args.timesteps,
        "seed": seed,
        "do_tn": not args.no_text_normalization,
    }


def generate(args: argparse.Namespace) -> Path:
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"FireRedTTS3 manifest already exists: {manifest_path}")
    for index in range(1, len(args.text) + 1):
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        candidates = [destination]
        if args.autotune_preset != "none":
            candidates.extend([
                args.out_dir / f"{args.prefix}-raw-{index:02d}.wav",
                destination.with_suffix(destination.suffix + ".json"),
            ])
        existing = next((path for path in candidates if path.exists()), None)
        if existing:
            raise FileExistsError(f"FireRedTTS3 output already exists: {existing}")

    revision = args.space_revision or _space_revision(args.space_id, args.timeout)
    outputs: list[dict[str, Any]] = []
    for index, text in enumerate(args.text, start=1):
        cue_seed = args.seed + index - 1
        payload = _payload(args, text, cue_seed)
        event_id = _submit_voice_design(args.base_url, payload, args.timeout)
        result = _wait_for_result(args.base_url, event_id, args.timeout)
        destination = args.out_dir / f"{args.prefix}-{index:02d}.wav"
        raw_destination = (
            args.out_dir / f"{args.prefix}-raw-{index:02d}.wav"
            if args.autotune_preset != "none" else destination
        )
        probe = _download_wav(
            _download_url(args.base_url, result[0]), raw_destination, args.timeout
        )
        output: dict[str, Any] = {
            "id": f"{args.prefix}-{index:02d}",
            "text": text,
            "seed": cue_seed,
            "path": str(destination),
            "voice_plan": result[1] if len(result) > 1 else None,
            **probe,
        }
        if args.autotune_preset != "none":
            project_src = Path(__file__).resolve().parents[1] / "src"
            if str(project_src) not in sys.path:
                sys.path.insert(0, str(project_src))
            from eprs.autotune import render_autotune, settings_for

            settings = settings_for(
                args.autotune_preset,
                key=args.autotune_key,
                scale=args.autotune_scale,
            )
            _, tuning_manifest, _ = render_autotune(
                raw_destination,
                destination,
                settings,
                intent=(
                    f"Apply the {args.autotune_preset} pitch treatment to this "
                    f"synthetic FireRedTTS3 cue in {args.autotune_key} "
                    f"{args.autotune_scale}."
                ),
            )
            output["raw"] = {
                "path": str(raw_destination), "sha256": sha256(raw_destination),
            }
            output["autotune_manifest"] = display_path(tuning_manifest)
        output["sha256"] = sha256(destination)
        outputs.append(output)

    manifest = {
        "schema": "eprs.firered-tts3-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "provider": "Hugging Face Space",
        "space_id": args.space_id,
        "space_base_url": args.base_url,
        "space_revision": revision,
        "model": MODEL_ID,
        "model_license": MODEL_LICENSE,
        "mode": "voice-design",
        "instruction": args.instruct,
        "inference_cfg": args.inference_cfg,
        "timesteps": args.timesteps,
        "seed": args.seed,
        "text_normalization": not args.no_text_normalization,
        "hf_token_used": bool(os.environ.get("HF_TOKEN")),
        "autotune": {
            "preset": args.autotune_preset,
            "key": args.autotune_key if args.autotune_preset != "none" else None,
            "scale": args.autotune_scale if args.autotune_preset != "none" else None,
            "raw_cues_preserved": args.autotune_preset != "none",
        },
        "outputs": outputs,
        "rights": (
            "Reference-free synthetic voice design; no human reference audio was "
            "uploaded by this runner. Model and linked Space declare Apache-2.0."
        ),
        "review": (
            "technical remote render only; creative listening, disclosure, rights, "
            "release, and publication remain separate EPRS gates"
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    args = parser().parse_args()
    try:
        print(generate(args))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
