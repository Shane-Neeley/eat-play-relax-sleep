# Getting started with EPRS

EPRS is easiest to understand by making one small, inspectable thing. The
first run creates a song workspace and a diagnostic audition; it does not
pretend that a render is a finished or approved song.

## 1. Install and check the local toolchain

From the repository root:

```bash
uv sync --locked --dev
./scripts/eprs doctor
```

The toolchain registry reports what is available without installing apps or
reading credentials. Machine-specific paths belong in the ignored
`.eprs-local/` directory.

## 2. Open the Beat Lab

```bash
make studio
```

Open <http://localhost:8000>. Beat Lab is a browser-first way to hear a
pattern, mutate it, and copy its portable BeatScript source. For the language
and headless rendering path, see [BeatScript](BEATSCRIPT.md).

## 3. Make one song workspace

Start from a player-facing brief. Classify every supplied file explicitly as a
recording, evidence, or reference:

```bash
./scripts/eprs make-song "Signal Garden" \
  --prompt "A loose guitar invitation answered by a warm, slightly crooked groove" \
  --preserve "the room sound and the breath before the answer" \
  --avoid "automatic tuning and quantization" \
  --question "Does the answer feel like a reply rather than a repeated loop?"
```

If you have local material, add it explicitly:

```bash
./scripts/eprs make-song "Signal Garden" \
  --prompt "A loose guitar invitation answered by a warm, slightly crooked groove" \
  --recording "guitar=/absolute/path/to/guitar.wav" \
  --evidence "lyric fragments=/absolute/path/to/lyrics.txt" \
  --reference "https://example.com/a-research-lead" \
  --preserve "the room sound and the breath before the answer" \
  --avoid "automatic tuning and quantization"
```

Never infer rights, consent, or permission from possession of a file. Raw
recordings are copied into an immutable intake area; transformations go to new
song-relative paths.

## 4. Inspect the handoff

```bash
sed -n '1,220p' songs/signal-garden/NOW.md
./scripts/eprs status songs/signal-garden --verify
```

`NOW.md` is the shallow recovery point. It points to the latest request,
inputs, route hints, source, audition, visual preview, and next decision.
`status --verify` checks the recorded evidence for drift.

## 5. Continue one bounded step

For a request-bound agent handoff:

```bash
./scripts/eprs context songs/signal-garden --verify --format markdown
./scripts/eprs dispatch next --song songs/signal-garden --agent AGENT_NAME
```

For a performed recording, make the first source-aware audition before
replacing the performance:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --shape call-response \
  --intent "Let the guitar invite; let the programmed part answer after the room breathes."
```

Listen end to end and record a keep/change/stop decision. A technical render is
not a creative approval.

## Where to go next

- Want the OpenClaw version? Read [Ask an agent for a tune](AGENTIC_TUNE.md).
- Want coded rhythm? Read [Sonic Pi in EPRS](SONIC_PI.md) or
  [BeatScript](BEATSCRIPT.md).
- Want to record or edit a human performance? Read [Recording](RECORDING.md)
  and [Source-aware sketches](SOURCE_SKETCHES.md).
- Want a finished video? Follow [Video delivery](VIDEO.md), [picture review](PICTURE.md),
  [YouTube assets](YOUTUBE_ASSETS.md), and [release packages](RELEASES.md).
- Want the whole documentation map? Open [docs/README.md](README.md).
