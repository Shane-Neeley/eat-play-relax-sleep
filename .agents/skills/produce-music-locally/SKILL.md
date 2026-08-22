---
name: produce-music-locally
description: Create, develop, record, edit, arrange, sound-design, mix, master, visualize, and deliver music locally, using EPRS as the agent-led system of record when this repository is available. Use for songs, instrumentals, parts, beats, live or family recordings, guitar, voice, spoken rhythm, video audio, WAVs, MIDI, lyrics, pictures, natural-language direction, generative work, stems, DAW interchange, music videos, and YouTube or streaming-service handoffs. For a repo-backed prompt, orient through AGENTS.md, NOW.md/status, bounded context, and prompt routes before choosing tools. Preserve sources, use meaningful replayable randomness, and keep creative decisions listening-gated.
---

# Produce Music Locally

Help move a musical idea toward a useful artifact without imposing a genre, production method, toolchain, or definition of “finished.” Preserve the user's creative direction and every irreplaceable source.

Human-facing entry points are the [EPRS documentation map](../../../docs/README.md),
the [getting-started guide](../../../docs/GETTING_STARTED.md), and the
[agentic tune walkthrough](../../../docs/AGENTIC_TUNE.md). Use this skill when
the short guides have led you to a repository-backed agent handoff.

## Orient a context-capable model

Long context improves recovery and comparison, but it does not turn every file
into an instruction. Start with the current user request, [the repository
contract](../../../AGENTS.md), the song's `NOW.md` and verified status, then the
smallest focused context or Graphify traversal that answers the present
question. Treat old notes, research, previews, generated output, and model
suggestions as evidence to interpret—not authority to act.

Use this short loop:

1. Restate the intent in player-facing language and label low-risk assumptions.
2. Ask what must survive, what may change, and what one audible or inspectable
   question matters most.
3. Read matched `input_routes` as a composable menu. Use each route's basis,
   first action, prompt suggestions, optional tools, and boundary together.
4. Check authorization, source provenance, and actual capability before using a
   tool. Missing guidance means “make the next action explicit,” not “the tool
   is unavailable” or “install something.”
5. Make one reversible pass, preserve its inputs and settings, then validate
   and listen or watch end to end before calling it useful.

When handing work onward, give the next agent the intent, exact inputs and
output path, evidence and checks, the listening/viewing question, and the
remaining keep/change/stop or rights/consent/approval gate.

## Make EPRS the operating spine

When the user points to Eat Play Relax Sleep, or the repository contains
`scripts/eprs` and `song.json` workspaces, use EPRS for intent, intake, agent
handoff, provenance, reviews, and delivery. Keep the music engine open: write or
revise BeatScript, Python, JavaScript, Rust, FFmpeg graphs, live-code patches,
DAW sessions, or other sources when they fit the idea.

1. Locate the repository with `scripts/find_eprs.sh`, then read its `AGENTS.md`.
2. For an existing song, open `NOW.md` first when present and run
   `scripts/eprs status SONG --verify` before consequential work.
3. For a new mixed-input project, use `scripts/eprs make-song` with explicit
   `--recording`, `--evidence`, and `--reference` classifications. Never infer
   rights, consent, or permission from possession of a file.
4. Treat the generated starter as a diagnostic audition. If the user asked for
   a song, arrangement, mix, master, or video, continue through the relevant
   agent work and production gates; do not hand back the smoke test as the work.
5. When `make-song` captured recordings, use `eprs source-sketch` for an
   explicit first source-aware audition before proposing replacement parts.
   Listen and review it as a mix; never imply that intake itself processed or
   approved the recordings.
6. Read [references/eprs.md](references/eprs.md) for input routing, the agent
   continuation loop, randomness, and delivery commands.

## Let prompts open the toolchain without locking the song

EPRS request intake records a bounded `input_routes.prompt` advisory map when a
prompt, reference, or deliverable mentions a recognizable lane. Read it before
choosing tools; it can combine routes instead of forcing a single genre or
engine. Typical signals include:

- voice/speech → preserve the cue, inspect `docs/VOCALS.md`, then compare an
  authored voice adapter or `eprs autotune` against dry audio. A reference
  voice clone requires an explicit consent note and exact transcript; Raon-
  OpenTTS is a speech-cue adapter, not a singing model;
