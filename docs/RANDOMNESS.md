# Randomness and artifact novelty

EPRS uses randomness to propose alternatives, not to hide decisions. A fresh
agent-led pass records its seed, creative fingerprint, comparison scope, and
collision count so the result can be diagnosed. Supplying that seed explicitly
allows an exact replay.

## What a fresh pass guarantees

`make-song` and `source-sketch` use OS entropy when `--seed` is omitted. Before
writing a new pass, each command compares the proposed artifact with the
fingerprints recorded in that song:

- `make-song` fingerprints the audible BeatScript structure: tempo, meter,
  resolution, bar count, swing, and every track's kind, steps, and options. It
  excludes the title and seed, so a new number alone cannot satisfy novelty.
- `source-sketch` fingerprints the arrangement shape, starter-bed checksum,
  immutable source checksums, relationship roles, and every occurrence's
  start, duration, gain, and pan. It excludes labels, prose intent, and seed.

If a proposal matches prior song history, the command draws again. It tries at
most 1,024 candidates and fails before creating request, score, or media
artifacts if none is new. `NOW.md` and the run record show how many prior
fingerprints were checked and how many collisions were rejected.

The source-sketch history scan validates compact fields already bound into its
checksummed manifest. It does not reread and rehash every large recording on
every retry. The final sketch verifier still checks the selected pass against
the real source and bed files.

## Replay and limits

Passing `--seed` deliberately disables the fresh-artifact gate. This makes
diagnosis and exact replay possible, including an intentional duplicate. The
mode is recorded as `explicit-replay` and surfaced in `NOW.md`.

The guarantee is song-local and depends on retaining that song's manifests and
creative files. Older records that predate creative fingerprints may not
participate. It is not a global uniqueness, originality, rights, or copyright
claim. Two different fingerprints can still sound related, and randomness is
not a substitute for taste. Listening review and keep/change/stop decisions
remain required.

Use fresh mode to explore another answer. Use an explicit seed when comparing,
debugging, or deliberately rebuilding the same answer.
