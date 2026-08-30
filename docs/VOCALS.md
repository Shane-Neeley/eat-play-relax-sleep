# Synthetic voices and audible pitch correction

Checked 2026-08-11. EPRS treats TTS and pitch correction as two different
instruments. TTS chooses a synthetic voice, words, diction, emotion, and
prosody. Autotune maps the voiced fundamental-frequency contour toward an
explicit musical note set. Keeping the stages separate lets an agent preserve
the raw cue, change the tuning without regenerating the performance, and make
an honest raw/tuned comparison.

## Mandatory voice-source policy (effective 2026-08-29)

Never use macOS `say`, Apple system TTS, or any built-in Mac voice. Samantha,
Alex, and every other bundled system voice are prohibited permanently, even as
an offline fallback. If a voice is needed, use a Hugging Face TTS/singing model
with verified code, checkpoint, license, and reproducibility, or use Shane's
explicitly authorized cloned voice kept outside the public repository. A
melodic or sung clone must pass through EPRS autotune with its key, scale,
preset, and sidecar preserved; speech cues may remain untreated when no
musical pitch treatment is intended.

Preserve raw and treated audio, model/clone provenance, hashes, version,
license, consent boundary, settings, and review. Never imitate a named artist
or claim that a clone is a performer identity. See [VOICE_POLICY.md](VOICE_POLICY.md)
for the release gate. Historical notes that mention Samantha are archival
records and are not approved implementation examples.

## What the recent Strokes record suggests

The relevant recent album is the Strokes' seventh album, *Reality Awaits*
(2026), not *The New Abnormal* (2020). Public credits identify Rick Rubin as
producer and Jason Lader as recording/mixing engineer, but no reliable source
found in this pass publishes the exact tuning plug-in, key maps, retune times,
or automation. Do not invent those settings.

What can be supported is the audible production relationship. Contemporary
reviews repeatedly describe Casablancas' processing as heavy and exposed rather
than invisible correction: “gloopy” pitch correction on “Going Shopping,” a
metallic or warbling voice across much of the album, and a deliberate collision
between synthetic vocal texture and otherwise direct rock instrumentation.
Reviews disagree sharply about whether it works. The useful production lesson
is not to copy his voice; it is to make pitch correction an authored timbral
role, use a melody strong enough to survive it, and automate or omit the effect
when intelligibility and emotional detail matter more.

