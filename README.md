# Eat Play Relax Sleep

A local-first creative operating system where agents and musicians can write code, run audible experiments, preserve source recordings, develop songs, visualize rhythm, and prepare finished media without turning one tool into a bottleneck.

The public repository contains playable BeatScript studies, reusable creative templates, an interactive browser Beat Lab, safe recording intake, experiment lineage, SVG rhythm maps, audio analysis, and a YouTube-ready FFmpeg adapter.

It also includes a [promptable audio-reactive visual engine](docs/VISUALS.md): custom seeded SVG worlds rendered through Remotion, with natural-language score compilation and per-render provenance—no faces or stock footage required.
The visual-method research ranking lives in [VISUAL_METHODS.md](docs/VISUAL_METHODS.md).
The current local-model and Suno collaboration ranking lives in
[AI_GENERATION.md](docs/AI_GENERATION.md).

## Start in five minutes

```bash
./scripts/eprs doctor
./scripts/eprs doctor --workflow source-to-master --strict
./scripts/eprs doctor --workflow daw-handoff --strict
./scripts/eprs performance # read-only active/orphaned visual-worker check
make check test
# During implementation, use the fast control-plane tier; run `make test`
# before checkpoints because it includes the media-heavy FFmpeg round trips.
make test-fast
./scripts/render_demos.sh
open build/demos/porchlight-pocket.wav
make studio             # then open http://localhost:8000
make visuals-install
./scripts/eprs doctor --workflow full-local-production --strict
./scripts/eprs adapter list --available --workflow full-local-production
make visual-studio      # interactive Remotion preview
```

Generated demos land in ignored `build/demos/`; source compositions remain small text files in Git.

`doctor` reads the versioned [`config/toolchain.json`](config/toolchain.json)
registry and reports resolved tools, versions, capabilities, and installation
hints without changing the machine. Use `./scripts/eprs doctor --strict` in
onboarding or automation when missing core requirements should fail the check.
Use repeatable `--workflow` profiles or `--capability` requirements to ask
whether a specific task is ready. Profiles resolve through capabilities rather
than preferred application names, so a new compatible provider can replace an
older one without rewriting song data or scheduler logic. New adapters can
extend the registry without hard-coding detection logic. Drop-in
`eprs.software-adapter/v1` profiles then teach people and agents how an installed
tool should receive and return portable work without starting it or enabling
control. V2 production-plan steps can declare exact capabilities; focused
context reports non-ranking adapter fit, and dispatch releases a claim when a
declared capability is missing or unknown. See [toolchain and environment checks](docs/TOOLCHAIN.md) and
[software adapter profiles](docs/ADAPTERS.md).

Machine-specific applications and private paths belong in the automatically
discovered, Git-ignored `.eprs-local/` directory. Start from
`templates/toolchain-extension.json` and `templates/software-adapter.json`;
local extensions are additive and cannot shadow shared providers or make a
private tool mandatory.

`eprs performance` is the read-only “is it actually stuck?” check. It reports
only EPRS-owned Remotion/Chromium processes, separates active workers from
orphaned browser roots, applies a configurable stale threshold, and can include
recent song visual-render timings with `--song`. It never stops a process.

## Make a song

`songs/` is a private-by-default local workspace. Git ignores everything created there except its policy README. Publishable teaching material should be deliberately copied into `examples/` only after checking rights, credits, personal information, and file size.

For the shortest path, let the harness create the workspace, capture supplied
material, queue agent planning, render a seeded sketch, make a rhythm map, and
try an 8-second visual preview:

```bash
./scripts/eprs make-song "Signal Garden" \
  --prompt "A loose guitar invitation answered by family voices; warm, human, and slightly crooked" \
  --recording "guitar=/path/to/guitar.wav" \
  --recording "family voices=/path/to/family.wav" \
  --evidence "lyric fragments=/path/to/lyrics.txt" \
  --reference "https://example.com/a-reference" \
  --preserve "room sound and the breath before the answer" \
  --avoid "automatic tuning and quantization"
```

The command uses fresh OS entropy by default, so repeated prompts produce new
variations. It writes `songs/signal-garden/NOW.md` as the shallow handoff and a
portable Graphviz production map beside the run manifest. Use
the recorded seed for an exact replay, or add a new run to an existing song:

