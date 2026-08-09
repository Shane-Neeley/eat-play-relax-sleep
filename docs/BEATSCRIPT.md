# BeatScript: hearing code as time

BeatScript is deliberately smaller than a DAW. It is a shared sketchpad for a musician and an agent.

```beat
title "Porchlight Pocket"
tempo 94
meter 4/4
resolution 16
bars 8
swing 0.54
seed 1977

track kick  | X... ..x. .... x... | ; gain=0.78 humanize_ms=5
track snare | .... X... .... X... | ; gain=0.58 humanize_ms=8
notes bass  | C2 . . . C2 . G1 . Bb1 . . . G1 . . . | ; voice=bass length=1.5
```

The primary subdivision is set by `resolution`: 16 means sixteenth notes, 12 means eighth-note triplets in 4/4, and 24 means sixteenth-note triplets. Bars and visual `|` separators are for comprehension; patterns cycle if they are shorter than the song.

Pattern symbols:

- `X`: accent
- `x`: normal hit
- `g`: ghost or feathered hit
- `o`: open/articulated hit
- `.` or `-`: rest

Note lanes use spaces. `C3+E3+G3` is a chord, `.` is a rest, and `~` is currently silence reserved for a future tie operation.

Track options after `;` include `gain`, `pan` (-1 to +1), `humanize_ms`, `offset_ms`, and `sample`. Note lanes also accept `voice` and step-based `length`. A sample path is resolved relative to the `.beat` file. The headless renderer accepts 16-bit PCM WAV; FFmpeg can safely create a derived compatible stem from other source formats.

Long-form arrangements can scope any lane with one-indexed `start_bar` and `end_bar`. Add `every_bars=N` to sound only every Nth bar within that range—useful for crash marks and other sparse events. For example, this marks bars 17, 25, 33, and 41:

```beat
track chorus_crash | X... .... .... .... | ; kind=crash start_bar=17 end_bar=48 every_bars=8 gain=0.2
```

`offset_ms` applies a deliberate fixed pocket offset; a negative value sits ahead of the grid and a positive value sits behind it. `humanize_ms` then adds seeded variation around that position.

`swing 0.50` is straight. Values above it delay every second subdivision; the allowed ceiling is intentionally 0.75. Swing and `humanize_ms` approximate timing but do not claim to create pocket—the performance relationship in the brief remains authoritative.

## Intuition exercises

1. Remove every hat and listen for whether the kick/snare relationship still speaks.
2. Move one kick by one sixteenth; describe the bodily effect before looking at the grid.
3. Compare the same pattern at swing 0.50, 0.54, and 0.62.
4. Keep the drums fixed and rotate a five-step percussion pattern underneath them.
5. Replace one synthetic lane with a live or field-recorded take and retain its original timing.
6. Use `mutate` with the same seed twice, then a different seed; decide what should be authored and what can remain procedural.
