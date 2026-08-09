# Declarative arrangement and working mixes

A mix score states the musical relationship before its coordinates: what leads,
what answers, which decay stays audible, and where silence must remain. It then
places immutable or selected sources on a shared timeline without hiding the
decisions inside a transient command line or DAW state.

Optional `evidence` entries checksum-bind the exact phase observation, research,
session context, comparison, or listening note that shaped placement and
balance. Each entry must say how it affected this mix; see [decision evidence
bindings](EVIDENCE_BINDINGS.md). A binding is provenance, not approval or new
authority.

## Start from the template

```bash
cp templates/mix.json songs/signal-garden/code/first-mix.json
```

A multi-source score can look like this:

```json
{
  "schema": "eprs.mix/v1",
  "title": "Porch answer study",
  "intent": "The guitar opens the room; family voices answer; one chime marks the release.",
  "output": {"sample_rate": 48000},
  "tracks": [
    {
      "id": "guitar-loop",
      "role": "foreground phrase",
      "intent": "Keep the pick attack and performed push inside the loop.",
      "path": "recordings/selected/guitar-loop/<selection>.wav",
      "start_seconds": 0,
      "duration_seconds": 12.8,
      "gain_db": -7,
      "pan": -0.15,
      "fade_out_ms": 20
    },
    {
      "id": "family-answer",
      "role": "human response",
      "intent": "Enter after the guitar breath; retain room and tuning variation.",
      "path": "recordings/selected/family-answer/<selection>.wav",
      "start_seconds": 3.2,
      "source_start_seconds": 0.4,
      "duration_seconds": 5.6,
      "gain_db": -5,
      "pan": 0.1,
      "fade_in_ms": 8,
      "fade_out_ms": 30
    },
    {
      "id": "release-chime",
      "role": "release marker",
      "intent": "Let the full decay cross the last vocal breath.",
      "path": "recordings/selected/chime/<selection>.wav",
      "start_seconds": 10.4,
      "gain_db": -12,
      "pan": 0.35
    }
  ]
}
```

All paths are relative to the song and must remain inside its workspace. Ingest
and select external sources first so the mix always points to preserved project
material.

## Render and inspect

```bash
./scripts/eprs mix songs/signal-garden/code/first-mix.json \
  --song songs/signal-garden

./scripts/eprs status songs/signal-garden --verify
```

The renderer writes a deterministic 32-bit float stereo WAV and
`eprs.mix-render/v1` provenance sidecar under `mixes/<mix-title>/`. An identical
score with unchanged sources returns the existing verified render.

Float output is intentional working headroom. Overlapping full-scale sources
can exceed 0 dBFS without being clipped to an integer ceiling. The sidecar and
CLI report a warning when that happens; lower the explicit gains and render a
new recipe or declare a safe negative gain in the later master recipe before
integer conversion. The renderer never resolves the warning with
automatic normalization, compression, limiting, or soft clipping.

## Hand the arrangement to another audio tool

When a DAW, editor, collaborator, or different agent should continue the mix,
prepare a [DAW-neutral common-start interchange package](DAW_INTERCHANGE.md).
The package snapshots this exact mix and its provenance, renders one aligned
float stem per track, and proves their unity sum reconstructs the reference
mix. It does not require or infer a `keep` decision.

An external pass returns through `eprs interchange return`, not by placing an
unattributed bounce in `mixes/`. The return contract preserves lossless bytes,
binds the exact interchange parent and any added recordings, discloses tool
state and unknowns, and produces another pending working mix. The same
complete-listen `mix-review` keep decision is required before mastering.

## Controls and invariants

- `start_seconds` places a source on the mix timeline.
- `source_start_seconds` and `duration_seconds` choose a region without editing
  the source. Omit duration to use the remainder of a file with known length.
- `gain_db` is explicit and limited to −90 through +12 dB.
- `pan` ranges from −1 to +1. The conservative balance law attenuates the far
  side without adding compensating gain; center preserves the source channels.
- `fade_in_ms` and `fade_out_ms` are optional and cannot extend beyond the
  selected source region.
- Mono and stereo sources are accepted. Prepare a derived stereo stem before
  using a multichannel source in a v1 mix.
- Sources are resampled to the song/output sample rate because a mix needs one
  clock. Source rate and every other conversion decision remain in provenance.

No operation quantizes, tunes, denoises, stretches, compresses, limits, or
normalizes a performance. If an experiment calls for one of those changes, add
a future explicit, versioned transformation rather than smuggling it into mix
rendering.

## Continue toward delivery

Listen through the entire float mix—including its opening, balances, overlaps,
headroom, transitions, final decay, and silence—and record what you heard:

```bash
./scripts/eprs mix-review \
  songs/signal-garden/mixes/porch-answer-study/<mix>.wav \
  --song songs/signal-garden \
  --decision keep \
  --listening-note "Listened end to end; the family answer stays present, overlap headroom is understood, and the final chime clears the silence."
```

Choose `keep`, `change`, or `stop`. The command rechecks the float WAV and every
source checksum before atomically updating only its sidecar. Repeating the same
note and decision is idempotent. Re-rendering the unchanged recipe preserves the
review. A changed mix score creates a new render that needs its own listen.

Mastering accepts only a checksum-verified mix with a recorded `keep` decision
and listening note. The master recipe and sidecar bind both the mix audio hash
and the exact approved mix-sidecar hash, so later source drift or a changed mix
decision invalidates downstream provenance. A kept mix can also become an
experiment result. It is not itself a YouTube file or an approved final master.

Keep the editable JSON score, source recordings, and float render. Only copy a
verified lossless master and its platform-specific derivatives into `FINAL/`.