```bash
./scripts/eprs make-song --song songs/signal-garden \
  --prompt "Keep the guitar, but make the answer more sparse" --seed <seed>

# Rebuild the latest request-to-output map; DOT always works and SVG is optional.
./scripts/eprs map songs/signal-garden
```

The starter render deliberately does not touch supplied recordings. Continue
explicitly when you want to hear those immutable sources in a reversible first
arrangement:

```bash
./scripts/eprs source-sketch songs/signal-garden \
  --shape call-response \
  --intent "Let the guitar invite; family voices answer after the room breathes."
```

This writes an editable mix score, float working mix, checksummed source-sketch
record, updated production map, and shallow `_LISTEN.wav`/`NOW.md` handoff. It
uses fresh entropy by default for role-aware entrances and conservative
no-boost balance/pan choices; pass `--seed` to replay a pass. It does not tune,
quantize, denoise, normalize, compress, limit, or time-stretch a performance.
Choose `--shape one-pass`, `call-response`, or `loop` explicitly; prompt text
never silently authorizes repetition or excerpting, and every occurrence stays
visible in the editable mix score.
See [source-aware sketches](docs/SOURCE_SKETCHES.md).

The harness does not browse, download, upload, or publish. Supply a local
downloaded video as a `--recording` when its audio should be preserved, and put
the source URL in `--reference` for an agent to research under the normal
request/work evidence rules.

```bash
./scripts/eprs new "Signal Garden"
cp templates/creative-brief.md songs/signal-garden/briefs/v1.md
./scripts/eprs status songs/signal-garden

./scripts/eprs experiment \
  --song songs/signal-garden \
  --beat examples/beats/porchlight-pocket.beat \
  --brief songs/signal-garden/briefs/v1.md \
  --hypothesis "The second-bar kick answer leaves room for a guitar pickup" \
  --seed 23

./scripts/eprs render examples/beats/porchlight-pocket.beat \
  --out songs/signal-garden/experiments/pocket-v1.wav
./scripts/eprs analyze songs/signal-garden/experiments/pocket-v1.wav

./scripts/eprs finish songs/signal-garden/experiments/<experiment-id> \
  --result songs/signal-garden/experiments/pocket-v1.wav \
  --listening-note "The guitar pickup has space; the second bar answers rather than repeats." \
  --decision keep

# Return later—or hand the project to another agent—and recover the state.
./scripts/eprs status songs/signal-garden
```

`status` is read-only. It summarizes sources, experiments, production files, and
final deliverables; flags missing manifests or result evidence; and suggests the
next safe action. Add `--json` when another agent or automation should consume
the versioned `eprs.status/v1` report. Add `--verify` before a consequential
handoff to hash raw recordings, frozen inputs, and results and detect drift.

Give another person or agent a bounded, evidence-aware handoff:

```bash
./scripts/eprs context songs/signal-garden \
  --purpose "Render the smallest audible answer and preserve human timing" \
  --work <work-id> --work-run 1 \
  --experiment <experiment-id> \
  --verify --format markdown \
  --out songs/signal-garden/notes/context/next-agent.md
```

The `eprs.agent-context/v1` packet includes creative intent, current status,
focused evidence previews, due work, recent experiments and performance
comparison decisions, recent comp/processing notes, guardrails, and tool
capabilities under an explicit text budget. It never embeds binary media,
launches an agent, broadens authorization, or uploads the private packet. See
[bounded agent context](docs/AGENT_CONTEXT.md).

## Start from one prompt and a folder of ideas

After creating the song workspace, capture what you want and everything you are
providing before an agent starts making production choices:

