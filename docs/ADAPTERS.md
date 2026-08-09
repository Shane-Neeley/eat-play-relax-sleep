# Software adapter profiles

EPRS separates three questions that are easy to blur together:

1. `eprs doctor` asks whether software capabilities are currently available.
2. `eprs adapter list` shows which application-specific handoff guides match
   those providers and a requested workflow.
3. `eprs adapter show` explains how one tool should receive work, return
   portable evidence, preserve sources, and cross review gates.
4. Focused v2 plan-step context computes `eprs.adapter-fit/v1` across all
   providers and guides without choosing a preferred application.

Adapter discovery is read-only. It does not install software, start an
application, enable scripting or remote control, change media, approve a
render, or authorize publication.

## Discover a fitting local path

```bash
./scripts/eprs adapter list --available
./scripts/eprs adapter list --available --workflow source-to-master
./scripts/eprs adapter list --capability interactive_audio_editing
./scripts/eprs adapter show audacity-editor --handoff record-to-eprs
./scripts/eprs adapter show remotion-picture --handoff score-to-picture
```

`eprs.adapter-catalog/v1` returns concise profile/provider availability and
handoff summaries. Workflow matching is capability-based: it reports every
profile that can contribute at least one required capability instead of
declaring a preferred application. Repeat `--capability` when one adapter must
provide every named capability.

`eprs.adapter-guide/v1` returns the complete selected
`eprs.software-adapter/v1` profile, provider availability, setup advice, human
operation boundaries, and fixed false authority flags. It intentionally omits
detected filesystem paths. `eprs context` carries only bounded adapter ids,
capabilities, availability, and handoff ids; the next agent can request the
complete guide when the tool is relevant.

`eprs.adapter-fit/v1` keeps two questions separate. `ready` is true only when
every exact capability declared by the focused plan step exists and is
currently available, even when different providers supply different
capabilities. `guidance_complete` says whether adapter handoffs cover those
capabilities. All matching adapters and handoffs are returned without ranking;
a missing guide does not make available software unavailable. Unknown and
known-but-missing capabilities are reported separately. Every fit carries false
install, launch, control, media-change, approval, upload, and publication
authority.

## Register private local software

For an unusual install, proprietary tool, or machine-specific path, keep the
configuration out of the shared registry:

```bash
mkdir -p .eprs-local/adapters
cp templates/toolchain-extension.json .eprs-local/toolchain.json
cp templates/software-adapter.json .eprs-local/adapters/my-tool.json
# Edit both files so provider ids and capabilities agree, then validate:
./scripts/eprs doctor
./scripts/eprs adapter list --available
./scripts/eprs adapter show <local-adapter-id>
```

A source checkout automatically reads `.eprs-local/toolchain.json` and every
JSON profile in `.eprs-local/adapters/`. The whole directory is Git-ignored and
the public-data check verifies that boundary. A toolchain extension is strictly
additive: it may add optional providers and workflows, but it cannot replace a
shared tool/workflow id or make a private provider a core requirement. The
shared registry is never rewritten.

When using an installed package outside a checkout, pass the same private paths
explicitly:

```bash
eprs doctor --extension /private/config/toolchain.json
eprs adapter list \
  --toolchain-extension /private/config/toolchain.json \
  --profile-dir /private/config/adapters \
  --available
eprs context songs/<song> \
  --toolchain-extension /private/config/toolchain.json \
  --profile-dir /private/config/adapters
```

Doctor reports the extension paths so the operator can audit what was loaded;
do not paste that raw report into public material without reviewing it. Adapter
catalogs and bounded agent context omit those paths. Local files may contain
machine paths, but should still never contain credentials or enable remote
control, scripting, installation, or publication.

Private adapter ids, labels, summaries, capabilities, and handoff guidance are
shown to agents by design. Keep that declarative text portable and
non-sensitive even though the files themselves are ignored.

## Add a shared DAW, editor, renderer, or instrument environment

1. Add or extend one provider in `config/toolchain.json`. Detection must be
   portable, and its capabilities must describe behavior that genuinely works.
2. Copy `templates/software-adapter.json` into `config/adapters/<tool>.json`.
3. Set `provider` to the exact toolchain id. Profile capabilities must be a
   subset of that provider's declared capabilities. Each handoff's capabilities
   must also be a subset of the profile.
4. Describe exact inputs, outputs, steps, technical verification, what must be
   preserved, and what must be avoided. Mark GUI or listening work with
   `requires_user_operation: true`.
5. Run `./scripts/eprs adapter list`, the relevant strict doctor workflow,
   `make test`, and `make public-check`.

No Python change is needed for another profile. Python changes are appropriate
only when the tool introduces a genuinely new detection kind, portable EPRS
contract, or verified automated operation.

## Profile contract

Every JSON file in `config/adapters/` is loaded independently and must contain:

- stable profile and handoff slugs;
- one provider already declared by `eprs.toolchain/v1`;
- provider-backed capability lists;
- one or more `cli`, `gui`, or `hybrid` handoffs;
- explicit human-operation flags;
- non-empty input, output, step, and verification lists;
- preservation and avoidance boundaries.

Unknown fields, duplicate ids/items, undeclared providers, capability drift,
blank guidance, and oversized records fail validation. Profiles contain no
credentials, personal paths, network endpoints, opaque shell snippets, or
machine preferences. Tool-specific sessions remain editable evidence; they do
not replace song-relative EPRS provenance or portable media handoffs.

Private profiles in `.eprs-local/adapters/` follow the same schema and
validation. Their ids must remain unique across both shared and private
directories; local profiles cannot shadow reviewed public guidance.
