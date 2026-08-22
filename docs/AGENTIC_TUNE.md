# Ask an agent for a tune

This is a copyable orchestration pattern for OpenClaw, Codex, Claude Code, or
another local agent. The coordinator can call the EPRS CLI, but EPRS remains
the system of record for intent, source preservation, evidence, reviews, and
release gates.

There is no hidden native OpenClaw integration in this repository. Treat the
agent prompt as a contract for what the coordinator may do, then keep the
result in the song workspace.

## Give the agent a bounded brief

```text
Work in /path/to/eat-play-relax-sleep.

Use EPRS to make a 12-bar instrumental called “Porch Signal”: a loose guitar
invitation answered by a sparse, slightly crooked groove. Prefer Sonic Pi for
the coded bed if it is available; BeatScript is the deterministic fallback.

Preserve the breath before the answer and leave room for a human guitar take.
Do not quantize, tune, normalize, compress, publish, upload, or touch any file
under songs/*/recordings/raw/. Do not claim that a render is approved.

Return the exact song-relative paths for the source, rendered experiment,
production map, and next human listening question.
```

The important parts are the player-facing idea, what must survive, what must be
avoided, and the exact continuation evidence—not the agent's choice of model.

## Let EPRS create the first bounded pass

```bash
./scripts/eprs make-song "Porch Signal" \
  --prompt "A loose guitar invitation answered by a sparse, slightly crooked 12-bar groove" \
  --preserve "the breath before the answer and room for a human guitar take" \
  --avoid "quantization, tuning, normalization, compression, and publication" \
  --question "Does the answer feel like a reply rather than a repeated loop?" \
  --no-visual

./scripts/eprs status songs/porch-signal --verify
./scripts/eprs source-sketch songs/porch-signal \
  --shape call-response \
  --intent "Let the guitar invite; let the coded bed answer after the room breathes."
```

`make-song` captures the brief, creates the workspace, and makes a diagnostic
audition. `source-sketch` is the next source-aware arrangement step when a
recording is present. Neither command approves, uploads, or publishes.

## Queue one agent-owned work item

Use a queue when the agent should return a frozen result instead of continuing
through the whole song in one process:

```bash
./scripts/eprs work add --song songs/porch-signal \
  --title "Write the Sonic Pi bed" \
  --kind "bounded coded groove experiment" \
  --prompt "Write a finite, seeded 12-bar Sonic Pi bed that leaves a pickup-sized gap for guitar" \
  --require-result sonic-pi-source \
  --require-result listening-note

./scripts/eprs work claim-next \
  --song songs/porch-signal \
  --agent openclaw
```

The completed work should return the editable source, rendered candidate,
technical checks, what was heard or watched, and a keep/change/stop decision.
If the agent cannot listen, it should leave a concrete listening question
instead of converting measurements into approval.

## Keep the tool handoff explicit

When Sonic Pi fits, save a finite, seeded `.rb` source and capture a bounded
lossless audition. Sonic Pi's Run button proves code executed; it does not by
itself prove that the audio is useful or approved. Read [Sonic Pi in EPRS](SONIC_PI.md)
and the project-local [Sonic Pi skill reference](../.agents/skills/produce-music-locally/references/sonic-pi.md).

For a different lane, let the prompt route to the smallest fitting tool:

- performed audio → recording intake, rhythm evidence, source sketch, listen;
- coded rhythm → BeatScript or Sonic Pi source, bounded render, listen;
- picture → visual score or editor handoff, picture review, sync check;
- release → approved master/video, rights and credits, package, then separate
  publication authorization.

The [project-local music skill](../.agents/skills/produce-music-locally/SKILL.md)
contains the agent-facing continuation loop; [docs/README.md](README.md) maps
the deeper human-facing workflows.
