# BeatScript: hearing code as time

BeatScript is deliberately smaller than a DAW. It is a shared sketchpad for a musician and an agent.

## Default song length

Most songs should target roughly **2–3 minutes** once they become complete listening
versions. Short 8–24 bar renders are still useful, but label them as sketches,
controls, or arrangement studies; do not let a short prototype silently become the
default finished-song length.

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

Track options after `;` include `gain`, `pan` (-1 to +1), `humanize_ms`, `offset_ms`, and `sample`. Note lanes also accept `voice` and step-based `length`. A sample path is resolved relative to the `.beat` file. The headless renderer accepts 8-, 16-, 24-, or 32-bit integer PCM WAV, including the 24-bit output from `eprs autotune`; FFmpeg can safely create a derived compatible stem from other source formats.

Sample lanes can opt into explicit source leveling with `sample_level=rms` or
`sample_level=peak`. RMS leveling defaults to a target RMS of `0.16` and a
peak ceiling of `0.88`; override them with `sample_target_rms=`,
`sample_target_peak=`, and `sample_peak_ceiling=` when a source needs a
different role. This is per-source gain staging, not a claim that different
recordings have equal biological loudness. The final prototype renderer also
raises non-silent under-filled mixes to its safe `0.92` peak instead of leaving
them unnecessarily quiet. Delivery mastering remains an explicit separate
decision.

Long-form arrangements can scope any lane with one-indexed `start_bar` and `end_bar`. Add `every_bars=N` to sound only every Nth bar within that range—useful for crash marks and other sparse events. For example, this marks bars 17, 25, 33, and 41:

```beat
track chorus_crash | X... .... .... .... | ; kind=crash start_bar=17 end_bar=48 every_bars=8 gain=0.2
```

`offset_ms` applies a deliberate fixed pocket offset; a negative value sits ahead of the grid and a positive value sits behind it. `humanize_ms` then adds seeded variation around that position.

`swing 0.50` is straight. Values above it delay every second subdivision; the allowed ceiling is intentionally 0.75. Swing and `humanize_ms` approximate timing but do not claim to create pocket—the performance relationship in the brief remains authoritative.

For odd or unfamiliar meters, do a separate bar-grid preflight before treating
the render as a finished song. A lane whose pattern length wraps partway through
the meter can be an intentional polyrhythmic device, but it can also be an
accidental 4/4 phrase pasted into 7/8. EPRS reports that condition explicitly;
it is a human-review risk, not evidence of musical sophistication. Use
`eprs quality` and document the intended grouping and why the listener can feel
the pulse.

## From a loop to a late-blooming form

A private local trial validated a useful form-first pattern. Three materially
different BeatScript auditions were frozen with separate seeds and rendered as
lossless controls. The listener kept the 24-bar version whose arrangement
withheld the bass until bar 9, introduced its high answer at bar 17, dropped the
kick for a two-bar breakdown, and returned the complete relationship only for
the final two bars. The keep decision belonged to the listener; the successful
render and analysis did not create approval by themselves.

The reusable lesson is to make form with scoped lanes rather than expecting one
busy loop to imply an arrangement:

```beat
title "Late Bloom Study"
tempo 94
meter 4/4
resolution 16
bars 24
swing 0.575
seed 26081001

notes intro_chords | C#3+E3+G#3+B3 . . . . . . . A2+C#3+E3+B3 . . . . . . . | ; voice=lead start_bar=1 end_bar=4 gain=0.10 length=5.8
track body_kick | X... .... ..x. ...g | X... ...g .... x... | ; kind=kick start_bar=5 end_bar=20 gain=0.72 humanize_ms=6
track body_snare | .... X... .... .... | .... X... ..g. .... | ; kind=snare start_bar=5 end_bar=20 gain=0.43 offset_ms=11 humanize_ms=7
notes body_bass | C#2 . . . . . G#1 . B1 . . C#2 . . . . | ; voice=bass start_bar=9 end_bar=20 gain=0.31 length=1.45
notes late_answer | . . . . G#4 . B4 . . . C#5 . . B4 . . | ; voice=lead start_bar=17 end_bar=20 gain=0.10 length=1.7
track break_stick | .... .... x... .... | ; kind=stick start_bar=21 end_bar=22 gain=0.10
track final_kick | X... .... ..x. ...g | ; kind=kick start_bar=23 end_bar=24 gain=0.74
notes final_answer | . . . . G#4 . B4 . . . C#5 . E5 . C#5 . | ; voice=lead start_bar=23 end_bar=24 gain=0.11 length=1.8
```

This is a teaching reduction, not the private score. Its important decisions
are player-readable:

- establish harmony before drums;
- establish drums before bass;
- let the bass answer the kick rather than duplicate it;
- delay the brightest register until the form has earned it;
- remove the center during the breakdown instead of adding another fill; and
- use fixed offsets for authored pocket, then smaller seeded humanization
  around those positions.

The kept audition also had substantially more section contrast than the two
controls when analyzed, but loudness range was used only as a lead for
listening. It did not rank the songs or substitute for the complete-listen
decision.

## Intuition exercises

1. Remove every hat and listen for whether the kick/snare relationship still speaks.
2. Move one kick by one sixteenth; describe the bodily effect before looking at the grid.
3. Compare the same pattern at swing 0.50, 0.54, and 0.62.
4. Keep the drums fixed and rotate a five-step percussion pattern underneath them.
5. Replace one synthetic lane with a live or field-recorded take and retain its original timing.
6. Use `mutate` with the same seed twice, then a different seed; decide what should be authored and what can remain procedural.