Sources: [official album page](https://shop.thestrokes.com/products/reality-awaits-lp),
[Pitchfork album review](https://pitchfork.com/reviews/albums/the-strokes-reality-awaits/),
[The Guardian review](https://www.theguardian.com/music/2026/jul/24/the-strokes-reality-awaits-review),
[Le Monde review](https://www.lemonde.fr/en/culture/article/2026/07/26/the-strokes-lose-themselves-in-a-sea-of-auto-tune-on-reality-awaits_6755846_30.html),
and [Qobuz credits](https://www.qobuz.com/fr-fr/album/reality-awaits-the-strokes/vpnzte04xcv00).
These sources support the album context, credits, and broad audible character;
they do not support a claim about unpublished plug-in parameters.

## The control model

Pitch correction begins with a monophonic F0 estimate. Each voiced frame is
expressed as MIDI pitch:

```text
midi = 69 + 12 * log2(f0_hz / 440)
```

The nearest allowed note comes from the declared key and scale. EPRS then uses:

- `correction_strength`: how far the source travels toward that target. This is
  analogous to leaving some natural pitch deviation rather than forcing every
  frame to the note center.
- `retune_ms`: how quickly the correction delta responds. Zero makes an exact
  step; a slower response retains more of an attack and glide.
- `switch_hysteresis_cents`: how much better a neighboring target must become
  before the tuner switches. This prevents chatter at note boundaries.
- `minimum_note_ms`: the minimum normal target hold. Very large pitch leaps can
  still break it so a new syllable is not dragged across an old note.
- `wet`: processed/dry balance. Partial blends are intentionally phasey because
  the WORLD resynthesis is not sample-identical to the source; that can be a
  texture, but it must be auditioned in mono.
- `formant_shift_semitones`: optional movement of the resonant spectral envelope
  independent of F0. Leave it at zero for neutral identity preservation.

Fast, full-strength correction reduces portamento and vibrato into discrete
steps. Slower or partial correction retains more phrase motion. Antares' own
documentation describes Retune Speed, Flex-Tune, and Humanize as distinct
controls, while Melodyne likewise separates pitch center, modulation/vibrato,
note transitions, and formants. EPRS does not claim these controls reproduce a
proprietary algorithm; they expose the same musical decisions in a deterministic
local renderer. See the [Auto-Tune guide](https://antarestech.com/blog/pitch-correction-the-complete-guide-to-tuning-vocals),
[Auto-Tune Hybrid manual](https://antares-web-frontend.sfo3.cdn.digitaloceanspaces.com/documentation/pdfs/Auto-Tune-Hybrid-Manual.pdf),
and [Melodyne formant guide](https://helpcenter.celemony.com/M5/doc/melodyneStudio5/en/M5tour_ToolFormants?env=standAlone).

The renderer uses the open WORLD vocoder to estimate F0, spectral envelope, and
aperiodicity, replace only the voiced F0 contour, and resynthesize the cue. That
keeps pitch and formant decisions separate and makes the characteristic vocoder
edge explicit. See the [WORLD project](https://github.com/mmorise/World) and
[PyWorld wrapper](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder).

## Agent vocabulary

An agent should translate a player request into one declared preset, key/scale,
and intent. It must not infer the song key from a noisy mix and silently tune.

| Player direction | Starting preset | Relationship to audition |
| --- | --- | --- |
| “Just steady the long notes” | `transparent` | partial correction, slow response, conservative switching |
| “Lock it to the synth but keep the phrase” | `tight` | strong correction with short transitions |
| “Make every note click into the grid” | `hard-step` | full correction and zero retune time |
| “Make the voice wobble like damaged software” | `gloopy` | near-hard correction, short holds, slight formant drop, phasey wet/dry blend |

These names describe processing behavior, not a living artist. Never ask Qwen
to imitate Julian Casablancas or any other identifiable person.

## Render an existing voice

Use an isolated Python environment because PyWorld, NumPy, and SoundFile are
optional production dependencies:

```bash
python3 -m venv .eprs-local/voice-processing
# PyWorld 0.3.5 still imports pkg_resources, which setuptools 81 removed.
.eprs-local/voice-processing/bin/pip install 'setuptools<81' numpy soundfile pyworld

PYTHONPATH=src .eprs-local/voice-processing/bin/python -m eprs.cli autotune \
  songs/maybe-mode/audio/cues/maybe-cue-01.wav \
  --out songs/maybe-mode/audio/cues-tuned/maybe-cue-01.wav \
  --intent "Make the title cue click into the pentatonic synth answer." \
  --preset gloopy --key A --scale major-pentatonic
```

Or put that environment first on `PATH` and use the project front door:

```bash
PATH=.eprs-local/voice-processing/bin:$PATH ./scripts/eprs autotune ...
```

Every render refuses to overwrite its source or an existing output. It writes a
24-bit WAV plus `.wav.json` sidecar with input/output checksums, resolved
controls, voiced-frame coverage, correction distances, target notes, engine,
peak, and review warning. It does not normalize or limit.

## Generate, clone, and tune Qwen TTS in one bounded call

Qwen3-TTS supports natural-language control of timbre, emotion, and prosody;
that makes it useful for authoring the input performance before tuning. The
official [Qwen3-TTS repository](https://github.com/QwenLM/Qwen3-TTS) and
[technical report](https://arxiv.org/abs/2601.15621) document VoiceDesign,
CustomVoice, and instruction control.

```bash
PATH=.eprs-local/qwen3-tts/bin:$PATH scripts/qwen3_tts_voice.py \
  --model Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice \
  --mode custom-voice --speaker Ryan --device cpu \
  --instruct "Synthetic adult voice; compact melodic chant, long vowels, clean consonants." \
  --text "Maybe mode." --text "Still deciding." \
  --out-dir songs/maybe-mode/audio/qwen-tuned-v1 --prefix maybe \
  --autotune-preset gloopy --autotune-key A --autotune-scale major-pentatonic
```

The combined runner preserves both `*-raw-*.wav` and tuned `*.wav` cues. Its
batch manifest points to each per-cue autotune sidecar. Advanced controls remain
available through standalone `eprs autotune`, so an agent can make several
treatments from one immutable synthetic performance without rerunning TTS.

For high-fidelity cloning from Shane's explicitly authorized local reference,
use the Qwen Base checkpoint. The runner requires the exact transcript and a
consent note, withholds the private path from the manifest, verifies that the
reference checksum remains unchanged, and computes the clone prompt once for
the full bounded batch:

```bash
PATH=.eprs-local/qwen3-tts/bin:$PATH scripts/qwen3_tts_voice.py \
  --model Qwen/Qwen3-TTS-12Hz-1.7B-Base \
  --mode voice-clone --device cpu \
  --reference-audio .eprs-local/private-voice/reference-voice.wav \
  --reference-text "Exact words spoken in the reference sample." \
  --consent-note "Speaker owns this sample and authorizes this local EPRS voice test." \
  --text "Knock on the green." --text "Let the whole tree know." \
  --out-dir songs/the-listening-field/audio/qwen-clone-v1 --prefix green-voice
```

The default ICL route uses both the reference codes and speaker embedding for
better likeness. `--x-vector-only` removes the transcript requirement but is a
documented lower-fidelity fallback. Qwen cloning remains speech-first; use
SoulX-Singer or a permitted singing conversion lane when the performance must
carry authored notes and singer-like phrasing.

## Use CuteTTS for compact high-similarity clone trials

The official [CuteTTS repository](https://github.com/OPPO-Mente-Lab/CuteTTS)
publishes a 230M-parameter Apache-2.0 speech model with explicit Apple Silicon
support. It is a strong fast-control lane for Shane's consented local voice:
the EPRS runner loads the model once per bounded batch, uses a new seed for
each cue, hashes every model checkpoint and output, withholds the private
reference path, and verifies that the reference remains unchanged.

```bash
.eprs-local/cutetts-env/bin/python scripts/cutetts_voice.py \
  --model-dir .eprs-local/CuteTTS/model/CuteTTS \
  --model-revision MODEL_REVISION --code-revision CODE_REVISION \
  --reference-audio .eprs-local/private-voice/reference-voice.wav \
  --consent-note "Speaker owns this sample and authorizes this local EPRS voice test." \
  --text "Knock on the green." --text "Let the whole tree know." \
  --out-dir songs/the-listening-field/audio/cutetts-clone-v1 \
  --prefix green-voice --seed 20260830 --device mps
```

CuteTTS's current public API rebuilds reference conditioning for each cue, so
the manifest records `reference_conditioning_reused: false`; EPRS does not
claim an optimization the upstream interface cannot provide. Treat the raw
output as speech, do a level-matched blind comparison with Qwen Base, and use
the separate score-conditioned SoulX-Singer lane for authored singing. Keep
the reference, clone renders, transcript, and private manifest outside Git.

## Use Raon-OpenTTS for a consented speech voice cue

This repository is public: never check a personal reference recording, its
transcript, a cloned-voice render, or a private provenance manifest into Git.
Store the reference outside tracked files (for example under the ignored
`.eprs-local/private-voice/` directory), keep generated song workspaces under
the ignored `songs/` directory, and run the public-check before publishing.
The example below uses placeholder paths and text; replace them locally with
the speaker's exact transcript and an explicit consent note.

The official [Raon-OpenTTS-1B model card](https://huggingface.co/KRAFTON/Raon-OpenTTS-1B)
and [source repository](https://github.com/krafton-ai/Raon-OpenTTS) describe an
English zero-shot TTS model that conditions speech on a reference recording and
its exact transcript. EPRS keeps this as a separate optional adapter because
the model card is CC-BY-NC-4.0, the model renders at 16 kHz, and it is
speech-first rather than score-conditioned singing synthesis.

Prepare the official checkout, checkpoint, and 16 kHz HiFi-GAN vocoder in the
ignored `.eprs-local/raon-opentts-env` environment and the source checkout under
`.eprs-local/raon-opentts`. Then run a small, new cue batch:

```bash
PATH=.eprs-local/raon-opentts-env/bin:$PATH \
  ./scripts/eprs doctor --workflow local-reference-voice-collaboration
./scripts/raon_opentts_voice.py \
  --reference-audio .eprs-local/private-voice/reference-voice.wav \
  --reference-text "Exact words spoken in the reference sample." \
  --consent-note "Speaker owns this sample and consents to local reference-conditioned speech cues for this song." \
  --text "Maybe mode." --text "Still deciding." \
  --checkpoint .eprs-local/raon-opentts/checkpoints/1B/model_last.pt \
  --vocoder-dir .eprs-local/raon-opentts/pretrained_models/tts-hifigan-libritts-16kHz \
  --out-dir songs/maybe-mode/audio/raon-v1 \
  --prefix maybe-raon --autotune-preset tight \
  --autotune-key A --autotune-scale major-pentatonic
```

The reference stays local and is checksummed in the manifest; it is not copied
into the output directory or sent to Hugging Face. Keep the raw cue and tuned
cue separate, disclose the result as a consented synthetic/reference-conditioned
speech cue, and review the complete mix. For actual singing, record the vocal
and use the existing `eprs autotune` path, or author target notes with
[`scripts/note_aware_melody.py`](../scripts/note_aware_melody.py) before any
final pitch cleanup. Do not use Raon speech TTS or autotune as a substitute for
melody, phrasing, or a performer.

Before a pull request or release, verify both the index and the candidate file
set: `git ls-files | rg -i 'voice|reference|recordings/raw|audiosample'` should
show only generic code, tests, and documentation. Also run
`make public-check`; an ignored file is still private only while it
remains outside the staged/public file set.

## Use FireRedTTS3 as an optional remote voice-design lane

The public [FireRedTTS3 Space](https://huggingface.co/spaces/hugging-apps/firered-tts3)
exposes the Apache-2.0 FireRedTTS3 Instruct model's reference-free Voice Design
endpoint. This is useful when local model memory is tight and the cue text and
voice description are safe to send to Hugging Face. The EPRS runner does not
expose voice cloning: its default path sends no human reference recording.

```bash
PATH=.eprs-local/qwen3-tts/bin:$PATH PYTHONPATH=src \
  scripts/firered_tts3_voice.py \
  --instruct "Original adult electro-ranger voice; playful, punchy, rhythmic, no real-person imitation." \
  --text "Wild signal. Turn it up." \
  --out-dir songs/wild-signal/audio/firered-v1 --prefix wild-signal \
  --seed 20260814 --inference-cfg 1.2 --timesteps 10 \
  --autotune-preset hard-step --autotune-key E --autotune-scale minor-pentatonic
```

Each cue uses its own deterministic seed. The manifest records the Space/model,
current Space revision when retrievable, CFG, flow steps, text-normalization
choice, generated voice plan, raw/tuned checksums, and whether an `HF_TOKEN` was
used without ever storing the token. A 429 is surfaced once and is not retried in
a loop. Remote render success is still not a listening, rights, release, or
publication approval; disclose the synthetic voice in upload metadata.

## Try Bark for less robotic hook vocals

For fast experiments where the request is "make it feel more like a singer,"
EPRS can use Hugging Face `suno/bark-small` as a lightweight performance-voice
source before autotune:

```bash
PATH=.eprs-local/qwen3-tts/bin:$PATH PYTHONPATH=src scripts/bark_singer_voice.py \
  --model suno/bark-small --voice-preset v2/en_speaker_6 --device cpu \
  --text "Wake up, eat up, play, relax, sleep. Gorilla schedule with a banger beat." \
  --out-dir songs/gorilla-schedule/audio/bark-singer-v1 --prefix gorilla-singer \
  --autotune-preset tight --autotune-key C --autotune-scale minor-pentatonic
```

Bark is not a score-conditioned singing synthesizer, so use it for short hooks
and chants rather than long lyric sheets. Preserve its raw cue, tuned cue, and
manifest exactly like the Qwen path. Do not prompt it to imitate a real singer.

## Listening rules

Speech-first TTS is not a singing synthesizer. A short cue with sustained vowels
usually tunes more coherently than a paragraph of conversational speech. Check
the sidecar's `voiced_ratio`; low coverage means the pitch system had little
harmonic material to control. Then compare raw and tuned cues at matched level:

1. Are the words and final consonants still clear?
2. Does the target scale agree with the bass and stressed melody notes?
3. Do note changes feel intentional instead of chattering?
4. Does the formant setting preserve the intended character?
5. Does the wet/dry blend hollow out in mono?
6. Does the effect earn its place in this phrase, or should the next phrase be raw?

Keep the raw cue, tuned cue, sidecar, exact TTS manifest, arrangement source,
and complete listening render. Technical success is not creative approval or
release clearance.

## Note-aware singing and field-call melodies

The failure mode behind weak earlier autotune passes was architectural: EPRS
was asking a speech-first TTS cue to become a singer after it had already been
rendered. WORLD can correct the F0 frames it finds, but it cannot invent a
stable held note, a new syllable boundary, or a musical phrase envelope.

For a phrase that must sing, render short vowel-led cues, author the target
MIDI note and hold length in the arrangement, then run:

```bash
PATH=.eprs-local/qwen3-tts/bin:$PATH \
  .eprs-local/qwen3-tts/bin/python scripts/note_aware_melody.py \
  --item "audio/qwen/raw-ah.wav|auto|69|2.0|8.0|-3" \
  --item "audio/qwen/raw-oh.wav|auto|72|1.5|10.0|-3" \
  --out audio/vocal-melody.wav \
  --manifest audio/vocal-melody.wav.json \
  --total-seconds 24
```

The renderer estimates `auto` source pitch, uses Rubber Band R3 with formant
preservation for the declared shift, stretches to the declared duration, and
places the note on a timeline with tiny anti-click fades. It works for voice,
birds, frogs, cats, or any other monophonic field cue; the input source and its
license/provenance remain immutable. It is a composition stage, not a claim
that an animal recording contains a human-intended melody.

Use `eprs autotune` after this stage only when the result needs a light final
scale cleanup. Do not use autotune as the primary note generator for a speech
paragraph. The better long-term singing candidates remain score-conditioned
singing models such as [SoulX-Singer](https://huggingface.co/Soul-AILab/SoulX-Singer)
and singing voice conversion such as [so-vits-svc](https://github.com/svc-develop-team/so-vits-svc);
they need a separate hardware, model-license, and reproducibility evaluation.
