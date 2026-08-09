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
parametric `eq`, `fade`, multi-tap `echo`, and an opt-in `compressor`. Chain
order is meaningful. Filters preserve the source sample rate and mono/stereo
layout. Echo extends the output by its longest declared delay. No operation
silently tunes, denoises, normalizes, limits, time-stretches, or performs
automatic gain control.

Compression is never a default. If the musical reason truly calls for it, add
an explicit operation and declare `threshold_db`, `ratio`, `attack_ms`,
`release_ms`, `makeup_db`, `knee`, `mix`, `detection`, and `link`. The sidecar
records the resolved values and warns that the result needs a level-matched
comparison with the source.

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
