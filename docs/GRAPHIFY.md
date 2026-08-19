# Graphify architecture map

EPRS keeps a local Graphify map at `graphify-out/`. The directory is ignored
because the map is a derived inspection surface, not song or source-of-truth
data. Use it to navigate the repository before changing a cross-cutting
contract, and refresh it after an agent wave.

## The small operating loop

Ask a focused architecture question and keep traversal useful by filtering the
edge context:

```bash
graphify query "How does a captured prompt become a bounded agent task and then a reviewed musical artifact?" \
  --context calls --context imports --context contains --budget 1600
```

Before changing a shared symbol, inspect its reverse blast radius:

```bash
graphify affected build_agent_context --depth 2
graphify affected load_song_manifest --depth 2
```

Use a shortest path for a specific handoff, and use `god-nodes` only as a
starting point. Generic helpers such as `sha256()`, `utc_now()`, and `slugify()`
are structurally central but are not automatically product concepts:

```bash
graphify path create_production_plan dispatch_next_work --undirected
graphify god-nodes --top 20
graphify diagnose multigraph --undirected
```

After code changes, update incrementally; it re-extracts changed code without
paying for a full corpus rebuild. If docs or research changed too, run the
ordinary update so their semantic nodes are refreshed:

```bash
graphify update .
graphify check-update .
```

For a long local agent wave, `graphify watch .` rebuilds code changes and flags
non-code changes for a later semantic update. Useful derived views are:

```bash
graphify export callflow-html
graphify tree --root src/eprs
```

## Prompt patterns for useful exploration

Context-capable agents get better results when the question names a boundary,
not just a broad topic. Useful patterns include:

```text
Which symbols carry the request-to-experiment handoff, and what are their direct callers?
What changes if I edit <shared symbol>; which tests and user-facing contracts are affected?
What is the shortest path from <input> to <review gate>, and where can authority widen?
Which nodes are utility hubs rather than musical concepts, and how should I avoid reading them as architecture?
Which tests demonstrate that this route is advisory, bounded, and listening-gated?
```

Use `--context calls --context imports --context contains` for implementation
orientation, then verify the answer in the source and focused tests. Ask a
second narrower query rather than accepting a truncated traversal. If the map
does not contain a relationship, say that it is unknown and inspect the source;
never invent an edge from naming or proximity.

## Feedback and agent access

When a query produces a useful architectural decision, the result can be
recorded in Graphify's local work memory and aggregated into lessons. Do not
save private prompts, lyrics, credentials, or raw media content:

```bash
graphify save-result \
  --question "What is the safest bridge from request intake to the next musical experiment?" \
  --answer "Use request-bound planning, dispatch, bounded context, and explicit review gates." \
  --type query --nodes build_agent_context dispatch_next_work \
  --outcome useful
graphify reflect --graph graphify-out/graph.json
```

Graphify's installed source also includes an MCP server with query, node,
community, god-node, statistics, and shortest-path tools. It is optional and
requires the MCP extra; the source-backed entry point is:

```bash
python -m graphify.serve --graph graphify-out/graph.json --transport stdio
```

Keep this read-only graph surface separate from EPRS authority. Graph results
can orient an agent and expose relationships, but they never authorize
browsing, audio edits, raw-source writes, listening approval, publication, or
upload.
