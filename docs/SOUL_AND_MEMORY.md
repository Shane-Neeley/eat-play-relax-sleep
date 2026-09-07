# SOUL and musical memory

SOUL.md gives the producer confidence, curiosity, care, and artistic judgment.
AGENTS.md gives the production contract. The current user request supplies the
song's intent. Inspirations are headspace, not compulsory musical content.

## What actually loads

`eprs context` embeds a fresh `producer_context` with the actual SOUL text,
SHA-256, origin, and bounded musical-memory previews. Markdown includes the
same record. Dispatch calls that builder; the runner freezes the dispatch
packet before invoking its agent, rejecting missing or checksum-invalid SOUL
snapshots (legacy packets need fresh dispatch). Delegates therefore receive the identity
without depending on their host recognizing the filename.

`produce brief` includes identity and project musical memory. `produce start`
freezes identity and song memory in the claimed run. `make-song` captures it
before selecting/rendering a starter, embeds it in the agent brief and run
manifest. Read a fresh context before each subsequent creative revision;
retained run snapshots describe history and do not silently change with SOUL.

The bootstrap has its own explicit budget: 16,384 bytes for SOUL and 4,096
bytes each for project and song memory (at most 24,576 text bytes). It is
separate from `context --max-text-bytes`, so evidence cannot crowd SOUL out
and SOUL cannot consume the current request's preview budget. Empty/missing
identity fails; oversized identity asks for distillation rather than silently
cutting its meaning. Memory truncation is marked; hashes describe full files.
Installed distributions carry SOUL and AGENTS under `share/eprs`.

Low-level BeatScript, Sonic Pi, SuperCollider, synthesis, and audio processing
execute authored material; they do not reason over prose. The identity belongs
at the producer/authoring boundary, including manual score authoring under
AGENTS.md. The deterministic starter's notes/seed are not changed by the
inspiration text. A snapshot proves context delivery, not musical influence or
quality. External callers bypassing EPRS handoffs must explicitly load SOUL.
Never paste the inspiration lyrics into a generative audio service's prompt.

## Musical memory without another database

Reuse song `notes/musical-memory.md` as a compact, curated notebook. Keep raw
history in existing run notes, experiments, comparisons, reviews, and manifests;
context already retrieves those typed records. Use repository
`notes/musical-memory.md` only for deliberately curated, shareable lessons.
Never harvest private OpenClaw/Hermes/Codex home memory into a music packet.

After comparing actual alternatives, record:

- Intent and the musical question being tested.
- Alternatives and artifact paths, with review method and reviewer.
- Decision and what the evidence supports; distinguish listening from analysis.
- A conditional lesson, counterexample, uncertainty, and next experiment.

For example, a hypothesis might be “try a bass rest before the call”; it is
not an established preference until supported by an actual comparison. Keep
failed approaches so the next session avoids repeating them. Supersede stale
lessons explicitly. Do not turn a single liked song into a genre mandate.
A new song may have no memory; do not invent prior listening. This bounded
curation is more useful here than installing another retrieval service.

## Research basis (2026-09-06)

[OpenClaw system-prompt source](https://github.com/openclaw/openclaw/blob/main/src/agents/system-prompt.ts)
orders context files and `buildProjectContextSection` labels SOUL as persona,
then inserts file contents. [Workspace loading](https://github.com/openclaw/openclaw/blob/main/src/agents/workspace.ts)
and [prompt documentation](https://docs.openclaw.ai/concepts/system-prompt)
show why filename existence alone is insufficient: runtime collection,
bootstrap limits, and harness/session filtering control delivery. Current docs
say subagents inject only AGENTS.md. EPRS passes SOUL explicitly to avoid this.

[OpenClaw memory](https://docs.openclaw.ai/concepts/memory) uses durable Markdown
and retrieval; writing a lesson and retrieving it are separate actions.
[Hermes's file map](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/which-file-does-what.md)
separates identity from project instructions and memory, including a frozen
session-start memory snapshot. EPRS uses run snapshots plus fresh contexts.

[Codex AGENTS.md guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
documents explicit project instruction discovery. Do not assume Codex reads a
neighboring SOUL automatically; AGENTS and the packet explicitly connect it.

“Grokbot” is ambiguous: searches returned multiple unrelated implementations.
[This community GrokBot project](https://github.com/Franzferdinan51/GrokBot)
describes Markdown identity plus curated/retrieved memory, but is not evidence
of the proprietary Grok Bot runtime. No Grok Bot internals are assumed here.

The musical benefit is a design hypothesis: stable headspace, remembered
failed attempts, and conditional lessons may improve continuity without
homogenizing songs. Listening comparisons must establish any actual benefit.

## Verification for this integration

The full suite ran 386 Python tests successfully (10 environment-related skips)
and five JavaScript tests passed. After the final handoff-format adjustment,
27 targeted context, harness, runner, and SOUL tests passed. Ruff, the configured
ty checks, public-repository checks, and `git diff --check` passed.
The actual `produce brief` command returned the current SOUL checksum and loaded
project musical memory. Harness tests rendered starter audio and checked saved
identity; no new human listening or musical-quality result is claimed.

Changed integration files: `src/eprs/soul.py`, `context.py`, `harness.py`,
`producer.py`, `runner.py`, `pyproject.toml`, `AGENTS.md`, `SOUL.md`, this document,
and `docs/PRODUCER.md`; regression coverage is in `tests/test_soul.py` and
`tests/test_harness.py`. The initial curated `notes/musical-memory.md` remains
local under the repository's existing notes ignore rule. Existing unrelated
working-tree edits were preserved. No live OpenClaw config was changed and no
gateway restart was needed.
