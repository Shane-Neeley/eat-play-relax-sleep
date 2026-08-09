# Experiments from any creative source

An experiment asks one musical or production question and preserves exactly
what informed the answer. It does not require BeatScript, a fixed tempo, a
finished arrangement, or even an audio result.

## Freeze the material behind the question

Use a short role that says what each source contributes:

```bash
./scripts/eprs experiment \
  --song songs/signal-garden \
  --brief songs/signal-garden/briefs/v1.md \
  --source "guitar loop=songs/signal-garden/recordings/raw/guitar/<take>.wav" \
  --source "family voices=songs/signal-garden/recordings/raw/family-voices/<take>.wav" \
  --source "spoken pocket=songs/signal-garden/recordings/raw/boom-clap/<take>.m4a" \
  --source "lyric fragments=notes/lyric-fragments.txt" \
  --source "reference notes=notes/research.md" \
  --hypothesis "Can the chimes answer the family phrase while the guitar loop stays unresolved?" \
  --seed 23
```

`--source ROLE=PATH` is repeatable and accepts any file. Useful roles include a
performance function (`guitar loop`), a human source (`family voices`), an
interpretive purpose (`spoken pocket`), or an idea source (`philosophy`,
`lyrics`, `research notes`). Roles must be unique within one experiment.

`--beat` and `--brief` remain shortcuts for their common roles:

```bash
./scripts/eprs experiment \
  --song songs/signal-garden \
  --beat examples/beats/porchlight-pocket.beat \
  --brief songs/signal-garden/briefs/v1.md \
  --hypothesis "Does the second-bar answer leave room for the guitar pickup?"
```

## What gets copied

- A source already under `recordings/raw/` is immutable by project policy. The
  experiment stores its checksum and a portable path relative to the song, but
  does not duplicate the media.
- A mutable song file or a file outside the song is copied under the
  experiment's `inputs/` folder. Later edits to the original cannot silently
  change the historical experiment.
- `experiment.json` records the role, original name, storage decision, path,
  checksum, hypothesis, and deterministic seed.

New experiments use `eprs.experiment/v2`. The CLI still reads and finishes v1
experiments, so existing project history does not need an eager migration.

Completed agent research, lyric, or production work can become experiment
evidence without a manual copy-and-paste step:

```bash
./scripts/eprs work promote <work-id> \
  --song songs/signal-garden \
  --hypothesis "Do the researched call-and-response relationships leave the family performance in front?" \
  --seed 23
```

The new experiment freezes the selected work run, its request, and its local
evidence. Its `eprs.work-run-origin/v1` record maps that snapshot to experiment
input IDs, so later recurring runs cannot silently change the question being
tested. See [agent work](AGENT_WORK.md).

## Close the loop

Create the smallest audible or inspectable result that can answer the
hypothesis. Preserve human timing and roughness unless changing either one is
the explicit question. A harness or renderer may attach technical result
evidence while leaving the experiment in `rendered` state; this is explicitly
pending a real listen, not a `keep`, `change`, or `stop` decision. Then analyze
relevant technical properties and record what a listener heard:

```bash
./scripts/eprs analyze songs/signal-garden/experiments/<id>/audition.wav

./scripts/eprs finish songs/signal-garden/experiments/<id> \
  --result songs/signal-garden/experiments/<id>/audition.wav \
  --listening-note "The chime answers the breath after the phrase; the last guitar note still hangs." \
  --decision keep
```

Results outside the experiment are copied into `results/` without modifying the
source. Run `eprs status songs/<song-name>` when handing the work to another
person or agent; it flags missing input and result references. Run
`eprs status songs/<song-name> --verify` before a consequential handoff to
compare the stored checksums with every raw recording, input, and result.
