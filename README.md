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

EPRS lets an agent produce music across different creative tools. A prompt
becomes contrasting sketches, an authored arrangement, a reviewed master and
video, and an authorized release. Daily and on-demand runs share a small
production coordinator while native sessions and deeper tools stay available.

Start with [the producer workflow](docs/PRODUCER.md): `eprs produce brief`
suggests exploratory routes, `produce start` prevents competing runs, and
`produce advance` preserves stage evidence. Favorites provide occasional
context without defining the next song's style.

The system is designed to make it possible to ask:

- What did the agent actually change?
- Which source, seed, settings, and tool produced this result?
- Which methods were used, rejected, or never evidenced—and why?
- What remains for a human to hear, play, decide, or approve?
- Can another person or agent continue without guessing?

## Choose your path

| If you want to… | Start here |
| --- | --- |
| Produce a song daily or whenever inspiration arrives | [Agentic producer](docs/PRODUCER.md) |
| Make your first local study | [Getting started](docs/GETTING_STARTED.md) |
| Ask OpenClaw or another agent for a bounded tune | [Agentic tune walkthrough](docs/AGENTIC_TUNE.md) |
| See how the tools fit together | [Tool guide](docs/TOOLS.md) |
| Audit or contrast song-making methods | [Song method manifests](docs/SONG_METHOD_MANIFESTS.md) · [Method-space audit](docs/METHOD_AUDIT.md) |
| Browse every documentation route | [Documentation map](docs/README.md) |
| Understand the architecture and boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Inspect requests, plans, and work queues | [Agent work](docs/AGENT_WORK.md) · [Production requests](docs/PRODUCTION_REQUESTS.md) |
| Write or run BeatScript | [BeatScript](docs/BEATSCRIPT.md) |
| Use Sonic Pi | [Sonic Pi](docs/SONIC_PI.md) · [agent reference](.agents/skills/produce-music-locally/references/sonic-pi.md) |
| Record, mix, make visuals, or deliver video | [Recording](docs/RECORDING.md) · [Mixing](docs/MIXING.md) · [Pedalboard effects](docs/PEDALBOARD.md) · [Visuals](docs/VISUALS.md) · [Video](docs/VIDEO.md) |
| Prepare a public release | [Releases](docs/RELEASES.md) · [Publication](docs/PUBLICATION.md) |
| Contribute code, docs, or skills | [Contributing](CONTRIBUTING.md) · [AGENTS.md](AGENTS.md) · [.agents skills](.agents/skills/README.md) |

The short pages are entry points. They link to the longer contracts, research
notes, and implementation documents only when that detail becomes useful.

## Requirements and tested platform

**Application integrations have been tested on macOS only.** The current
working system uses an Apple Silicon Mac. Audacity, Sonic Pi, Shotcut, and
SuperCollider workflows—including app discovery and handoffs—have not been
validated on Windows or Linux. Some command-line components include Linux
installation hints, but that is not a claim that the complete app workflow has
been tested there.

Install these before using the core checkout:

| Software | Requirement | Used for |
| --- | --- | --- |
| [Git](https://git-scm.com/) | Needed for a source checkout and contribution workflow. | Clone, update, and inspect source history. |
| [uv](https://docs.astral.sh/uv/) | Required by the documented setup, test, and quality commands. | Installs the locked Python environment and runs EPRS commands reproducibly. |
| Python 3.11 or newer | Required; `uv` can install the project runtime. | EPRS command line, BeatScript rendering, manifests, planning, and release preparation. |
| [FFmpeg and FFprobe](https://ffmpeg.org/) | Required. On macOS, `brew install ffmpeg` is the usual route. | Audio/video inspection, processing, interchange, mastering, and delivery checks. |

The following software is optional. Install only the lanes you intend to use:

| Software | Install when you need… | Mac test status |
| --- | --- | --- |
| [Audacity](https://www.audacityteam.org/) | Hands-on recording, waveform editing, audition, and lossless export. | Installed and exercised on macOS; scripting is not enabled by default. |
| [Sonic Pi](https://sonic-pi.net/) | Live-coded synthesis, samples, MIDI/OSC, and bounded performance capture. | Installed and exercised on macOS. |
| [Shotcut](https://www.shotcut.org/) | Editable video timelines, captions, keyframes, MLT projects, and manual picture review. | Installed and exercised on macOS. |
| [SuperCollider](https://supercollider.github.io/) | Optional `scsynth` synthesis, granular processing, and algorithmic composition. | Installed and exercised on macOS. |
| [Node.js](https://nodejs.org/) | Remotion visuals, the visual studio dependencies, and JavaScript tests. | Installed and tested on macOS. |
| OpenCV | Optional bounded video, thumbnail, motion, and crop-quality analysis. Install with `make opencv-install`. | Installed and tested headlessly on macOS. |
| [Graphviz](https://graphviz.org/) | Optional SVG production, lineage, and arrangement maps; DOT output works without it. | Optional; not required by the tested core workflow. |

Local AI model environments are also optional and are deliberately excluded
from the base `uv sync`. Qwen3-TTS and CuteTTS have been tested locally for
consent-bound speech cloning; SoulX-Singer for score-conditioned singing;
Raon-OpenTTS as a speech control; Seed-VC for singing conversion; and ACE-Step
for a bounded music-generation experiment. These model lanes were tested on
Apple Silicon/macOS only and should be installed in ignored, isolated
`.eprs-local` environments. See [synthetic voices](docs/VOCALS.md),
[SoulX-Singer](docs/SOULX_SINGER.md), [optional AI audio](docs/AI_GENERATION.md),
and the versioned [toolchain registry](docs/TOOLCHAIN.md) before installing
weights or using a private reference recording.

After installation, use `./scripts/eprs doctor` to see which required and
optional capabilities are available on the current machine. Doctor reports
availability; it does not install software or imply that a render has passed
human listening or release review.

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
  --preserve "The unquantized guitar attack and the room decay" \
  --question "Should the groove answer every phrase or only the final one?" \
  --no-visual
```

Run the [five-minute getting-started route](docs/GETTING_STARTED.md) for the
next checks, or use `./scripts/eprs status songs/porch-signal --verify` to see what the workspace
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
