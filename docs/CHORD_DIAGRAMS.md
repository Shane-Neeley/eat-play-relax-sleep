# Chord diagrams in EPRS

Chord diagrams are a small player-facing layer that can sit beside a backing
track, a play-along timeline, or a simple chord lookup. They are not an audio
analysis result. EPRS should render them only from an authored or explicitly
declared chord set, with the tuning and voicing visible.

Use this note when a request includes guitar, ukulele, chord charts, chord
shapes, play-along help, or a backing track that should be playable at a glance.
The reusable starting point is [`templates/chord-set.json`](../templates/chord-set.json).

## The EPRS boundary

- A musical observation may report pitch candidates and pulse leads, but it
  deliberately leaves key and chord unset. Do not turn an observation into a
  chord diagram without a human or arrangement decision.
- A progression is the timing source for a play-along. The diagram renderer
  consumes the same bar/beat chord events as the backing-track recipe; it does
  not infer changes from waveform peaks or from the rendered video.
- A shape is a playable voicing, not merely a chord name. Store the instrument,
  tuning, capo, fret position, string order, open/muted state, and optional
  finger numbers with it.
- A visual render remains a derived candidate. Keep the chord-set JSON,
  renderer/source, audio or master binding, output checksum, and visual/sync
  review together under the normal EPRS picture and YouTube gates.

## Instrument conventions

### Guitar

For standard tuning, diagrams read left to right as `E A D G B e`: string 6
to string 1, low to high. Six vertical lines are strings; horizontal lines are
frets. A thick top line is the nut for an open-position shape. If the shape
starts above the nut, show the starting fret number rather than implying that
the first visible row is fret 1.

### Ukulele

For common high-G standard tuning, diagrams read left to right as `G C E A`:
string 4 to string 1. This is string order, not pitch order. The `g` is
reentrant and sits above the C string in pitch, so always print the string
labels and the tuning name. A low-G ukulele keeps the same string order but
changes the pitch of the fourth string; that is a different tuning and must be
declared.

### Shared notation

- `X` above a string means mute or do not play it.
- `O` above a string means play it open, with no fretting finger.
- A filled dot means fret that string. A number inside it is the suggested
  fretting-hand finger: `1` index, `2` middle, `3` ring, `4` pinky. Fingerings
  are suggestions, not a claim that every player must use them.
- A barre should be shown as a continuous bar plus its finger number; do not
  hide a barre inside several unrelated dots.
- Chord names should use ordinary readable symbols (`E7`, `F#m`, `Bb`, `Cadd9`)
  and match the spelling used in the progression. Do not silently rename an
  enharmonic chord in the diagram.
- If a diagram is a movable shape, show the position and the first fret. If a
  capo changes the sounding key, show both the capo and the written shape.

The canonical data representation uses one string entry per visible string in
diagram order. `frets` contains strings such as `X`, `0`, `1`, and `12`;
`fingerings` contains either a finger number or `null`. This keeps open and
muted states explicit and makes the same data usable by SVG, Pillow, Remotion,
HTML, or a future native player.

## Three display modes

### 1. Chord lookup

Use when the user asks “how do I play this?” or wants a compact reference.
Show a tidy grid of three to six shapes, grouped by instrument and tuning.
Each card contains, in order:

1. chord name;
2. diagram;
3. string labels and `X`/`O` markers;
4. position/capo and a compact fingering string.

Keep one visual scale across the grid. Do not mix a tiny guitar diagram beside
a huge ukulele diagram or make difficult voicings look equally beginner-safe.
Label alternatives as `easy`, `open`, `movable`, or `color` only when that
description is actually declared by the arranger.

### 2. Current + next

Use for a backing track or a simple play-along. Give the current chord the
largest card and a quiet next-chord cue. A slim previous/current/next strip is
usually more useful than a full page of diagrams. Show the key, tempo, meter,
tuning, capo, and bar number in a small metadata row. Highlight the current
bar and leave upcoming bars legible but visually subordinate.

The current chord should change on the authored bar/beat event, not when a
visual animation happens to cross a frame. If a chord lasts multiple bars,
keep the card stable and advance the progress marker.

### 3. Full progression map

