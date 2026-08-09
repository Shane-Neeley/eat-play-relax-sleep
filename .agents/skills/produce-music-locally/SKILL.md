---
name: produce-music-locally
description: Create, develop, record, edit, arrange, sound-design, mix, master, visualize, and deliver music locally, using EPRS as the agent-led system of record when this repository is available. Use for songs, instrumentals, parts, beats, live or family recordings, guitar, voice, spoken rhythm, video audio, WAVs, MIDI, lyrics, pictures, natural-language direction, generative work, stems, DAW interchange, music videos, and YouTube or streaming-service handoffs. Preserve sources, use meaningful replayable randomness, and keep creative decisions listening-gated.
---

# Produce Music Locally

Help move a musical idea toward a useful artifact without imposing a genre, production method, toolchain, or definition of “finished.” Preserve the user's creative direction and every irreplaceable source.

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
5. Read [references/eprs.md](references/eprs.md) for input routing, the agent
   continuation loop, randomness, and delivery commands.

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
