# Synthetic voices and audible pitch correction

Checked 2026-08-11. EPRS treats TTS and pitch correction as two different
instruments. TTS chooses a synthetic voice, words, diction, emotion, and
prosody. Autotune maps the voiced fundamental-frequency contour toward an
explicit musical note set. Keeping the stages separate lets an agent preserve
the raw cue, change the tuning without regenerating the performance, and make
an honest raw/tuned comparison.

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

## Generate and tune Qwen TTS in one bounded call

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