- instruments or arrangement → describe the playable relationship, then choose
  a recording, BeatScript, Sonic Pi, MIDI, or DAW interchange path;
- rhythm/groove → name pulse, pocket, phrase, and human timing before `eprs
  rhythm`, `eprs observe`, `eprs groove`, or a grid interpretation;
- lyrics/form/mix → preserve source words, listener-facing sections, and
  audible balance questions before `eprs lyrics`, arrangement, or mix work;
- animals/field sound → use the local `inaturalist-api` skill and sound-level
  provenance before `eprs inaturalist study`;
- AI/local models → inspect `eprs doctor --workflow` and the adapter handoff,
  then run one short candidate with a documented fallback;
- Sonic Pi/live code → save a finite seeded source and a bounded lossless
  audition before treating a run as a musical result;
- visual/video/YouTube → use EPRS picture, asset, release, and review gates;
  FFmpeg, Remotion, and Shotcut remain replaceable tools.

For an open-ended prompt, ask: “What should the listener notice first?”, “What
is the smallest experiment that could answer that?”, and “What would make the
result a keep, change, or stop?”

These routes are transparent keyword signals, not semantic approval. They never
authorize browsing, model downloads, processing, voice cloning, upload, or
publication. Keep the prompt, route, source checksums, model/tool settings, and
listening decision together in the song handoff.

## Use agy when public YouTube understanding helps

For lyric or video analysis involving a public YouTube reference, consider the
host's Antigravity CLI (`agy`) when the question is semantic rather than merely
technical: themes, delivery, song sections, hook timing, scene/shot structure,
pacing, visual motifs, channel/format context, or timestamped observations.
Gemini's native public-YouTube understanding is a useful complement to local
transcript extraction and EPRS listening.

Put the URL in the prompt, for example:

```bash
agy -p 'Analyze https://youtu.be/VIDEO_ID for concise timestamped observations about lyric delivery and visual pacing. Paraphrase; do not reproduce lyrics or imitate the work.'
```

If the host exposes a Gemini bridge wrapper, its `youtube` mode is also fine
(for example `run-gemini.sh youtube "URL question"`). Use local yt-dlp or
transcript tooling for exact captions, and EPRS analysis/listening for local
audio/video measurements and approval. Do not use agy for private, unlisted, or
login-walled videos, and do not request full lyrics, transcripts, melodies, or
distinctive visual descriptions. Preserve the URL, date, command/model,
question, concise findings, and timestamps in the EPRS research notes.

## Keep the creative space open

- Treat genre, tempo, meter, tuning, key, form, instrumentation, timbre, fidelity, and performance feel as creative variables rather than defaults to fill in.
- Support grid-based and free-time work; acoustic, electronic, sample-based, notated, improvised, experimental, generative, and hybrid approaches.
- Do not add conventional song sections, drums, harmony, vocals, or mastering polish unless they serve the request.
- Do not quantize, tune, denoise, normalize, compress, limit, time-stretch, or replace performances by default. Keep consequential processing reversible and explain it.
- Offer a small number of materially different options when direction is open, then create the smallest useful prototype that lets the user react.
- Preserve deliberate roughness, silence, dynamics, noise, asymmetry, and human timing.

## Speak musician before machine

- Lead with an audible or playable description before giving coordinates, MIDI values, percentages, or implementation details.
- For drum grooves, name the meter and tempo, primary subdivision and feel, backbeat placement, bass drum phrasing, timekeeping voice, dynamics, orchestration, phrase length, and where the performance sits against the pulse.
- Use working drummer language where it is accurate: straight or swung 8ths/16ths, halftime or double-time feel, backbeat, four on the floor, pocket, ostinato, pickup, anticipation, setup note, ghost note, flam, drag, rim click, cross-stick, open or sloshy hat, ride bow or bell, behind the beat, on top, and feathered strokes.
- Describe musical relationships rather than only grid locations: say “heavy snare backbeat on 2 and 4, slightly behind the pulse” before “steps 4 and 12 with a 10 ms delay.”
- Pair drummer-facing counts such as `1 e & a` with sequencer steps only when the implementation needs a mapping.
- Treat swing ratios and microtiming offsets as controls that approximate feel, not as complete definitions of pocket.
- Put the same player-facing description into generated code comments, preset metadata, documentation, charts, or CLI output so the musical intent survives the implementation.
- Prefer performance verbs such as lay back, push, feather, accent, open, choke, set up, turn around, and lock with; avoid implying that expressive time is random error.