```bash
./scripts/eprs new "Signal Garden"
./scripts/eprs request capture \
  --song songs/signal-garden \
  --title "First prompt and supplied ideas" \
  --prompt "Loop the guitar invitation and let the family answer remain human." \
  --recording "guitar invitation=/path/to/guitar.wav" \
  --recording "family voices=/path/to/family.wav" \
  --recording "spoken boom-clap=/path/to/beat-idea.m4a" \
  --evidence "lyric fragments=/path/to/lyrics.txt" \
  --preserve "Breath, overlap, room sound, and performed timing" \
  --avoid "Automatic tuning or quantization" \
  --question "Where can chimes answer without closing the phrase?"
# Let an agent author the roadmap from the exact prompt and supplied files.
./scripts/eprs work add --song songs/signal-garden --request <request-id>
./scripts/eprs dispatch next --song songs/signal-garden --agent planning-agent
# Finish the work with the authored v2 plan as `production plan` result evidence,
# then validate the exact frozen result and preserve agent/run provenance.
./scripts/eprs plan accept-work <work-id> \
  --song songs/signal-garden --result production-plan
# Inspect dependency state, then queue only one unstarted actionable step;
# request inputs named by that step are inherited.
./scripts/eprs plan progress <plan-id> --song songs/signal-garden
./scripts/eprs plan queue-next <plan-id> --song songs/signal-garden
./scripts/eprs context songs/signal-garden --request <request-id> \
  --purpose "Choose one narrow, audible first question" --verify --format markdown
```

To author the roadmap manually instead of through agent work:

```bash
cp templates/production-plan.json songs/signal-garden/code/production-plan.json
# Bind the template to the captured request and rewrite its steps and gates.
./scripts/eprs plan add songs/signal-garden/code/production-plan.json \
  --song songs/signal-garden
```

Recordings enter immutable raw intake; lyrics, MIDI, notes, images, and other
evidence are frozen with checksums. Capturing the request never authorizes an
agent to browse, process, upload, or publish. The optional request-bound plan is
an immutable dependency map, not an executor or approval record. See
[production-request intake](docs/PRODUCTION_REQUESTS.md) and [production
plans](docs/PRODUCTION_PLANS.md).

`request capture` is the low-friction path and deliberately asks the caller to
classify each file as a recording or evidence. Use the complete
`templates/production-request.json` plus `request add` when files need distinct
kinds, notes, or rights/permission statements.

`plan accept-work` is the agent-first continuation: it accepts only completed
request-origin work whose frozen result is a valid v2 plan for that exact
request, then records an append-only acceptance receipt. It does not execute the
plan or imply that any consent, listening, technical, upload, or publication
gate is satisfied.

## Queue research, lyrics, and recurring agent work

Capture work that informs the song but is not yet an audio experiment:

```bash
./scripts/eprs work add \
  --song songs/signal-garden \
  --title "Research family call-and-response" \
  --kind "YouTube research" \
  --prompt "Find three performance relationships we can discuss without copying an arrangement; preserve links and uncertainty." \
  --require-result research-record \
  --reference "family group singing" \
  --source "lyric fragments=notes/porch-light-fragments.txt"

./scripts/eprs work list --song songs/signal-garden --due
./scripts/eprs dispatch next --song songs/signal-garden --agent research-agent
# The agent fills this attributed schema and sets work.item/run to this claim.
cp templates/research.json /tmp/research.json
./scripts/eprs work finish <work-id> \
  --song songs/signal-garden \
  --summary "Captured attributed observations and two experiment ideas." \
  --decision complete \
  --result "research record=/tmp/research.json"

# Freeze attributed sources, observation versus interpretation, uncertainty,
# copying boundaries, and the smallest original experiment ideas.
./scripts/eprs research add /tmp/research.json --song songs/signal-garden

# Preserve exact lyric alternatives, then review each by reading or singing it.
./scripts/eprs lyrics add /tmp/lyrics.json --song songs/signal-garden
./scripts/eprs lyrics review <lyrics-id> --song songs/signal-garden \
  --variant <variant-id> --decision alternate \
  --listening-note "What this version contributes when read or sung in context."

# Turn the useful findings into one audible question.
./scripts/eprs work promote <work-id> \
  --song songs/signal-garden \
  --hypothesis "Can one chime answer the family phrase without closing the guitar cadence?" \
  --seed 23
```

