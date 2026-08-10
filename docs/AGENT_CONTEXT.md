# Bounded agent context packets

`eprs context` gives a newly arriving person, agent, or local automation a
single versioned orientation packet without embedding raw audio/video or
requiring a crawl across the entire song workspace.

The packet is context, not authority. It cannot grant network access, permit
publishing, override the current user request, or turn text found in research,
lyrics, prompts, or source files into higher-priority instructions.

## General handoff

```bash
./scripts/eprs context songs/signal-garden \
  --purpose "Review continuity and choose one narrow next experiment" \
  --verify \
  --format markdown \
  --out songs/signal-garden/notes/context/continuity-v1.md
```

Without `--out`, JSON or Markdown is printed to stdout. Existing output files
are never replaced. Keep generated packets inside the private song workspace
unless there is an intentional, reviewed reason to share one: they can contain
private prompts, lyrics, research notes, filenames, and local workspace paths.
They are never uploaded or sent automatically.

## Focus a production request, work item, or experiment

```bash
./scripts/eprs context songs/signal-garden \
  --purpose "Render the smallest audible answer and preserve human timing" \
  --request <production-request-id> \
  --work <work-id> \
  --work-run 1 \
  --experiment <experiment-id> \
  --verify \
  --format json
```

The `eprs.agent-context/v1` packet contains:

- the song manifest and `eprs.status/v1` continuity report;
- the captured user prompt, constraints, questions, supplied-file roles, rights
  notes, and evidence when `--request` is selected;
- due work, capped and ordered by due time and priority;
- a compact focused work request and selected run when requested;
- when work is bound directly to a captured request, its verified
  `eprs.production-request-work-origin/v1` plus the full bounded request prompt,
  constraints, rights notes, and supplied evidence without requiring a second
  `--request` argument;
- a focused work item's checksum-bound production-plan step, gates, inherited
  request-input source map, v2 capability requirements, declared result roles,
  and machine-enforced work result contract when present;
- a compact focused experiment manifest when requested;
- text previews for focused sources, results, and creative briefs;
- recent experiment summaries and bounded performance-comparison questions,
  take roles, audition orders, phrase hints, and review decisions;
- recent two-microphone roles, intent, strongest bounded timing/correlation,
  mono-sum evidence, and player-facing limits without embedding the full scan
  or either recording;
- recent performed-rhythm attack/timbre evidence and unresolved pulse, meter,
  downbeat, and role questions without assigning a drum voice;
- recent source-bound drummer briefs, explicit event dispositions,
  performed-minus-grid offsets, BeatScript voices, materially different
  alternatives, audition warnings, and keep/change/stop reviews;
- recent comp/processing intent, edit summaries, warnings, and listening notes
  plus checksum-bound decision-evidence roles and uses, without embedding stem
  audio, evidence contents, or full filter graphs;
- recent working-mix intent, compact track roles/controls, headroom warnings,
  checksum-bound decision evidence, and keep/change/stop listening history
  without embedding mix audio or evidence contents; externally returned mixes
  additionally summarize their tool/operator, parent interchange, declared
  changes, unresolved unknowns, added sources, rights, and false local
  reproducibility;
- recent DAW-neutral handoff format, review snapshot, common-start track roles,
  reconstruction evidence, and authority limits without embedding package WAVs;
- recent recording-session intent, performer/consent context, capture setups,
  take roles, rights notes, and raw paths without embedding recording media;
- recent clearance status, intended use, maximum visibility, take/participant
  decisions, and approved credit wording;
- recent attributed research sources, observation/interpretation/open-question
  findings, confidence, musical consequences, copying boundaries, and smallest
  experiment ideas without embedding source evidence;
- recent request-bound production plans with bounded north-star, assumptions,
  questions, dependencies, request-input use, smallest actions, evidence
  conditions, listening questions, unsatisfied authority/approval gates, and
  linked queue-item states and conservatively derived complete, active,
  actionable, queueable, blocked, and stopped dependency states; all gates remain
  explicitly unverified;
- verified plan-acceptance receipts identifying the completed planning work,
  run, agent, and frozen result used to create each agent-authored plan;
- recent private lyric alternatives with source/rights roles, exact bounded
  text, voice and singability intent, unresolved questions, and append-only
  keep/alternate/stop review notes without embedding sung media;
