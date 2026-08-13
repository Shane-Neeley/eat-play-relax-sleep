# Promptable music visuals

The visual system turns a high-level prompt into a versioned score, then renders that score deterministically against an audio file. It does not generate faces or depend on a single model.

## The visual instrument rack

- **EPRS SVG engine + Remotion:** production default. Frame-accurate, seedable, parameterized, locally previewable, and suitable for H.264 delivery.
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

Three built-in worlds are intentionally orthogonal:

- `portal`: depth, machinery, threshold, feedback echoes.
- `ribbons`: flow, tape, wave, smear, midrange motion.
- `constellation`: sparse nodes, relationships, silence, high-frequency detail.

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

Draft mode renders at half resolution for fast decisions. Full mode renders
1920×1080 H.264/yuv420p in BT.709, with AAC at 48 kHz and a half-frame-rate
GOP. Each render receives a JSON sidecar containing hashes for the score, audio,
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
