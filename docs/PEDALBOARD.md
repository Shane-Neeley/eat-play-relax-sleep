# Pedalboard

EPRS has an optional, pinned Pedalboard lane for native Python audio effects
and file I/O. It is deliberately separate from the core install because the
upstream project is GPL-3.0 and ships a native extension. EPRS does not copy
Pedalboard source into this repository; the local extra installs the upstream
wheel and preserves its license/notice obligations.

## What the source shows

The checked upstream release is `v0.9.24` at
`a3f824ff3026eac6f409b538a5df1d10f46eba32`.

- `pedalboard/__init__.py` exposes the native extension, built-in plugin
  classes, the `Pedalboard` ordered container, and external-plugin loading.
- `pedalboard/io` uses JUCE-backed `AudioFile` readers/writers and supports
  chunked processing, preserving sample rate and keeping memory bounded.
- `pedalboard/plugins` implements the built-ins in C++/JUCE: gain, dynamics,
  filters, chorus/phaser, delay/reverb, distortion/clip, bitcrush, pitch
  shift, and plugin containers such as `Mix`.
- The native binding releases Python's GIL while processing. The v0.9.24
  release also adds threaded MP3 encoding through `AudioFile.encode`; that is
  useful for delivery experiments but is not silently substituted for the
  lossless WAV master.
- The upstream tests cover chunked state continuity, I/O, threading, plugin
  containers, pitch/time effects, and optional VST3/Audio Unit loading.

## EPRS contract

Install the optional lane with:

```bash
make pedalboard-install
```

Render a song-local recipe with:

```bash
uv run --locked --extra pedalboard eprs pedalboard \
  songs/<song>/code/<recipe>.json --song songs/<song>
```

Recipes use `eprs.pedalboard/v1`. They accept ordered built-in chains and
parallel `mix` branches, but intentionally do not serialize arbitrary VST3 or
Audio Unit paths. Every output is a float working stem under `stems/` with an
adjacent `eprs.pedalboard-render/v1` sidecar containing the exact normalized
recipe, source/output checksums, package version, upstream revision, probe,
analysis, and review state. `eprs pedalboard-review` records the listening
decision without changing audio.

The final export still goes through the EPRS 24-bit master path. Pedalboard's
creative contribution must be named in the song making-of note and should be
audible as an arrangement choice—parallel space, filter movement, modulation,
or controlled dirt—not merely a hidden loudness pass.

## License note

Pedalboard and its bundled JUCE/VST3 components are GPL-3.0 according to the
upstream `LICENSE` and `NOTICE`. The generated audio is not source code, and
this repo does not vendor or modify the upstream implementation. Recheck the
upstream notice before distributing a derivative software bundle.
