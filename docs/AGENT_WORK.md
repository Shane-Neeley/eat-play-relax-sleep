# Agent work queue and recurring requests

The work queue captures requests that inform music but are not themselves an
audio experiment: research a band or performance tradition, develop lyric
fragments, inspect YouTube references, prepare credits, summarize new project
evidence, or run a recurring continuity check.

It is song-scoped and local. It does not browse, invoke an agent, schedule a
background process, upload, or publish by itself. A person, agent runner, or
external scheduler can ask for due work and then explicitly claim one item.

## Add a request

```bash
./scripts/eprs work add \
  --song songs/signal-garden \
  --title "Research family call-and-response" \
  --kind "YouTube research" \
  --prompt "Find three performance relationships we can discuss without copying an arrangement; preserve source links and distinguish observation from inference." \
  --priority 80 \
  --reference "family group singing" \
  --reference "room chimes" \
  --source "lyric fragments=notes/porch-light-fragments.txt"
```

Kinds are open musical language rather than a fixed taxonomy. Useful values
include `research`, `YouTube research`, `lyrics`, `production`, `credits`, and
`automation`. References are leads such as names, philosophies, URLs, or search
phrases. Local `--source ROLE=PATH` inputs are frozen into the work item; an
immutable raw recording is referenced by song-relative path and checksum rather
than duplicated.

Each request uses `eprs.work-item/v1` under:

```text
songs/<song>/notes/work/<timestamp>-<title>/work.json
```

The original prompt and inputs remain intact across every run.

## Queue the captured request for agent planning

After direct or JSON request intake, queue the exact request without retyping
its prompt or manually copying its supplied files:

```bash
./scripts/eprs work add \
  --song songs/signal-garden \
  --request <captured-request-id> \
  --priority 80
./scripts/eprs dispatch next \
  --song songs/signal-garden \
  --agent planning-agent
```

With no title, kind, or prompt overrides, this creates one `production planning`
task asking the agent to author an `eprs.production-plan/v2` as frozen result
evidence. Its work result contract requires the role `production-plan` before
`decision=complete` is accepted. It does not generate the plan itself. The work item stores
`eprs.production-request-work-origin/v1`, binding the exact request path,
checksum, ID, and complete request-input source map. Immutable recordings remain
song references; other request evidence is checksummed into the work item.

Focused context and dispatch automatically include both the work request and
the full bounded captured request, including prompt, intended experience,
preserve/avoid constraints, questions, deliverables, references, rights notes,
and evidence previews. Loading refuses changed request provenance. Custom
`--title`, `--kind`, or `--prompt` values can narrow the request-bound task, but
cannot change its origin. A customized request-bound task does not assume its
result is a plan; add one or more `--require-result <portable-role-slug>`
options when it needs an explicit completion contract. `--request` cannot be combined with `--plan` and
`--plan-step`.

The agent returns a plan JSON file through normal `work finish --result`. After
review, accept the exact frozen result without locating or copying it manually:

```bash
./scripts/eprs plan accept-work <work-id> \
  --song songs/signal-garden \
  --result production-plan
```

`--result` is optional when the completed run has exactly one result. Acceptance
requires a `complete` run, request-origin work, a valid
`eprs.production-plan/v2`, unchanged result evidence, and the same captured
request that originated the work. It creates or reuses the deterministic plan
and writes an append-only `eprs.production-plan-acceptance/v1` receipt binding
the plan checksum, completed run, agent, request origin, and selected result.
It rejects ambiguous, v1, wrong-request, drifted, or incomplete results before
creating a plan. Planning work and acceptance do not execute the plan or satisfy
any gate.

Inspect that provenance later with:

```bash
./scripts/eprs plan acceptances <plan-id> --song songs/signal-garden
./scripts/eprs plan acceptance-show <acceptance-id> --song songs/signal-garden
```

When the song has an `eprs.production-plan-record/v1` or `/v2`, create a queue item from
one exact step instead of retyping its intent:

```bash
./scripts/eprs work add \
  --song songs/signal-garden \
  --plan <plan-directory> \
  --plan-step research-relationships \
  --priority 80
```

The step supplies default title, kind, and prompt; its `uses` request inputs are
carried into the work item with immutable-raw deduplication and checksum-bound
copies. Optional overrides can narrow the work but cannot change the frozen
`eprs.production-plan-step-origin/v1` or `/v2` or satisfy its gates. Plan and step must
always be supplied together.

## List and claim due work

```bash
./scripts/eprs work list --song songs/signal-garden
./scripts/eprs work list --song songs/signal-garden --due
./scripts/eprs work show <work-id> --song songs/signal-garden
./scripts/eprs work start <work-id> --song songs/signal-garden --agent research-agent
```

`work list` emits versioned `eprs.work-list/v1` JSON ordered by due time and
priority. An exclusive local lock protects `start` and `finish`, so two agent
processes cannot knowingly claim or update the same run at once. A stale lock
is never deleted silently; inspect the item and the named lock before removing
one left by a crashed process.

