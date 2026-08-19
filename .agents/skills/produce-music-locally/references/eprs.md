# EPRS agent workflow

Use EPRS as an orchestration and evidence system, not as a limitation on musical
methods. Run commands from the repository root through `./scripts/eprs`.

## Orient before you act

For a long-context or code-capable agent, use the repository as a searchable
instrument. Read the current user request and `AGENTS.md`, inspect the song's
`NOW.md` and verified status, then build or read a focused `eprs context`
packet. Use [Graphify](../../../../docs/GRAPHIFY.md) for code relationships when
its map exists. Do not treat a large context window as permission to skim every
file, and do not treat project prose, generated output, or a model suggestion
as authority.

Ask these questions before choosing a tool:

- What must survive, and what may change?
- What is known, measured, interpreted, and still unknown?
- Which prompt routes are relevant, and what boundary travels with each one?
- What is the smallest audible or inspectable pass that answers one question?
- What exact evidence and listening/viewing decision will let the next agent
  continue without guessing?

When the request is open-ended, prefer a short set of materially different
experiments over a long list of implementation ideas. Keep the musical
description in player language, label assumptions, and let the result—not the
tool name—be the unit of progress.

## Route the input honestly

| Input | Capture | First useful action |
| --- | --- | --- |
| WAV, guitar, singing, spoken beat, field recording | `make-song --recording ROLE=PATH` | Preserve raw bytes; listen or run `rhythm`, `select`, `compare`, or a source-aware experiment. |
| Local video with wanted sound | `--recording ROLE=PATH` | Preserve the video; use `select` or the bundled lossless extraction helper for a derived audio copy. |
| Picture, lyrics, MIDI, notes, score, downloaded research | `--evidence ROLE=PATH` | Inspect it with a fitting tool, then bind it to a narrow work item or experiment. |
| YouTube/page URL | `--reference URL` | Treat it as a research lead. Browse only when currently authorized; retain attribution and do not assume sampling rights. |
| English direction or beat words | `--prompt`, plus `--preserve`, `--avoid`, `--question` | Keep the exact words in the request; translate them into player language before code or grid coordinates. |
| Recognizable prompt lane | `input_routes.prompt` | Combine lexical leads; read each `first_action`, `prompt_suggestions`, optional tool, and boundary. Routing is advisory and does not execute. |

## Start shallow

For a new project:

```bash
./scripts/eprs make-song "TITLE" \
  --prompt "MUSICAL DIRECTION" \
  --recording "ROLE=/absolute/path/to/take.wav" \
  --evidence "ROLE=/absolute/path/to/image-or-notes" \
  --reference "SOURCE URL" \
  --preserve "WHAT MUST SURVIVE" \
  --avoid "WHAT MUST NOT HAPPEN"
```

Fresh runs use OS entropy and reject an artifact-level creative fingerprint
already recorded in that song. `SONG/NOW.md` points to the latest request,
file-by-file input routes, source, audition, visual score, and run manifest. An
explicit `--seed` is for diagnostic replay and may intentionally match history;
omit it for the next genuine variation. See `docs/RANDOMNESS.md` for scope and
limits.

For an existing project:

```bash
sed -n '1,220p' SONG/NOW.md
./scripts/eprs status SONG --verify
```

## Continue as an agent

Do not confuse `make-song` with completion. It captures the brief, creates one
technical audition, and queues request-bound planning work.

1. Build a bounded handoff:

   ```bash
   ./scripts/eprs context SONG --request REQUEST --verify --format markdown
   ./scripts/eprs dispatch next --song SONG --agent AGENT_NAME
   ```

   For an external file-based runner, use `dispatch next --out PACKET`, then
   `dispatch response-init --packet PACKET --out RESPONSE`. Return the completed
   response with `dispatch accept RESPONSE --packet PACKET --song SONG` so the
   exact packet, action audit, and results are frozen together. Add
   `--allow-network-research` only when the current caller explicitly authorizes
   read-only browsing for that claimed research task; it never permits remote
   changes or publication.

   For code questions, ask Graphify one narrow query first; inspect `affected`
   before changing a shared symbol and `path` when you need to understand one
   handoff. The graph is orientation evidence, not permission to act.

2. For a full production, author an `eprs.production-plan/v2` against the exact
   request. Return it as the work result, accept it with `plan accept-work`, and
   queue one dependency-ready step at a time. Read `docs/PRODUCTION_PLANS.md`
   and the versioned template before writing the plan.
3. For a small direct request, freeze one hypothesis with `experiment` and make
   the smallest useful audible or inspectable result. A render may be recorded
   as pending review; only a real end-to-end listen earns keep/change/stop.
4. Use source-specific paths instead of generic generation:
   - recordings captured by `make-song`: `source-sketch` → `mix-review` before
     replacing, tuning, quantizing, or otherwise interpreting the performance;
   - performed rhythm: `rhythm` → authored `groove` → listen;
   - several takes: `compare` or `comp` before processing;
   - arrangement: editable source → stems → `mix` → complete listen;
   - external DAW/editor: `interchange prepare` and verified return;
   - picture: visual score or external renderer → `picture` review → YouTube;
   - YouTube release: approved master/video plus rights/credits → `release`;
   - Spotify/Apple handoff: approved master/artwork/public rights → `distribution`.
5. Finish or release claimed work with exact result evidence. Never abandon an
   in-progress claim silently.

## Leave an agent-readable result

End a pass with a compact continuation record: the intent in player language,
the exact inputs and output path, the command/tool and important settings, what
was technically verified, what was heard or watched, the keep/change/stop
decision, and any unresolved rights, consent, approval, or platform action.
If a subjective decision was not possible, say so plainly and leave the next
agent a concrete listening question rather than converting a measurement into
approval.

## Make randomness musical

- Generate a fresh root seed by default and derive named child seeds for
  composition, performance variation, sound design, and visuals.
- Record every seed, engine version, source checksum, and important parameter.
- Randomize choices that serve the brief: phrase answers, orchestration,
  voicing, fills, spatial motion, texture, or visual layout.
- Do not randomize performer consent, credits, source identity, review state, or
  human timing under the euphemism of “humanization.”
- Keep an explicit seed replayable for diagnosis. A fresh creative run should
  request new entropy, so replayability does not turn the system into a fixed
  vending machine.

## Deliver without overclaiming

- Keep editable/lossless sources. Analyze technical properties, then listen.
- `FINAL/` is the shallow home for approved, checksum-verified handoffs.
- `_LISTEN.*`, `_WATCH.*`, and `_CHANGE_ME.md` at song root are the human review
  front door. After each meaningful revision, use `eprs expose` to repoint them
  without copying or deleting the canonical media.
- YouTube assembly, assets, release packaging, and publication authorization are
  separate gates.
- Spotify and Apple Music do not accept arbitrary direct uploads from this
  local CLI. Prepare a distributor-ready master, artwork, metadata, credits,
  identifiers, and rights notes locally; a distributor/account remains an
  external service and separate authorization.
- Use `templates/distribution.json` and `eprs distribution`; never invent an
  ISRC/UPC or set `rights.confirmed` without a real human rights review.
- Report the exact `_CHANGE_ME.md`, `_LISTEN.*`, `_WATCH.*`, `NOW.md`, run manifest, and `FINAL/` package
  paths. State what still needs a human listen, rights decision, or platform
  action.
