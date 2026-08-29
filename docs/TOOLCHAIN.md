# Toolchain registry and environment checks

`config/toolchain.json` is the versioned source of truth for local software
that the project can use. It lets a contributor or agent teach `eprs doctor`
about a new renderer, DAW helper, command-line tool, or application without
rewriting the diagnostic code.

Run the read-only check from the repository root:

```bash
./scripts/eprs doctor
./scripts/eprs doctor --strict
./scripts/eprs doctor --workflow source-to-master --strict
./scripts/eprs doctor --workflow performed-groove-development --strict
./scripts/eprs doctor --workflow daw-handoff --strict
./scripts/eprs doctor --workflow daily-agent-work --workflow youtube-release
./scripts/eprs doctor --capability live_coding --strict
./scripts/eprs adapter list --available --capability audio_recording
./scripts/eprs adapter show sonic-pi-live-code --handoff record-lossless-stem
```

The `eprs.doctor/v1` JSON report includes resolved paths, concise version
strings, capabilities, platform applicability, and actionable installation
hints. `--strict` exits nonzero only when a required tool is unavailable;
optional creative tools remain choices. Doctor never installs, upgrades,
enables scripting, or changes system settings.

Sonic Pi's optional v5 routes are exposed separately so a plan can ask for
`live_coding`, `sample_playback`, `audio_recording`, `midi_io`,
`ableton_link`, `session_recording`, or `local_osc` without pretending that a
live GUI session is a deterministic EPRS render. See [Sonic Pi in EPRS](SONIC_PI.md)
for the version notes, gentle defaults, source map, and review checklist.

## Ask whether one workflow is ready

The registry also declares portable workflow profiles. A profile names the
capabilities a task needs, not the applications that must provide them:

- `daily-agent-work`: verified queue dispatch and checksum-bound result history;
- `performed-groove-development`: spoken/played attack observation through one
  explicit drummer-facing BeatScript audition and listening decision;
- `source-to-master`: supplied performances through reversible development and
  lossless mastering, including non-destructive two-microphone phase evidence
  and checksum-bound render-decision evidence;
- `daw-handoff`: common-start float stem interchange with measured mix
  reconstruction plus byte-preserved, disclosure-bound lossless return from
  another audio tool;
- `visual-production`: local audio analysis, promptable rendering, and
  renderer-neutral picture capture/review;
- `youtube-release`: approved master through title-card or packet-verified
  picture assembly, reviewed video and publishing assets, a rights-aware FINAL
  package, and offline publication handoff;
- `full-local-production`: the complete local prompt-and-recordings-to-YouTube
  handoff path, including visuals and recurring agent work.

`--workflow` is repeatable, so a scheduler can require only the paths a job
will use. `--capability` composes an ad hoc requirement when no named profile
fits. Add `--strict` when missing core tools or requested capabilities should
produce exit status 2.

The `eprs.doctor/v1` response keeps core and task readiness separate:

- `core_ready` covers required project tools and the Python runtime;
- `workflow_catalog` lists every profile with current readiness and missing
  capabilities;
- `requirements` records requested profiles, their combined capabilities,
  interchangeable providers, missing capabilities, and focused setup actions;
- `ok` is true only when both core and requested requirements are ready.

Doctor remains read-only. Setup actions are advice for a person or authorized
automation; they are never executed by the command.

Capability availability deliberately does not contain tool-operation advice.
Use `eprs adapter list` to match detected providers to portable handoff guides,
and `eprs adapter show <id>` for exact inputs, outputs, steps, verification,
preservation, and unsafe defaults. See [software adapter profiles](ADAPTERS.md).

## Extend one machine without editing shared configuration

Copy `templates/toolchain-extension.json` to
`.eprs-local/toolchain.json` and edit it for the installed application or
command set. The ignored `eprs.toolchain-extension/v1` file may add optional
tools and workflows. It cannot replace shared ids or declare a local tool as
required, and loading it never rewrites `config/toolchain.json`.

Source checkouts discover that file automatically. An installed package or
automation can use one or more explicit paths:

```bash
eprs doctor --extension /private/config/toolchain.json --strict
eprs adapter list \
  --toolchain-extension /private/config/toolchain.json \
  --profile-dir /private/config/adapters
```

`eprs.doctor/v1.extensions` records the exact loaded files for local audit.
Bounded agent context exposes only the resulting capability and adapter
summaries, not registry, extension, command, or application paths. The local
directory is for machine paths and private preferences, never credentials,
silent installers, network authority, or publication settings.

## Add or replace a shared tool

Each `eprs.toolchain/v1` entry declares:

- a stable `id`, human label, and one of `command-set`, `project-path`, or
  `application`;
- whether it is required for the core workflow;
- command names or candidate paths;
- capability names exposed when detection succeeds;
- optional platform limits and installation hints.

A command-set may also declare `python_modules` when availability depends on an
optional module in the active EPRS interpreter rather than on a standalone
executable. `doctor` checks those modules without importing creative code into
normal startup; this keeps lanes such as headless OpenCV discoverable while
leaving the base install small.

The top-level `workflows` array declares a stable slug, label, description, and
unique capability list. Every workflow capability must be advertised by at
least one tool entry, which catches stale or misspelled integration contracts.
Multiple tool entries may advertise the same capability. Readiness uses any
available provider, so adding a DAW bridge, renderer, or media toolkit does not
require a preference switch or changes to the workflow profile.

Use `command-set` when every named executable is needed, such as FFmpeg plus
FFprobe. Relative `project-path` entries resolve from the repository root, which
fits locally installed adapters such as Remotion. Application entries may list
several known locations and are available if any exists.

Command detection uses the system executable search path. Version inspection is
optional and runs only a single recognized read-only argument (`--version`,
`-version`, `-V`, or `version`) with a five-second timeout; absent or empty
arguments do not launch the command. Private application/project-path entries
must use absolute paths so their meaning cannot depend on the caller's working
directory.

When integrating another tool, keep the persisted song contracts independent
of it. The adapter should consume existing briefs, song-relative paths, and
versioned provenance, and should emit a new file plus evidence rather than
silently replacing source material. Add a capability name only when the
detected installation truly supports that path, then add a focused test and
usage documentation. Add the capability to a workflow only when that workflow
truly cannot operate without it; creative options should not become mandatory
just because they are installed locally.

Do not put credentials, private paths, network endpoints, or machine-specific
preferences in the shared registry. Security-sensitive features—such as
Audacity scripting or remote OSC—remain explicit user choices even when the
host application is installed.
