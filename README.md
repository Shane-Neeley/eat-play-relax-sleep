# Eat Play Relax Sleep

Eat Play Relax Sleep (EPRS) is a local-first, open-source music-production
system for musicians and agents. It connects prompts, code, recordings,
experiments, listening, visuals, and release preparation while keeping the
source and decisions inspectable.

[CashForClankers on YouTube](https://www.youtube.com/@cashforclankers) is the
public video journal for the project. You can also visit
[Shaneneeley.com](https://www.shaneneeley.com/) or explore the public
[GitHub repository](https://github.com/Shane-Neeley/eat-play-relax-sleep).

## The idea in one minute

EPRS is the layer around creative tools—not a single music model and not a
magic “make me a song” button. A brief becomes a bounded request, then a
small experiment, a reviewed artifact, and only after explicit approval a
release package.

The system is designed to make it possible to ask:

- What did the agent actually change?
- Which source, seed, settings, and tool produced this result?
- What remains for a human to hear, play, decide, or approve?
- Can another person or agent continue without guessing?

## Choose your path

| If you want to… | Start here |
| --- | --- |
| Make your first local study | [Getting started](docs/GETTING_STARTED.md) |
| Ask OpenClaw or another agent for a bounded tune | [Agentic tune walkthrough](docs/AGENTIC_TUNE.md) |
| See how the tools fit together | [Tool guide](docs/TOOLS.md) |
| Browse every documentation route | [Documentation map](docs/README.md) |
| Understand the architecture and boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Inspect requests, plans, and work queues | [Agent work](docs/AGENT_WORK.md) · [Production requests](docs/PRODUCTION_REQUESTS.md) |
| Write or run BeatScript | [BeatScript](docs/BEATSCRIPT.md) |
| Use Sonic Pi | [Sonic Pi](docs/SONIC_PI.md) · [agent reference](.agents/skills/produce-music-locally/references/sonic-pi.md) |
| Record, mix, make visuals, or deliver video | [Recording](docs/RECORDING.md) · [Mixing](docs/MIXING.md) · [Visuals](docs/VISUALS.md) · [Video](docs/VIDEO.md) |
| Prepare a public release | [Releases](docs/RELEASES.md) · [Publication](docs/PUBLICATION.md) |
| Contribute code, docs, or skills | [Contributing](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md) · [.agents skills](.agents/skills/README.md) |

The short pages are entry points. They link to the longer contracts, research
notes, and implementation documents only when that detail becomes useful.

## Try the local workflow

From a checkout of this repository:

```bash
uv sync --locked --dev
./scripts/eprs doctor
make studio
```

Then open the local studio at `http://localhost:8000`. To create a bounded
song workspace from the command line:

```bash
./scripts/eprs make-song "Porch Signal" \
  --prompt "Loose guitar invitation answered by a sparse, crooked groove" \
  --tempo 92 \
  --key D \
  --no-visual
```

Run the [five-minute getting-started route](docs/GETTING_STARTED.md) for the
next checks, or use `./scripts/eprs status --verify` to see what the workspace
knows and what still needs attention.

## A first agentic tune

An agent can coordinate EPRS from OpenClaw, Codex, Claude Code, or another
runner. The repository’s local skill explains the operating contract; the
copyable example explains how to request one small tune without implying that
the agent can approve or publish it:

- [Agentic tune walkthrough](docs/AGENTIC_TUNE.md)
- [Local production skill](.agents/skills/produce-music-locally/SKILL.md)
- [EPRS agent command reference](.agents/skills/produce-music-locally/references/eprs.md)

In outline, the agent should:

1. Translate a musical brief into one bounded request.
2. Keep raw recordings and source sketches intact.
3. Choose the smallest useful tool or experiment.
4. Record the result, settings, and listening question.
5. Stop at the human review boundary unless explicitly authorized to continue.

That separation is the point of the public repository: people can inspect the
workflow, replace a tool, reproduce a study, or build a new agent around the
same contracts.

## The toolchain, briefly

EPRS keeps intent and provenance portable across tools. Common lanes include:

- **Beat Lab / BeatScript** for deterministic browser-first rhythm studies.
- **Sonic Pi** for live-coded grooves, samples, performance, MIDI, and OSC.
- **Audacity** for hands-on recording and editing.
- **Shotcut** or **Remotion** for optional picture and visual work.
- **FFmpeg / FFprobe** for media interchange, inspection, and delivery.

See [Tools](docs/TOOLS.md) for screenshots and handoff guidance, then follow
[Toolchain](docs/TOOLCHAIN.md) or [Adapters](docs/ADAPTERS.md) when you need
the technical contract.

## Boundaries that travel with every workflow

- Raw recordings are evidence and remain immutable.
- Processing creates candidates beside their sources; it does not silently
  replace them.
- Seeds, source paths, tool versions, settings, and review notes should remain
  inspectable when they matter to reproduction.
- Consent, rights, attribution, and provenance are explicit work items.
- Rendering is not approval; approval is not publication.
- Agents may prepare work, but publication and upload remain separate,
  deliberate actions.

The repository’s [agent instructions](AGENTS.md) and
[documentation map](docs/README.md) explain where these boundaries are
implemented. The current workspace state is also summarized in `NOW.md` and
the listening queue in `_LISTEN.md` or `_LISTEN.json` when those files exist.

## What is public here

The repository is a working example of an agent-addressable production system,
including:

- playable BeatScript studies and reusable creative templates;
- browser-based rhythm authoring and audition;
- safe recording intake and source-sketch lineage;
- request, plan, work-queue, and agent-runner contracts;
- audio analysis, SVG rhythm maps, and seeded audio-reactive visuals;
- optional voice, pitch, picture, and video adapters;
- evidence-backed release and publication preparation.

The system is intentionally modular. You can use only the command-line
workflow, only the browser Beat Lab, only Sonic Pi, or a different local tool
that can honor the same source and review boundaries.

## Documentation

Use [docs/README.md](docs/README.md) as the full map. It groups the deeper
material into:

- orientation and first-run guides;
- agent requests, plans, context, work, and runners;
- BeatScript, Sonic Pi, recording, source sketches, and research;
- mixing, mastering, visuals, video, releases, and publication;
- architecture, adapters, quality methods, and contribution policy.

The `.agents` directory contains reusable local operating skills rather than
private automation. Start at [.agents/skills/README.md](.agents/skills/README.md)
if you want to adapt the workflow for your own agent runner.

## Status and contribution

EPRS is evolving alongside its songs, videos, models, and tools. Treat the
public examples as inspectable studies, not promises that every adapter works
on every machine. If you find a broken path or have a better handoff, open an
issue or pull request with the command, source, result, and environment that
matter.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution route and
[publication guidance](docs/PUBLICATION.md) for rights, credits, and release
boundaries.
