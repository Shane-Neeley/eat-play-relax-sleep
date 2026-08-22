# EPRS documentation

This is the long-form map for [Eat Play Relax Sleep](../README.md). The root
README is intentionally short: it explains the project and sends each reader
to one useful next place.

## Start here

- [Getting started](GETTING_STARTED.md) — install the project, open Beat Lab,
  make the first song workspace, and understand the next safe action.
- [Ask an agent for a tune](AGENTIC_TUNE.md) — a copyable OpenClaw-style
  orchestration prompt plus the bounded EPRS commands it can call.
- [See the tools](TOOLS.md) — screenshots, roles, and handoff boundaries for
  BeatScript, Sonic Pi, Audacity, Shotcut, Remotion, and FFmpeg.

## Agent and orchestration layer

Read these when the work is being planned, delegated, or resumed by an agent:

- [Production requests](PRODUCTION_REQUESTS.md) — capture prompts, files,
  references, rights notes, and input routes.
- [Production plans](PRODUCTION_PLANS.md) — freeze a dependency-aware roadmap
  without silently executing it.
- [Bounded agent context](AGENT_CONTEXT.md) — prepare a verified handoff for a
  person, agent, or automation.
- [Agent work queue](AGENT_WORK.md) — claim, finish, release, and promote
  request-bound work.
- [Isolated agent runners](AGENT_RUNNERS.md) — packet/response execution with
  OS isolation and receipts.
- [Graphify](GRAPHIFY.md) — navigate code and document relationships when the
  repository graph exists.

The project-local agent skills live in
[`.agents/skills/`](../.agents/skills/README.md). Start with
[`produce-music-locally`](../.agents/skills/produce-music-locally/SKILL.md),
then read its [EPRS reference](../.agents/skills/produce-music-locally/references/eprs.md)
or [Sonic Pi reference](../.agents/skills/produce-music-locally/references/sonic-pi.md)
only when that route is relevant.

## Creative lanes

- [BeatScript](BEATSCRIPT.md) — compact, deterministic rhythm sources.
- [Sonic Pi in EPRS](SONIC_PI.md) — live-coded synthesis, sampling, cues, and
  bounded lossless auditions.
- [Recording](RECORDING.md) — human-operated capture and safe intake.
- [Source-aware sketches](SOURCE_SKETCHES.md) — the first reversible
  arrangement around a preserved performance.
- [Rhythm and musical observations](RHYTHM.md) and
  [groove development](GROOVE.md) — evidence before grid decisions.
- [Lyrics](LYRICS.md), [vocals](VOCALS.md), and [processing](PROCESSING.md) —
  source-bound writing and reversible sound work.
- [iNaturalist media](ANIMAL_SOUND_AI_2026.md) — attributed organism sound and
  photo references with release boundaries.

## Arrangement, picture, and release

- [Mixing](MIXING.md), [mastering](MASTERING.md), and
  [DAW interchange](DAW_INTERCHANGE.md) — editable audio and external-tool
  handoffs.
- [Visuals](VISUALS.md), [picture handoff](PICTURE.md), and
  [Shotcut](SHOTCUT.md) — renderer-neutral picture work.
- [Video delivery](VIDEO.md) and [YouTube assets](YOUTUBE_ASSETS.md) — assemble
  and review a listening video without publishing it.
- [Release packages](RELEASES.md) and [publication](PUBLICATION.md) — rights,
  credits, checksums, offline upload inputs, and append-only receipts.
- [Distribution](DISTRIBUTION.md) — distributor-ready handoffs for streaming
  services; no account or upload authority is hidden here.

## Architecture, policy, and research

- [Architecture](ARCHITECTURE.md) — why intent, evidence, lineage, and review
  stay separate from the creative tool.
- [Toolchain registry](TOOLCHAIN.md) and [adapter profiles](ADAPTERS.md) —
  capability discovery without machine-specific credentials or paths.
- [Randomness](RANDOMNESS.md), [experiments](EXPERIMENTS.md), and
  [evidence bindings](EVIDENCE_BINDINGS.md) — replayability without turning
  creative work into a fixed vending machine.
- [Quality gaps](QUALITY_GAPS.md), [research](RESEARCH.md), and
  [visual methods](VISUAL_METHODS.md) — current evidence and unresolved work.
- [Contributing](../CONTRIBUTING.md) and the root [agent contract](../AGENTS.md)
  — public contribution rules and non-negotiable safety boundaries.

## How to use this map

Start shallow, follow one route, and return to the song's `NOW.md` or
`_LISTEN.*` handoff before opening another branch. A document can explain a
capability; it does not grant permission to browse, process, upload, publish,
or claim a creative decision.
