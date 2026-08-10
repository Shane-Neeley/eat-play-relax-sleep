# Architecture

Eat Play Relax Sleep separates intent, irreversible sources, reproducible experiments, and delivery artifacts.

```text
captured prompt + supplied files
      │
      └── request-origin planning work ── authored production plan ── plan-step work

creative brief
      │
      ├── BeatScript / Sonic Pi / DAW / live performance
      │          │
      │          └── experiment manifest ── listening decision ── next experiment
      │
source recordings (immutable + checksummed)
      │
      ├── explicit source sketch ── editable mix score ── float diagnostic mix ── listening decision
      ├── rhythm observation ── authored drummer brief + grid interpretation ── reviewed audition
      │
      └── selected takes ── explicit comp ── explicit processing ── reviewed stems ── mix
                                                                                         ├── common-start DAW interchange
                                                                                         └── lossless master ── delivery copies ── FINAL/
```

A captured production request can precede the brief: it binds the user's prompt,
preservation constraints, questions, references, permission notes, and mixed
supplied files before any agent chooses a representation or experiment.

## Why the layers are orthogonal

- **Intent is not implementation.** A brief can survive a move from BeatScript to Sonic Pi, Audacity, a DAW, or live musicians.
- **A source is not an edit.** Raw takes retain evidentiary and emotional value even when a later edit changes.
- **An experiment is not a song version.** It answers a narrow question with frozen inputs and a decision; promoted results become part of the song.
- **A master is not a platform file.** The editable/lossless truth stays independent of YouTube's current encoding requirements.
- **A working output is not a handoff.** `FINAL/` contains only approved, verified copies; their editable sources remain in the working folders.
- **Measurements are not taste.** Checksums, loudness, peaks, and sync catch errors; listening notes decide whether the music works.

## Components

- `src/eprs`: standard-library Python core; no network and no runtime packages.
- `config/toolchain.json`: versioned, portable detection and capability records
  for required and optional software. `eprs.doctor/v1` resolves it without
  installing or enabling anything. Provider-neutral workflow profiles compose
  capabilities for task-specific readiness, allowing a new compatible adapter
  to replace an older tool without changing song contracts.
- `config/adapters/*.json`: drop-in `eprs.software-adapter/v1` handoff guides
  linked to toolchain providers. They describe inputs, outputs, operation
  boundaries, preservation, and verification without starting applications or
  storing application state in song contracts. `eprs.adapter-catalog/v1` and
  `eprs.adapter-guide/v1` expose installed matches without detected paths.
- `.eprs-local/`: ignored, additive `eprs.toolchain-extension/v1` providers and
  private adapter profiles for machine-specific software. Local ids cannot
  shadow shared contracts, local tools cannot become core requirements, and
  agent context exposes outcomes rather than private configuration paths.
- `eprs status`: read-only continuity layer for humans and agents; it inventories
  a song, validates referenced evidence, optionally verifies checksums, and
  exposes versioned `eprs.status/v1` JSON.
- `eprs.performance/v1`: a read-only diagnostic over EPRS-owned visual render
  and isolated agent-runner processes plus optional recent song receipts. It
  distinguishes active work from stale orphaned Chromium roots and reports
  elapsed time, CPU, memory, render timing, runner deadline/cleanup/isolation,
  capped-log, raw-integrity, and response evidence without stopping processes
  or granting operational authority.
- Fresh `make-song` and `source-sketch` passes compare artifact-level creative
  fingerprints against song-local history before writing a candidate. The
  seed, scope, and collision count remain visible; explicit seeds permit exact
  replay. Source history uses manifest-bound compact fields so large recordings
  are not rehashed for every candidate. See `docs/RANDOMNESS.md`.