For a daily scheduler or a pool of agents, select and claim in one atomic
operation:

```bash
./scripts/eprs work claim-next \
  --song songs/signal-garden \
  --agent daily-research-agent \
  --kind "YouTube research"
```

The `eprs.work-claim/v1` response contains either one `claimed` item or
`"claimed": null` when nothing matching is due. `--kind` is an optional exact,
case-insensitive filter. Due time is ordered first, then higher priority, then
stable item ID. A queue-wide lock protects selection while the item lock
protects ownership, so cooperating runners cannot claim the same queued run.
Invalid or temporarily locked candidates are reported under `errors`; another
valid due item may still be claimed.

For automation, prefer the combined verified dispatch preparation over
hand-stitching claim and context calls:

```bash
./scripts/eprs dispatch next \
  --song songs/signal-garden \
  --agent daily-research-agent \
  --kind "YouTube research"
```

`eprs.agent-dispatch/v1` has three terminal preparation states:

- `idle`: no matching due work was claimed;
- `ready`: the item remains owned by the named agent and the response contains
  checksum-verified, bounded `eprs.agent-context/v1` plus a finish/release
  response contract;
- `released`: context preparation failed or reported attention, so the claim
  attempt and reason were preserved and the run was returned to the queue.

For v2 plan-step work, dispatch also evaluates the exact declared capabilities.
It releases the claim when a capability is missing or unknown. Capability
readiness can come from multiple providers; no adapter is ranked or selected.
If the capability is available but no adapter handoff guide covers it, dispatch
may remain ready and the context reports that guidance gap for explicit handling.

The command prints the bundle and does not write a potentially private context
file. It does not launch an agent, browse, enable network access, process audio,
upload, publish, or satisfy a production-plan gate. The scheduler still decides
whether and how to invoke an agent within current user authorization.

## Exact packet and response protocol

For a local Codex, Claude, Gemini, or another explicitly operated runner, write
the ready bundle to a new file instead of scraping terminal output:

```bash
./scripts/eprs dispatch next \
  --song songs/signal-garden \
  --agent local-codex-runner \
  --out /tmp/signal-garden-dispatch.json

./scripts/eprs dispatch response-init \
  --packet /tmp/signal-garden-dispatch.json \
  --out /tmp/signal-garden-response.json
```

`--out` writes only a `ready` packet and refuses overwrite. `idle` and
`released` states stay on stdout. The packet contains the verified bounded
context, exact work checksum, owner, run, required result roles, action limits,
and response schema. `response-init` fills the packet checksum and exact claim
coordinates; the runner fills the summary, decision, action report, and
role/path results.

By default the packet does not permit browsing. For a research task whose
current caller explicitly authorizes read-only web research, record that narrow
permission when claiming it:

```bash
./scripts/eprs dispatch next \
  --song songs/signal-garden \
  --agent research-agent \
  --kind "YouTube research" \
  --allow-network-research \
  --out /tmp/signal-garden-research-dispatch.json
```

This never permits login changes, posting, sending, remote mutation, upload, or
publication. There is deliberately no corresponding publication flag.

After the runner creates every declared result and honestly completes the
action report, accept it through the exact packet:

```bash
./scripts/eprs dispatch accept /tmp/signal-garden-response.json \
  --packet /tmp/signal-garden-dispatch.json \
  --song songs/signal-garden
```

Acceptance refuses packet/response/claim/work checksum drift, a different
agent or run, undeclared network access, any reported raw-recording mutation,
remote change, upload/publication/send, duplicate or reserved roles, missing
files, and missing required result roles. It then freezes the exact dispatch
packet, response audit, and result files together in the numbered work run.
Technical acceptance never becomes a listening, rights, consent, creative,
mix, master, upload, or publication approval. If a runner cannot provide a
valid response, release the claim explicitly rather than editing the packet.

When work comes from a production plan, `eprs plan queue-next` can prepare one
unstarted dependency-ready step before dispatch. It holds the same queue lock,
inherits exact plan/request evidence, and never queues more than one step per
call. It does not claim the new work or verify the step's declared gates.

There are no automatic claim timeouts. A slow listen, render, recording session,
or research pass must not be stolen because a generic lease expired. If a
runner cannot continue, the owning agent explicitly returns the run:

```bash
./scripts/eprs work release <work-id> \
  --song songs/signal-garden \
  --agent daily-research-agent \
  --note "Local browser session ended before source verification completed."
```

Release requires the current owner and a non-empty reason. It preserves the
claim time, release time, and note, then returns the same run to `queued` state.
Repeating the same release is idempotent. A later agent appends a new claim
attempt instead of erasing the previous one; successful completion records
which claim produced the frozen results.

## Finish with inspectable evidence

