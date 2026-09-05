# Song method manifests

EPRS keeps detailed provenance beside recordings, studies, stems, mixes,
masters, pictures, and release packages. `song-manifest.json` adds the missing
album-scale view: what methods are evidenced for this song, why they were used
or declined, which prompts and settings mattered, and which other routes were
available.

The manifest is an index, not a replacement for sidecars. It has four evidence
levels:

- `events` are song-mutating EPRS command attempts recorded automatically,
  including a `completed` or deliberately non-specific `nonzero` outcome;
- `manual_records` capture software or techniques used outside the EPRS CLI,
  including considered, rejected, failed, and superseded routes;
- `artifacts` index current song-local structured records and editable creative
  sources by checksum, schema, context fields, and software declarations;
- `notes` are deliberately loose sections for prompts, ideas, thoughts,
  questions, and other context that should survive without becoming a rigid
  production ontology.

The `method_space` snapshot lists every EPRS command and parameter, every
declared software provider and capability, every adapter handoff, and every
workflow known to the checkout that built the manifest. A method marked
`not-evidenced` is a useful lead for a contrasting experiment; it is not proof
that nobody used it before the ledger existed.

## Normal use

Mutating command attempts rebuild the manifest automatically. A nonzero event
may be a creative/technical hold or an operational error; inspect the changed
artifacts and owning sidecars rather than guessing which. Read-only
commands such as `status`, `check`, `analyze`, `context`, and `manifest show`
remain read-only and do not create ledger entries.

If a read-only analysis materially changes a creative decision, record that
decision with `manifest record` or its supporting context with `manifest note`.
The automatic event ledger is intentionally an operation log, not a claim that
every inspection command was captured.

Rebuild or inspect explicitly:

```bash
./scripts/eprs manifest build songs/my-song
./scripts/eprs manifest build songs/my-song --probe-tools
./scripts/eprs manifest show songs/my-song
./scripts/eprs manifest verify songs/my-song
./scripts/eprs manifest compare songs/first-song songs/second-song
```

`--probe-tools` freezes current availability and detected versions into that
catalog snapshot. Ordinary automatic rebuilds preserve the portable declared
catalog without repeatedly probing the machine.

## Record an external or human-operated method

Use `manifest record` for Sonic Pi, Audacity, a DAW, an instrument, a room
performance, a model sidecar, a custom script, a deliberate absence of a tool,
or any method whose use cannot be reconstructed from an EPRS command:

```bash
./scripts/eprs manifest record \
  --song songs/my-song \
  --method "Sonic Pi live-code" \
  --kind composition \
  --status used \
  --reason "The groove needed a performed push that the fixed grid did not provide." \
  --software-version "4.5.1" \
  --prompt "Let the guitar invite; answer after the room breathes." \
  --setting '{"seed":23,"bpm":92}' \
  --input "guitar=recordings/raw/guitar/take.wav" \
  --output "groove=beats/sonic-pi-groove.wav" \
  --alternative "BeatScript fixed-grid audition" \
  --note "Recorded one bounded, lossless pass." \
  --tag live-performance
```

The status vocabulary is intentionally small—`used`, `considered`, `rejected`,
`failed`, or `superseded`—while `kind`, `reason`, settings, notes, alternatives,
and tags remain open-ended. Inputs and outputs are checksummed. External paths
are reduced to a basename plus the checksum so a public manifest does not leak
a machine-specific location.

Record rejected routes too. “Rejected Sonic Pi because the hook needed exact
sample-repeatability” is as useful for a future orthogonal song as a successful
render record.

## Keep loose creative context

No fixed list of sections is imposed:

```bash
./scripts/eprs manifest note \
  --song songs/my-song \
  --section "ideas for an opposite version" \
  --text "No animal roll call: one call becomes a recurring melody, answered by live guitar." \
  --tag album-contrast
```

Notes are append-only records under `notes/manifest/`; rebuilding never edits
them. Edit by adding a correction or superseding method record, not by rewriting
history.

Prompts, notes, and settings are song content and may be committed with a song.
Do not put credentials, private machine paths, or unrelated personal data in
them. EPRS makes path fields portable; it cannot reliably redact secrets hidden
inside free-form prose.

## Album-level comparisons

Because every song uses the same generated schema, album tooling can compare:

- method and provider frequency;
- used versus considered/rejected methods;
- fixed seed versus fresh exploration;
- programmed, performed, generated, source-derived, and hybrid lanes;
- repeated settings or processing chains;
- prompts, reasons, alternatives, and unresolved ideas;
- CLI methods and adapter handoffs that remain untried.

This makes “make a similar song,” “change only the processing,” and “choose a
truly orthogonal method” evidence-backed queries rather than guesses from a
finished WAV.

`manifest compare` first verifies every input manifest, then reports completed CLI methods, explicitly declared used
methods, artifact-evidenced legacy CLI methods, shared/exclusive method sets,
and pairwise Jaccard overlap. The number is a production-method diagnostic, not
a claim that two songs sound similar or different.

## Verification and limits

`manifest verify` checks the generated index, append-only records, editable
sources, structured artifacts, and song-local manual inputs/outputs against
their recorded checksums. Binary media are listed in `asset_inventory`; their
authoritative checksums remain in their existing EPRS provenance sidecars and
lineage records so automatic rebuilds do not rehash an entire album.

A manifest can prove that evidence exists and has not changed. It cannot prove
that an undocumented method was never used, that a reason was wise, that a
listener approved the music, or that rights and publication gates were met.