Work items preserve prompts, local source evidence, ownership, run history, and
checksummed results. Optional repeatable `--require-result` slugs define which
role-labeled files must be present before `decision=complete` can change the
work item; additional evidence is allowed, and follow-up/stop outcomes can
still preserve diagnostic results. V2 plan steps can carry the same contract
with `required_result_roles`. Default request-planning work automatically
requires `production-plan`. `--cadence daily` or `weekly` makes completion schedule the
next future run; an external agent runner still has to query, claim, perform,
and finish due work explicitly. `dispatch next` atomically chooses due work and
prepares verified bounded context; preparation failures are released with a
preserved reason. A ready owner that cannot continue uses `work release` with a
reason. Claims never expire or transfer silently. Promotion
freezes a completed request, its sources, and its result evidence into a normal
musical experiment; future
recurring runs cannot rewrite those inputs. The queue never browses, schedules
itself, uploads, or publishes. `research add` also never browses or downloads;
it normalizes supplied research and optionally freezes local evidence. See
[agent work and recurring requests](docs/AGENT_WORK.md) and [attributed research
records](docs/RESEARCH_RECORDS.md). See [source-bound lyric
development](docs/LYRICS.md) for variant preservation and review.

## Find the final output

Open any song and review the top-sorted `_LISTEN.wav`, `_WATCH.mp4`, and
`_CHANGE_ME.md` first. These are relative symlinks to the current canonical
media, so they do not duplicate large files or erase provenance. After making a
new version, an agent can update them explicitly:

```bash
./scripts/eprs expose --song songs/signal-garden \
  --audio mixes/new-version.wav --video video/new-version.mp4 \
  --label "Bass and second-verse revision" --status review
```

`_CURRENT.json` records the exact targets and checksums. Root pointers are for
fast review; only approved packages in `FINAL/` are release handoffs.

Every new song gets a `songs/<name>/FINAL/` folder. This is the single handoff
location for atomic YouTube or distributor packages whose media passed
technical checks and creative approval:

```text
songs/signal-garden/FINAL/
  signal-garden-<release-id>/
    signal-garden-master.wav
    signal-garden-youtube.mp4
    youtube-metadata.json
    HANDOFF.md
    release.json
```

Drafts and experiments stay in `experiments/`, audition mixes in `mixes/`,
lossless working masters in `masters/`, and video work files in `video/`. Use
`eprs release` to copy approved bytes without moving or overwriting their
editable sources. Nothing in `FINAL/` is uploaded automatically. See [the
delivery workflow](docs/DELIVERY.md).

Prepare a separate Spotify/Apple Music distributor handoff without requiring a
video or contacting a platform:

```bash
cp templates/distribution.json songs/signal-garden/code/distribution.json
./scripts/eprs distribution songs/signal-garden/code/distribution.json \
  --song songs/signal-garden
```

This verifies an approved lossless master, 3000×3000-or-larger square artwork,
metadata, a human rights confirmation, and public clearance for traced raw
performances. The resulting `FINAL/*-dsp-*/` directory still requires a
separately authorized distributor submission. See [streaming distribution
handoffs](docs/DISTRIBUTION.md).

Prepare a checksum-bound input contract for a future separately authorized
uploader without contacting YouTube:

```bash
./scripts/eprs publication prepare \
  songs/signal-garden/FINAL/<release-directory> \
  --song songs/signal-garden
```

After an authorized external uploader returns the actual video ID, URL,
visibility, and timestamps, preserve that state with `publication receipt`.
FINAL remains immutable and unpublished in its own manifest; external state is
append-only history. See [offline publication handoffs](docs/PUBLICATION.md).

## Bring in a live or field recording

```bash
./scripts/eprs ingest /path/to/take.wav \
  --song songs/signal-garden \
  --role guitar \
  --note "Dynamic microphone, edge of speaker, room ambience, no click"

# For a multi-person or multi-microphone recording day:
cp templates/recording-session.json songs/signal-garden/code/recording-session.json
# Fill in honest take paths, capture chains, participant/consent context, and rights notes.
./scripts/eprs session add songs/signal-garden/code/recording-session.json \
  --song songs/signal-garden

./scripts/eprs experiment \
  --song songs/signal-garden \
  --brief songs/signal-garden/briefs/v1.md \
  --source "guitar=songs/signal-garden/recordings/raw/guitar/<take>.wav" \
  --source "lyrics=notes/porch-light-fragments.txt" \
  --hypothesis "Can the vocal enter before the guitar loop resolves?" \
  --seed 23
```

`ingest` copies one take into immutable raw storage, hashes it, probes it, and
writes a provenance sidecar. `session add` validates a whole recording day
before intake, deduplicates or references its raw takes, and atomically records
performer roles, capture setups, time/tuning context, consent, and rights.
Neither command moves or processes a source. Read [the recording
workflow](docs/RECORDING.md) before editing irreplaceable takes.

