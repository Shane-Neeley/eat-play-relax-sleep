# EPRS technology-gap review — 2026-08-29

This review turns the scheduler shortlist into a small capability garden for a
general, agentic music-and-video producer. EPRS adopts a tool only when it adds a
clear option without becoming a required style, model, renderer, or release
path. Every adopted lane must leave the portable EPRS source and ordinary review
gates intact.

The supplied scheduler message contained nine entries even though it was titled
“top 10.” Essentia is restored here as the tenth item from the preceding EPRS
research note.

## Decision

| Rank | Candidate | Decision | Why |
| --- | --- | --- | --- |
| 1 | SuperCollider / scsynth | Adopted, optional | High musical upside from UGens, granular/sample processing, and algorithmic composition. It is installed as a 3.14.1 macOS cask and exposed only through a read-only handoff profile. |
| 2 | OpenCV | Adopted, optional | Directly addresses the blurry-video failure mode with bounded focus, contrast, edge, motion, crop-geometry, and thumbnail evidence. It is a headless Python extra, not a core dependency. |
| 3 | Apple Metal / metal-cpp | Hold | Valuable only after a measured WebGPU bottleneck. It is a native C++17 integration path, so adding it now would create a second renderer before the current vGPU path has failed. |
| 4 | Faust | Hold | Strong portable DSP option and a useful future bridge to SuperCollider, but a new compiler/plugin distribution lane is more machinery than the current daily loop needs. Revisit for a specific reusable DSP effect. |
| 5 | Skia | Hold | High-quality 2D rendering is attractive, but direct Python/Node integration and another raster/vector backend would duplicate current Pillow/SVG/Remotion coverage. |
| 6 | OpenTimelineIO | Hold | Good interchange foundation, but current EPRS interchange already covers the immediate common-start stem problem. Add it when daily work has multiple editorial timeline branches or real OTIO consumers. |
| 7 | BirdNET-Analyzer | Hold, analysis-only candidate | Useful for descriptive bird-source validation, but the source code and model licenses differ; current model terms are CC BY-NC-SA 4.0. It should not enter a monetized release path without an exact model-rights decision. |
| 8 | WhisperKit / Argmax OSS | Hold | Native Apple-Silicon timestamps could improve caption latency, but current local Whisper is already a working optional lane and Swift/Xcode packaging is a new build surface. Revisit if caption throughput becomes a daily bottleneck. |
| 9 | Godot | Hold | A compelling authored-world lane, but it is a full engine and would compete with Remotion/vGPU for picture ownership. Keep it as a future isolated scene adapter, not a default renderer. |
| 10 | Essentia | Hold | Deep MIR coverage is useful for research, but AGPL-3 licensing and native build/binding friction make it too heavy for the current quality gate. Revisit for a sharply defined descriptor study. |

## Adopted interfaces

### OpenCV video quality

`eprs video-quality` samples a bounded, evenly spaced set of frames and writes an
`eprs.video-quality/v1` report. The report is evidence, not approval. It reports:

- Laplacian-variance focus evidence and a p25 sharpness floor;
- grayscale contrast and Canny edge density;
- sampled frame-to-frame absolute difference as a lightweight motion signal;
- center-crop geometry when a target aspect is supplied; and
- the strongest sampled frame as a thumbnail candidate.

The lane is installed with `make opencv-install`, which uses the headless
`opencv-python-headless` extra. No OpenCV import occurs during normal EPRS
startup, and no full-local-production workflow depends on it. A soft or static
visual can still be kept when that is what the prompt asks for; metrics only
identify likely technical risk.

The analyzer refuses source files over 4 GiB, frames over 4096 pixels or 16
megapixels, and sampling requests over a 250-megapixel decode budget. It also
holds incomplete sample decodes, fingerprints the source with SHA-256, and
stores only a basename in the JSON report so a shareable report does not expose
the operator's filesystem path.

Example:

```bash
make opencv-install
uv run --locked --extra opencv eprs video-quality \
  songs/example/video/candidate.mp4 \
  --target-width 1280 --target-height 720 \
  --out songs/example/notes/video-quality.json
```

### SuperCollider / scsynth

SuperCollider is installed locally for experiments, but EPRS does not embed an
`.scd` runtime in its core or replace BeatScript/Sonic Pi. The adapter keeps the
source, local samples, server settings, render, and review decision visible. Use
it for a specific synthesis hypothesis, then hand a new WAV back through normal
EPRS analysis, mix, master, picture, and release gates.

The installed app includes `sclang`, `scsynth`, and `supernova`; the shared
registry detects the app as an optional provider. Keep server control bound to
localhost and do not enable remote OSC just because the application is present.

## Revisit triggers

- Adopt Metal only after a reproducible vGPU render or frame-quality benchmark
  shows WebGPU is the bottleneck rather than the scene design.
- Adopt Faust for one named DSP primitive whose output must be shared across two
  backends; do not install it merely because it is general.
- Adopt OpenTimelineIO after two or more real interchange consumers need cuts,
  transitions, or editorial metadata that the current stem package cannot carry.
- Reassess BirdNET or Essentia only with an exact model/library rights record and
  a bounded analysis experiment.
- Reassess WhisperKit when caption timing or CPU cost is a measured daily
  bottleneck, not as a speculative replacement.
- Reassess Godot only for a concrete authored-world brief that Remotion/vGPU
  cannot express without a second renderer becoming the simpler option.

## Primary references

- [SuperCollider](https://github.com/supercollider/supercollider) — GPL-3.0;
  `scsynth`, `supernova`, `sclang`, and macOS builds.
- [OpenCV](https://github.com/opencv/opencv) and [OpenCV optical flow
  documentation](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html) —
  Apache-2.0 computer-vision library.
- [Apple metal-cpp](https://github.com/apple/metal-cpp) — Apache-2.0, header-only
  C++ interface requiring C++17.
- [Faust](https://github.com/grame-cncm/faust) — compiled signal-processing and
  synthesis language.
- [Skia](https://skia.org/about/) — 2D graphics backend candidate.
- [OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO) —
  Apache-2.0 editorial interchange API.
- [BirdNET-Analyzer](https://github.com/birdnet-team/BirdNET-Analyzer) — MIT
  source with model-specific CC BY-NC-SA terms.
- [Argmax OSS Swift](https://github.com/argmaxinc/argmax-oss-swift) — MIT
  on-device Speech AI SDK with macOS 14/Xcode 16 prerequisites.
- [Godot](https://github.com/godotengine/godot) — MIT 2D/3D engine.
- [Essentia](https://github.com/MTG/essentia) — AGPL-3.0 audio/MIR library.
