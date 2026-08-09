"""Parser and deterministic transformations for the small, legible .beat language."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random
import re
import shlex


NOTE_RE = re.compile(r"^[A-Ga-g](?:#|b)?-?\d$")


@dataclass
class Track:
    name: str
    kind: str
    steps: list[str]
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class Beat:
    title: str = "Untitled"
    tempo: float = 100.0
    meter: tuple[int, int] = (4, 4)
    resolution: int = 16
    bars: int = 4
    swing: float = 0.5
    seed: int = 1
    tracks: list[Track] = field(default_factory=list)
    source: Path | None = None

    @property
    def steps_per_bar(self) -> int:
        return round(self.resolution * self.meter[0] / self.meter[1])

    @property
    def total_steps(self) -> int:
        return self.steps_per_bar * self.bars

    @property
    def seconds_per_step(self) -> float:
        return 60.0 / self.tempo * 4.0 / self.resolution

    @property
    def duration(self) -> float:
        return self.total_steps * self.seconds_per_step


def _split_options(text: str) -> tuple[str, dict[str, str]]:
    body, marker, tail = text.partition(";")
    options: dict[str, str] = {}
    if marker:
        for token in shlex.split(tail):
            if "=" not in token:
                raise ValueError(f"Expected key=value track option, got {token!r}")
            key, value = token.split("=", 1)
            options[key.strip()] = value.strip()
    return body.strip(), options


def _pattern_steps(text: str) -> list[str]:
    compact = "".join(c for c in text if not c.isspace() and c != "|")
    invalid = sorted(set(compact) - set(".xXgo-"))
    if invalid:
        raise ValueError(f"Unknown pattern symbols: {''.join(invalid)}")
    return list(compact.replace("-", "."))


def _note_steps(text: str) -> list[str]:
    tokens = [token for token in text.replace("|", " ").split() if token]
    for token in tokens:
        if token in {".", "-", "~"}:
            continue
        for note in token.split("+"):
            if not NOTE_RE.match(note):
                raise ValueError(f"Invalid note token {token!r}")
    return ["." if token == "-" else token for token in tokens]


def parse(text: str, source: Path | None = None) -> Beat:
    beat = Beat(source=source)
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        # Inline comments start with whitespace + '#'; accidentals such as C#3 remain notes.
        line = line.partition(" #")[0].strip()
        if not line:
            continue
        command, _, rest = line.partition(" ")
        command, rest = command.lower(), rest.strip()
        try:
            if command == "title":
                values = shlex.split(rest)
                beat.title = " ".join(values)
            elif command == "tempo":
                beat.tempo = float(rest)
            elif command == "meter":
                top, bottom = rest.split("/", 1)
                beat.meter = (int(top), int(bottom))
            elif command == "resolution":
                beat.resolution = int(rest)
            elif command == "bars":
                beat.bars = int(rest)
            elif command == "swing":
                beat.swing = float(rest)
            elif command == "seed":
                beat.seed = int(rest)
            elif command in {"track", "notes"}:
                name, _, pattern = rest.partition(" ")
                if not name or not pattern:
                    raise ValueError(f"{command} needs a name and pattern")
                body, options = _split_options(pattern)
                kind = "notes" if command == "notes" else options.pop("kind", name)
                steps = _note_steps(body) if command == "notes" else _pattern_steps(body)
                beat.tracks.append(Track(name=name, kind=kind, steps=steps, options=options))
            else:
                raise ValueError(f"Unknown directive {command!r}")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source or '<beat>'}:{number}: {exc}") from exc
    validate(beat)
    return beat


def load(path: str | Path) -> Beat:
    source = Path(path).resolve()
    return parse(source.read_text(encoding="utf-8"), source)


def validate(beat: Beat) -> None:
    if not 20 <= beat.tempo <= 400:
        raise ValueError("tempo must be between 20 and 400 BPM")
    if beat.meter[0] < 1 or beat.meter[1] not in {1, 2, 4, 8, 16}:
        raise ValueError("meter must use a positive numerator and power-of-two denominator")
    if beat.resolution not in {4, 8, 12, 16, 24, 32}:
        raise ValueError("resolution must be one of 4, 8, 12, 16, 24, or 32")
    if not 1 <= beat.bars <= 512:
        raise ValueError("bars must be between 1 and 512")
    if not 0.5 <= beat.swing <= 0.75:
        raise ValueError("swing must be between 0.50 (straight) and 0.75")
    if not beat.tracks:
        raise ValueError("a beat needs at least one track")
    for track in beat.tracks:
        if not track.steps:
            raise ValueError(f"track {track.name!r} has no steps")
        try:
            start_bar = int(track.options.get("start_bar", "1"))
            end_bar = int(track.options.get("end_bar", str(beat.bars)))
            every_bars = int(track.options.get("every_bars", "1"))
            float(track.options.get("offset_ms", "0"))
        except ValueError as exc:
            raise ValueError(f"track {track.name!r} has an invalid arrangement option") from exc
        if not 1 <= start_bar <= end_bar <= beat.bars:
            raise ValueError(
                f"track {track.name!r} bar range must satisfy 1 <= start_bar <= end_bar <= bars"
            )
        if every_bars < 1:
            raise ValueError(f"track {track.name!r} every_bars must be positive")


def expanded_steps(track: Track, count: int) -> list[str]:
    return [track.steps[index % len(track.steps)] for index in range(count)]


def track_active(track: Track, step_index: int, steps_per_bar: int) -> bool:
    """Whether a track should sound at this step in a sectioned arrangement."""
    bar = step_index // steps_per_bar + 1
    start_bar = int(track.options.get("start_bar", "1"))
    end_bar = int(track.options.get("end_bar", str(10**9)))
    every_bars = int(track.options.get("every_bars", "1"))
    return start_bar <= bar <= end_bar and (bar - start_bar) % every_bars == 0


def dumps(beat: Beat) -> str:
    lines = [
        f'title "{beat.title}"',
        f"tempo {beat.tempo:g}",
        f"meter {beat.meter[0]}/{beat.meter[1]}",
        f"resolution {beat.resolution}",
        f"bars {beat.bars}",
        f"swing {beat.swing:g}",
        f"seed {beat.seed}",
        "",
    ]
    for track in beat.tracks:
        command = "notes" if track.kind == "notes" else "track"
        body = " ".join(track.steps) if command == "notes" else "".join(track.steps)
        chunks = [body[i : i + beat.steps_per_bar] for i in range(0, len(body), beat.steps_per_bar)] if command == "track" else [body]
        formatted = " | ".join(chunks)
        options = dict(track.options)
        if command == "track" and track.kind != track.name:
            options = {"kind": track.kind, **options}
        suffix = "" if not options else " ; " + " ".join(f"{k}={v}" for k, v in options.items())
        lines.append(f"{command} {track.name} | {formatted} |{suffix}")
    return "\n".join(lines) + "\n"


def mutate(beat: Beat, seed: int, amount: float = 0.08) -> Beat:
    """Return a restrained deterministic rhythm variation, preserving downbeats."""
    if not 0 <= amount <= 0.5:
        raise ValueError("mutation amount must be between 0 and 0.5")
    rng = random.Random(seed)
    copy = Beat(**{**beat.__dict__, "seed": seed, "tracks": []})
    for track in beat.tracks:
        steps = list(track.steps)
        if track.kind != "notes":
            for index, value in enumerate(steps):
                if index % beat.steps_per_bar == 0 or rng.random() >= amount:
                    continue
                if value == ".":
                    steps[index] = "g" if rng.random() < 0.7 else "x"
                elif value in {"g", "x"}:
                    steps[index] = "." if rng.random() < 0.55 else ("x" if value == "g" else "g")
        copy.tracks.append(Track(track.name, track.kind, steps, dict(track.options)))
    return copy
