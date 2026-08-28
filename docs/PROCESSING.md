# Reversible stem processing

Processing starts with a sentence a player can understand. An `eprs.process/v1`
recipe names one song-relative source, the stem's role, the overall intent, and
an ordered chain of explicit operations. Every operation also requires its own
musical intent. The renderer writes a new 32-bit float WAV under `stems/`; it
never edits the source.

When an exact phase observation, research record, session note, or listening
decision materially shaped the chain, add an optional checksum-bound `evidence`
entry explaining how it constrained this recipe. See [decision evidence
bindings](EVIDENCE_BINDINGS.md). Evidence informs the chain; it never grants
permission for processing or replaces listening.

The source may be an immutable take, a lossless selection, or a reviewed
[performance comp](COMPING.md). Comp phrase choices first; keep processing as a
separate recipe so an agent can revise tone without rewriting the edit.

```bash
cp templates/process.json songs/signal-garden/code/family-voices.json
# Edit the source path, intent, and controls.
scripts/eprs process songs/signal-garden/code/family-voices.json \
  --song songs/signal-garden
```

Available operations are deliberately small: `gain`, `highpass`, `lowpass`,
parametric `eq`, `fade`, multi-tap `echo`, an opt-in `compressor`, explicit
`trim`, and bounded `time_stretch`. Chain order is meaningful. Filters
preserve the source sample rate and mono/stereo layout. Echo extends the
output by its longest declared delay. `trim` is the explicit chop/region
operation; `time_stretch` uses one declared `tempo_ratio` from 0.5 to 2.0
(`1.0` is rejected), where values above 1 make the sound faster. These edits
are useful for fitting a licensed field recording to a song's pocket, but they
never alter the immutable source and always produce a warning requiring a
level-matched, beat-grid listening comparison. No operation silently tunes,
denoises, normalizes, limits, or performs automatic gain control.

For an iNaturalist sound that should become an audible rhythmic layer, use the
source study and rhythm evidence to select the call-bearing region, then make
one or more explicit processing recipes. Render each short source slice with
`trim`/`time_stretch`, review it, and place the resulting stems repeatedly in
an `eprs.mix/v1` arrangement at authored bar positions. The public mix may
contain the edited, attributed sound; the original iNaturalist file remains
untouched and its observation/sound license stays in the lineage.

Compression is never a default. If the musical reason truly calls for it, add
an explicit operation and declare `threshold_db`, `ratio`, `attack_ms`,
`release_ms`, `makeup_db`, `knee`, `mix`, `detection`, and `link`. The sidecar
records the resolved values and warns that the result needs a level-matched
comparison with the source.

Example beat-fit recipe:

```json
{
  "schema": "eprs.process/v1",
  "title": "rattle pocket slice",
  "role": "rattlesnake percussive layer",
  "intent": "Keep the bright rattle transient but fit this call-bearing slice to the authored pocket.",
  "source": "references/inaturalist-audio/<frozen-sound>.m4a",
  "operations": [
    {"type": "trim", "intent": "Chop to the measured bright burst; preserve the source file.", "start_seconds": 0.42, "duration_seconds": 0.38},
    {"type": "time_stretch", "intent": "Slow the slice into the 118 BPM eighth-note pocket without changing pitch.", "tempo_ratio": 0.86},
    {"type": "highpass", "intent": "Leave kick and bass room while keeping the rattle edge.", "frequency_hz": 2400},
    {"type": "gain", "intent": "Place the real source under the authored drums without masking the hook.", "db": -8}
  ]
}
```

After listening, record what you heard without changing the audio:

```bash
scripts/eprs process-review stems/family-voices/...wav \
  --song songs/signal-garden \
  --decision keep \
  --listening-note "The words read clearly and the room still sounds like us."
```

Use `change` when a new recipe should replace the idea, and `stop` when the
processing direction is not worth pursuing. A new recipe creates a new stem;
old renders and decisions remain inspectable. These are working stems, not
masters. Compare them in the arrangement at sensible matched loudness before
deciding that louder is better.
