# Isolated agent runners

EPRS can launch one explicit file-based agent against one checksum-bound ready
dispatch packet. This is an opt-in execution boundary, not a general shell and
not an unattended publisher.

Runner v1 requires an OS sandbox:

- macOS uses `sandbox-exec`;
- Linux uses Bubblewrap (`bwrap`);
- other systems, or either system without its sandbox provider, refuse to run.

The child gets a private workspace under
`notes/runner-runs/<profile>/<run>/workspace`. The OS denies network access and
host writes outside that workspace. EPRS invokes an executable plus a literal
argument list without a shell, caps each output log, enforces a deadline, owns
the process group, terminates descendants, verifies cleanup, hashes immutable
raw recordings before and after, validates the bound response, and preserves a
receipt. On failure it returns the work item to the queue with the reason.

## Profile and run

Copy the profile template to ignored `.eprs-local/` and replace its executable
and arguments with an installed file-based agent:

```bash
mkdir -p .eprs-local/runners
cp templates/runner-profile.json .eprs-local/runners/my-agent.json
scripts/eprs runner validate .eprs-local/runners/my-agent.json
scripts/eprs doctor --workflow isolated-agent-runner --strict

scripts/eprs dispatch next \
  --song songs/<song> --agent <agent-name> \
  --out /tmp/<song>-packet.json
scripts/eprs runner run .eprs-local/runners/my-agent.json \
  --packet /tmp/<song>-packet.json --song songs/<song>
scripts/eprs performance --song songs/<song>
scripts/eprs runner show notes/runner-runs/<profile>/<run> \
  --song songs/<song>
```

Profiles use `eprs.runner-profile/v1` and the
`eprs.packet-response-files/v1` protocol. The only argument placeholders are
`{packet}`, `{response}`, and `{workspace}`. The packet and response
placeholders are mandatory. `network_mode` must be `deny`; v1 intentionally
does not weaken that rule even if a dispatch packet permits read-only research.

For online research, hand the packet to a separately operated agent and accept
its response through the ordinary dispatch protocol. A later runner may add a
read-only HTTP proxy with method/host/request receipts; ordinary OS sandboxes
cannot prove that arbitrary network access stayed read-only.

The agent cannot edit the repository, song, or raw recordings directly. It
returns files in its workspace; the parent validates and freezes them into the
work run. A future reviewed patch-application step can safely extend code-edit
workflows without granting a child general host writes.

A completed receipt proves execution, isolation evidence, cleanup, artifact
checksums, and response acceptance. It does not prove listening, musical
quality, creative approval, consent, rights, release readiness, upload, or
publication.
