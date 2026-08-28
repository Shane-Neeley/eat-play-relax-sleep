# EPRS chord diagram design system

This file is the visual contract for guitar and ukulele chord diagrams in
lookup sheets, play-alongs, backing-track screens, and chord-map videos. It is
written for agents and renderers: preserve the hierarchy and tokens even when
the output medium changes from SVG to Pillow, Remotion, HTML, or a native UI.

## 1. Visual Theme & Atmosphere

**Midnight practice-room instrument panel.** The mood is focused, calm, and
slightly musical without becoming retro-guitar-poster decoration. The diagram
is the instrument; the UI chrome exists to help the eye land on the current
shape quickly.

Use a near-black blue canvas, charcoal surfaces, hairline borders, and one
lavender-blue active accent. Keep motion slow and purposeful. The feeling is
precise enough for a lesson and warm enough for a late-night play-along.

## 2. Color Palette & Roles

| Token | Hex | Role |
| --- | --- | --- |
| `canvas` | `#0B0C10` | Main background; never use pure black |
| `surface-1` | `#14161C` | Primary card and panel |
| `surface-2` | `#1B1E26` | Raised current-chord card and active timeline cell |
| `hairline` | `#303542` | Borders and quiet grid lines |
| `grid` | `#596173` | Fret/string lines; lighter than borders |
| `ink` | `#F4F6FB` | Chord name and essential labels |
| `ink-muted` | `#A7AFBF` | Metadata, fret numbers, secondary labels |
| `ink-faint` | `#717A8D` | Inactive timeline and tertiary copy |
| `primary` | `#7C82E8` | Current chord, focus ring, playhead, active dot |
| `primary-soft` | `#25284C` | Subtle active fill; never a full-screen gradient |
| `open-mark` | `#D8DCE8` | Open-string circle; use shape and label too |
| `mute-mark` | `#A7AFBF` | Muted-string X; use shape and label too |

Text under 18pt should target at least 4.5:1 contrast against its surface;
large chord names and other large text should target at least 3:1. Do not use
`primary` as the only signal for the active chord: pair it with weight, a
border, and the word or position that is changing.

## 3. Typography Rules

Use `SF Pro Display, -apple-system, system-ui, Segoe UI, sans-serif` for
display and `SF Pro Text, -apple-system, system-ui, Segoe UI, sans-serif` for
body. Use `SF Mono, Menlo, ui-monospace, monospace` for compact fret strings,
bar numbers, and technical metadata.

| Token | Size | Weight | Line height | Use |
| --- | ---: | ---: | ---: | --- |
| `display` | 64px | 600 | 1.05 | Current chord in a 1080p video |
| `display-compact` | 32px | 600 | 1.1 | Current chord in a lookup card |
| `card-title` | 20px | 600 | 1.2 | Chord card heading |
| `body` | 15px | 400 | 1.45 | Instructions and context |
| `label` | 12px | 500 | 1.3 | String labels, mode labels, metadata |
| `mono` | 12px | 400 | 1.35 | `X 0 2 0 2 0`, bar/fret detail |

Use slight negative tracking (`-0.02em`) for chord names 32px and larger. Use
positive tracking (`0.08em`) only for small uppercase eyebrows. Never set the
diagram itself in an italic or decorative font.

## 4. Component Stylings

**Chord card.** `surface-1`, 1px `hairline` border, 8px radius, 20px padding.
The active card gets `surface-2`, a 2px `primary` edge, and a restrained
`primary-soft` wash. No glass blur and no large drop shadow.

**Chord diagram.** Draw the nut at 3px, ordinary frets and strings at 2px, and
finger dots at 22–28px depending on the output size. Put the string labels in a
fixed row above the nut. Put `X`/`O` directly above those labels with enough
vertical room that they cannot be mistaken for finger dots. Keep finger numbers
centered inside dots with a medium-weight sans face.

**Barre.** Use one rounded horizontal capsule behind the finger number. It must
touch the relevant strings and align exactly with the fret line. Add a small
`barre` text cue only in lookup mode when the shape would otherwise be unclear.

