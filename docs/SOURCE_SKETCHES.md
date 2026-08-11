# Source-aware sketches

`eprs source-sketch` makes a reversible first arrangement from recordings that
were explicitly captured by `eprs make-song`. It is the bridge between safe raw
intake and a useful first listen; request capture by itself never starts audio
processing.

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --intent "Let the guitar invite; family voices answer after the room breathes."
```

The command binds the exact run, captured request, and immutable recording
checksums. It writes:

- an editable `eprs.mix/v1` score in `code/`;
- a stereo float diagnostic mix and provenance under `mixes/`;
- a checksummed `eprs.source-sketch/v1` record under
  `notes/source-sketches/`;
- an optional short, audio-reactive visual driven by the source-aware mix;
- an updated Graphviz production map; and
- shallow `_LISTEN.wav`, optional `_WATCH.mp4`, and `NOW.md` pointers.

The arrangement keeps each recording byte-for-byte unchanged. Role words only
guide a small set of musical choices: explicit occurrences, entrance bar,
conservative gain reduction, and narrow panning. The player's push, drag,
breath, pitch, overlap, room sound, attack, decay, drift, and noise remain
intact. Short fade-outs occur only when a one-pass source extends beyond the
diagnostic bed or an explicitly requested conversational excerpt ends.

When phrasing matters, create a bounded [musical observation](MUSICAL_OBSERVATIONS.md)
and opt it into the pass:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --observation notes/musical-observations/family-answer/<id>-musical.json \
  --intent "Use one complete observed answer and preserve its breath-to-decay boundary"
```

This chooses one measured region as an unchanged excerpt. Exact observation,
source, result, selected-region, mix-score, and render checksums remain linked.
Pitch and pulse candidates are retained as arranger questions, never automatic
key, chord, tempo, meter, tuning, quantization, or time-stretch controls.

## Explicit arrangement shapes

Prompt text never silently turns into repetition or editing. Choose the
occurrence shape directly:

- `--shape one-pass` places every captured recording once and is the default;
- `--shape call-response` requires at least two recordings, auditions each
  opening phrase in two turns four bars apart, and records that excerpting and
  repetition were explicitly requested. A rhythm/harmonic/bass source is
  preferred as the call; if every source has the same broad role, the first is
  the call and the remaining sources answer; and
- `--shape loop` repeats each complete captured phrase at the next whole-bar
  stride that can contain it. It inserts no stretch, warp, seam crossfade, or
  timing correction; a short phrase therefore leaves its natural gap before
  the next entrance.

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --shape call-response \
  --intent "Let the guitar call twice; family voices answer each turn."

./scripts/eprs source-sketch songs/signal-garden \
  --shape loop \
  --intent "Let each complete phrase recur as an ostinato without warping it."
```

Every occurrence is a separate, source-relative track in the editable mix
score. The source-sketch record groups those tracks back under the immutable
recording, exposes their bar/time positions, and states whether repetition or
excerpting was requested.

Fresh OS entropy is the default. The command compares each proposed audible
arrangement fingerprint with prior source sketches in the song and redraws a
collision, so another pass changes more than the seed. The compact history scan
does not repeatedly hash large source files; final verification still checks
the chosen pass against the actual media. Reproduce a useful pass by supplying
its recorded seed:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --intent "Let the guitar invite; family voices answer after the room breathes." \
  --seed 777
```

Use `--no-bed` to hear the source relationship without the generated starter
pocket and `--no-visual` for an audio-only pass. Neither option changes a
supplied recording.

Every pass requires a complete listen. Record that decision on its working mix:

```bash
./scripts/eprs mix-review <mix.wav> --song songs/signal-garden \
  --listening-note "The invitation and answer leave enough air." \
  --decision keep
```

`keep` means the diagnostic answered its current musical question. It is not a
master approval, rights clearance, upload authorization, or publication
authorization. See [randomness and artifact novelty](RANDOMNESS.md) for the
fingerprint scope and limits.

## A cross-tool pattern that worked: environmental call plus authored pulse

A successful local prototype paired an intact 70-second environmental
vocalization recording with a deterministic 57.6-second Sonic Pi beat, then
auditioned and refined the relationship in Audacity. The musical value came
from the contrast: freely timed calls supplied irregular living phrases and
room depth, while a restrained electronic pulse supplied a stable frame. The
calls were not useful because they had been forced onto the grid; their gaps,
timing, and environmental tail were the reason the pairing worked.

The portable EPRS version of that workflow is:

1. Capture the environmental take and authored beat as distinct recordings
   with truthful roles, provenance, permission, and rights notes.
2. Keep both raw files unchanged. Preserve the editable Sonic Pi source and its
   deterministic seed as composition evidence alongside the rendered beat.
3. Use `source-sketch --shape one-pass --no-bed` for the smallest reversible
   relationship audition, or author an `eprs.mix/v1` score when exact entrances
   and common-start placement are the musical question.
4. Do not quantize, gate, denoise, or chop the environmental calls merely to
   make them resemble percussion. Listen first for whether the stable beat
   frames the free-time phrases.
5. When Audacity or another editor should continue the balance, use an
   [interchange package](DAW_INTERCHANGE.md), preserve the native session
   separately, and capture a lossless return with declared changes and
   unknowns.
6. Record the complete-listen decision separately from technical analysis and
   from any eventual clearance or release decision.

This pattern generalizes to birds, room sound, spoken calls, playground noise,
water, machinery, or another human/environmental performance. The source role
and rights context must remain specific even when the public teaching pattern
is generic.
