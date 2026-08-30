# Local voice-model lab — 2026-08-30

This pass tested higher-fidelity, faster local voice cloning without uploading
the private reference or promoting any output to a song, performer credit, or
release. All outputs and detailed manifests remain in ignored local storage.

## What ran on the 16 GB M4

Both lanes used the same short target line, immutable explicitly authorized
reference, MPS device, and 24 kHz mono PCM output. Timings are process-local;
the cold Qwen result includes a one-time model acquisition and must not be
compared with warm inference as if it were generation time.

| Lane | Load / prompt | Generation | Audio | RTF | Through render |
| --- | ---: | ---: | ---: | ---: | ---: |
| CuteTTS Base, seed 4243 | 4.23s load | 5.39s | 3.20s | 1.68 | 10.96s |
| Qwen3-TTS 1.7B Base, seed 4243, cached | 8.72s load + 1.01s clone prompt | 6.17s | 2.48s | 2.49 | 19.03s |
| Qwen3-TTS 1.7B Base, seed 4242, first acquisition | 281.39s load + 6.88s clone prompt | 7.06s | 2.88s | 2.45 | 298.63s |

CuteTTS's own speaker encoder gave the CuteTTS candidate 0.769 cosine
similarity to the reference and the Qwen candidate 0.703. That is useful only
as a triage signal: an encoder from one competing model family is not an
impartial judge. CuteTTS was also much quieter, so the next comparison must be
blind and loudness-matched without changing the preserved raw files.

The current outcome is to keep both lanes. CuteTTS is the compact iteration
control; Qwen Base is the transcript-aware ICL control and can compute one
clone prompt for a full batch. CuteTTS's current public API performs reference
conditioning inside each generation call, so EPRS records that it is not
reused instead of claiming false batch savings.

## Research direction

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) remains the strongest
  transcript-aware test: the Base checkpoints expose reference-code plus
  speaker-embedding cloning, while x-vector-only operation is an explicit
  lower-information fallback. The [technical report](https://arxiv.org/abs/2601.15621)
  is the architectural reference.
- [CuteTTS](https://github.com/OPPO-Mente-Lab/CuteTTS) is the first compact
  Apple-Silicon lane tested here. Its 230M size, Apache-2.0 terms, measured M4
  speed, and encouraging identity triage justify the new adapter and runner.
- [Chatterbox](https://github.com/resemble-ai/chatterbox) is the next fidelity
  experiment: start with the 350M English Turbo model, preserve its watermark,
  and compare the same consented prompt and line. Nano is a useful CPU-speed
  control; Multilingual V3 is unnecessary until a multilingual song needs it.
- [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) is the next latency
  control. Its small CPU-oriented streaming architecture and reusable voice
  embeddings make it valuable even if blind likeness trails the larger models.
- [SoulX-Singer](https://huggingface.co/Soul-AILab/SoulX-Singer) remains the
  score-conditioned singing lane. It should receive authored MIDI/F0 and
  phonemes rather than asking speech cloning to invent stable sung notes.
- [Seed-VC](https://github.com/Plachtaa/seed-vc) remains the singing-conversion
  baseline when a source performance already supplies phrasing and melody.

CUDA-oriented IndexTTS2.5 and CosyVoice3 remain research candidates rather
than immediate M4 defaults. Raon-OpenTTS stays available as a historical local
control, but its 16 kHz output and CC-BY-NC-4.0 terms make it less attractive
for a release-bound lane.

## Engineering changes and next gate

The Qwen runner now supports consent-bound Base-model cloning, validates exact
reference transcript by default, hashes the source before and after inference,
and computes its clone prompt once per batch. The new CuteTTS runner loads one
model per bounded batch, refuses overwrites, hashes all safetensors and outputs,
redacts private paths, advances seeds per cue, and records load/generation/RTF
evidence. Autotune imports and settings are resolved once per batch.

The next experiment is a three-way blind listening sheet: CuteTTS, Qwen Base,
and Chatterbox Turbo, all using the same words, reference, seed policy, and
loudness-matched playback copies. Score word accuracy, Shane likeness, high-
frequency artifacts, breath/noise behavior, dynamics, emotional usefulness,
and fit in the actual arrangement. Keep raw outputs immutable. Pocket TTS then
sets the speed floor, and the best speech timbre can be tested separately in
SoulX-Singer with an authored score.

The optional formant-aware autotune A/B is not currently reproducible in the
existing local voice-processing environment because its PyWorld import hits a
local Python/Expat ABI error. Raw clone generation is unaffected; repair that
isolated environment before claiming tuned-clone results.
