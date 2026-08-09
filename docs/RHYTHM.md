# From performed beat language to rhythm evidence

A musician can say or tap more than a grid can preserve: the pickup into a
`boom`, the space before a `clap`, the stronger last answer, or a phrase that
leans forward without changing tempo. `eprs rhythm` observes that performance
before an agent decides how to interpret it.

## Observe a spoken or played pocket

```bash
./scripts/eprs rhythm /path/to/boom-clap.m4a \
  --song songs/signal-garden \
  --role "spoken pocket" \
  --note "Boom is the low gesture, clap is the answer; listen for the push into the final pair"
```

External media is first preserved in immutable raw intake. The command decodes
a mono analysis stream in memory and writes no processed audio. Its versioned
JSON observation lands under:

```text
songs/signal-garden/notes/rhythm/spoken-pocket/
```

The source remains unchanged. An identical request is idempotent.

## What the observer reports

`eprs.rhythm-observation/v2` contains:

- each detected attack's source-relative time and level;
- a dynamic hint such as `accent`, `normal`, or `soft`;
- cautious `lower/rounder`, `brighter/noisier`, or `mixed/uncertain` timbre hints;
- exact intervals, median spacing, and timing variability;
- a spacing-derived tempo candidate with half/double-time alternatives;
- a player-facing summary before the implementation details;
- the source checksum, media properties, algorithm version, and thresholds.
- a result ID binding the measured attacks, summaries, thresholds, and explicit
  interpretation limits as one internally consistent evidence payload.

The verifier continues to read legacy v1 observations, but a new groove
development requires result-bound v2 evidence so event timing cannot be changed
before interpretation without detection.

The timbre labels are signal-based inferences, useful for finding contrasting
gestures in a vocal `boom—clap`; they are not speech recognition or drum
replacement. The report explicitly leaves these decisions open:

- meter and phrase length;
- downbeat location;
- whether events are beats, subdivisions, or free-time gestures;
- which gesture the performer means as kick, snare, clap, chime, or something else.

Listen to the source and confirm those roles with the musician. Measurements do
not decide what the body hears.

## Choose a listening region

For a long memo or rehearsal recording, focus the observer on the relevant
performance:

```bash
./scripts/eprs rhythm /path/to/rehearsal.wav \
  --song songs/signal-garden \
  --role "table-tap bridge idea" \
  --start 84.2 --duration 12.5 \
  --note "The third pair drags intentionally"
```

Analysis is limited to 120 seconds per observation so a long recording cannot
silently consume unbounded memory. Use `eprs select` first when the listening
region itself should become reusable audio.

`--sensitivity` ranges from 0 to 1; higher values retain fewer, clearer attacks.
`--min-gap-ms` prevents one gesture from being reported as several attacks; its
150 ms default suits spoken syllables. Lower it deliberately for fast taps or
rolls. Keep the defaults until listening shows a specific missed or doubled
event.

## Carry the evidence into an experiment

Freeze both the performance and its observation, because the JSON does not
replace the sound:

```bash
./scripts/eprs experiment \
  --song songs/signal-garden \
  --source "spoken performance=songs/signal-garden/recordings/raw/spoken-pocket/<take>.m4a" \
  --source "timing observation=songs/signal-garden/notes/rhythm/spoken-pocket/<observation>.json" \
  --hypothesis "Can a drummer answer the bright gesture while preserving the late third pair?"
```

Only create a grid, MIDI file, or BeatScript sketch after that hypothesis calls
for one. Any later quantized representation should reference this observation
so differences between performed timing and the grid remain inspectable.

When the next useful question is specifically how a drummer might embody the
idea, copy `templates/groove.json` and use `eprs groove add`. That contract
requires player language and an explicit disposition for every observed attack,
preserves performed-minus-grid offsets, keeps materially different pulse/free-
time alternatives, and renders one synthesized BeatScript audition. See
[drummer-facing groove development](GROOVE.md). Listen against the source and
record `eprs groove review`; the grid remains an interpretation, not a
transcription or correction.

Before handoff, run `eprs status songs/<song-name> --verify`. Status inventories
the observation and verifies that its referenced source still matches the
recorded checksum.