`--role` is deliberately broader than “instrument”: it can be `family voices`,
`boom-clap beat idea`, `chimes`, `room sound`, or any useful description. The
older `--instrument` spelling remains an alias for existing scripts.

Select a phrase or make a literal performance loop without changing its speed,
pitch, internal timing, or dynamics:

```bash
./scripts/eprs select /path/to/guitar-line.wav \
  --song songs/signal-garden \
  --role "guitar loop" \
  --start 12.4 --duration 3.2 --repeat 4 \
  --crossfade-ms 8 \
  --note "Keep the pick attack and the breath before beat one"
```

External input is ingested automatically before selection. The lossless result
and versioned recipe land under `recordings/selected/`; raw input remains
untouched. Crossfade is opt-in because a hard boundary or audible seam may be
part of the performance. See [audio selections](docs/SELECTIONS.md).

Turn a verbal `boom—clap` performance into timing evidence a drummer or agent
can discuss without forcing it onto a grid:

```bash
./scripts/eprs rhythm /path/to/boom-clap.m4a \
  --song songs/signal-garden \
  --role "spoken pocket" \
  --note "Boom is the low gesture; clap is the answer; preserve the push into the last pair"
```

The observation keeps performed attack times, dynamics, cautious timbre hints,
spacing character, and tempo ambiguity. It does not claim a meter, downbeat,
subdivision, or kick/snare mapping. See [performed rhythm
observations](docs/RHYTHM.md).

After listening, author one explicit drummer-facing interpretation and render
the smallest synthetic audition without changing the performance:

```bash
cp templates/groove.json songs/signal-garden/code/groove.json
./scripts/eprs groove add songs/signal-garden/code/groove.json \
  --song songs/signal-garden

# After comparing the complete prototype with the spoken/played source:
./scripts/eprs groove review songs/signal-garden/notes/grooves/<title>/<id> \
  --song songs/signal-garden --decision keep \
  --listening-note "The low-high exchange and open space preserve the performed idea."
```

Every observed attack must be mapped, marked as a pickup, or intentionally
omitted. The record retains player language, alternative pulse/free-time
hearings, and performed-minus-grid timing instead of treating expressive timing
as error. See [drummer-facing groove development](docs/GROOVE.md).

Before processing or mixing two microphones, measure one explicit relationship
without “fixing” either performance:

```bash
./scripts/eprs phase \
  recordings/raw/family-close/<take>.wav \
  recordings/raw/family-room/<take>.wav \
  --song songs/signal-garden \
  --role-a "family close microphone" --role-b "family room microphone" \
  --intent "Hear whether the room supports the phrase in stereo and mono" \
  --duration 8
```

The JSON report compares bounded timing, correlation, and mono-sum evidence,
but never delays, aligns, polarity-inverts, or renders the microphones. Listen
to the unchanged sources before making a creative decision. See
[two-microphone timing and polarity evidence](docs/PHASE.md).

When that observation—or research, session context, a comparison, or a private
listening note—actually changes a processing or mix choice, add it to the
recipe's optional `evidence` list with its song-relative path and a sentence
explaining its use. The render checksum-binds the exact file and later review
refuses drift. See [decision evidence bindings](docs/EVIDENCE_BINDINGS.md).

Compare performances without aligning waveforms or letting level decide which
one is “best”:

```bash
cp templates/performance-compare.json songs/signal-garden/code/guitar-takes.json
./scripts/eprs compare songs/signal-garden/code/guitar-takes.json --song songs/signal-garden
./scripts/eprs compare-review songs/signal-garden/notes/comparisons/guitar-answer-takes/<report>.json \
  --song songs/signal-garden --take guitar-take-one --decision keep \
  --listening-note "The gathering motion sets up the family entrance."
```

Reports expose phrase shape, attack spacing, dynamics, and both audition
orders, but never an automatic winner. See [performance-aware take
comparison](docs/PERFORMANCE_COMPARISON.md).

Assemble chosen phrases into one reversible performance stem without corrective
processing:

