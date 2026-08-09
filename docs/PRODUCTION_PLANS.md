# Request-bound production plans

A captured request preserves what the user wants and supplied. A production
plan turns that exact request into an inspectable dependency graph before an
agent begins making unrelated choices or pretending one automatic pipeline fits
every song.

Plans describe possible work; they do not perform it. They cannot browse,
record, process media, satisfy consent or rights, approve a listen, upload, or
publish. The current user instruction and the normal evidence/approval commands
remain authoritative.

## Create a plan

```bash
cp templates/production-plan.json songs/signal-garden/code/production-plan.json
# Point request at one captured request. Keep only relevant steps and exact
# provided-item IDs, then rewrite the intent and questions for this song.
./scripts/eprs plan add songs/signal-garden/code/production-plan.json \
  --song songs/signal-garden
```

`eprs.production-plan/v2` requires:

- one captured production request, bound by song-relative path and checksum;
- a `north_star`, explicit assumptions, and open questions;
- one to 100 steps with open musical `kind` and player-facing `intent`;
- dependencies forming an acyclic graph;
- optional `uses` IDs that must exist in the request's supplied evidence;
- an explicit `required_capabilities` list on every step (including `[]` when
  none are required);
- an optional non-empty `required_result_roles` list of exact portable slugs
  when completed work must return particular evidence files;
- the `smallest_action`, expected output roles, concrete `done_when` evidence,
  and an optional listening question; and
- explicit gates that a plan can never satisfy on its own.

Supported gates are `user-direction`, `performer-consent`, `source-rights`,
`listening-decision`, `technical-verification`, `upload-authorization`, and
`publication-authorization`. A gate names a boundary; it is not proof that the
boundary has been crossed.

Capability IDs are exact portable slugs, not software preferences. They say
what a step needs, not which application should provide it. Focused context
classifies each one against the current toolchain as available, missing, or
unknown, so a plan can name a future capability without pretending it is ready.
The declaration grants no authority to install, launch, control, or process
with software. Existing `eprs.production-plan/v1` records remain fully
supported and retain their original shape; add capability fields only by using
v2.

`outputs` remain human-readable expectations, while `required_result_roles`
are machine-enforced evidence IDs a runner must use with `work finish` when it
declares `complete`. The result contract proves only that role-labeled,
checksummed files returned. It does not prove `done_when`, answer a listening
question, or satisfy a consent, rights, review, technical, upload, or
publication gate. Additional result roles are allowed. A `needs-followup` or
`stop` decision may preserve diagnostic evidence without falsely completing
the contract.

The deterministic record lands under:

```text
songs/<song>/notes/plans/<title>-<plan-id>/plan.json
```

Running the same spec returns the same record. `entry_steps` are simply the
dependency roots where execution could begin. They are not a live completion
tracker. Use work items, experiment decisions, recording/session records,
reviews, and release evidence to record actual progress.

## Accept an agent-authored plan result

When `work add --request` was completed with a v2 plan as frozen result
evidence, validate and freeze it directly:

```bash
./scripts/eprs plan accept-work <planning-work-id> \
  --song songs/signal-garden \
  --result production-plan
```

This is stricter than passing an arbitrary path to `plan add`: the completed
run must have decision `complete`, its request-origin checksum must still
verify, and the plan must target that exact captured request. Multiple results
require an explicit role-derived result ID. The resulting append-only
`eprs.production-plan-acceptance/v1` receipt preserves the work item, run,
agent, selected result, plan checksum, and false execution/gate/publication
authority. Repeating the same acceptance returns the same receipt.

Derive current dependency progress from checksum-bound plan-step work:

```bash
./scripts/eprs plan progress <plan-directory> --song songs/signal-garden
```

`eprs.production-plan-progress/v1` is read-only. A step becomes `complete` only
when it has plan-linked work whose final state is `completed`; queued or
in-progress follow-up work conservatively keeps it active, and stopped work does
not satisfy dependencies. The report distinguishes complete, active,
actionable, queueable, blocked, and stopped steps. “Active” and “actionable” can
overlap when a dependency-ready item is queued but not yet claimed. `queueable`
is narrower: the dependencies are complete and no plan-linked work has started.