- `eprs.agent-context/v1`: a bounded, read-only handoff view over song status,
  due work, focused production-request/work/experiment evidence, creative
  briefs, recent request, production-plan, research, lyric variants, experiment,
  performance-comparison, comp, and processing decisions,
  available capability booleans, and concise software-adapter ids/handoffs. It
  embeds no binary media, marks previews as untrusted data, and never expands
  authorization or invokes an agent.
- `eprs.production-request/v1`: the user's prompt, intended experience,
  preserve/avoid constraints, questions, deliverables, references, and declared
  supplied files. `eprs.production-request-record/v1` preserves recordings in
  raw intake and freezes other evidence under one atomic request directory.
  JSON `request add` and direct prompt-and-files `request capture` share the
  same validator and record contract. The record adds a non-executing
  `input_routes` index derived from declared handling, role words, and filename
  extension so agents can quickly route performances, rhythm ideas, lyrics,
  pictures, notation, documents, and research leads without content inference.
- `eprs.source-sketch/v1`: an explicit continuation from one exact agent-led
  run and captured request. It classifies supplied recordings only to choose
  seeded entrances, conservative no-boost gain, and narrow pan; writes an
  editable `eprs.mix/v1` score and float diagnostic mix; preserves every source
  checksum; optionally renders a source-synced visual; and updates the shallow
  listening handoff and Graphviz production map. It never tunes, quantizes,
  denoises, normalizes, compresses, limits, time-stretches, approves, or
  publishes the performance.
- `eprs.production-plan/v1` and `/v2`: immutable, request-checksum-bound dependency
  graph with a north star, assumptions, open questions, request-input use,
  smallest actions, output/evidence conditions, listening questions, and
  explicit consent/rights/review/upload/publication gates. V2 additionally
  freezes exact per-step required capability slugs and optional required result
  role slugs. Its deterministic
  record can supersede an older plan for the same request, but cannot execute a
  step, track completion, or satisfy any gate.
- `eprs.production-plan-acceptance/v1`: append-only proof that one exact frozen
  result from a completed request-origin agent run validated as a v2 plan for
  the same captured request. It binds work, agent, result, plan, and checksums
  without changing plan identity, executing a step, or satisfying a gate.
- `eprs.production-plan-progress/v1`: a read-only projection over a verified
  plan and its checksum-bound plan-step work. Completed decisions unblock
  dependencies; active follow-up and stopped work do not overstate completion.
  Consent, rights, listening, technical, upload, and publication gates always
  remain unverified in this projection.
- `eprs.production-plan-queue/v1`: one lock-protected preparation transaction
  that selects at most one unstarted dependency-ready step and creates its
  checksum-bound work item. Repeated calls do not duplicate active work, and
  invalid queue evidence is refused. It neither executes work nor verifies a
  declared plan gate.
- `eprs.recording-session/v1`: a DAW-neutral capture-day declaration with
  player-facing intent, time/tuning/room context, pseudonymous participant
  roles, explicit consent notes, arbitrary microphone/recorder setups, and
  take-to-person/setup relationships. `eprs.recording-session-record/v1`
  deterministically binds every take and its immutable raw provenance without
  assuming a grid, processing chain, public credit, or publication permission.
- `eprs.recording-clearance/v1`: one exact recording-session subset, intended
  use, maximum visibility, take rights decisions, participant consent decisions,
  and named/collective/anonymous/no-credit choices. Its immutable record binds
  the session checksum; pending and declined records remain evidence but cannot
  satisfy a release gate.
- `eprs.audio-lineage/v1`: a checksum-verified traversal from master through
  mix, comp, processing, and selection provenance to immutable raw takes. Known
  derived schemas are followed; authored leaves remain explicit and unguessed.
- `eprs.experiment/v2`: role-labeled inputs from any file-based creative source.
  Mutable or external sources are frozen as experiment copies; immutable raw
  intake stays deduplicated as a song-relative, checksummed reference.
