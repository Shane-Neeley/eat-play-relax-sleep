# Production patterns — Raven, Then River (2026-08-27)

This note records reusable EPRS production lessons from the independent
field-intelligence run. It is intentionally public-safe: the daily reading
spark is abstracted, and no private source details or contributor identity are
included.

## Creative method

The public ShaneNeeley.com context suggested giving a long shape room to
breathe. I transformed that into a fictional current crossing open space, then
made a 96 BPM 11/8 (3+3+3+2) instrumental question: an unquantized CC0 field
cue is a quiet punctuation layer, while the bass, pluck, wood, and response
phrases are entirely newly composed. The form has a real floorless open-water
subtraction, a harmonic crossing, and a register-shifted return.

The source was frozen before conversion and kept separate from its derived
playback WAV. The preserved iNaturalist observation is the provenance record;
its spacing and grain are a compositional constraint, not animal language,
intent, or a translation claim. See the public observation and API references:

- https://www.inaturalist.org/observations/392928640
- https://api.inaturalist.org/v1/docs/

## Method comparison

Recent catalog entries emphasized source-free acoustic-body or procedural
geometry pieces. This run deliberately changes three axes at once: a real
compatible-rights field texture (still low and unquantized), a smooth odd-meter
pocket, and a wide fictional twilight waterline film. The visual is drawn with
Pillow and assembled with FFmpeg: amber call ripples, a separate pale current,
dark reeds, and a crescent moon. No real wildlife, person, place, logo, stock
footage, waveform, or generative-AI asset appears.

## Failure-driven improvements

- The first renderer rebuilt a static gradient for every frame and was stopped
  when the performance bound was clear. Caching that layer made the render
  practical.
- The second renderer used 2.75 quarter beats for an 11/8 bar. Representative
  frame review caught the early call/gap timing; the release renderer uses the
  correct 5.5-quarter-beat bar and recomputed event times.
- Thumbnail/caption upload used the authorized API fallback after the browser
  upload. Studio's altered/synthetic-content field was explicitly set to
  “No, AI wasn’t used”: deterministic BeatScript/Pillow/FFmpeg, ordinary DSP,
  synths, and a CC0 recording are not generative-AI media.

## Verified release

The checksum-verified FINAL package was published to CashForClankers after
local rights, originality, quality, media, metadata, and channel checks. The
watch page and max-resolution thumbnail returned HTTP 200; `yt-dlp` matched the
title, channel ID, public visibility, upload date, and 221-second duration; the
English authored SRT was accepted. Studio's copyright scan was delayed but
showed no claim or warning at publication time; that state is recorded in the
immutable receipt rather than overstated as a completed scan.

- YouTube: https://www.youtube.com/watch?v=Stb1aXLAow8
- Final release: `songs/raven-then-river/FINAL/raven-then-river-public-youtube-release-e5c224e425/`
- Publication receipt: `songs/raven-then-river/notes/publications/e5c224e4252b74ec42845e332d55aa889b63029ea4023a517baaae31e90c6b23/receipts/stb1axlaow8-ea9d40e162.json`
- Frontier packet: local workspace evidence (not part of the public repository)

## Reuse boundary

Keep the process lessons—cache static visual layers, calculate odd-meter bars
in quarter beats, and inspect sync frames before packaging. Do not reuse this
exact raven/call-punctuation, 11/8, twilight-waterline, amber-ripple,
crescent/reeds, or no-text wide-thumbnail lane in the next daily release.
