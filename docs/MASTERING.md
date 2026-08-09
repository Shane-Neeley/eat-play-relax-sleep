# Refusal-first lossless mastering

Mastering is a destination decision, not an automatic polish pass. The v1
workflow converts an approved float working mix into a stable 24-bit lossless
source while preserving its balance and dynamics.

“Approved” is enforced provenance, not a filename convention: the mix must be
inside the song’s `mixes/` tree, its audio and sources must still match their
checksums, and `mix-review` must contain a complete-listen `keep` decision. The
master binds the exact approved mix sidecar as well as the mix audio.

It deliberately does not provide a loudness target, limiter, compressor,
normalizer, stereo widener, denoiser, tuner, or exciter.

## Declare the delivery intent

```bash
cp templates/master.json songs/signal-garden/code/lossless-master.json
```

```json
{
  "schema": "eprs.master/v1",
  "title": "Signal Garden lossless master",
  "intent": "Preserve the approved mix balance and dynamics while creating a safe lossless source.",
  "destination": "lossless archive and YouTube source",
  "source": "mixes/signal-garden/<approved-mix>.wav",
  "gain_db": 0,
  "true_peak_ceiling_dbfs": -1,
  "output": {
    "sample_rate": 48000,
    "bit_depth": 24
  }
}
```

The source path must stay inside the song. `gain_db` is the only level-changing
operation. The true-peak ceiling is a guard: it refuses a recipe whose measured
source peak plus explicit gain would cross the boundary. It never turns the
audio down, limits peaks, or aims for the ceiling.

## Render and resolve headroom

```bash
./scripts/eprs master songs/signal-garden/code/lossless-master.json \
  --song songs/signal-garden
```

If a float mix peaks at +3.2 dBFS with a −1 dBFS ceiling, zero gain fails with a
clear error. Decide whether the mix balance should change or declare enough
negative `gain_db` in a new recipe. The renderer checks the predicted peak
before conversion and measures the 24-bit result again afterward.

Successful output lands under `masters/<master-title>/` with
`eprs.master-render/v1` provenance containing:

- source and output checksums, probes, and loudness/true-peak measurements;
- the exact kept mix-sidecar path, checksum, schema, and review decision;
- explicit gain, predicted peak, measured output peak, and declared ceiling;
- sample-rate or mono-to-stereo conversion notes;
- confirmation that normalization, compression, limiting, soft clipping, and
  dither were not added;
- independent technical-render, creative-listen, FINAL-promotion, and
  publication state.

Master v1 emits 24-bit PCM WAV. Conversion from float necessarily quantizes to
the delivery bit depth; v1 adds no dither. A future dither adapter should be an
explicit versioned choice rather than an invisible default.

## Listen before approval

Technical success does not mean the master is creatively approved. Listen to
the complete rendered file, including its beginning, final decay, and silence,
then record what you heard:

```bash
./scripts/eprs master-approve \
  songs/signal-garden/masters/signal-garden-lossless-master/<master>.wav \
  --song songs/signal-garden \
  --listening-note "Listened end to end; vocal balance, guitar transients, chime decay, and final silence are approved."
```

The approval command first rechecks the master and source hashes. It updates the
sidecar only; the audio bytes stay unchanged. Repeating the same approval note
is idempotent. It does not promote, encode, upload, or publish anything.

`eprs status songs/signal-garden --verify` reports how many masters still need a
creative listen. Only an approved, verified master should become a YouTube
source or be copied into `FINAL/`.