**Progression strip.** Use equal-width bar cells, 8px gaps, and a 6px radius.
The current cell gets the primary edge and a filled progress mark; upcoming
cells remain readable on `surface-1`. Show `1`–`12` or short chord names, not
both if the cells become crowded.

**Metadata row.** Small, quiet chips for `GUITAR · STANDARD`, `E`, `84 BPM`,
`4/4`, and `CAPO 0`. Chips are compact rectangles with 6px radius; do not turn
every bit of information into a pill.

**Playhead.** Use a 2px primary line or a small filled marker. It should track
the authored bar/beat event and never cover the current diagram.

## 5. Layout Principles

Use an 8px base spacing scale: `8, 16, 24, 32, 48, 64`. Preserve generous
negative space around the chord name and diagram.

For a 16:9 play-along at 1920x1080, use 96px outer margins. The preferred
layout is a 7-column current-chord region, a 3-column next/metadata rail, and a
full-width 12-bar progression strip along the bottom. For a lookup sheet, use
four equal cards on desktop and two on tablet. A single current chord should
always dominate a multi-chord screen.

Instrument string order is part of the visual layout: guitar shows `E A D G B
e`; ukulele shows `G C E A` for high-G or the same labels with `LOW G` plainly
declared. Do not reorder labels by pitch without an explicit alternate mode.

## 6. Depth & Elevation

Use a four-level surface ladder: canvas → surface-1 → surface-2 → active edge.
Elevation is mostly contrast and a 1px border, not shadow. If a shadow is
needed on a light preview surface, use `0 8px 24px rgba(0,0,0,.22)`; on the
dark release canvas keep it under `.18` opacity. No floating neon glows, bevels,
fake wood grain, or perspective fretboards.

The current chord can have a soft 12px primary halo at 10% opacity, but the
diagram lines and finger dots must remain crisp above it.

## 7. Do's and Don'ts

### Do

- Make the chord name readable from the edge of the room before the fingering
  details are read up close.
- Keep the nut, fret numbers, string labels, open circles, mute marks, and
  finger dots in predictable positions.
- Use typography, borders, and position as well as color to show state.
- Give guitar and ukulele their own tuning label and diagram width.
- Test a still frame at delivery resolution and a narrow phone layout.

### Don't

- Do not show a generic “CAGED” or “ukulele” diagram without a tuning.
- Do not use a waveform, equalizer, decorative photo, or animation behind the
  dots when it harms fingering legibility.
- Do not place twelve full diagrams on a 16:9 play-along frame.
- Do not rely on red/green to communicate muted/open/current state.
- Do not make an open-position shape look like a movable shape, or vice versa.

## 8. Responsive Behavior

| Viewport | Behavior |
| --- | --- |
| 1920x1080 | Current chord 64px; diagram 280–340px wide; full 12-bar strip |
| 1280x720 | Current chord 48px; diagram 220–280px; keep outer margin ≥64px |
| 768–1024px | Current + next becomes stacked; progression stays horizontal and scrollable |
| 480–767px | One diagram card per row; 32px chord name; metadata wraps into two rows |
| under 480px | Lookup becomes one column; play-along hides tertiary copy before the diagram |

Keep touch controls at least 44px high. Never shrink string labels or finger
numbers below a readable size to preserve a decorative layout. If a play-along
timeline must scroll, keep the current chord card pinned and the active cell in
view.

## 9. Agent Prompt Guide

Use this compact prompt when creating a new chord visual:

> Render a glanceable EPRS chord-diagram view for `[instrument]` in
> `[tuning/capo]`. Use the authored progression and exact `shape_id` values
> from `[chord-set path]`. Show the current chord large, the next chord quiet,
> and a bar-based progression strip. Use the midnight practice-room palette,
> 8px spacing scale, crisp 2px grid lines, a distinct 3px nut, readable string
> labels, explicit `X`/`O` markers, and optional finger numbers. Keep all
> musical information above decorative motion. Bind timing to the backing-track
> time map, preserve EPRS provenance, and leave the artifact as a candidate until
> complete visual/sync review.

When the user asks only for a reference sheet, switch to lookup mode and omit
the playhead. When the user asks for a backing track, keep the same chord-set
data and add the approved audio/master binding; do not create a second,
visually divergent chord map.
