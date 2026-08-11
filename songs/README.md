# Local song workspaces

Everything below this directory is private-by-default local creative work and is ignored by Git. This protects recordings, briefs, experiments, listening notes, generated media, and unfinished compositions from an accidental `git add .`.

Create a workspace with:

```bash
./scripts/eprs new "My Project"
```

Then capture a prompt and supplied material without first writing a schema:

```bash
./scripts/eprs request capture --song songs/my-project \
  --title "First idea" --prompt "Keep the guitar loose and leave room to answer." \
  --recording "guitar=/path/to/guitar.wav" \
  --evidence "lyrics=/path/to/lyrics.txt"
```

Recordings are copied into immutable raw intake; evidence is frozen separately.
The command does not process, browse, upload, publish, or infer permission.

Default duration: most complete songs should land around 2–3 minutes. Shorter
renders are welcome as experiments or sketches, but should be labeled as such
until the arrangement is intentionally complete.

To contribute a public teaching project, copy only the smallest useful, rights-cleared source material into `examples/songs/`. Remove personal paths and private notes, confirm recording and sample permissions, and run `make public-check` before committing.

Each new song exposes `_LISTEN.*`, `_WATCH.*`, `_CHANGE_ME.md`, and
`_CURRENT.json` at its root so the current review version sorts above the
working folders. These are lightweight pointers, not duplicate media and not
approval. `FINAL/` remains the immutable release handoff after technical
inspection, creative approval, and rights checks. Nothing is uploaded
automatically.
