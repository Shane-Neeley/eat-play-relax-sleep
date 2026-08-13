"""Search the reference catalog shipped with the installed Sonic Pi app."""

from __future__ import annotations

import argparse
from html import unescape
import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable


SCHEMA = "eprs.sonic-pi-catalog/v1"
KINDS = ("synth", "fx", "sample", "function")
FILES = {
    "synth": "synths.json",
    "fx": "fx.json",
    "sample": "samples.json",
    "function": "lang.json",
}


def _candidate_reference_dirs() -> list[Path]:
    candidates: list[Path] = []
    configured = os.environ.get("SONIC_PI_REFERENCE_DIR")
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        Path("/Applications/Sonic Pi.app/Contents/Resources/etc/doc/generated/native/reference"),
        Path("/usr/share/sonic-pi/etc/doc/generated/native/reference"),
        Path("/usr/lib/sonic-pi/etc/doc/generated/native/reference"),
        Path("/opt/sonic-pi/etc/doc/generated/native/reference"),
    ])
    return candidates


def locate_reference_dir(explicit: str | Path | None = None) -> Path:
    candidates = [Path(explicit).expanduser()] if explicit else _candidate_reference_dirs()
    for candidate in candidates:
        if all((candidate / filename).is_file() for filename in FILES.values()):
            return candidate.resolve()
    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(
        "Sonic Pi's generated reference catalog was not found. "
        "Pass --reference-dir or set SONIC_PI_REFERENCE_DIR. "
        f"Searched: {searched}"
    )


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Sonic Pi reference file must contain an object: {path}")
    return value


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(text).split())


def _page_entry(kind: str, page: dict) -> dict:
    entry = {
        "kind": kind,
        "name": str(page.get("key", "")),
        "title": str(page.get("title") or page.get("summary") or page.get("key", "")),
    }
    for key in ("summary", "usage", "introduced"):
        if page.get(key) not in (None, ""):
            entry[key] = page[key]
    description = _plain_text(page.get("doc_html"))
    if description:
        entry["description"] = description
    options = []
    for option in page.get("opts", []):
        normalized = {"name": option.get("name")}
        for key in ("default", "min", "max", "max_excl", "slidable"):
            if key in option:
                normalized[key] = option[key]
        if option.get("doc"):
            normalized["description"] = " ".join(str(option["doc"]).split())
        options.append(normalized)
    if options:
        entry["options"] = options
    return entry


def load_catalog(reference_dir: str | Path | None = None) -> dict:
    root = locate_reference_dir(reference_dir)
    synths = _read_json(root / FILES["synth"])
    effects = _read_json(root / FILES["fx"])
    samples = _read_json(root / FILES["sample"])
    functions = _read_json(root / FILES["function"])

    entries: list[dict] = []
    entries.extend(_page_entry("synth", page) for page in synths.get("pages", []))
    entries.extend(_page_entry("fx", page) for page in effects.get("pages", []))
    for group in samples.get("groups", []):
        for name in group.get("samples", []):
            entries.append({
                "kind": "sample",
                "name": str(name),
                "title": str(name).replace("_", " ").title(),
                "group": str(group.get("title", "Ungrouped")),
            })
    entries.extend(_page_entry("function", page) for page in functions.get("pages", []))
    return {"schema": SCHEMA, "reference_dir": str(root), "entries": entries}


def summarize(catalog: dict) -> dict:
    entries = catalog["entries"]
    counts = {kind: sum(entry["kind"] == kind for entry in entries) for kind in KINDS}
    sample_groups = sorted({
        entry["group"] for entry in entries
        if entry["kind"] == "sample" and entry.get("group")
    })
    return {
        "schema": SCHEMA,
        "reference_dir": catalog["reference_dir"],
        "counts": counts,
        "sample_groups": sample_groups,
    }


def list_entries(catalog: dict, kind: str) -> list[dict]:
    _validate_kind(kind)
    return [entry for entry in catalog["entries"] if entry["kind"] == kind]


def find_entry(catalog: dict, kind: str, name: str) -> dict:
    _validate_kind(kind)
    normalized = name.removeprefix(":").lower()
    for entry in catalog["entries"]:
        if entry["kind"] == kind and entry["name"].lower() == normalized:
            return entry
    raise KeyError(f"Unknown Sonic Pi {kind}: {name}")


def search_entries(
    catalog: dict,
    query: str,
    kinds: Iterable[str] = KINDS,
    limit: int = 30,
) -> list[dict]:
    requested = tuple(kinds)
    for kind in requested:
        _validate_kind(kind)
    terms = [term.lower() for term in query.split() if term]
    if not terms:
        raise ValueError("search query must contain at least one non-space character")
    matches = []
    for entry in catalog["entries"]:
        if entry["kind"] not in requested:
            continue
        haystack = json.dumps(entry, ensure_ascii=False).lower()
        if all(term in haystack for term in terms):
            matches.append(entry)
            if len(matches) >= limit:
                break
    return matches


def _validate_kind(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query the generated reference catalog shipped with Sonic Pi."
    )
    parser.add_argument("--reference-dir", help="Directory containing synths.json and peers")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("summary", help="Report installed catalog counts")

    listing = commands.add_parser("list", help="List every entry of one kind")
    listing.add_argument("kind", choices=KINDS)

    search = commands.add_parser("search", help="Search names, docs, groups, and options")
    search.add_argument("query")
    search.add_argument("--kind", choices=KINDS, action="append", dest="kinds")
    search.add_argument("--limit", type=int, default=30)

    show = commands.add_parser("show", help="Show one exact entry")
    show.add_argument("kind", choices=KINDS)
    show.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = load_catalog(args.reference_dir)
        if args.command == "summary":
            result: object = summarize(catalog)
        elif args.command == "list":
            result = list_entries(catalog, args.kind)
        elif args.command == "search":
            if args.limit < 1:
                raise ValueError("--limit must be positive")
            result = search_entries(catalog, args.query, args.kinds or KINDS, args.limit)
        else:
            result = find_entry(catalog, args.kind, args.name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": SCHEMA, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
