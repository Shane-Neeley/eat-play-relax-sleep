# Source-aware sketches

`eprs source-sketch` makes a reversible first arrangement from recordings that
were explicitly captured by `eprs make-song`. It is the bridge between safe raw
intake and a useful first listen; request capture by itself never starts audio
processing.

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --intent "Let the guitar invite; family voices answer after the room breathes."
```

The command binds the exact run, captured request, and immutable recording
checksums. It writes:

- an editable `eprs.mix/v1` score in `code/`;
- a stereo float diagnostic mix and provenance under `mixes/`;
- a checksummed `eprs.source-sketch/v1` record under
  `notes/source-sketches/`;
- an optional short, audio-reactive visual driven by the source-aware mix;
- an updated Graphviz production map; and
- shallow `_LISTEN.wav`, optional `_WATCH.mp4`, and `NOW.md` pointers.

The arrangement keeps each recording byte-for-byte unchanged. Role words only
guide a small set of musical choices: entrance bar, conservative gain reduction,
and narrow panning. The player's push, drag, breath, pitch, overlap, room sound,
attack, decay, drift, and noise remain intact. Short fade-outs occur only when a
source extends beyond the diagnostic bed.

Fresh OS entropy is the default, so another pass gets a different seed and
combination of choices. Reproduce a useful pass by supplying its recorded seed:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --intent "Let the guitar invite; family voices answer after the room breathes." \
  --seed 777
```

Use `--no-bed` to omit the generated starter pocket and `--no-visual` for an
audio-only pass. Neither option changes a supplied recording.

Every pass requires a complete listen. Record that decision on its working mix:

```bash
./scripts/eprs mix-review <mix.wav> --song songs/signal-garden \
  --listening-note "The invitation and answer leave enough air." \
  --decision keep
```

`keep` means the diagnostic answered its current musical question. It is not a
master approval, rights clearance, upload authorization, or publication
authorization.
