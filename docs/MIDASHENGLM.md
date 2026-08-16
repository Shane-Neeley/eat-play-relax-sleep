# MiDashengLM options in EPRS

MiDashengLM-Gen is an optional audio-scene lane, not the center of EPRS. The model combines speech, music, sound effects, and environment from a structured prompt. That makes it interesting for hooks, transitions, scene beds, animal-response sketches, and process-story sound design. It is not a substitute for Sonic Pi/BeatScript's groove, local mastering, guitar space, or Shotcut's timeline authority.

## Current findings — August 15, 2026

- Official project: <https://github.com/xiaomi-research/midashenglm-gen>
- Paper: <https://arxiv.org/abs/2608.11804>
- Model: <https://huggingface.co/mispeech/midashenglm-gen>
- Tested Space: <https://huggingface.co/spaces/hugging-apps/midashenglm-gen>
- Space endpoint: `https://hugging-apps-midashenglm-gen.hf.space`
- Space hardware: ZeroGPU/A10G; the public app uses `model.to("cuda")` and exposes `/generate_audio`.
- Output claim from the app: 16 kHz mono WAV. Preserve it before any local resampling or mixing.
- The first live probe was honest but blocked by the Space's ZeroGPU quota. No MiDashengLM audio is claimed in the resulting song unless a returned WAV and checksum exist.

The official repository describes a Qwen3-1.7B backbone plus flow-matching audio generation and a 10-step Euler inference path. Those are project/model claims; EPRS still needs local evidence for speed, quality, and rights before treating another runtime as a production option.

## Structured scene grammar

The model's prompt fields are useful even when the hosted model is unavailable:

```text
<|caption|> overall scene and timing
<|asr|> exact spoken/chant text, or <|unknown|>
<|speech|> voice role, emotion, delivery, or <|unknown|>
<|music|> groove, instruments, density, and form
<|sfx|> discrete sound events
<|env|> environment and recording perspective
```

In EPRS, this is a planning vocabulary, not a lock-in. The local arrangement can use Sonic Pi, BeatScript, Qwen TTS, Seed-VC, autotune, iNaturalist audio, guitar, Shotcut, or future tools. The manifest must say which tools actually rendered the sound.

## Safe EPRS handoff

1. Check endpoint health, current quota, model revision, license, and whether the prompt contains private or identifying material.
2. Make one bounded generation. If the Space reports quota exhaustion, stop; do not retry in a loop.
3. Preserve the original returned WAV, prompt, seed, settings, endpoint, and checksum outside `FINAL` until reviewed.
4. Bring the sketch into a local mix as one source stem. Let the local beat, arrangement, rights, mastering, and YouTube checks remain authoritative.
5. If the model did not render, label the result as a local scene-grammar experiment rather than MiDasheng output.

## Creative uses worth testing

- A one-bar vocal/animal-response hook before the beat fully arrives.
- A scene transition between a raw iNaturalist call and its tuned musical answer.
- A short process-story bed that makes the software experiment audible without becoming narration-heavy.
- A call-and-response map: `music` holds the pocket, `sfx` carries the raw call, `speech` supplies a human hook, and `env` widens the world.
- A deliberately strange meter or guitar vamp arranged locally while the model contributes only a texture sketch.

## Rights and release language

Keep the public description neutral and do not include personal/source identifiers. Do not claim a MiDashengLM render, local run, or human performance unless the release manifest supports that claim. If generated audio is realistic enough to trigger platform disclosure rules, handle that in the publication checklist; the software name itself does not replace the rights and disclosure review.
