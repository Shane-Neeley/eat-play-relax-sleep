# Move an arrangement between audio tools

`eprs interchange prepare` turns one exact verified working mix into a
self-contained, DAW-neutral folder. Every arranged track becomes a stereo
32-bit float PCM WAV with the same sample rate, duration, and timeline start.
Import every stem at session time zero and leave its fader at unity to recover
the current arrangement in Audacity, Logic, Ableton Live, Reaper, Pro Tools, a
command-line pipeline, or another tool that reads standard WAV files.

```bash
./scripts/eprs interchange prepare \
  songs/signal-garden/mixes/first-listening-mix/<mix>.wav \
  --song songs/signal-garden
```

The deterministic package lands under:

```text
songs/signal-garden/interchange/<mix-title>-<package-id>/
  README.md
  interchange.json
  reference-mix.wav
  mix-provenance.json
  stems/
    01-guitar-loop.wav
    02-family-answer.wav
    03-release-chime.wav
```

The stem audio includes the working mix's declared trim, timeline placement,
fades, gain, conservative pan law, and sample-rate conversion. It does not add
normalization, compression, limiting, tuning, time-stretching, phase alignment,
or any other correction. The original sources and mix remain unchanged.

## Reconstruction is tested, not assumed

After rendering, the command sums every exported stem at unity and compares the
decoded samples with an exact copy of the working mix. The package is refused
unless the maximum absolute difference is at most `0.00001`. The manifest also
records RMS error, signal-to-error ratio, decoded sample count, and the fixed
tolerance so another agent can inspect the result rather than trusting a label.

Run the read-only verifier before a handoff:

```bash
./scripts/eprs interchange verify \
  songs/signal-garden/interchange/<mix-title>-<package-id> \
  --song songs/signal-garden
```

It checks the recipe-derived package ID, every checksum, common-start and media
format declarations, the reference mix and provenance snapshot, reconstruction
evidence, and the explicit false authority/action flags. `eprs status --verify`
performs the same package checks as part of song continuity.

## What the package means

The source mix need not have a `keep` decision: a common use is handing a
working arrangement to a musician for the next pass. The package snapshots the
current review state and the exact mix-sidecar checksum. Recording a later
review creates a different package ID rather than rewriting the earlier handoff.

This is an editable mix-state exchange, not a raw-recording archive. The stems
are derived and balanced for reconstruction; immutable raw takes stay in the
song workspace with their existing provenance. The package does not infer
creative approval, promote anything to `FINAL/`, or authorize upload or
publication.

On import:

1. Set the destination session to the manifest sample rate.
2. Place every file in `stems/` at time zero.
3. Start with faders at unity and pan centered; balance and pan are already
   represented in the stereo stem bytes.
4. Disable automatic normalization, warping, tempo matching, fades, and
   polarity or phase correction.
5. Compare the DAW sum with `reference-mix.wav` before making new choices.
6. Export the new mix as mono or stereo lossless audio from package time zero.
7. Save new work separately and capture the return as described below.

## Bring a DAW pass back without inventing provenance

Copy the return template into the song, then declare the exact source package,
external tool and version, operator, audible changes, known settings, unresolved
unknowns, rights context, and any song-local recordings added after export:

```bash
cp templates/daw-return.json songs/signal-garden/code/daw-return.json
./scripts/eprs interchange return songs/signal-garden/code/daw-return.json \
  --song songs/signal-garden
```

`returned_mix` may point outside the song so an export can be collected from a
DAW bounce directory. EPRS accepts only mono or stereo PCM, FLAC, or ALAC with a
known sample rate and duration. It copies those bytes unchanged into
`mixes/daw-return/`; it never normalizes, resamples, limits, tunes, denoises, or
otherwise processes the bounce. Lossy MP3/AAC returns are refused.

Every change needs a musical intent, audible description, and
`settings_or_unknown`. Use `unknown` when plug-in state, routing, automation, or
other details are unavailable. The sidecar truthfully marks external rendering
as not reproducible by EPRS and turns each unresolved item into a warning. It
binds the parent package ID and manifest checksum, exact pre-DAW mix, returned
audio checksum, disclosures, rights note, and checksums of any added sources.
Raw added recordings require their immutable `eprs.recording/v1` intake
sidecars.

The captured return is still an unapproved working mix. Listen end to end and
use the normal gate:

```bash
./scripts/eprs mix-review songs/signal-garden/mixes/daw-return/<title>/<mix>.wav \
  --song songs/signal-garden \
  --decision keep \
  --listening-note "Listened end to end; the external balance, transitions, dynamics, and silence are intentional."
```

Only then may `eprs master` use it. Verification and mastering fail if the
return, its disclosures, parent interchange manifest, original mix, or an added
source has changed. This captures an exact round trip; it does not claim the
external DAW session can be rebuilt, infer creative approval, authorize FINAL
promotion, or authorize publication.