```bash
cp templates/comp.json songs/signal-garden/code/family-comp.json
./scripts/eprs comp songs/signal-garden/code/family-comp.json --song songs/signal-garden
./scripts/eprs comp-review songs/signal-garden/stems/family-voices/family-answer-comp/<comp>.wav \
  --song songs/signal-garden --decision keep \
  --listening-note "The joins disappear into the room, and the breath still feels intentional."
```

Every selected phrase and every cut, silence, or opt-in crossfade needs a
musical reason. No tuning, quantizing, denoising, normalization, compression,
limiting, or time-stretching is inserted. See [reversible performance
comping](docs/COMPING.md).

Turn a selected performance into a reversible float working stem with only the
processing the recipe names:

```bash
cp templates/process.json songs/signal-garden/code/family-voices.json
# Edit the song-relative source, player-facing intent, and explicit controls.
./scripts/eprs process songs/signal-garden/code/family-voices.json \
  --song songs/signal-garden
./scripts/eprs process-review songs/signal-garden/stems/family-voices/...wav \
  --song songs/signal-garden --decision keep \
  --listening-note "Clearer beside guitar; the shared room still feels intact."
```

Every operation needs a musical reason. Gain, filters, EQ, fades, echo, and an
opt-in compressor are available; tuning, denoising, normalization, limiting,
automatic gain control, and time-stretching are never inserted. See
[reversible stem processing](docs/PROCESSING.md).

Experiments are not limited to BeatScript. Repeat `--source ROLE=PATH` to freeze
performances, spoken beat ideas, chimes, MIDI, lyrics, research notes, images,
or any other file needed to answer one hypothesis. See [the experiment
workflow](docs/EXPERIMENTS.md).

Arrange selected performances into a reversible working mix:

```bash
cp templates/mix.json songs/signal-garden/code/first-mix.json
# Edit paths, placement, intent, gain, pan, and fades in the JSON score.
./scripts/eprs mix songs/signal-garden/code/first-mix.json \
  --song songs/signal-garden
./scripts/eprs mix-review songs/signal-garden/mixes/<title>/<mix>.wav \
  --song songs/signal-garden --decision keep \
  --listening-note "Listened end to end; balance, headroom, entrances, decay, and silence are intentional."
./scripts/eprs status songs/signal-garden --verify
```

Mixes render as 32-bit float WAV so overlapping sources retain headroom rather
than clipping. The renderer reports over-zero peaks for explicit correction and
does not normalize, compress, limit, tune, or stretch performances. Mastering
refuses a mix until `mix-review` records a complete-listen `keep` decision. See
[declarative mixing](docs/MIXING.md).

Move the exact arrangement into another DAW or audio tool without rebuilding
its timeline by hand:

```bash
./scripts/eprs interchange prepare \
  songs/signal-garden/mixes/<title>/<mix>.wav \
  --song songs/signal-garden
./scripts/eprs interchange verify \
  songs/signal-garden/interchange/<title>-<package-id> \
  --song songs/signal-garden

# After an external pass, declare the tool, decisions, unknowns, rights, and
# any added song-local recordings; returned_mix must be lossless.
cp templates/daw-return.json songs/signal-garden/code/daw-return.json
./scripts/eprs interchange return songs/signal-garden/code/daw-return.json \
  --song songs/signal-garden
```

The self-contained package has one common-start stereo float WAV per arranged
track, an exact reference-mix copy, provenance snapshot, and decoded-sample
proof that summing the stems reproduces the mix. A return copies lossless bytes
unchanged, binds them to that package, records external decisions and unknowns,
and re-enters the normal mix-review gate. It adds no normalization, alignment,
tuning, compression, or authority. See [DAW-neutral
interchange](docs/DAW_INTERCHANGE.md).

Create a deliberate lossless master only after the working mix is ready:

```bash
cp templates/master.json songs/signal-garden/code/lossless-master.json
# Point source at the chosen float mix; set explicit gain and peak ceiling.
./scripts/eprs master songs/signal-garden/code/lossless-master.json \
  --song songs/signal-garden

# After listening to the complete rendered master:
./scripts/eprs master-approve songs/signal-garden/masters/<title>/<master>.wav \
  --song songs/signal-garden \
  --listening-note "Listened end to end; balance, dynamics, fades, and silence are approved."
```

The peak ceiling is a refusal guard, not a limiter or normalization target. A
master that would exceed it fails until the recipe declares a safe gain. See
[lossless mastering](docs/MASTERING.md).