Every declared gate remains `gates_verified: false`. Work completion can unblock
the dependency graph, but cannot prove user direction, performer consent,
source rights, a listening decision, technical verification, upload authority,
or publication authority.

## Revise instead of overwriting

Plans are immutable snapshots. To change direction, edit the source spec and
set `supersedes` to the prior plan ID, directory, or manifest path:

```json
{
  "schema": "eprs.production-plan/v2",
  "supersedes": "first-path-from-prompt-to-listening-film-<id>",
  "request": "notes/requests/<request-id>/request.json"
}
```

The omitted fields above are still required in a real spec. A revision can
supersede only a verified plan for the same request and binds the exact prior
manifest checksum. The older plan remains intact, so a later agent can see what
changed without treating the newest plan as retroactive history.

## Execute one smallest action

Inspect a plan and choose one entry step whose gates are actually satisfied by
current authority and evidence:

```bash
./scripts/eprs plan show <plan-directory> --song songs/signal-garden
./scripts/eprs work add \
  --song songs/signal-garden \
  --plan <plan-directory> \
  --plan-step develop-words
```

The plan step supplies a default title, kind, and bounded prompt. Override any
of them only when the requested work genuinely needs a narrower description.
Every request input named by the step's `uses` list is carried into the work
item automatically: immutable raw media remains a song reference, while frozen
request evidence is copied and checksummed under the work item. Additional
`--source ROLE=PATH` evidence remains available, but its role cannot collide
with an inherited request-input ID.

The work item stores `eprs.production-plan-step-origin/v2` for a v2 plan (and
the original `/v1` origin for a v1 plan): exact plan path,
checksum, request evidence, normalized step, gates, and request-input-to-work-
source map. V2 origins also preserve `required_capabilities` and any declared
`required_result_roles`. The latter becomes an immutable
`eprs.work-result-contract/v1` on the queued work. Loading or
claiming refuses changed plan provenance. Queue state and
run results then provide inspectable execution history without mutating the
plan. Neither the generated prompt nor a claimed work item satisfies a gate.

For a scheduler or returning agent, prepare the first declaration-ordered
unstarted actionable step without reconstructing `work add` arguments:

```bash
./scripts/eprs plan queue-next <plan-directory> \
  --song songs/signal-garden \
  --priority 70
```

Use `--step <step-id>` when the user has selected one exact branch. The command
returns versioned `eprs.production-plan-queue/v1` JSON with `queued` or `idle`
status. It holds the shared work-queue lock across fresh progress calculation
and work creation, refuses invalid queue evidence, queues at most one step, and
is idempotent once that step has work. A later call can advance only after
dependency work has completed with frozen results.

`plan queue-next` inherits the plan step, request provenance, and named request
inputs exactly like manual `work add --plan ... --plan-step ...`. It does not
claim or execute the work. Its response and resulting prompt keep
`gates_verified: false`; current user authority and every declared gate must
still be checked before an agent performs the step.

Later dependent steps become appropriate only when their predecessors have
real outputs and decisions. Revise the plan when the graph itself changes; do
not edit a frozen record to fake progress. A work item can preserve recurring
agent ownership and results, while an experiment is the right bridge for one
audible hypothesis.

## Continuity

```bash
./scripts/eprs status songs/signal-garden --verify
./scripts/eprs context songs/signal-garden --verify --format markdown
```

Status counts plans, steps, derived complete/active/actionable/blocked/stopped
states, the narrower queueable count, revisions, verified agent-work acceptance
receipts, linked plan-step work, and
invalid records. Context includes
the same conservative progress projection plus bounded north-star,
assumptions, questions, step
dependencies, request-input use, smallest actions, evidence conditions,
listening questions, gates, and linked work states. A focused work context also
includes its bounded plan-step origin. It never executes a plan or embeds
supplied binary media.
