# Reversible performance comping

A comp chooses moments from several performances while keeping every source
take intact. `eprs comp` is for family vocals, guitar phrases, chimes, spoken
ideas, room performances, and other material where an ordered phrase should
become one editable stem before processing or mixing.

Compare takes first when the choice is still open. Then write exactly why each
chosen region belongs:

```bash
cp templates/comp.json songs/signal-garden/code/family-comp.json
# Edit source paths, listening regions, phrase intent, and every boundary.
scripts/eprs comp songs/signal-garden/code/family-comp.json \
  --song songs/signal-garden
```

An `eprs.comp/v1` score has an overall player-facing intent, ordered segments,
and exactly one transition between every neighboring pair. Every segment and
transition requires its own intent. Transition types are:

- `cut`: place the next phrase directly after the previous one;
- `silence`: insert an exact declared breath or gap; and
- `crossfade`: overlap triangular fades for an exact declared duration.

Crossfades are opt-in and must be shorter than both neighboring regions. A
hard cut or audible change in room tone may be the honest musical edit, so the
renderer never smooths a boundary automatically.

Sources must be song-relative mono or stereo media with known duration. When
all sources share sample rate and channel layout, the comp preserves them. When
they differ, the score must explicitly declare `output.sample_rate` and/or
`output.channels`; the provenance records each conversion. Output is a 32-bit
float working stem under `stems/<role>/<title>/`.

Comping never tunes, quantizes, denoises, normalizes, compresses, limits,
time-stretches, or applies automatic gain. It trims and joins only the regions
the score names. Each source checksum, resolved filter graph, expected duration,
format choice, measurements, and safety invariant are written beside the stem.

After auditioning the complete edit against its source takes:

```bash
scripts/eprs comp-review stems/family-voices/family-answer-comp/<comp>.wav \
  --song songs/signal-garden --decision keep \
  --listening-note "The joins disappear into the room, and the held breath still feels intentional."
```

Use `change` when another region or boundary should be tried, and `stop` when
the comp direction is not serving the performance. Reviews change only the
sidecar; audio remains byte-identical. A revised score creates a new stem and
preserves the earlier listening decision.