- `eprs.work-item/v1`: a song-scoped research, writing, production, or recurring
  automation request with its original prompt, frozen inputs, claim state,
  numbered runs, decisions, and checksummed results. `eprs.work-list/v1` is the
  compact due-work interface for people and external agent runners; it is not a
  background scheduler or a permission boundary.
- `eprs.work-result-contract/v1`: optional exact role-labeled evidence required
  before a work run may record `decision=complete`. Validation happens before
  output copying or queue mutation, permits additional results, and does not
  satisfy content, listening, technical, consent, rights, or publication gates.
- `eprs.production-request-work-origin/v1`: a checksum-bound bridge from one
  captured prompt and all its supplied inputs into an agent work item. Focused
  context expands the exact bounded request automatically so an agent can
  author a plan without the core inventing creative steps or retyping sources.
- `eprs.production-plan-step-origin/v1` and `/v2`: checksum-bound bridges from one exact
  production-plan step and its captured-request inputs into a work item. Raw
  input remains referenced, other evidence is frozen, and the plan, request,
  step, gates, and source map remain inspectable across claims and runs. V2
  also preserves the plan step's capability and result-role requirements.
- `eprs.work-claim/v1`: the result of an atomic due-work selection. A queue lock
  serializes selection, an item lock serializes ownership changes, and explicit
  release records failed/restarted attempts without lease-based claim stealing.
- `eprs.agent-dispatch/v1`: a scheduler-facing preparation transaction over one
  claim and checksum-verified bounded context. It returns idle, agent-ready, or
  explicitly released state; a failed preparation records its attempt instead
  of silently stranding ownership. It does not execute work, invoke an agent,
  or satisfy plan gates. Network research remains false unless the caller
  explicitly records narrow read-only permission; publication is never granted.
- `eprs.agent-response/v1`: a packet-checksum-, work-checksum-, run-, and
  owner-bound return from an external agent runner. The accept transaction
  verifies its declared actions and required result roles, refuses authority or
  evidence drift, and freezes the packet, response, and results in one work run.
  Read-only research must be explicitly enabled on the packet; raw mutation,
  remote changes, sending, upload, and publication remain forbidden.
- `eprs.runner-profile/v1`: a private, shell-free executable and literal
  argument contract for the packet/response file protocol. Only packet,
  response, and workspace placeholders are allowed; mandatory automatic OS
  isolation and hard network denial cannot be weakened by a profile.
- `eprs.agent-runner-execution/v1`: a song-local receipt over one staged
  profile and dispatch packet, mandatory sandbox provider, writable workspace,
  deadline, process group, bounded stdout/stderr, raw before/after integrity,
  accepted response, and failure release. It proves an execution boundary, not
  taste, consent, rights, approval, upload, or publication.
- `eprs.adapter-fit/v1`: a focused, non-ranking projection of declared
  plan-step capabilities onto current doctor results and all matching adapter
  handoffs. It separates software readiness from guide coverage and carries
  fixed false operational and publication authority.
- `eprs.work-run-origin/v1`: the self-contained bridge from one completed work
  run to `eprs.experiment/v2`. It maps a frozen request snapshot, original work
  sources, and selected run results to experiment input IDs without coupling
  that experiment to future recurring runs.
- `eprs.completed-work-origin/v1`: the reusable request/run/results provenance
  snapshot used by research, lyric development, and future non-experiment
  artifacts. It verifies the selected completed run and its evidence while
  allowing a recurring work item to append unrelated later runs.
- `eprs.research/v1`: attributed source metadata, direct observations,
  interpretations, open questions, confidence, musical consequences, explicit
  copying boundaries, and smallest original experiment ideas. The deterministic
  `eprs.research-record/v1` optionally binds a completed work run and freezes
  explicitly supplied local evidence; it never browses or downloads sources.
- `eprs.lyrics/v1`: source- and optional completed-work-bound lyric alternatives
  with intent, voice, preserve/avoid boundaries, exact text, singability notes,
  and unresolved questions. `eprs.lyric-development/v1` preserves raw sources
  by reference, freezes other evidence, and appends per-variant
  keep/alternate/stop reviews without rewriting or automatically selecting text.