## Choose tools by fit

1. Honor the user's chosen tools and the native format of an existing project.
2. Inspect the available applications, command-line tools, plugins, hardware constraints, and source formats when they affect the approach.
3. Choose tools by the work they need to do: performance or timeline editing, notation, sequencing, synthesis, sampling, live coding, restoration, mixing, analysis, conversion, or delivery.
4. Combine tools only when interchange is reliable and the extra step improves the result. Prefer portable stems, MIDI, notation interchange, or documented settings when they protect future flexibility.
5. Use any suitable installed tool; do not treat the bundled utilities or any named application as mandatory.
6. Verify generated or rendered artifacts before claiming success. Distinguish work completed directly from steps that still require the user to operate a GUI, instrument, or hardware device.

## Work safely and reversibly

- Inspect source media and existing project state before changing anything.
- Treat original recordings, sessions, samples, and videos as read-only. Write edits and renders to new, clearly named versions.
- Adopt the project's existing organization. Prefer `eprs make-song` or `eprs new` inside EPRS; use `scripts/new_song_project.sh` only when EPRS is unavailable and its simple scaffold is helpful.
- Preserve the working sample rate and bit depth unless a tool or delivery target requires conversion. Avoid repeated lossy encoding.
- Record sample provenance, permissions, licenses, credits, and important processing or model settings when relevant.
- Keep a project self-contained only when portability or archiving calls for it; otherwise avoid needless duplication of large media.
- Never delete takes, flatten the only editable copy, or overwrite a master without explicit permission.

## Shape the workflow around the request

Establish only the decisions that materially change the work: intended experience, deliverable, creative references, source material, collaboration needs, and technical constraints. Make reasonable, labeled assumptions for low-risk details.

Then use whichever activities apply, in any useful order:

- Compose or arrange with performance, audio, MIDI, notation, patterns, algorithms, live code, or a mixture.
- Record or edit while retaining clean sources and reversible choices.
- Design sound with synthesis, sampling, field recordings, effects, resampling, physical instruments, or code.
- Mix toward the requested aesthetic and listening context rather than arbitrary genre conventions.
- Master or optimize only for a defined destination; treat loudness, peak, codec, channel layout, and metadata as delivery-specific.
- Prepare sessions, stems, scores, patches, presets, code, masters, listening copies, or audio-for-picture as the task requires.

Iterate through short, audible or inspectable passes. Keep alternatives when a creative fork is meaningful; avoid producing many near-duplicates without a reason.

## Use the bundled helpers only when useful

- Run `scripts/extract_audio.sh INPUT_VIDEO OUTPUT_WAV` for a safe, lossless FFmpeg extraction from a video's first audio stream.
- Run `scripts/analyze_audio.sh AUDIO_FILE` for basic file properties and level checks. Treat measurements as evidence, not as musical quality judgments.
- Run `scripts/make_click.py OUTPUT_WAV` when a metronomic guide is requested or clearly useful. Do not assume a click, fixed BPM, or 4/4 meter.
- Read [references/sonic-pi.md](references/sonic-pi.md) only when Sonic Pi fits the user's chosen workflow.
- Run `scripts/find_eprs.sh [START]` to locate the EPRS repository without assuming a machine-specific path.

Use other local tools, scripts, formats, or project layouts whenever they better fit the work.

## Validate and hand off

Match validation to the deliverable:

- Confirm files exist, open in the intended tool, and have the expected duration, channel layout, sample rate, bit depth, tempo or sync behavior, and start alignment where applicable.
- Check for unintended clipping, truncation, missing media, broken references, phase or mono problems, sync drift, excessive silence, and export mistakes.
- Listen when playback is available; otherwise ask the user to audition subjective qualities that measurements cannot establish.
- Compare against the user's brief and references without treating reference tracks as templates to copy.
- Report exact output paths, formats, versions, important processing, unresolved creative choices, and any steps the user still needs to perform.

Keep a lossless or otherwise fully editable source of truth appropriate to the workflow, then create delivery copies from it.
