# EPRS method-space audit

This is the practical map of creative routes EPRS can preserve. The live,
machine-readable inventory is the `method_space` section of each
`song-manifest.json`; it is generated from the CLI parser,
`config/toolchain.json`, and `config/adapters/*.json`, so flags, choices,
defaults, providers, and adapter handoffs do not drift into a hand-maintained
list.

## Intent, exploration, and orchestration

- `new`, `make-song`, production requests, plans, work queues, dispatch,
  isolated runners, context packets, and production maps;
- prompt, intended experience, preserve/avoid boundaries, questions,
  references, rights notes, result contracts, due dates, agents, and seeds;
- fresh entropy with collision checks or explicit replay seeds;
- small experiments, source-aware sketches, mutation, alternatives, and
  keep/change/stop review rather than one unexamined full render.

These methods change *how a song is explored*. Reusing the same render engine
with a new subject is not an orthogonal production method.

## Source, performance, and observation

- immutable human recording intake; sessions, participants, setups, room,
  tuning, time context, consent, clearance, and credit decisions;
- selection, regioning, repetition, seams, compare order, comp cuts,
  crossfades, phase/mono observation, rhythm attacks, phrase regions, pitch and
  pulse candidates;
- live guitar, voice, percussion, found sound, room sound, Sonic Pi performance,
  MIDI, Ableton Link, OSC, Audacity, or a returned DAW performance;
- iNaturalist sound/photo freezing, attribution, licensing, measured sound
  studies, and separate beat/noise/lyric/vocal/tone hypotheses.

The important axis is authored performance versus fixed code versus
source-derived arrangement—not merely which instrument label appears.

## Composition and sound generation

- BeatScript: tempo, meter, resolution, bars, swing, notes, drums, samples,
  seeded humanization, voices, gain, pan, envelopes, filters, mutation, render,
  and SVG visualization;
- Sonic Pi: finite seeded live code, synthesis, sample playback, recording,
  MIDI/Link, OSC, and session capture;
- SuperCollider/scsynth: synthesis, granular processing, algorithms, and local
  audio-server experiments;
- performed composition, lyric variants, call-and-response, groove
  interpretation, note-aware melody, source-first or bed-first arrangements;
- optional bounded generation: ACE-Step, MiniMax Music 3, MiDashengLM-Gen,
  Qwen3-TTS, CuteTTS, Raon-OpenTTS, FireRedTTS3, DiffSinger, Seed-VC, and
  Amphion Vevo; each remains candidate evidence with model/revision, prompt,
  seed, settings, license, rights, and review boundaries.

Orthogonal candidates should differ on several of these axes—for example live
free-time guitar plus room percussion versus seeded BeatScript plus eight
one-shot samples—not only in BPM or palette.

## Analysis, editing, processing, and arrangement

- FFprobe/media analysis, creative quality reports, optional OpenCV video and
  thumbnail checks, Basic Pitch/OpenVPI GAME audio-to-MIDI studies, and Demucs
  tentative stem separation;
- explicit stem recipes: trim, gain, fades, filtering, time stretch, and any
  intentionally declared non-default processing with a musical reason;
- performance comping, autotune presets/key/scale, source-versus-result review,
  float mix scores, track entrances, offsets, gain, pan, evidence bindings,
  and headroom checks;
- Audacity or other DAW-neutral interchange, reconstruction verification,
  declared return tool/version/session, known changes, unknowns, added sources,
  and a fresh end-to-end mix review;
- lossless mastering with explicit technical limits and a separate complete
  listening approval.

Repeated trim/stretch/filter/fade recipes are one corridor even when applied to
many different sources. Manifests make that repetition countable.

## Visuals and picture

- prompt-to-score visuals with seed, title, timing, quality, orientation, and
  renderer choice;
- deterministic Remotion or headless vgpu, custom authored Python/Pillow/FFmpeg,
  editable Shotcut/MLT timelines, ChatCut handoffs, still images, photographs,
  captions, beat markers, keyframes, crops, and audio reassembly;
- renderer-neutral picture capture and review before YouTube assembly.

Visual novelty is recorded separately from musical novelty so a new wrapper
cannot accidentally stand in for a new song method.

## Delivery, release, and feedback

- YouTube assembly, video-quality checks, complete picture/sync approval,
  thumbnails, captions, chapters, accessibility context, and asset review;
- verified release packages, credits, clearances, distribution handoffs,
  current review pointers, offline publication preparation, and append-only
  external publication receipts;
- audience/analytics research can become attributed research or a bounded work
  item, but it does not retroactively approve a creative decision.

## What the manifest closes

Before this ledger, most individual EPRS outputs were highly auditable but the
song as a whole was not. There was no automatic record of the CLI route, no
complete snapshot of unused methods and tunable flags, and no uniform place to
record external software, rejected approaches, prompts, or loose thoughts.

The new manifest closes that aggregation gap while retaining EPRS's existing
boundaries:

- exact evidence stays beside the artifact that owns it;
- mutating CLI attempts and their completed/nonzero outcome are recorded automatically;
- external and human-operated methods can be added explicitly;
- rejected and failed methods remain useful album history;
- free-form sections prevent today's schema from prescribing tomorrow's work;
- `not-evidenced` always means unknown/unused-in-ledger, never “proven absent.”