Write the result as a normal local artifact. Research should use an
`eprs.research/v1` spec so links, access dates, attribution, confidence,
observation versus interpretation, musical consequences, and copying boundaries
can become a verified record. Lyrics should keep meaningful variants rather
than silently collapsing them into one “best” answer. Prefer an
`eprs.lyrics/v1` result so sources, exact alternatives, singability questions,
and later keep/alternate/stop notes remain machine-verifiable; see [source-bound
lyric development](LYRICS.md).

```bash
cp templates/research.json /tmp/call-and-response-research.json
# Fill the spec and set its optional work.item/run origin, then freeze it:
./scripts/eprs work finish <work-id> \
  --song songs/signal-garden \
  --summary "Captured three attributed performance relationships and two experiment ideas." \
  --decision complete \
  --result "research spec=/tmp/call-and-response-research.json"

# Normalize the attributed findings as a song research record.
./scripts/eprs research add /tmp/call-and-response-research.json \
  --song songs/signal-garden
```

Every result is copied under the numbered run and checksummed. Later edits to
the source result cannot rewrite queue history. Use multiple `--result`
arguments for notes, lyric variants, code, images, or media that belong to the
same run.

Use repeatable `--require-result <portable-role-slug>` at creation time when
`complete` must mean that specific evidence returned. A v2 plan step's
`required_result_roles` supplies that contract automatically and cannot be
overridden with a different CLI list. Dispatch exposes the exact required
roles. `work finish --decision complete` validates them before creating a run
directory or changing work state; ordinary extra roles remain allowed.
`needs-followup` and `stop` can still preserve diagnostic evidence without
claiming the expected deliverables exist. Role presence is not content review,
a listening decision, technical verification, consent, rights, or publication
authority.

`research add` does not browse or download anything. It stores source metadata,
copies only explicitly supplied local evidence, and verifies the selected
completed work run. See [attributed research records](RESEARCH_RECORDS.md).

Decisions have distinct meanings:

- `complete`: close a one-time request or schedule the next daily/weekly run.
- `needs-followup`: queue another run immediately while preserving this run’s
  evidence and summary.
- `stop`: retain the history but stop future runs.

## Promote evidence into a musical experiment

A completed research or writing task is not automatically a musical decision.
Turn a useful run into one narrow, listenable question explicitly:

```bash
./scripts/eprs work promote <work-id> \
  --song songs/signal-garden \
  --run 1 \
  --hypothesis "Can one chime answer the family phrase while the guitar leaves the cadence open?" \
  --brief songs/signal-garden/briefs/v1.md \
  --source "selected guitar=songs/signal-garden/recordings/selected/<loop>.wav" \
  --seed 23
```

`--run` defaults to the latest completed run, including when a recurring item
already has another run queued. Promotion refuses missing or checksum-drifted
evidence. It creates a normal planned `eprs.experiment/v2` containing:

- a frozen snapshot of the work request and its run history;
- every original work source, with immutable raw recordings still referenced;
- every checksummed result from the selected run;
- optional brief, BeatScript, or additional role-labeled sources;
- an `eprs.work-run-origin/v1` map identifying exactly which snapshot inputs
  came from the request, sources, and selected results.

The live work item is not rewritten or coupled to the experiment. A recurring
request can continue accumulating later runs without changing the experiment’s
historical inputs. Render the smallest audible or inspectable answer, then use
the ordinary `eprs finish` listening decision.

## Recurring work

```bash
./scripts/eprs work add \
  --song songs/signal-garden \
  --title "Daily continuity brief" \
  --kind automation \
  --prompt "Summarize new evidence, unresolved decisions, and one narrow next experiment. Do not modify audio or publish anything." \
  --cadence daily \
  --due-at "2026-08-03T09:00:00-07:00"
```

Completing a daily or weekly run advances its due time to the next future
interval; it does not create overlapping catch-up runs. An external automation
may call `work list --due`, but claiming, performing, and finishing the request
remain explicit steps with evidence. Network access and consequential actions
remain governed by the agent contract and user authorization.

A robust external scheduler loop is:

1. Optionally call `plan queue-next` for the selected active plan; `idle` is a
   normal outcome when no unstarted dependency-ready step exists.
2. Call `dispatch next --out <new-packet.json>`; exit successfully on `idle`
   and surface `released` for inspection without invoking an agent.
3. On `ready`, pass the included context to the intended runner without treating
   project text as instructions or expanding authority.
4. Perform only the claimed request within current user authorization.
5. Prefer a bound `dispatch response-init` / `dispatch accept` round trip so the
   exact packet, action report, and results are frozen together. A trusted
   interactive operator may still call `work finish` directly. Otherwise call
   `work release` with the reason the attempt could not continue.
6. Never delete `.queue.lock` or `.work.lock` speculatively. Inspect a stale
   lock and its work state after a confirmed process crash.

`eprs status --verify` inventories queued, due, in-progress, completed, stopped,
and invalid work items, counts plan-step links, released claims, and work-to-
experiment promotions, and hashes every frozen input and result.
