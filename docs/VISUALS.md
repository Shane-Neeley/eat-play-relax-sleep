# Promptable music visuals

The visual system turns a high-level prompt into a versioned score, then renders that score deterministically against an audio file. It does not generate faces or depend on a single model.

For guitar or ukulele play-alongs, use the authored chord-set contract before
choosing a visual renderer. The chord map is a semantic timing layer: bind it
to the same bar/beat progression as the backing track, then render the current
shape and progression strip through the normal picture review boundary. See
[Chord diagrams in EPRS](CHORD_DIAGRAMS.md) and the
[glanceable diagram design system](CHORD_DIAGRAM_DESIGN.md). Do not infer a
chord map from `eprs observe` output.

## The visual instrument rack

- **EPRS SVG engine + Remotion:** production default. Frame-accurate, seedable, parameterized, locally previewable, and suitable for H.264 delivery.
- **vgpu:** headless WebGPU adapter and the default music-video backend when a song benefits from beat-reactive procedural motion. It runs the same `eprs.visual/v1` score through an offscreen Dawn device, writes inspectable PNG frames, and lets FFmpeg mux the declared audio without opening a browser. Use the EPRS SVG/Remotion path when a specific editorial or live-action composition is the better fit.
- **Hydra:** future live video-synth adapter for feedback, fractals, pixel operations, and Sonic Pi/OSC performance.
- **Meyda or p5.sound:** future real-time feature extraction for browser installations and live input.
- **Three.js:** future WebGL 2 / 3D and shader-world adapter. Check WebGL capability and keep shader errors enabled while developing.
- **Python:** orchestration, audio probing, prompt compilation, provenance, offline feature extraction, and batch experiments.
- **Audacity / Sonic Pi:** produce and perform audio; export or record lossless stems. Visuals consume those derivatives and never alter source takes.

## Compile a prompt

```bash
scripts/eprs visual-prompt \
  "Slow cold constellation of circuit nodes; guitar pulls them together; silence lets them drift" \
  --title "Sleep Circuit" --seed 808 \
  --out songs/first-light/visuals/sleep-circuit.json
```

This deterministic compiler is a starting assistant, not an art director. Agents should refine the resulting `eprs.visual/v1` JSON using the supplied prompt, [visual brief](../templates/visual-brief.md), and listening notes. The original prompt stays in the score.

Four built-in worlds are intentionally orthogonal:

- `portal`: depth, machinery, threshold, feedback echoes.
- `ribbons`: flow, tape, wave, smear, midrange motion.
- `constellation`: sparse nodes, relationships, silence, high-frequency detail.
- `meadow`: daylight, grass movement, firefly-scale points, and expanding chirp rings.

The `eclipse-shadow` motif adds a deterministic partial-eclipse disc and moving
shadow limb over the selected signal world. It is an authored visual symbol for
an astronomical event, not a claim that the music models the physics of the
eclipse. Keep the event timing and location in the song note or research record,
not in an opaque renderer default. Event geometry should use a bounded
anti-aliased edge, clip the occluder and halo to the subject mask, and keep the
disc face high-contrast; otherwise the offset shadow can darken the background
and make the moon read as blurry.

The `cricket-pulse` motif is paired with the meadow world for field-recording
tracks that need a bright organic visual lane. It is an authored visual
response, not a claim that animal calls contain decoded human messages.

The `paper-pond` motif is paired with a meadow world when a song needs a flat,
editorial field-source display: a moving paper shoreline, three ripple rings,
reeds, and one marker react to the declared audio controls. It is useful for
combining a real iNaturalist sound with an abstract research idea while keeping
the source audio authoritative. Do not turn it into literal animal footage,
charts, or a scientific forecast; keep the creative translation and provenance
in the song-local score and production note.

The `tide-pool` motif uses bounded domain warping, signed-distance-style ring
edges, phase-shifted caustics, and a restrained chromatic fringe for energetic
short-form visuals. It is deliberately graphic rather than a physical water
simulation. Use `--orientation portrait` with vgpu for a native 9:16 Short
(`720x1280` at full quality); keep the source audio and beat authoritative.
When additive rings or hotspots approach white, apply motif-local exponential
highlight compression before the shared vignette multiplier; this preserves
the palette and edge separation instead of producing a clipped, blurry disk.

## Optional natural-history photographs

A relevant iNaturalist photograph is a good source choice when a real species,
texture, or habitat is more truthful to the song than stock footage or generic
model imagery. It is never inserted automatically. First freeze an exact photo
with `eprs inaturalist photo`, then add up to four references to the visual
score, using paths relative to that score:

```json
"photographs": [
  {
    "path": "../references/inaturalist-photos/marsh-texture/observation-390608319-photo-715632441-large.jpg",
    "opacity": 0.3,
    "treatment": "soft-light"
  }
]
```

The renderer verifies each adjacent `eprs.inaturalist-photo/v1` sidecar and
checksum, refuses licenses outside CC0/CC BY for this public-ready path, stages
only the verified local bytes, and records every source in the render sidecar.
Photos crossfade slowly over the existing signal world with a restrained
credit overlay; they do not become location claims or “go here” pins. Use
`normal`, `soft-light`, or `screen` treatment and 0.05–0.85 opacity. A photo is
source material, not creative approval: still capture and review the complete
picture through the ordinary picture workflow.

