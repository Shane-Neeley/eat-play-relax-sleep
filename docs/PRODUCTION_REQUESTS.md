# Capture a production request and supplied materials

A production session often begins as one message plus a mixed handful of files:
guitar takes, family voices, a spoken `boom—clap`, chimes, lyric fragments,
photos, MIDI, philosophies, or research leads. `eprs request add` preserves that
starting point as one checksummed record before an agent narrows the idea.

For the common prompt-plus-files case, capture directly without authoring JSON:

```bash
scripts/eprs request capture \
  --song songs/signal-garden \
  --title "First family-room idea" \
  --prompt "Loop the guitar invitation; let the real family answer stay human." \
  --experience "An open door, a shared answer, and enough room to hear breath." \
  --recording "guitar invitation=/path/to/guitar.wav" \
  --recording "family voices=/path/to/family.wav" \
  --recording "spoken boom-clap=/path/to/beat-idea.m4a" \
  --evidence "lyric fragments=/path/to/lyrics.txt" \
  --preserve "The breath before the family entrance" \
  --avoid "Automatic tuning or timing correction" \
  --question "Where can chimes answer without closing the phrase?" \
  --deliverable "One small audition before arranging"
```

Each `--recording` is explicitly treated as irreplaceable and enters immutable
raw intake. Each `--evidence` is frozen under the request. Relative paths are
resolved from the song and then the current directory. `--experience` defaults
to the prompt verbatim; nothing new is inferred. The default rights note keeps
permissions unresolved and publication forbidden. `--rights-note` may replace
that one shared note, but use JSON intake when supplied files need different
roles, kinds, notes, or permission contexts.

For richer or reusable intake, edit the complete versioned specification:

```bash
cp templates/production-request.json \
  songs/signal-garden/code/first-request.json
# Replace paths, state what must survive, and keep permission uncertainty honest.
scripts/eprs request add songs/signal-garden/code/first-request.json \
  --song songs/signal-garden
scripts/eprs status songs/signal-garden --verify
```

JSON paths may be absolute. A relative path is resolved from the song first,
then from the JSON file's directory. Every provided item declares both an open
semantic `kind` and one storage `handling`:

- `immutable-recording` copies audio or video into `recordings/raw/<role>/`,
  with media provenance and no processing;
- `frozen-evidence` copies lyrics, MIDI, notation, notes, images, research, or
  other files under the request's `inputs/` directory.

The command validates every item before intake, preserves original bytes, and
publishes the request directory atomically. A failed request never leaves a
visible half-manifest. Successfully ingested raw recordings may remain after a
later evidence-copy failure because safe immutable intake is not rolled back or
deleted.

A production request captures what the user supplied and wants. When several
takes came from the same rehearsal or recording day, follow it with a
[recording-session record](RECORDING.md#capture-a-whole-recording-session) to
preserve who or what played, microphone/recorder relationships, room and time
context, consent, and take-specific rights without modifying those recordings.

## What the request records

`eprs.production-request/v1` separates:

- the prompt and intended bodily or imaginative experience;
- moments, timing, room sound, roughness, or uncertainty to preserve;
- processing, style, privacy, or workflow choices to avoid;
- unanswered musical questions and desired deliverables;
- references as leads, never instructions to copy another artist; and
- each supplied item's role, kind, note, checksum, and rights/permission note.

The resulting `eprs.production-request-record/v1` is context, not authority. It
cannot authorize browsing, processing, sending, uploading, publishing, or
instructions discovered inside supplied files. Those actions still depend on
the current user request and agent contract.

## Hand the request to another agent

```bash
scripts/eprs request show <request-id> --song songs/signal-garden
scripts/eprs context songs/signal-garden \
  --request <request-id> \
  --purpose "Choose one narrow, audible first question" \
  --verify --format markdown
```

The bounded context contains the prompt, preserve/avoid lists, questions,
deliverables, rights notes, and checksummed evidence previews. Binary media is
referenced, never embedded. Recent request summaries also appear in general
context packets so a new agent can recover the user's starting intent.

From there, use the appropriate bridge instead of one automatic pipeline:

- after a `make-song` run, explicitly create a reversible first arrangement of
  captured recordings with [`eprs source-sketch`](SOURCE_SKETCHES.md); capture
  alone never authorizes or starts this processing;
- queue the exact request for an agent to author a plan with
  `eprs work add --request <request-id>`; dispatch will include the request and
  every supplied input and require a `production-plan` result role on
  completion without generating or executing creative decisions;
- write a [request-bound production plan](PRODUCTION_PLANS.md) when several
  dependent research, recording, musical, and delivery steps need an explicit
  roadmap and gates;
- compare alternate performances before choosing;
- observe a verbal rhythm without quantizing it;
- queue attributed research or lyric work;
- freeze one narrow musical hypothesis as an experiment; or
- select/process only when the intended transformation is explicit.