Prepare a YouTube listening video only from that approved master:

```bash
cp templates/youtube.json songs/signal-garden/code/youtube.json
# Set the approved master path, title, and visual intent in the JSON recipe.
./scripts/eprs youtube songs/signal-garden/code/youtube.json \
  --song songs/signal-garden

# After watching the complete render and checking audio sync:
./scripts/eprs youtube-approve \
  songs/signal-garden/video/youtube/<title>/<video>.mp4 \
  --song songs/signal-garden \
  --review-note "Watched end to end; title, first/last frames, and sync are approved."
```

The renderer verifies H.264/AAC, yuv420p/BT.709, duration, and fast start, then
records provenance beside the MP4. It does not copy to `FINAL/`, upload, or
publish. See [YouTube delivery](docs/VIDEO.md).

Prepare and separately review the upload-facing assets for that exact video:

```bash
cp templates/youtube-assets.json songs/signal-garden/code/youtube-assets.json
# Author the thumbnail path, alt text, caption cues, chapters, and accessibility note.
./scripts/eprs youtube-assets add \
  songs/signal-garden/code/youtube-assets.json \
  --song songs/signal-garden
./scripts/eprs youtube-assets review \
  songs/signal-garden/video/youtube-assets/<title>/<bundle-id> \
  --song songs/signal-garden \
  --review-note "Checked the small thumbnail, every caption cue, every chapter, and accessibility context."
```

The bundle preserves the thumbnail unchanged, emits plain UTF-8 SubRip and
chapter files, and keeps upload authority false. See
[YouTube publishing assets](docs/YOUTUBE_ASSETS.md).

Package the fully approved master and video with credits, rights notes, and
proposed YouTube metadata—still without uploading or publishing:

```bash
cp templates/recording-clearance.json \
  songs/signal-garden/code/private-clearance.json
# Confirm exact take/participant decisions, credit wording, and visibility limit.
./scripts/eprs clearance add songs/signal-garden/code/private-clearance.json \
  --song songs/signal-garden

cp templates/release.json songs/signal-garden/code/release.json
# Point clearances at every approved record needed by the traced raw takes.
./scripts/eprs release songs/signal-garden/code/release.json \
  --song songs/signal-garden
./scripts/eprs status songs/signal-garden --verify
```

The atomic `FINAL/` directory includes checksum-bound media copies,
`HANDOFF.md`, `youtube-metadata.json`, copied session/clearance evidence, and an
`eprs.release-package/v1` manifest. Release traces the master to its raw takes
and refuses missing, pending, too-narrow, or credit-mismatched clearance. See
[local FINAL release packages](docs/RELEASES.md).

## BeatScript

Launch the interactive studio with `make studio`, then open <http://localhost:8000>. Its **Kids studio** toggle turns the same real sequencer into Creature Beat Club: tap friendly ghost, owl, frog, cat, robot, dinosaur, magic, and thunder sound pads; build spooky or animal loops; then copy the result as ordinary BeatScript.

```beat
tempo 94
meter 4/4
resolution 16
swing 0.54
track kick  | X... ..x. .... x... |
track snare | .... X.g. .... X... |
```

`X` is an accent, `x` a normal hit, `g` a ghost, and `.` a rest. The language stays close enough to drummer counts to discuss feel and precise enough to render deterministically. Learn it in [BeatScript](docs/BEATSCRIPT.md), then explore:

```bash
./scripts/eprs mutate examples/beats/porchlight-pocket.beat --seed 99 --amount .08 --out /tmp/variation.beat
./scripts/eprs render /tmp/variation.beat --out /tmp/variation.wav
./scripts/eprs visualize /tmp/variation.beat --out /tmp/variation.svg
```

## Make a funky promptable visual