Use for a 12-bar blues, song sheet, lesson, or a video made specifically for
playing along. Show the progression in bar-sized cells, with a single large
current diagram and no more than the next one or two shape cards. For a 12-bar
form, a 12-cell timeline is the default; repeat/cycle state should be visible.
Avoid twelve competing diagrams on screen at once.

For a video, preserve title-safe margins and test the smallest text at the
actual delivery size. The chord name is the primary read; the diagram is the
secondary read; metadata and credits are tertiary.

## Backing-track and play-along recipe

Put the chord set beside the audio recipe in `songs/<song>/code/`. The
`progression` array should use explicit bar and beat positions and stable chord
names. Each instrument view maps those names to its own exact `shape_id`, so a
guitar/ukulele toggle changes voicing without changing the backing-track clock.
A minimal play-along handoff should answer:

- What audio or approved master is being played?
- What are the key, tempo, meter, count-in, and cycle/repeat rules?
- Which instrument view is active: guitar or ukulele?
- What tuning and capo are active?
- Which exact shape is shown for each chord name?
- Does the visual follow the same time-zero and duration as the audio?
- Has the complete picture, sync, and final frame been reviewed?

When the user only asks for chord diagrams, omit playback state and render the
lookup mode. When the user asks to call up a backing track, keep the diagram
view deterministic and readable even if audio playback is unavailable; a
static diagram sheet is still a useful fallback.

## Visual quality rules

The companion design system is [`CHORD_DIAGRAM_DESIGN.md`](CHORD_DIAGRAM_DESIGN.md).
The short version is:

- use a dark, low-glare canvas with one clear accent for the active state;
- make the chord name and current-state indicator readable before the grid;
- use consistent line weights, generous spacing, and high-contrast labels;
- never communicate `X`, `O`, current state, or tuning by color alone;
- keep the nut visually distinct from ordinary fret lines;
- avoid decorative wood grain, faux fretboard perspective, busy equalizer bars,
  and motion that competes with the fingering;
- leave enough air around dots that finger numbers remain readable at a glance;
- test both a 1920x1080 video frame and a narrow phone-sized lookup layout.

The design reference is adapted from the precise, dark, restrained structure of
the Linear-style DESIGN.md collection, not copied as a brand treatment. EPRS
keeps its own musical palette and prioritizes instrument legibility.

## Quality checklist

Before keeping a chord-diagram artifact:

- [ ] The progression is authored or explicitly approved; no chord was guessed
      from an observation or waveform.
- [ ] Instrument, tuning, capo, string order, and first fret are declared.
- [ ] Every chord has a valid number of strings: six for guitar, four for uke.
- [ ] Every fret is `X`, `0`, or a positive fret number; fingerings align with
      the strings and do not obscure open/muted markers.
- [ ] The chord name, shape, and progression spelling agree.
- [ ] The current chord is driven by the same time map as the backing track.
- [ ] The visual is comfortably readable at delivery size and in a still frame.
- [ ] `X`/`O`, tuning, capo, and active state remain understandable without
      relying on color alone.
- [ ] Source, recipe, render, checksum, and review evidence remain in EPRS.

## Research notes

Researched 2026-08-20. The sources agree on the basic chart grammar: vertical
lines are strings, horizontal lines are frets, a thick top line represents the
nut, dots mark finger placement, finger numbers are suggestions, and `X`/`O`
mark muted and open strings. The ukulele-specific sources also make the
important distinction that standard high-G ukulele diagrams are written in
`G C E A` string order even though the C string is the lowest-toned string.

The visual rules above are EPRS interpretations for glanceable playback, not
claims made by those teaching pages. The compact current-plus-next layout is a
production choice that preserves the useful chart grammar while reducing the
amount of on-screen competition during a song.

Primary references:

- [Fender: How to Read Guitar Chord Charts](https://www.fender.com/articles/chords/read-guitar-chord-charts)
- [Fender: Ukulele Chord Guide](https://www.fender.com//articles/chords/ukulele-chords-for-beginners)
- [Fender: E7 chord on ukulele](https://www.fender.com//articles/chords/e7-ukulele-chord)
- [Kala: High-G and Low-G ukulele tuning](https://support.kalabrand.com/hc/en-us/articles/360028870411-What-Is-The-Difference-Between-High-G-and-Low-G-Tuning)
- [W3C: contrast minimum technique G18](https://www.w3.org/WAI/WCAG22/Techniques/general/G18)
