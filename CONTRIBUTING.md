# Contributing

Eat Play Relax Sleep is designed for many musical practices, tools, skill levels, and kinds of source material. Contributions should expand that creative range without assuming a particular person, studio, genre, operating system, or commercial service.

## Local setup

```bash
./scripts/eprs doctor
make check test public-check
make studio
```

The Python core has no runtime package dependencies. The optional visual renderer has its own setup under `visuals/`.

## Public and private material

- Keep active compositions, recordings, experiments, notes, and renders in `songs/`; Git ignores that directory by default.
- Put only deliberate, compact, rights-cleared teaching material in `examples/`.
- Never commit credentials, personal filesystem paths, private notes, raw personal recordings, unlicensed media, or generated build output.
- Preserve author and performer credits when they are intentionally public. Replace person-specific template defaults with blank or role-based fields.
- Treat `recordings/raw/` as immutable even though local song workspaces are ignored.

Run `make public-check` before committing. It verifies the local-song boundary and scans Git candidate files for common secrets, personal absolute paths, and person-specific owner defaults without printing matched secret values.

## Change quality

- Keep editable sources and deterministic seeds when randomness matters.
- Add or update tests for behavior changes.
- Add new application guidance as a provider in `config/toolchain.json` plus a
  validated drop-in profile under `config/adapters/`; keep song contracts
  provider-neutral and never place credentials or personal paths in profiles.
- Test machine-specific paths privately through `.eprs-local/` or explicit CLI
  extension/profile arguments; do not commit that local configuration.
- Keep accessibility, narrow screens, keyboard use, and reduced motion in scope for studio changes.
- Record provenance and permission for contributed media.
- Do not enable remote control, uploads, publishing, or Audacity scripting by default.

Generated audio and video should normally be reproducible from small sources rather than committed directly.
