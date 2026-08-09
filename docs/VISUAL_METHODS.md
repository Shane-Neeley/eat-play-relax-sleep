# Ranked visual methods for music

This is the current research ranking for EPRS. The ranking is based on the
actual job here: an agent should be able to turn a local master into an
interesting video, preserve the inputs and parameters, preview it quickly,
re-render it later, and keep the final output easy to inspect.

| Rank | Method | Best use | Why it fits / what to watch |
| --- | --- | --- | --- |
| 1 | **EPRS SVG worlds + Remotion** | Distribution-ready audio-reactive films | Already local and working in this repo. Remotion can read audio per frame, expose low/mid/high control bands, preview in Studio, and render a video or image sequence from the CLI. Keep the renderer behind the existing renderer-neutral picture boundary and re-check Remotion licensing when the team or usage model changes. |
| 2 | **FFmpeg `showwaves` / `showspectrum`** | Fast fallback, diagnostics, waveform/spectrum overlays | Tiny dependency surface, excellent for smoke tests and “is the audio actually here?” videos, and easy to run in batch. It is visually literal, so it should be a fallback or a layer inside a more authored composition rather than the house style. |
| 3 | **Graphviz production maps** | Arrangement maps, lineage diagrams, and “why this file exists” views | Now implemented by `eprs map` and every `make-song` run. Portable DOT is always written; SVG is added when Graphviz is installed. It is not a continuous music visualizer, but it makes request → source → agent work → experiment → media → review legible without folder diving. |
| 4 | **Butterchurn / projectM** | Fast, high-energy MilkDrop-style variants and live projection | Both turn FFT-driven equations and shaders into a huge visual space. Butterchurn is MIT-licensed WebGL; projectM is an LGPL C++ library with a cross-platform SDL frontend. Excellent “make it bump visually” candidates, but preset and texture packs carry their own licenses, and offline deterministic capture needs an adapter. |
| 5 | **Hydra + Meyda** | Live-coded performance visuals and improvised variants | Hydra is a free/open-source browser video synth with feedback, GLSL-like transforms, microphone FFT bands, beat callbacks, and MIDI/OSC extensions. It is a great live instrument, but microphone-oriented reactivity and interactive state make offline, frame-exact release capture a separate adapter problem. |
| 6 | **Three.js / WebGL shaders** | 3D spaces, particle systems, custom GPU worlds | `AudioAnalyser` makes frequency-domain data available to WebGL scenes and the ecosystem is broad. It can produce the most ambitious visuals, but headless rendering, GPU differences, and shader debugging add production risk. Build this after the current SVG path has a stable visual-score contract. |
| 7 | **p5.js + p5.sound** | Sketching and rapid visual experiments | Very approachable for agents and humans; FFT and waveform APIs are useful for testing a visual idea in minutes. It is better as a sandbox adapter than the primary release renderer until we add deterministic offline capture and provenance around sketches. |
| 8 | **CAVA / cavacore** | Terminal visuals, spectrum data, and a lightweight feature sidecar | MIT-licensed, cross-platform, and deliberately aesthetic. Raw output and the separated `cavacore` library can feed other renderers, making CAVA more interesting as an analysis/control layer than as the final house visual. Offline file-to-frame alignment still needs authoring. |
| 9 | **PraxisLIVE** | Node-and-code live audiovisual patches | Open-source hybrid visual programming with Processing, GStreamer, OpenGL, audio, JACK, and live code reload. Powerful for performances and installations; heavier and less deterministic than the release renderer, so capture through the renderer-neutral picture gate. |
| 10 | **Strudel / Sonic Pi semantic cues** | Agent-readable composition and live cue sources | These are not picture renderers. They are valuable upstream because named events such as `solo_enter`, `family_answer`, or `drop_machine` can drive visual changes more musically than raw FFT alone. Keep them optional and preserve the plain-text source. |

## Recommended production ladder

1. Use the current EPRS SVG/Remotion engine for authored release candidates.
2. Use FFmpeg waveform/spectrum output as the no-surprises fallback and
   technical diagnostic.
3. Keep the automatic Graphviz production map with every run; it is the
   diagnosis view, not the release picture.
4. Pilot Butterchurn first for instant high-energy variation, but ship only
   presets and textures whose exact licenses and provenance are known.
5. Add semantic cue files or OSC events when a track has meaningful musical
   moments that a spectrum cannot infer.
6. Add Hydra for live sessions and Three.js for a future GPU world, both behind
   the same `eprs.visual/v1` score plus renderer-neutral `eprs.picture/v1`
   capture.
7. Use CAVA/cavacore as a small spectrum-data sidecar when another visual tool
   needs stable band values; reserve PraxisLIVE for an intentional live patch.

## What the evidence says

- [Remotion `visualizeAudio()`](https://www.remotion.dev/docs/visualize-audio)
  returns per-frame amplitude values and explicitly separates low, middle, and
  high frequency regions; it also documents smoothing and the accuracy/speed
  tradeoff.
- [Remotion rendering](https://www.remotion.dev/docs/render) supports Studio,
  CLI, server-side rendering, audio-only output, and image sequences, which is
  why it remains the best current bridge from a score to a release candidate.
- [Hydra audio reactivity](https://hydra.ojack.xyz/docs/docs/learning/interactivity/audio/)
  exposes FFT bins, smoothing, cutoff, scale, volume, and beat detection, while
  [Hydra's main documentation](https://hydra.ojack.xyz/docs) describes it as a
  free and open-source browser video synth.
- [Three.js `AudioAnalyser`](https://threejs.org/docs/pages/AudioAnalyser.html)
  exposes FFT frequency data to a WebGL scene.
- [p5.sound](https://p5js.org/reference/p5.sound/) provides FFT, waveform, and
  amplitude analysis for browser sketches.
- [Graphviz documentation](https://graphviz.org/documentation/) covers DOT,
  layout engines, command-line renderers, and output formats; its
  [SVG output](https://graphviz.org/docs/outputs/svg/) is especially useful for
  an inspectable local dashboard.
- [Butterchurn](https://github.com/jberg/butterchurn) is an MIT-licensed WebGL
  MilkDrop implementation, while [projectM](https://github.com/projectM-visualizer/projectm)
  provides an LGPL cross-platform library and documents separately sourced
  preset packs.
- [CAVA](https://github.com/karlstav/cava) exposes raw spectrum output and the
  reusable cavacore library under MIT terms.
- [PraxisLIVE](https://www.praxislive.org/) combines node patching with live
  Java/Processing, GStreamer, OpenGL, audio, and JACK components.

## Randomness rule

Fresh `make-song` runs use OS entropy, so the same prompt is not a fixed vending
machine. Every run records the seed, and passing that seed explicitly makes a
diagnostic replay possible. The visual score, BeatScript, audio render, and
run manifest all stay tied to that seed.
