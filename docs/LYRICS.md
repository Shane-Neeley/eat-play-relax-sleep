# Source-bound lyric development

Lyric ideas are creative evidence, not disposable prompt output. `eprs lyrics`
preserves original fragments, genuinely different alternatives, the reason each
version exists, singability questions, and explicit review history without
silently collapsing everything into one “best” answer.

Lyric records are private song artifacts by default. They do not grant rights,
authorize sharing or publication, copy reference writing, or replace what a
singer reveals through breath, pitch, timing, accent, and group overlap.

## Optional public YouTube analysis with agy

When a lyric reference is a public YouTube video and the question is about
meaning, delivery, section shape, hook timing, performance, or public context,
use the host's Antigravity CLI (`agy`) when available. Gemini can understand a
public YouTube URL directly and return useful timestamped observations beyond
what captions alone reveal:

```bash
agy -p 'Analyze https://youtu.be/VIDEO_ID for concise timestamped observations about lyric delivery, sections, and performance. Paraphrase; do not reproduce lyrics or imitate the work.'
```

Use the host Gemini bridge's `youtube` mode instead when that is the available
entry point. Keep exact-caption needs on the local transcript path, and keep
singability, pitch, timing, and musical decisions gated by EPRS context and
human listening. Do not use agy for private, unlisted, or login-walled videos;
never ask for full lyrics or transcripts. Record the public URL, command/model,
date, question, concise findings, and timestamps in the lyric research notes,
then preserve the source boundary with `eprs research add` when applicable.

## Create alternatives

```bash
cp templates/lyrics.json songs/signal-garden/code/porch-light-lyrics.json
# Replace every placeholder. Remove `work` for standalone development, or bind
# it to the exact completed lyric-work run that produced the variants.
./scripts/eprs lyrics add songs/signal-garden/code/porch-light-lyrics.json \
  --song songs/signal-garden
```

`eprs.lyrics/v1` contains:

- intent, language, point-of-view/voice context, and explicit preserve/avoid
  boundaries;
- zero or more role-labeled, checksummed source files with rights notes;
- one to 100 variants with exact text, role, intent, cited source IDs,
  singability notes, and unresolved questions; and
- an optional completed work-run origin with checksummed result evidence.

Completed origins use the same `eprs.completed-work-origin/v1` verifier as
research artifacts, so the selected request, run decision, and results remain
consistent while an unrelated later recurring run may still be appended.

At least one source or completed work origin is required. Files already under
immutable raw recording intake remain song references; other sources are copied
under the lyric record. Original files are never rewritten. References may
inform an abstract relationship, but do not paste or imitate protected lyrics,
distinctive imagery, rhyme, meter, melody, or narrative.

The deterministic `eprs.lyric-development/v1` lands under:

```text
songs/<song>/notes/lyrics/<title>-<development-id>/
  lyrics.json
  sources/                 # only for copied non-raw sources
```

Re-running the same spec returns the same record and preserves its accumulated
reviews.

## Review by reading and singing

Every variant begins as `not-reviewed`. Read it aloud and, when possible, sing
it beside the actual performance before recording a decision:

```bash
./scripts/eprs lyrics review <lyrics-directory> \
  --song songs/signal-garden \
  --variant open-door \
  --decision keep \
  --listening-note "Sang the full refrain beside guitar; the last vowel leaves the family breath open."
```

Decisions mean:

- `keep`: this variant should continue into a musical experiment;
- `alternate`: preserve it as a meaningful option or creative fork;
- `stop`: retain it as history but do not let it drive the next experiment.

Several variants may be kept. A decision updates only review metadata; exact
source and variant text remain immutable. Re-review appends a new note, so a
choice can change after it is actually sung. The record becomes review-complete
only when every variant has a note. A local lock prevents concurrent reviewers
from silently overwriting one another; inspect before removing a stale lock
left by a confirmed crash.

## Connect work and music

For an agent-led lyric pass:

1. Queue a plan step or ordinary `lyrics` work item.
2. Have the agent return a filled `eprs.lyrics/v1` spec while preserving
   meaningful alternatives.
3. Finish the work run with that spec as result evidence.
4. Set the spec's `work.item` and `work.run`, then use `lyrics add`.
5. Read or sing each variant and record its explicit review.
6. Freeze kept variants into one small musical experiment with the real vocal
   or instrumental context; never treat the text record as a performance.

## Continuity

```bash
./scripts/eprs lyrics show <lyrics-directory> --song songs/signal-garden
./scripts/eprs status songs/signal-garden --verify
./scripts/eprs context songs/signal-garden --verify --format markdown
```

Status counts sources, variants, pending and reviewed decisions, complete
records, completed-work origins, and drift. Context includes bounded private
text, voice and singability intent, unresolved questions, decisions, and notes,
but never embeds a sung recording or copied source file.
