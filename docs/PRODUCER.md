# Agentic music production

EPRS coordinates a producer working across musical tools. The agent makes
creative decisions; software renders them; evidence describes what happened.
Daily and on-demand work use the same front door. Production is an opportunity
to make a good song, not a quota to publish anything that renders.

## Start or resume

```sh
./scripts/eprs produce status
./scripts/eprs produce brief --key 2026-09-05
./scripts/eprs new "A New Song"
./scripts/eprs produce start --key 2026-09-05 --owner my-producer \
  --song songs/a-new-song --concept songs/a-new-song/code/concept.json
```

The concept is an object with six nonempty authored fields: `engine`,
`composition`, `groove`, `sound_world`, `form`, and `visual`. Describe actual
methods, not promotional genre labels. `config/producer.json` contains an open
menu of starting lanes and quality questions. It is not a fixed song generator.

`brief` suggests three underused lanes from completed run history. The producer
must check tool availability and choose on musical merit. Historical song
manifests remain important: absent new-run history is unknown, not proof a
method is unused. Favorites are discovered from real album folders, including
nested handoffs that stale album indexes miss. They may illustrate one useful
quality; they are not a style target, reward function, or mandatory comparison.
Explore unfamiliar music as well as developing established strengths.

An atomic filesystem lock serializes state changes on this Mac/Linux workflow.
Only one active production claim exists across schedulers and manual runs.
Duplicate run keys are refused even after completion. The returned owner token
is needed to advance or hold a run. A failed or abandoned run stays visible;
another agent must explicitly hold it with a reason before starting a new run.
There is no silent expiry and no implicit second upload on retry.

## Make the music

1. Form an audience promise and a musical premise. Render two distinct short
   sketches, usually 15–30 seconds, before paying for a complete arrangement.
   Compare the actual artifacts; preserve the alternative and explain the choice.
2. Arrange the winner into a deliberate emotional arc. Default to accessible
   4/4; find diversity in genre, groove, harmony, instrumentation and form rather
   than unusual time signatures. Use the current public daily quote/thought and
   a new iNaturalist animal as daily seeds, then change the actual music. No
   universal four-section, UI panel, shader, or early-drop rule applies.
3. Use the actual tool selected. A Sonic Pi companion file beside a BeatScript
   render is not a Sonic Pi performance. Keep native sources, stems and receipts.
4. Revise the weak section. Check actual audio for clipping, bad joins, unwanted
   silence, masking and mono cancellation. Keep source material immutable.
5. Compose picture to the arrangement. Retain native projects, images, prompts,
   licenses and frame evidence. A different palette cannot substitute for a
   different musical method.

Untreated robotic TTS is not an acceptable vocal deliverable unless explicitly
requested. Write a melody and rhythm, produce singing or deliberately shape
pitch, retain raw/tuned audio and processing evidence, and review the result in
the mix. Autotune is a process, not proof of convincing vocal delivery. Rewrite,
regenerate or omit a failed voice. Instrumentals remain a full creative lane.

SuperCollider now has a bounded native offline route:

```sh
uv run python scripts/render_supercollider.py \
  songs/a-new-song/code/score.scd songs/a-new-song/audio/render-v1.wav
```

The trusted `.scd` script receives the new WAV path as `thisProcess.argv[0]`.
It should call `Score.recordNRT` and exit from its completion callback. The
wrapper refuses existing outputs, enforces a deadline, terminates the process
group, probes the WAV and records input/output checksums. It is execution of
trusted native code, not a sandbox. Sonic Pi, BeatScript, recorded performance,
DAW returns, sample instruments and optional model lanes remain available.

## Advance with evidence

```sh
./scripts/eprs produce advance --key 2026-09-05 --token TOKEN \
  --stage arrange --note "Two sketches rendered; the sparse response leaves room for the refrain." \
  --artifact audio/sketch-a.wav --artifact audio/sketch-b.wav
```

Stages are `sketch → arrange → mix → picture → package → complete`; `hold` is
available from any active stage. Each transition freezes nonempty song-relative
artifacts and verifies all prior evidence has not changed. This is coordination
and audit, not proof of creative quality or authorization. Completion means the
production work is complete, not necessarily published. Publication needs its
own receipt from the platform, including verified visibility and media identity.

Review records must say who or what reviewed which bytes and by which method.
Score analysis, full decoding, measurements, frame sampling, model listening
and human listening are different evidence. Never claim human listening from a
render log or fill an old human-approval field with an agent's technical check.
Honor the current user's authorization for autonomous review/publication; when
their request authorizes an agent-reviewed test, preserve that distinction in
the release notes. Existing human-reviewed EPRS release contracts remain valid.

`produce package --key KEY --token TOKEN --review notes/review.json` supports
an explicitly attributed `eprs.producer-review/v1` record after the package
stage. It requires reviewer/type/method, a keep decision and specific note,
rights and limitations, and checksummed `master` and `video` records. It verifies
prior stage evidence, full decode, 24-bit PCM master, soundtrack presence,
duration agreement and low-band audio correlation against the master. It freezes
a new `eprs.producer-package/v1` under FINAL without inventing old human approvals.
This command never uploads, authorizes publication, or guarantees musical taste.

Declare vocals in the concept as `vocals.mode`: `instrumental`,
`human-performance`, `synthetic-singing`, `processed-synthetic`, or
`spoken-requested`. All vocal modes require a song-relative `vocals.review`
record naming reviewer/method/delivery_note/keep decision and checksummed vocal
and complete-mix context. Processed synthetic speech additionally requires
`vocals.processing` pointing at an actual `eprs.autotune-render/v1` sidecar with
verified raw/output bytes; the review must cover the processed output. Requested
speech requires a preserved `vocals.request_evidence` file. Declarations and
assessments must be truthful; this gate catches missing evidence, not every
possible perceptual defect in a voice.

## Schedulers and learning

Keep scheduler prompts short: repository location, run key/owner, this workflow,
current user authorization, and delivery preferences. Use one daily slot or
non-overlapping ownership days across producers. Both must claim through this
command. On-demand requests use a distinct run key and the same lock.

Separate production from weekly research and channel analysis. Daily work need
not discover a new paper, install a new model, modify the codebase, or publish
to keep a streak. Record a precise hold and repair when appropriate.

For releases, preregister one audience hypothesis and a comparable baseline.
Review at 48 hours and seven days using watch duration, retention, traffic
context and subscriber conversion. Small samples stay inconclusive. Do not
confuse views, engaged views, impressions or click-through rate, or treat a
format change as a controlled title test. Let evidence inform experiments
without dictating every creative choice.

## Regional discovery and workbench briefs

Before daily seed selection, use `docs/WILDLIFE_SCOUT.md` to refresh a bounded
regional shortlist and a sound-specific query when useful. Use the current
request's region, or the operator's saved region. Retain uncertainty, avoid
recently selected taxa, and do not force rare species to have usable audio.
Read exported `eprs.workbench-brief/v1` files as authored production requests;
map their tunable musical, voice, album and picture directions into the concept.
For albums, declare the shared motif and each track's different groove,
instrumentation and form before rendering individual songs.
