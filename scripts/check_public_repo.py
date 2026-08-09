#!/usr/bin/env python3
"""Fail when public Git candidates cross the repository's privacy boundary."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]

PERSONAL_PATTERNS = {
    "macOS user path": re.compile(b"/" + rb"Users/[A-Za-z0-9._-]+"),
    "Linux user path": re.compile(b"/" + rb"home/[A-Za-z0-9._-]+"),
    "person-specific default": re.compile(
        rb"(?:owner\s*:\s*|default[_ -]?owner\s*[=:]\s*)['\"]?" + b"Sha" + rb"ne\b",
        re.IGNORECASE,
    ),
}

SECRET_PATTERNS = {
    "private key": re.compile(b"-----" + rb"BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\b" + b"gh" + rb"[pousr]_[A-Za-z0-9_]{20,}\b"),
    "OpenAI-style secret": re.compile(rb"\b" + b"sk" + rb"-[A-Za-z0-9_-]{20,}\b"),
    "Google API key": re.compile(rb"\b" + b"AI" + rb"za[0-9A-Za-z_-]{20,}\b"),
    "Slack token": re.compile(rb"\b" + b"xox" + rb"[baprs]-[A-Za-z0-9-]{10,}\b"),
}


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=check, capture_output=True
    )


def candidate_paths() -> list[Path]:
    result = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8", errors="surrogateescape")
        if path.is_file():
            paths.append(path)
    return paths


def ignored(path: str) -> bool:
    return git("check-ignore", "--quiet", path, check=False).returncode == 0


def main() -> int:
    failures: list[str] = []
    if not ignored("songs/private-project/song.json"):
        failures.append("songs/* is not protected by .gitignore")
    if ignored("songs/README.md"):
        failures.append("songs/README.md policy file is unexpectedly ignored")
    if not ignored(".eprs-local/toolchain.json"):
        failures.append(".eprs-local/ is not protected by .gitignore")

    for path in candidate_paths():
        try:
            data = path.read_bytes()
        except OSError as exc:
            failures.append(f"cannot inspect {path.relative_to(ROOT)}: {exc}")
            continue
        for label, pattern in {**PERSONAL_PATTERNS, **SECRET_PATTERNS}.items():
            match = pattern.search(data)
            if match:
                line = data.count(b"\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(ROOT)}:{line}: detected {label}")

    if failures:
        print("Public repository check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Public repository check passed ({len(candidate_paths())} candidate files inspected).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
