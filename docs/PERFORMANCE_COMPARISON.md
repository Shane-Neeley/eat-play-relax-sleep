# Compare performances without choosing by meter

Two takes can differ in timing, breath, attack, dynamics, room response, and
phrase intention without either being “more correct.” `eprs compare` builds a
listening worksheet from two to twelve song-relative recordings. It never
aligns waveforms, scores timing as error, or declares a winner.

```bash
cp templates/performance-compare.json \
  songs/signal-garden/code/guitar-takes.json
# Point each take at immutable intake, choose comparable listening regions,
# and write questions that matter to the song.
scripts/eprs compare songs/signal-garden/code/guitar-takes.json \
  --song songs/signal-garden
```

The `eprs.performance-compare/v1` worksheet requires a player-facing intent,
non-empty listening questions, and an ID, role, path, and optional performance
note for each take. Regions may differ in length and position, but each is
limited to two minutes so one report remains useful to audition.

The `eprs.performance-comparison/v1` report records source checksums and:

- quiet, median, and strong frame levels—not a quality score;
- performed attack landmarks, spacing variability, and cautious timbre hints;
- a four-part envelope profile with an explicitly inferential phrase-shape hint;
- pairwise differences expressed as right-minus-left measurements; and
- both forward and reverse audition orders to reduce first-take bias.

Listen at a sensible matched level and answer the declared questions. Loudness
is not quality, and a measurement cannot tell whether a hesitation feels
vulnerable, uncertain, funny, spacious, or wrong. Record a role for every take:

```bash
scripts/eprs compare-review notes/comparisons/guitar-answer-takes/<report>.json \
  --song songs/signal-garden --take guitar-take-one --decision keep \
  --listening-note "The gathering motion sets up the family entrance."

scripts/eprs compare-review notes/comparisons/guitar-answer-takes/<report>.json \
  --song songs/signal-garden --take guitar-take-two --decision alternate \
  --listening-note "The extra air may suit the quiet arrangement."
```

`keep` means carry this performance forward, `alternate` preserves a meaningful
creative fork, and `stop` means this take need not drive the next experiment.
None deletes or edits audio. Review refuses missing or checksum-changed sources,
and `status --verify` reports incomplete worksheets or evidence drift.
