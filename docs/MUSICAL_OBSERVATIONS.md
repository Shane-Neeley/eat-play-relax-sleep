# Phrase, pitch, and pulse evidence

`eprs observe` gives an arranger a bounded first look at a supplied performance
without tuning it, quantizing it, choosing a key, or choosing a tempo:

```bash
./scripts/eprs observe /path/to/family-answer.wav \
  --song songs/signal-garden \
  --role "family answer" \
  --note "Is the last sung note a return, or does it ask the guitar for another phrase?"
```

External audio is first copied into immutable raw intake. Analysis decodes one
temporary 8 kHz mono stream in memory; it never writes processed audio. The
checksum-bound `eprs.musical-observation/v1` JSON lands in
`notes/musical-observations/<role>/`. Repeating the exact request returns the
same verified artifact instead of decoding the source again.

## What is measured

- level-defined phrase regions, meaningful quiet gaps, and four-part envelope
  profiles;
- a capped sample of periodic frames with frequency, nearest note-name, and
  confidence evidence;
- attack landmarks and half/event/double-time BPM possibilities; and
- player-language questions that keep musical interpretation with the listener.

The report always leaves `key_or_chord`, selected BPM, selected meter, and the
grid unset. A periodicity estimator works best on one sustained voice at a
time. Chords, several singers, distortion, room sound, attacks, and octave
ambiguity can all produce plausible but wrong note names. Level contrast can
also split one legato phrase or join two quiet phrases. Listen to the unchanged
source before an agent uses any landmark.

## Performance boundary

One observation is limited to 120 seconds. It uses a single 8 kHz mono decode,
10 ms level hops, 20 ms pitch hops, and at most 256 detailed pitch frames. This
keeps CPU and memory bounded even when the source is a long phone video. On the
2026-08-09 development machine, the three-second regression fixture takes
about 1.6 seconds for a fresh observation; a cache hit verifies provenance and
does not run signal analysis. `eprs status` and `eprs context` read and verify
the stored result rather than silently re-analyzing media.

For a long rehearsal, choose the musical question first:

```bash
./scripts/eprs observe /path/to/rehearsal.mov \
  --song songs/signal-garden --role "bridge guitar" \
  --start 84.2 --duration 18 \
  --note "Find the complete breath-to-decay phrase; do not assume the tapping is quarter notes."
```

This artifact is evidence for the next arrangement experiment, not a claim
that a song is in tune, in time, harmonically understood, or ready to release.

## Use one observation explicitly

Nothing consumes an observation merely because it exists. Bind it to a fresh
diagnostic arrangement deliberately:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --observation notes/musical-observations/family-answer/<id>-musical.json \
  --intent "Use one complete observed family sentence, then leave room for the guitar to reply"
```

The seed chooses one of that source's measured phrase regions, then the mix
uses its exact source start and unwarped duration. The source-sketch record,
mix score, render evidence, and agent context all retain the observation and
selected region checksums. Note-name and BPM candidates appear only as open
listening leads; they do not change pitch, timing, key, chord, tempo, or meter.
Repeat `--observation` for different captured sources. A source may have only
one observation per pass, and an observation for uncaptured audio is refused.
