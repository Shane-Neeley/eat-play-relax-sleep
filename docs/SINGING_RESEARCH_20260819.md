# Singing research and test pass — 2026-08-19

## Finding

The previous workflow used speech-first Raon-OpenTTS output, Rubber Band note
placement, and EPRS/WORLD pitch correction. That can place a vowel on a target
note, but it cannot invent the singer-specific behavior that makes a line read
as singing: stable voiced onsets, consonant-to-vowel transitions, intentional
portamento, breath-shaped amplitude, and expressive pitch motion.

The most promising local path is therefore a hybrid:

1. Use a score-conditioned singing model to generate the line from lyrics and
   MIDI-like note targets.
2. Keep the raw model render as the primary vocal.
3. Offer a light EPRS/WORLD pass only as an A/B option for scale cleanup.
4. Keep speech-first Raon cues as spoken anchors, not as the sung lead.

## Methods considered

| Method | What it is good at | Why it is not the primary path here |
| --- | --- | --- |
| EPRS/WORLD via PyWorld | Transparent correction of an existing monophonic performance; modified-BSD WORLD analysis/synthesis | It cannot create a stable sung source from speech or invent phrase-level singing behavior. |
| Rubber Band R3 | Formant-preserving pitch shift and duration placement for short cues | It moves a source performance; it does not generate a singer. |
| so-vits-svc | Singing voice conversion that preserves a source singer's melody and intonation | It needs a real singing input and a trained target voice; the upstream repository is archived and AGPL-3.0. |
| OpenVPI DiffSinger | Highly controllable score/phoneme singing with variance controls | The normal workflow expects a compatible voicebank/training setup rather than zero-shot conditioning from this short speech reference. |
| SoulX-Singer | Apache-2.0 zero-shot singing synthesis with score or F0 control and unseen-singer conditioning | Larger local model and more integration work; output still requires listening review. |

The research references are the [WORLD repository](https://github.com/mmorise/World),
[so-vits-svc](https://github.com/svc-develop-team/so-vits-svc),
[OpenVPI DiffSinger](https://github.com/Metal-Studioo/OpenVpi-DiffSinger), and
[SoulX-Singer](https://huggingface.co/Soul-AILab/SoulX-Singer).

## Local test

The SoulX-Singer test used the consented local Raon reference-conditioned cue
“Wake up, eat, play, relax, and sleep.” as the timbre prompt and an authored
C3 → E♭3 → G3 → C4 → G3 → E♭3 → C3 score. A second score used “A quiet idea
becomes a song.” The model rendered both on the M4 in roughly 15–17 seconds
per phrase after model load.

Measured on the first phrase:

- 6.95 seconds, 24 kHz mono, −17.8 LUFS, −2.4 dBFS true peak
- 62.6% voiced-frame coverage
- pitch snapshots around C3, E♭3, G3, C4, G3, E♭3, C3

The light transparent EPRS pass was kept as a technical A/B option, not merged
into the main score-led vocal. It made a small average correction
(13.9 cents) but also detected extra low/high targets in unvoiced frames; the
raw SoulX render is the safer musical default until listening says otherwise.

## Outputs

- Raw score-conditioned sung phrase: `songs/shane-s-natural-signal/audio/soulx-singer-v1/generated/c3-eb3-g3-c4/generated.wav`
- Raw second sung phrase: `songs/shane-s-natural-signal/audio/soulx-singer-v1/generated/quiet-idea/generated.wav`
- Raw-vs-transparent A/B: `songs/shane-s-natural-signal/audio/soulx-singer-v1/generated/ab-raw-vs-eprs-transparent.wav`
- Full working mix: `songs/shane-s-natural-signal/mixes/shane-s-natural-signal-soulx-singer-score-led-mix/`

This is a private technical preview. The voice reference, Raon renders, and
SoulX outputs remain local-only; no master, upload, publication, or push was
performed.
