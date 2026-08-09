"""Generate inspectable SVG rhythm maps from BeatScript."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .beat import Beat, expanded_steps, track_active


COLORS = {"X": "#ff5f4a", "x": "#ff9e64", "g": "#7dcfff", "o": "#9ece6a"}


def svg(beat: Beat, output: str | Path) -> Path:
    label_width, cell, row = 150, 24, 42
    width = label_width + beat.total_steps * cell + 40
    height = 132 + len(beat.tracks) * row
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#111318"/>',
        '<style>text{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;fill:#e7e9ee}.muted{fill:#858b98}.grid{stroke:#30343d}.bar{stroke:#697080}</style>',
        f'<text x="24" y="34" font-size="20">{escape(beat.title)}</text>',
        f'<text class="muted" x="24" y="60" font-size="13">{beat.tempo:g} BPM · {beat.meter[0]}/{beat.meter[1]} · swing {beat.swing:.2f} · seed {beat.seed}</text>',
    ]
    top = 92
    for index in range(beat.total_steps + 1):
        x = label_width + index * cell
        klass = "bar" if index % beat.steps_per_bar == 0 else "grid"
        parts.append(f'<line class="{klass}" x1="{x}" y1="{top - 12}" x2="{x}" y2="{height - 24}"/>')
    for row_index, track in enumerate(beat.tracks):
        y = top + row_index * row
        parts.append(f'<text x="24" y="{y + 18}" font-size="14">{escape(track.name)}</text>')
        for step_index, token in enumerate(expanded_steps(track, beat.total_steps)):
            if token == "." or token == "~" or not track_active(track, step_index, beat.steps_per_bar):
                continue
            x = label_width + step_index * cell + cell / 2
            color = COLORS.get(token, "#bb9af7")
            radius = 4 if token == "g" else 7
            parts.append(f'<circle cx="{x}" cy="{y + 13}" r="{radius}" fill="{color}"/>')
    parts.append("</svg>")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return destination