- `eprs.audio-selection/v1`: a non-destructive trim/repeat recipe, its immutable
  source checksum, explicit seam treatment, lossless working render, and output
  checksum. It is an adapter contract rather than an FFmpeg-specific database.
- `eprs.rhythm-observation/v2`: performed attack timestamps, level and timbre
  hints, interval evidence, pulse ambiguity, player-facing language, and
  explicit interpretation limits plus a result ID binding those measurements.
  It remains separate from quantized notation; the verifier accepts legacy v1
  observations, while new groove development requires result-bound v2 evidence.
- `eprs.musical-observation/v1`: one bounded, source-checksum-bound set of
  level-defined phrase regions, quiet gaps, capped monophonic periodicity
  candidates, and multiple optional pulse readings. It explicitly leaves key,
  chord, tempo, meter, grid, tuning, and phrase meaning unresolved, and lets
  status/context verify stored evidence without re-running analysis.
- `eprs.groove/v1`: one explicit, observation-checksum-bound drummer-facing
  interpretation. It requires meter/tempo relationship, subdivision and feel,
  backbeat/answer, low voice, timekeeping, dynamics, orchestration, phrase,
  pocket, preserve/avoid boundaries, alternatives, and an explicit disposition
  for every observed attack. `eprs.groove-development/v1` preserves each
  performed-minus-nominal-grid offset, a deterministic BeatScript score and
  synthesized audition, warnings, keep/change/stop listening history, and false
  authority flags. It never edits the performance or claims automatic role
  assignment, transcription, quantization, creative approval, or publication.
- `eprs.phase-observation/v1`: a recipe-derived, checksum-bound observation of
  one explicit two-microphone region. It records bounded offset correlation,
  mono-sum level evidence, ambiguity and player-facing limits, while explicitly
  recording that no delay, polarity inversion, audio render, or source change
  occurred.
- `eprs.evidence-binding/v1`: a reusable, bounded song-local reference that
  records the exact checksum, role, and recipe-specific use of an observation,
  research record, session record, comparison, or listening note. Process and
  mix recipe IDs include these optional bindings; review and mastering refuse
  drift without treating evidence as authority.
- `eprs.performance-compare/v1`: two to twelve source-bound takes, musical
  questions, and listening regions. `eprs.performance-comparison/v1` stores
  non-ranking landmarks, envelope, spacing, counterbalanced audition, and
  keep/alternate/stop evidence without aligning waveforms.
- `eprs.comp/v1`: ordered source regions and explicit player-intended cut,
  silence, or crossfade boundaries. `eprs.comp-render/v1` binds every source,
  edit, format conversion, float working stem, measurement, safety invariant,
  and keep/change/stop review without corrective processing.
- `eprs.process/v1`: one source and an ordered, player-intended operation chain.
  `eprs.process-render/v1` binds the immutable source checksum, resolved filter
  controls, float working stem, safety invariants, measurements, warnings, and
  keep/change/stop listening history. It never grants implicit processing.
- `eprs.mix/v1`: a human- and agent-editable arrangement score with musical
  intent, source-relative timeline placement, trims, explicit gains, conservative
  balance/pan, and fades. `eprs.mix-render/v1` preserves its resolved source
  checksums, filter graph, float render, measurements, headroom warnings, and
  keep/change/stop complete-listen history. Mastering accepts only an exact,
  checksum-verified kept mix and binds its approval sidecar checksum.
- `eprs.daw-interchange/v1`: a self-contained, recipe-derived snapshot of one
  verified working mix as common-start stereo float WAV stems, an exact
  reference-mix copy, provenance snapshot, import guidance, and decoded-sample
  reconstruction evidence. It carries review state but grants no approval,
  FINAL promotion, upload, or publication authority.
