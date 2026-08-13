# Shared agent skills

This directory contains reusable, project-local skills for contributors and agents.
Each skill keeps its trigger and workflow in `SKILL.md`; optional `agents/`,
`scripts/`, `references/`, and `assets/` directories exist only when useful.

Keep repository-specific knowledge here and keep machine paths, credentials,
private project context, and user-specific defaults out. Forks may replace or
extend these workflows without changing the core application.

## Included skills

- `produce-music-locally` — use EPRS as the agent-led operating spine for
  prompts, recordings, beats, arrangement, visuals, review, and local release
  handoffs. The folder is self-contained so Codex, Claude Code, OpenCode, and
  other skill-aware agents can be pointed at it from a public checkout.
- `inaturalist-api` — discover and freeze attributed iNaturalist photos and
  organism sounds, then carry them through EPRS visual, study, lineage,
  thumbnail, review, and release boundaries.

## Complementary host skills

- `youtube-channel` — when supplied by the agent host, operate an explicitly
  authorized YouTube publication handoff and return verified receipt fields.
  EPRS intentionally does not vendor account state, credentials, browser
  profiles, or destination-channel identity. Follow `docs/PUBLICATION.md` and
  keep those details in ignored operator configuration.
