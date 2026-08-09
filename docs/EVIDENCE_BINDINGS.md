# Bind decisions to the evidence behind them

An agent can explain a processing or mix choice in prose and still leave a
future collaborator unable to prove which observation it used. Optional
`evidence` entries in `eprs.process/v1` and `eprs.mix/v1` close that gap: each
entry binds one exact song-local file, its role, and how it affected the recipe.

```json
"evidence": [
  {
    "id": "family-microphone-relationship",
    "role": "two-microphone phase observation",
    "path": "notes/phase/family-close-and-family-room-<observation>.json",
    "use": "Preserve the observed room relationship; do not align or invert either microphone."
  }
]
```

The path must be relative to the song, remain inside the workspace, name a
non-hidden file, and exist before rendering. IDs are unique after portable slug
normalization. `role` says what the evidence is; `use` says what it changed—or
constrained—in this exact recipe. Up to 32 bindings are accepted so the record
stays deliberate rather than becoming a project-file dump.

The renderer resolves every entry into `eprs.evidence-binding/v1` with:

- normalized and declared IDs;
- role and recipe-specific use;
- song-relative path and SHA-256 checksum;
- the declared schema for reasonably sized JSON evidence, when detectable.

The bindings become part of the deterministic recipe ID. Changing a binding,
its intended use, or its evidence bytes cannot silently preserve provenance.
Render review rechecks every checksum; status checks structure and existence by
default and hashes evidence with `--verify`. A changed evidence file invalidates
the old render for review or mastering. Preserve it and render a new recipe from
the newer evidence rather than editing an old sidecar.

Good bindings include a phase observation, attributed research record,
recording-session record, performance comparison, lyric decision, completed
work result, or a private listening note inside the song. Audio sources already
have dedicated source lineage and normally should not be repeated as evidence.
External URLs belong in an attributed research record first; a render recipe
does not browse or freeze a URL.

Evidence does not grant authority. A clearance record can explain a decision,
but merely binding it does not satisfy release rights gates. A phase report can
constrain a mix, but binding it does not authorize alignment or polarity
inversion. Listening remains the creative approval boundary.

Legacy v1 process and mix recipes without `evidence` remain valid. This optional
contract makes consequential choices more inspectable without forcing every
small sketch to cite material it did not use.