- `eprs.daw-return/v1`: a disclosure contract for one lossless mix returned
  from an exact interchange package, including external tool/session identity,
  operator, musical changes, known settings or explicit unknowns, rights, and
  any newly added song-local sources. `eprs.daw-return-mix/v1` preserves the
  returned bytes unchanged, binds the parent package and original mix, marks
  external reproducibility false, and reuses the ordinary mix review and
  mastering gates without granting authority.
- `eprs.master/v1`: destination intent, one approved mix source, explicit gain,
  a refusal-only true-peak ceiling, and a declared 24-bit output. The
  `eprs.master-render/v1` sidecar separates technical success, creative
  listen-through approval, FINAL promotion, and publication.
- `eprs.youtube/v1`: title-card intent, an approved lossless-master reference,
  and explicit delivery dimensions/frame rate. `eprs.youtube-render/v1` binds
  the MP4 to the master and its approval provenance, records codec/color/fast-
  start verification, and keeps visual review, FINAL promotion, upload, and
  publication separate.
- `eprs.picture/v1`: a renderer-neutral declaration for finished picture,
  approved-master/time-zero relationship, guide-audio replacement policy,
  tool/version/session/operator, visual changes, unknowns, editable evidence,
  and rights. `eprs.picture-candidate/v1` preserves picture/evidence bytes and
  requires an independent keep/change/stop complete-picture review.
- `eprs.youtube/v2`: a reviewed picture candidate plus its exact approved
  master. Assembly discards guide audio, packet-verifies picture stream copy,
  packet-verifies AAC against a temporary master-only reference, and emits
  `eprs.youtube-render/v2` for the ordinary final sync-review gate.
- `eprs.youtube-assets/v1`: an approved-video reference, unchanged thumbnail
  source, explicit alt text, authored caption cues, authored chapters, and an
  accessibility note. `eprs.youtube-assets-bundle/v1` freezes a platform-rule
  check date, generated plain UTF-8 SubRip and chapter files, checksums, and a
  separate editorial/accessibility review while keeping upload authority false.
- `eprs.release/v1`: approved master/video selection, credits, rights note, and
  proposed platform metadata plus recording-clearance references. Release
  traces every known raw source, requires exact session/take/participant
  clearance at or above proposed visibility, verifies approved credit wording,
  and copies clearance/session evidence into `FINAL/`.
  `eprs.release-package/v1` atomically freezes verified copies; upload and
  publication remain false.
- `eprs.youtube-publication-handoff/v1`: a deterministic offline adapter
  contract binding one verified FINAL manifest, exact video bytes, uploader
  metadata, and maximum intended visibility. Its upload/publication authority
  remains false and it never contacts a platform.
- `eprs.youtube-publication-receipt-record/v1`: append-only caller-declared
  YouTube state bound back through the handoff to FINAL. It prevents visibility
  broadening and accidental second platform IDs, while leaving the immutable
  release's local publication flags unchanged.
- `scripts/eprs`: repository-local launcher.
- `.beat`: a compact rhythm-and-note language designed for humans and agents to read together.
- `studio`: browser Beat Lab using Web Audio; it teaches pulse, density, swing, and pattern relationships without installation.
- `songs`: self-contained, private-by-default local song workspaces ignored by Git.
- `songs/<name>/FINAL`: the single obvious local handoff folder for approved deliverables.
- `examples`: small, deliberately reviewed and publishable teaching artifacts.
- `templates`: high-level briefs and experiment records.
- `.agents/skills`: project-local reusable operating skills.

## Evolution model

Schemas carry names and versions (`eprs.song/v1`, `eprs.experiment/v2`). Readers
continue to accept experiment v1; add readers or migrations before changing
persisted meaning again. Keep adapters thin. A new DAW, model, visualization,
or synthesis engine should consume the same briefs, manifests, and recording
provenance rather than becoming the new database.
