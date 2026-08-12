# Reversible audio selections and loops

Start in player language: identify the phrase, pickup, breath, decay, or room
sound that matters. The selection coordinates implement that musical landmark;
they are not the musical explanation.

## Select one phrase

```bash
./scripts/eprs select /path/to/family-voices.wav \
  --song songs/signal-garden \
  --role "family answer" \
  --start 18.25 \
  --duration 4.6 \
  --note "Begin on the inhale; keep the laugh and the room decay"
```

If the source is outside the song, the command first copies it into immutable
raw intake with recording provenance. It then writes a lossless WAV and
`eprs.audio-selection/v1` JSON sidecar under:

```text
songs/signal-garden/recordings/selected/family-answer/
```

The raw take is never edited or moved. The output keeps the source sample rate,
channel layout, and PCM bit depth when the input is PCM WAV. Compressed input is
decoded once into lossless PCM working audio.

An iNaturalist sound can be selected after its separate rights review. The
downloaded reference remains outside `recordings/raw/` and its sidecar follows
the selected audio through lineage; do not treat research-grade identification
or a public sound URL as permission to release the sample.

## Repeat a performed phrase

```bash
./scripts/eprs select /path/to/guitar-line.wav \
  --song songs/signal-garden \
  --role "guitar loop" \
  --start 12.4 \
  --duration 3.2 \
  --repeat 4 \
  --note "Let the phrase lean forward internally; repeat only its boundary"
```

The default is a literal boundary. It does not time-stretch the phrase to a
tempo, move attacks to a grid, or hide the seam. If the intended loop should
blend at its joins, make that edit explicit:

```bash
./scripts/eprs select /path/to/guitar-line.wav \
  --song songs/signal-garden \
  --role "guitar loop" \
  --start 12.4 --duration 3.2 --repeat 4 \
  --crossfade-ms 8 \
  --note "Soften only the zero-crossing seam; preserve the pick attacks"
```

With a crossfade of `c` seconds, phrase duration `d`, and repeat count `n`, the
rendered duration is `d × n − c × (n − 1)`. Crossfade must be shorter than half
the selected phrase.

## Provenance and handoff

The sidecar records source and output checksums, source and output media probes,
selection coordinates, repeat count, crossfade, output codec, sample rate, and
the player-facing note. It also states that automatic normalization,
time-stretch, pitch shift, and dynamics processing were not used.

An identical recipe is idempotent and returns the existing verified selection.
Use a new note or coordinate when testing a meaningful alternative. Before a
handoff, run:

```bash
./scripts/eprs status songs/signal-garden --verify
```

This checks the selected render and its referenced source as well as raw intake
and experiment evidence. A selected phrase can then become an experiment input:

```bash
./scripts/eprs experiment \
  --song songs/signal-garden \
  --source "guitar loop=songs/signal-garden/recordings/selected/guitar-loop/<selection>.wav" \
  --hypothesis "Does the repeated guitar leave enough air for the family answer?"
```

Because selected audio is editable working material rather than immutable raw
intake, the experiment freezes its own copy.
