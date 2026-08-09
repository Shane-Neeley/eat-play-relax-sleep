# Shared agent skills

This directory contains reusable, project-local skills for contributors and agents.
Each skill keeps its trigger and workflow in `SKILL.md`; optional `agents/`,
`scripts/`, `references/`, and `assets/` directories exist only when useful.

Keep repository-specific knowledge here and keep machine paths, credentials,
private project context, and user-specific defaults out. Forks may replace or
extend these workflows without changing the core application.

## Included skill

- `produce-music-locally` — use EPRS as the agent-led operating spine for
  prompts, recordings, beats, arrangement, visuals, review, and local release
  handoffs. The folder is self-contained so Codex, Claude Code, OpenCode, and
  other skill-aware agents can be pointed at it from a public checkout.
