# Ranked production quality gaps

Checked 2026-08-10 against the current repository and
`tests/test_end_to_end.py`. This ranking names what still prevents EPRS from
proving the full product promise. A green technical test is not evidence that a
song bumps, moves someone, or deserves release.

| Rank | Remaining gap | Current evidence | Next proof required |
| --- | --- | --- | --- |
| 1 | **Real musical listening and revision loop** | The private end-to-end proof reaches a valid pending source-sketch review with immutable performances and no fabricated keep decision. A separate three-candidate BeatScript trial now has a real user keep decision on the exposed candidate, preserved without inflating it into mastering or release approval. That proves bounded audition and selection, but not yet feedback-driven revision. Unit tests prove renders and provenance, not taste. | Run one real user-owned guitar/voice/beat session through several materially different passes; collect complete-listen keep/change/stop notes and show that an agent can turn those notes into a clearly improved next pass. |
| 2 | **Arrangement intelligence beyond entrances, balance, and pan** | `source-sketch --observation` checksum-binds phrase/pitch/pulse evidence and uses one substantial measured phrase unchanged. In the private A/B, the user selected A's whole-source continuity but explicitly rejected the generated drums because they did not go along with the user's beat. Separately, a form-authored BeatScript trial successfully staged intro, delayed bass entrance, late high-register answer, breakdown, and final return across 24 bars; the user kept that complete relationship. The system preserves both decisions without treating either as mix approval. | Keep A's source choice, replace the grid-authored bed with a groove mapped from the user's attacks and phrase shape, and return one A/A2 comparison without automatic tuning or quantizing. Then bring the successful form-level staging into a source-aware complete arrangement rather than another placement sketch. |
| 3 | **Runner execution, isolation, and live performance diagnostics** | The explicit shell-free runner uses mandatory `sandbox-exec`/Bubblewrap isolation, hard network denial, workspace-only child writes, capped logs, a deadline, process-group cleanup, raw before/after hashes, validated response freezing, failure requeue, receipts, and `eprs performance` summaries. | Run one real local Codex/Claude/Gemini-compatible file-agent profile end to end. Then add a reviewed patch-application boundary and a read-only HTTP proxy before allowing runner-driven code changes or online research. |
| 4 | **Full-song visual proof at production length** | Ranked visual methods, Remotion worlds, Graphviz maps, source-synced drafts, render timings, timeouts, and orphan detection exist. The end-to-end proof skips rendering to stay fast. | Render two contrasting full-song visual methods from an approved mix, verify sync/color/codec and resource use, watch both end to end, and record a picture decision. Preserve renderer-neutral sources so Remotion is not a lock-in. |
| 5 | **Actual AI-music collaboration pilot** | ACE-Step is ranked first locally and has a provider-neutral non-executing adapter. Suno now exposes an official API platform; APIFrame is a lower-ranked third-party option with useful jobs/webhooks/stems but conflicting public pricing claims. No generated candidate has passed through a real EPRS comparison. | On suitable hardware, run a small fresh-seed ACE-Step batch from owned non-private material, or price-cap an official Suno API pilot after reviewing account terms. Capture exact provider/model/settings/runtime/cost/rights, compare candidates against a human-authored control, and retain only a musically useful contribution. |
| 6 | **Research-to-original-experiment loop for favorite songs and videos** | Requests route YouTube and other references into attributed research; dispatch requires explicit read-only network permission and research records enforce attribution/copying boundaries. | Complete one authorized reference study, normalize observations versus inference, then prove that its smallest original experiment uses only project-owned material and does not copy melody, lyrics, arrangement, stems, or samples. |
| 7 | **Release rehearsal with real rights and metadata** | Mix, mastering, picture, YouTube assets, FINAL packaging, distribution, and offline publication handoffs are individually verified and never upload. The private proof correctly stops before rights and listening gates. | With a genuinely approved song and artwork, complete clearance, master/video reviews, distributor metadata, and a local release package; then rehearse the offline handoff without submitting it. Platform submission remains separately authorized external work. |

## Performance budget for the next iterations

- Keep `make test-fast` under roughly 30 seconds on the current development
  machine; it includes the agent dispatch protocol but excludes media-heavy
  round trips.
- Keep the no-visual private mixed-input proof under 30 seconds. It currently
  completes in about 13 seconds on the checked machine.
- Keep `eprs observe` to one 8 kHz mono decode over at most 120 seconds and at
  most 256 pitch-analysis frames. The three-second fixture currently takes
  about 1.6 seconds per fresh observation, while a 52.1-second PCM working
  recording took 2.74 seconds; repeated requests must use the verified stored
  artifact rather than re-analyzing it.
- Run the complete media suite before a checkpoint. Its current 196-test
  baseline is about 4 minutes 39 seconds, plus five JavaScript tests.
- Any EPRS-launched renderer or future runner must use a bounded process group,
  a declared timeout, cleanup verification, and read-only health reporting.
- Do not trade away lossless sources, exact checksums, or complete-listen gates
  merely to hit a timing target.

The next engineering priority is rank 2, while rank 1 requires real user-owned
performances and listening reactions. Rank 3 should precede any unattended
agent runner.
