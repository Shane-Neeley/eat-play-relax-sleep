# Two-microphone timing and polarity evidence

Two microphones can preserve useful differences in distance, room, bleed, and
performance while also producing cancellations in mono. `eprs phase` measures
one explicit listening region before processing or mixing. It does not align,
delay, invert, render, or rewrite either recording.

Both sources must already be inside the same private song workspace. Preserve
external recordings with `eprs ingest` or `eprs session add` first:

```bash
./scripts/eprs phase \
  recordings/raw/family-close/<take>.wav \
  recordings/raw/family-room/<take>.wav \
  --song songs/signal-garden \
  --role-a "family close microphone" \
  --role-b "family room microphone" \
  --intent "Hear whether the room supports the last phrase in stereo and mono" \
  --start-a 18.2 --start-b 18.2 --duration 8 \
  --max-shift-ms 20 --step-ms 0.5
```

The versioned `eprs.phase-observation/v1` report lands in `notes/phase/`. An
identical request is idempotent. The command decodes bounded temporary mono
measurement streams in memory and writes JSON only.

## Read the result

The report includes correlation at the declared starts, the strongest positive
and negative relationships, the strongest absolute relationship, and normal
versus hypothetical B-polarity-inverted mono-sum levels. Positive B offset means
B appears later than A; negative means B appears earlier. A boundary warning
means the strongest candidate reached `--max-shift-ms`, so the scan may not have
enclosed the relationship.

Correlation is evidence, not causation or taste. Shared performance, bleed,
capture latency, room reflections, and periodic sound can all create strong or
ambiguous matches. A negative value is not an instruction to invert polarity;
a timing value is not permission to align microphones. Listen to the unchanged
sources in stereo and mono, and decide whether the distance and room are part of
the performance before writing any processing recipe.

## Bounds and provenance

- Analysis regions are 0.05 to 30 seconds.
- Offset scans are at most 100 ms in either direction and 401 candidates.
- Analysis runs at 2 kHz and caps correlation work at 20,000 points per
  candidate. Requested sub-sample steps are recorded with their effective
  resolution.
- Effectively silent or non-varying regions are refused.
- The report binds both song-relative source paths, checksums, region starts,
  roles, intent, controls, media probes, and an immutable recipe-derived ID.
- `eprs status <song> --verify` detects missing or drifted sources. Bounded agent
  context includes only the useful summary; the full correlation scan and all
  binary media are omitted.

If listening supports a change, express it later as a new, explicit and
reviewable processing or mix action. Preserve this observation and both raw
microphone files so another musician or agent can challenge the decision.