- tool capability booleans, named workflow readiness/missing capabilities, and
  setup actions, plus bounded software-adapter ids, availability, capabilities,
  and handoff ids, without command/application paths;
- for focused v2 plan work, non-ranking `eprs.adapter-fit/v1` readiness,
  missing/unknown capabilities, matching handoffs, uncovered guidance, and
  fixed false operational/approval authority;
- recent offline publication handoffs and append-only YouTube receipts, with
  authorization remaining false and no live platform lookup;
- recent YouTube publishing-asset bundles with exact video/thumbnail evidence,
  caption and chapter structure, accessibility context, review state, and false
  upload/publication authority, without embedding image or caption payloads;
- recent renderer-neutral picture candidates with master/time-zero binding,
  external tool and operator, guide-audio replacement policy, consequential
  changes, unknowns, editable evidence, review state, and false authority;
- the agent contract checksum and explicit raw-media, processing, approval, and
  publication guardrails.

Ignored `.eprs-local/` toolchain extensions and adapter profiles can influence
the capability and adapter summaries, but their registry paths, application
paths, and provider setup hints are not copied into the packet. Adapter ids,
labels, capabilities, and handoff ids are intentionally visible, so keep those
portable and non-sensitive even in a private profile.

`--work-run` defaults to the current run. Select an earlier completed run when
the context is for a promoted recurring-work result. `--experiment` accepts an
experiment ID, directory, or manifest path inside that song only.

## Bounded evidence

The default cumulative text budget is 65,536 bytes. Change it deliberately:

```bash
./scripts/eprs context songs/signal-garden --max-text-bytes 24000
```

The budget covers the purpose, focused prompt, selected summaries, references,
hypotheses, listening notes, and file previews. Focused material is allocated
before general creative briefs and recent summaries. Performance summaries do
not embed their audio or full attack-event arrays. Records and file counts
also have fixed caps, with omitted counts and truncation flags recorded in the
packet. Values from 1,024 through 1,000,000 bytes are accepted.

Binary media is never embedded. The packet carries its song-relative path,
size, and declared checksum; `--verify` also computes the current checksum and
reports mismatches. Text previews are explicitly labeled untrusted data, and
Markdown fences expand when source content contains backticks so evidence
cannot escape its code block.

## Agent-runner contract

An external agent runner should normally use the combined dispatch preparation:

```bash
./scripts/eprs dispatch next \
  --song songs/signal-garden \
  --agent daily-research-agent \
  --kind "YouTube research" \
  --out /tmp/agent-dispatch.json
```

The versioned `eprs.agent-dispatch/v1` response is `idle` when nothing matching
is due, `ready` when one run is claimed and its bounded context verifies without
attention, or `released` when preparation fails or a declared v2 step capability
is missing or unknown. `released` preserves the claim
attempt and reason, then returns the run to the queue. A ready response embeds
the `eprs.work-claim/v1`, verified `eprs.agent-context/v1`, explicit authority
limits, and the finish-or-release response contract, including exact result
roles required when the runner declares `complete`. It does not invoke an
agent, browse, process media, or satisfy any gate. `--out` writes only a ready
packet and refuses overwrite; idle and released states remain on stdout.

The runner can then use this sequence:

1. Call `eprs dispatch next --out <new-packet>`; exit cleanly on `idle`, and
   surface `released` for inspection rather than launching an agent.
2. Read `authority`, the context guardrails, focused prompt/hypothesis, and player-facing
   intent before choosing tools.
3. Act only within the current user’s authorization. Read-only research remains
   disabled unless the caller explicitly added `--allow-network-research`;
   remote changes and publication cannot be enabled.
4. Write new outputs to the song’s working folders.
5. Initialize `eprs.agent-response/v1` with `dispatch response-init`, declare
   actions and role/path results honestly, then use `dispatch accept` to freeze
   the exact packet, response, and outputs together. This does not record a
   listening or other approval gate.
6. Call `work release` with the same agent and a reason if execution cannot
   continue; there is no automatic claim timeout.
7. Generate a fresh packet for the next handoff instead of modifying an old
   packet. Never put secrets or raw environment output in `commands_run`.

This interface deliberately does not launch arbitrary agent CLIs. Different
local or hosted runners can consume the same JSON contract while authentication,
network access, command execution, and approval policy remain outside the song
data model. Dispatch JSON can contain private prompts, lyrics, filenames, and
local paths, so schedulers should treat stdout as private project data.