```bash
./scripts/eprs visual-prompt \
  "Acid tape ribbons fold around the guitar; kick recoils the room; silence turns the image to dust" \
  --title "Signal Garden" --seed 23 \
  --out songs/signal-garden/visuals/v1.json

./scripts/eprs visual-render songs/signal-garden/visuals/v1.json \
  --audio songs/signal-garden/masters/signal-garden.wav \
  --quality full --out songs/signal-garden/video/signal-garden.mp4

# Preserve and review this output (or any other renderer/editor output).
cp templates/picture.json songs/signal-garden/code/picture.json
./scripts/eprs picture add songs/signal-garden/code/picture.json \
  --song songs/signal-garden
./scripts/eprs picture review songs/signal-garden/video/pictures/<title>/<picture>.mp4 \
  --song songs/signal-garden --decision keep \
  --review-note "Watched every frame; visual arrangement and time-zero intent are keepers."

# Stream-copy reviewed picture and replace all guide audio with the approved master.
cp templates/youtube-picture.json songs/signal-garden/code/youtube-picture.json
./scripts/eprs youtube songs/signal-garden/code/youtube-picture.json \
  --song songs/signal-garden
```

See [renderer-neutral picture handoff](docs/PICTURE.md). The capture contract is
not tied to Remotion: editors, DAW video lanes, live-visual recorders, and future
agent tools can provide the same preserved picture/evidence handoff.

## System map

```text
.agents/skills/       project-local reusable agent workflows
examples/beats/       small contrasting rhythm studies
examples/songs/       deliberately publishable project examples
src/eprs/             dependency-free production CLI
studio/               interactive Web Audio Beat Lab
visuals/              Remotion + custom TypeScript visual renderer
templates/            briefs and experiment contracts
songs/<name>/         local creative work; ignored by Git
  README.md           song entry point and current handoff map
  briefs/             musical intent and delivery target
  code/               BeatScript, Sonic Pi, MIDI/code sources
  experiments/        frozen inputs, hypothesis, result, decision
  recordings/raw/     immutable originals + provenance sidecars
  recordings/selected editable working selections
  stems/ mixes/ interchange/ masters/ video/ visuals/ notes/
  FINAL/              approved handoff packages only

Open `songs/<name>/README.md` first. For video, `video/README.md` identifies
the source visual, reviewed picture candidates, delivery renders, and previews.
```

Read [the architecture](docs/ARCHITECTURE.md), [toolchain registry](docs/TOOLCHAIN.md), [software adapter profiles](docs/ADAPTERS.md), [production-request intake](docs/PRODUCTION_REQUESTS.md), [source-aware first sketches](docs/SOURCE_SKETCHES.md), [request-bound production plans](docs/PRODUCTION_PLANS.md), [bounded agent context](docs/AGENT_CONTEXT.md), [agent work queue](docs/AGENT_WORK.md), [attributed research records](docs/RESEARCH_RECORDS.md), [source-bound lyric development](docs/LYRICS.md), [audio selections](docs/SELECTIONS.md), [performed rhythm observations](docs/RHYTHM.md), [drummer-facing groove development](docs/GROOVE.md), [two-microphone timing and polarity evidence](docs/PHASE.md), [decision evidence bindings](docs/EVIDENCE_BINDINGS.md), [performance-aware take comparison](docs/PERFORMANCE_COMPARISON.md), [reversible performance comping](docs/COMPING.md), [reversible stem processing](docs/PROCESSING.md), [experiments](docs/EXPERIMENTS.md), [declarative mixing](docs/MIXING.md), [DAW-neutral interchange](docs/DAW_INTERCHANGE.md), [lossless mastering](docs/MASTERING.md), [research and orthogonal directions](docs/RESEARCH.md), [video delivery](docs/VIDEO.md), [renderer-neutral picture handoff](docs/PICTURE.md), [YouTube publishing assets](docs/YOUTUBE_ASSETS.md), [local FINAL release packages](docs/RELEASES.md), [streaming distribution handoffs](docs/DISTRIBUTION.md), [offline publication handoffs](docs/PUBLICATION.md), [the contribution and public-data policy](CONTRIBUTING.md), and [the agent contract](AGENTS.md).

## Tool philosophy

- The standard-library Python core is the reproducible fallback.
- Sonic Pi is the live-code, sample, OSC, and performance surface.
- Audacity is the hands-on recording/editing surface; external scripting is opt-in because its own manual warns about the expanded control boundary.
- FFmpeg/FFprobe are the media interchange, analysis, and delivery layer.
- Native DAW sessions, MIDI, notation, hardware, or future agent tools can be added through the same briefs, immutable sources, and experiment manifests.

Measurements catch clipping, missing streams, wrong sample rates, broken sync, and accidental changes. They do not decide whether a groove breathes.
