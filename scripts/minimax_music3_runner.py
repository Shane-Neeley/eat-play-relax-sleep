#!/usr/bin/env python3
"""Call a running MiniMax Music 3 service and preserve an EPRS WAV manifest.

MiniMax Music 3 is not a local-Mac model: the official checkpoint requires a
CUDA runtime and is too large for the project's 16 GB Apple Silicon machine.
This runner keeps the EPRS integration portable by talking to an explicitly
operated, OpenAI-compatible local or remote sidecar. It never downloads model
weights, stores credentials, or overwrites an existing output.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import os
import urllib.error
import urllib.request
import wave


DEFAULT_MODEL = "MiniMaxAI/MiniMax-Music3"
DEFAULT_ENDPOINT = "http://127.0.0.1:8000/v1/audio/speech"
LICENSE_URL = "https://huggingface.co/MiniMaxAI/MiniMax-Music3/blob/main/LICENSE"
MODEL_URL = "https://huggingface.co/MiniMaxAI/MiniMax-Music3"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    lyrics = command.add_mutually_exclusive_group(required=True)
    lyrics.add_argument("--lyrics", help="Tagged lyrics text")
    lyrics.add_argument("--lyrics-file", type=Path, help="UTF-8 tagged lyrics file")
    command.add_argument(
        "--instructions", required=True,
        help="MiniMax Structured Caption or concise music description",
    )
    command.add_argument("--out", type=Path, required=True, help="New WAV destination")
    command.add_argument("--endpoint", default=os.environ.get("EPRS_MINIMAX_MUSIC3_URL", DEFAULT_ENDPOINT))
    command.add_argument("--model", default=DEFAULT_MODEL)
    command.add_argument("--seed", type=int, default=20260814)
    command.add_argument("--max-new-tokens", type=int, default=2250)
    command.add_argument("--timeout", type=float, default=1800.0)
    command.add_argument("--version", action="version", version="minimax-music3-runner 0.1")
    return command


def _lyrics(args: argparse.Namespace) -> str:
    if args.lyrics_file is not None:
        return args.lyrics_file.read_text(encoding="utf-8")
    assert args.lyrics is not None
    return args.lyrics


def request_payload(args: argparse.Namespace) -> dict:
    if args.max_new_tokens < 1:
        raise ValueError("--max-new-tokens must be positive")
    return {
        "model": args.model,
        "input": _lyrics(args),
        "instructions": args.instructions,
        "response_format": "wav",
        "seed": args.seed,
        "max_new_tokens": args.max_new_tokens,
        "stream": False,
    }


def _validate_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as audio:
        frames = audio.getnframes()
        if frames <= 0:
            raise ValueError("MiniMax response contained an empty WAV")
        return {
            "sample_rate": audio.getframerate(),
            "channels": audio.getnchannels(),
            "sample_width_bytes": audio.getsampwidth(),
            "frames": frames,
            "duration_seconds": frames / audio.getframerate(),
        }


def generate(args: argparse.Namespace) -> Path:
    if args.out.suffix.lower() != ".wav":
        raise ValueError("MiniMax Music 3 output must be a WAV path")
    manifest_path = args.out.with_suffix(args.out.suffix + ".json")
    if args.out.exists() or manifest_path.exists():
        raise FileExistsError(f"refusing to overwrite MiniMax output: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = request_payload(args)
    request = urllib.request.Request(
        args.endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read(1024).decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax sidecar returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"MiniMax sidecar unavailable at {args.endpoint}. "
            "Run the CUDA sidecar or use the local EPRS fallback."
        ) from exc
    if "json" in content_type.lower():
        raise RuntimeError("MiniMax sidecar returned JSON instead of the requested WAV")
    args.out.write_bytes(body)
    try:
        probe = _validate_wav(args.out)
    except Exception:
        args.out.unlink(missing_ok=True)
        raise
    manifest = {
        "schema": "eprs.minimax-music3-render/v1",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": args.model,
        "endpoint": args.endpoint,
        "seed": args.seed,
        "max_new_tokens": args.max_new_tokens,
        "lyrics": _lyrics(args),
        "instructions": args.instructions,
        "output": {
            "path": str(args.out),
            "sha256": sha256(args.out),
            **probe,
        },
        "rights": {
            "model_license": "MiniMax-Music3 Community License",
            "license_url": LICENSE_URL,
            "model_url": MODEL_URL,
            "public_disclosure_required": True,
        },
        "review": "technical sidecar render only; EPRS creative, rights, and release gates remain separate",
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