## Preview and render

```bash
make visuals-install

scripts/eprs visual-render visuals/presets/garage-signal-bloom.json \
  --audio build/demos/porchlight-pocket.wav \
  --seconds 6 --quality draft \
  --timeout-seconds 600 \
  --out build/visuals/garage-signal-preview.mp4

make visual-studio
```

`make visuals-install` also renders a local ignored `demo.wav` so Remotion Studio opens usefully on a fresh clone. Replace that preview input through a render score before making creative decisions about a real song.

For a browser-free smoke test or a batch render, use the optional vgpu adapter:

```bash
make vgpu-doctor
scripts/eprs visual-render songs/signal-garden/visuals/signal.json \
  --audio songs/signal-garden/experiments/signal.wav \
  --renderer vgpu --quality draft --timeout-seconds 600 \
  --out songs/signal-garden/video/previews/signal-vgpu.mp4
```

vgpu writes a song-local `.controls.json` file containing bounded, hashed audio
controls and a `.mp4.json` `eprs.vgpu-render/v1` sidecar. The frame renderer is
procedural and intentionally does not stage photographs; scores with frozen
iNaturalist photographs should use Remotion's rights-checking path. vgpu full
renders are 1280×720 in landscape and 720×1280 with `--orientation portrait`,
so a headless iteration stays practical; the existing
Remotion full path remains the higher-resolution delivery default. A vgpu result
is still only a technical picture candidate: capture and complete-picture review
remain required.

Draft Remotion mode renders at half resolution for fast decisions. Remotion full
mode renders 1920×1080 H.264/yuv420p in BT.709; vgpu full mode renders
1280×720 landscape or 720×1280 portrait.
Both paths use AAC at 48 kHz and a half-frame-rate GOP. Each render receives a
JSON sidecar containing hashes for the score, audio,
and output plus elapsed time, concurrency, and the enforced render time budget.

The renderer owns Remotion, Chromium, and FFmpeg in one private process group.
Completion, timeout, or interruption stops that entire group so a canceled task
does not leave background visual workers consuming the machine. The default
budget is 1,800 seconds; use a lower `--timeout-seconds` for short previews and
raise it deliberately for a long full-resolution film.

For a real release, render full picture against the approved master, then move
through the renderer-neutral boundary instead of treating a Remotion file as
implicitly final:

```bash
cp templates/picture.json songs/signal-garden/code/picture.json
./scripts/eprs picture add songs/signal-garden/code/picture.json \
  --song songs/signal-garden
./scripts/eprs picture review songs/signal-garden/video/pictures/<title>/<picture>.mp4 \
  --song songs/signal-garden --decision keep \
  --review-note "Watched every frame; the visual arrangement serves the performance."
```

See [renderer-neutral picture handoff](PICTURE.md). This boundary also accepts
other editors and renderers, preserves their bytes and disclosures, and ensures
final delivery takes audio only from the approved master.

## Prompt score controls

- `world`, `seed`, four-color `palette`, and `background` define identity.
- `motion` controls speed, feedback, rotation, and turbulence.
- `reactivity` weights bass, mids, and highs independently.
- `texture` controls grain, scanlines, and bloom.
- `typography` controls whether and where the title transmits.
- `photographs` optionally layers up to four frozen, attributed iNaturalist
  references over the authored signal world.
- `avoid` carries negative intent and should be checked during visual review.

Audio-reactivity is not musical intelligence. FFT bands are useful control signals, but the brief decides why bass opens a door, why a guitar bends tape, or why silence removes particles.

## Performance path

For a live set, Sonic Pi can emit OSC cues for named musical events while Hydra or a custom browser visual receives them. Keep FFT reactivity for continuous texture and use OSC for semantic moments such as `door_open`, `solo_enter`, `drop_machine`, or `room_only`. Remote OSC remains opt-in.

A commented starting patch lives in [`visuals/adapters/sonic-pi-visual-cues.rb`](../visuals/adapters/sonic-pi-visual-cues.rb), with Audacity and FFmpeg handoff notes beside it.

## Licensing note

Remotion's published terms currently allow free use for individuals and teams up to three, including commercial use; larger collaborations have a paid-license boundary. Re-check the current terms before the team or usage model changes.

## Primary references

- [Remotion audio visualization](https://www.remotion.dev/docs/visualize-audio)
- [Remotion rendering](https://www.remotion.dev/docs/render)
- [Remotion Player](https://www.remotion.dev/docs/player)
- [Remotion licensing](https://www.remotion.dev/docs/license/pricing)
- [Hydra audio reactivity](https://hydra.ojack.xyz/docs/docs/learning/guides/audio/)
- [Meyda audio features](https://meyda.js.org/)
- [p5.FFT](https://p5js.org/reference/p5.sound/p5.FFT/)
- [Three.js AudioAnalyser](https://threejs.org/docs/pages/AudioAnalyser.html)
