# Sonic Pi in EPRS

Sonic Pi is a live-coded instrument and performance surface inside EPRS. It is
excellent for quickly finding a pocket, generating a synth/sample bed, syncing
to external musicians, and emitting musical cues for visuals. It is not the
project database, the rights record, or the final release renderer.

This guide was reviewed on 2026-08-11 against the local macOS install and the
upstream v5.0.0 release. The local app bundle and Homebrew cask both report
`5.0.0`.

## The EPRS boundary

Keep the roles separate:

```text
musical brief
    -> editable Sonic Pi source / .sonicpi set
    -> bounded lossless WAV stem
    -> EPRS analysis + complete listen
    -> EPRS mix/master/picture/release gates
```

Sonic Pi's Run button proves that code executed in a live session. It does not
prove that the audio was recorded, that the intended number of bars was
captured, that the result is not clipped or silent, or that it is approved for
release. Preserve the source, record a lossless stem, inspect it, and write a
keep/change/stop note before promotion.

The project handoff is intentionally read-only and human-operated:

```bash
./scripts/eprs adapter show sonic-pi-live-code --handoff develop-live-code
./scripts/eprs adapter show sonic-pi-live-code --handoff record-lossless-stem
./scripts/eprs adapter show sonic-pi-live-code --handoff sync-midi-or-link
./scripts/eprs adapter show sonic-pi-live-code --handoff record-session-video
./scripts/eprs adapter show sonic-pi-live-code --handoff drive-local-visuals
```

## Good ways to use it

### 1. Coded bed: the default EPRS route

Use finite sections, built-in synths, explicit timing, and conservative levels
to answer one arrangement question quickly. The starter in
[`examples/sonic-pi/eprs-gentle-groove-v5.rb`](../examples/sonic-pi/eprs-gentle-groove-v5.rb)
is deliberately a bounded 12-bar groove with no network control or infinite
loop. It can become a bed for Bark/Qwen vocals, guitar, or a found sound.

When a bed feels like a technically correct loop rather than a song, use
[`examples/sonic-pi/eprs-pull-me-in-v1.rb`](../examples/sonic-pi/eprs-pull-me-in-v1.rb)
as the arrangement reference. Its discipline is simple: introduce a motif
early, withhold the full pocket, make the lift audible, create a real drop, and
return with a changed final hook. More samples and more compression cannot
substitute for that sequence of expectations.

### 2. Sample instrument

Sonic Pi can play built-in and local WAV/AIFF/FLAC samples, change playback rate,
slice material, and layer samples with synths and FX. Use a song-relative,
permitted copy when a sample is going into a shareable project. An absolute path
is acceptable while exploring on one machine, but it must not become the only
copy of the source or leak a private filesystem path into public code.

For iNaturalist or other found sound, keep observation ID, creator, license,
and attribution in the EPRS evidence/credits sidecar. The Sonic Pi buffer is a
performance source, not a replacement for that rights record.

### Custom percussive field sounds

Sonic Pi can use a custom WAV, AIFF, or FLAC as a percussive instrument:

```ruby
sample "/absolute/path/to/animal-hit.wav", rate: 1.0, amp: 0.3
sample "/absolute/path/to/animal-hit.wav", start: 0.2, finish: 0.45, rate: 1.25, amp: 0.2
```

This works well for woodpecker drumming, cricket/katydid stridulation, frog
pulses, cicada pulse trains, and low fish or hydrophone thumps. Use `start:` and
`finish:` to isolate a hit from a longer recording, then use `rate:` to move the
gesture into a usable pocket. Keep the iNaturalist reference immutable and
preserve its sound-level license and attribution; a Sonic Pi path is not a
rights record.

For reproducible EPRS work, freeze the iNaturalist file first, run `eprs
inaturalist study` and optionally `eprs rhythm`, then make a new derived one-shot
under `audio/` or `audio/previews/`. Sonic Pi can audition the custom sample, but
the final stem still needs a lossless recording, ffprobe inspection, and a
complete listening decision. The portable project example is
[`examples/sonic-pi/percussive-animal-custom-sample-test.rb`](../examples/sonic-pi/percussive-animal-custom-sample-test.rb).
It is deliberately path-agnostic: replace `SAMPLE_PATH` with an authorized
local derived one-shot before running it. The source is syntax-checked; a live
Sonic Pi Run/Record remains a manual GUI step when the Mac is unlocked.

The percussive-animal field-test vocabulary is intentionally broad:

- **Pileated Woodpecker**: rim, stick, or fill; slice a resonant drum-roll
  cluster rather than quantizing the whole recording.
- **Verge Cricket** and **Common True Katydid**: bright shaker, hat, or ratchet
  textures; preserve an unquantized reference because pulse can vary.
- **Blanchard's Cricket Frog**: short rim/tom fill; alternate slices and
  velocity instead of looping one identical hit.
- **Oyster Toadfish**: sparse sub punctuation or a wet low hit; keep the
  hydrophone character instead of treating it as a clean kick replacement.

A local Sonic Pi 5 parameterized audition completed with no runtime error using
the full and sliced custom-sample calls shown in the example. That proves the
sample interface was exercised on this Mac, not that any particular animal
recording is an approved stem. The animal sounds remain references, their
iNaturalist observation/sound licenses stay in EPRS sidecars, and the musical
beat is an authored response rather than a claim about animal intent.

### 3. Live performance

`live_loop`, `cue`, `sync`, rings, functions, and controlled randomness make
Sonic Pi a good instrument for finding happy accidents. Use a live loop when the
musical hypothesis is interaction; use a finite `times` section when the
hypothesis is a repeatable release bed. A live performance capture should be
labelled as performance evidence unless all external state is frozen and
documented.

### 4. MIDI and Ableton Link

Sonic Pi v5 can follow an incoming MIDI clock with `use_bpm :midi`, optionally
selecting a named device and a `quantum:` bar length. It can also use
`link_audio` to stream audio from a named Ableton Link peer/channel and process
that stream like `live_audio`. These are powerful for a human jam, but they add
device/peer state that is not portable. Name the dependency, record the sync
settings, and capture a standalone WAV for EPRS.

### 5. Semantic visual cues

Use OSC for authored moments that an FFT cannot infer: `hook_enter`,
`guitar_answer`, `drop_machine`, or `room_only`. The existing starter sends
only to `127.0.0.1:57121`; continuous motion should still come from the
recorded audio. Remote OSC stays opt-in. See
[`visuals/adapters/sonic-pi-visual-cues.rb`](../visuals/adapters/sonic-pi-visual-cues.rb).

### 6. Session video and GUI streaming

v5 can record the Sonic Pi window plus the master mix on macOS/Windows and can
stream the GUI through Syphon/Spout-aware software. That is useful for a live
artifact, behind-the-scenes cut, or visual experiment. For an EPRS release,
keep the frame-accurate picture path and approved master as the source of truth;
do not silently substitute a desktop capture.

## Gentle defaults

- Start around `set_volume! 0.55`. In v5, `set_volume!` is a `0..1` fader after
  the limiter; old v4 values such as `set_volume! 2` are not portable.
- Treat `set_drive!` as a deliberate saturation control, not a loudness fix.
  Leave it alone for a first pass and let EPRS mastering handle delivery level.
- Keep individual layer amps modest, use low FX mix values, and leave headroom.
  A loud waveform is not evidence of a good groove.
- Prefer finite sections for recorded beds. Stop live loops before recording
  acoustic material so monitoring does not print into the take.
- If randomness is part of the idea, use `use_random_seed` and preserve the
  seed in the source or experiment manifest.
- Keep microphones, MIDI devices, controllers, Link peers, and OSC receivers
  explicitly enabled. A connected device is not automatically authorized or
  part of the song.
- Save the editable source or `.sonicpi` set, record WAV, inspect with
  `ffprobe`/`scripts/eprs analyze`, and listen from start to finish.
- When a macOS save dialog is involved, verify the resulting filename, duration,
  and bar count. A previous EPRS run found that an absolute filename could be
  interpreted as a colon-delimited Desktop filename; trim/choose the intended
  final performance before mixing.

## What v5 changed

The most important v5 change is architectural: SuperSonic replaces scsynth as
the audio engine. Audio input, output, sample rate, and buffer size can be
changed in the GUI without restarting or losing the running music. v5 also
adds or improves:

- lower-latency main limiting and separate volume/drive controls;
- `use_bpm :midi` with device selection and `quantum:` for external clock;
- `link_audio` for Ableton Link peer/channel streams;
- game-controller input through `sync` and `get`;
- per-device MIDI/controller enablement in the IO menu;
- session recording and Syphon/Spout GUI streaming;
- Quickstart Cards, richer completion with previews, runnable Docs examples,
  interactive synth/FX pages, Examples menu, and plain-text `.sonicpi` Sets;
- new music-theory aliases/chords/scales, including `:lydian_dominant`,
  `:phrygian_dominant`, `:minor_major7`, and `:maj13`.

Important compatibility notes:

1. `set_volume!` changed from the old `0..5` expectation to `0..1`.
2. The main limiter and internal FX order changed, so a v4 piece can sound
   different in v5. Re-audition old work rather than assuming byte-for-byte
   sonic equivalence.
3. v5 keeps configuration separately from v4; preferences do not automatically
   carry across.
4. The load/save toolbar meanings changed. The named actions are now
   `Load into Buffer...` and `Save Buffer As...`.

The local code registry exposes these routes as `live_coding`,
`sample_playback`, `audio_recording`, `midi_io`, `ableton_link`,
`session_recording`, and `local_osc`. The adapter profile keeps every route
optional and human-operated.

## Source map and change-log watch

Use the tagged release for installed behavior and the `dev` branch only for
future exploration. The upstream source is active, so new ideas should be
recorded with the version, source URL, musical consequence, and whether they
are safe for the portable EPRS path.

The v5 source tree is easiest to read by concern: `app/external/supersonic`
contains the new audio-engine integration; `app/server/ruby/lib/sonicpi/lang`
contains the Ruby-like language surface (with `core.rb` as a useful entry
point); and `app/gui-tests` contains executable GUI contracts for areas such as
audio-device policy, Sets, and tutorial/docs behavior. We do not vendor those
internals into EPRS. We pin the release URL, keep our own adapter contract
small, and test the handoff assumptions that matter to our songs.

- [Sonic Pi source tree](https://github.com/sonic-pi-net/sonic-pi)
- [v5.0.0 release](https://github.com/sonic-pi-net/sonic-pi/releases/tag/v5.0.0)
- [upstream CHANGELOG.md](https://github.com/sonic-pi-net/sonic-pi/blob/dev/CHANGELOG.md)
- [v5 language core source](https://github.com/sonic-pi-net/sonic-pi/blob/v5.0.0/app/server/ruby/lib/sonicpi/lang/core.rb)
- [official tutorial](https://sonic-pi.net/tutorial.html)

The release page is the authority for the current installed release. The raw
`dev` changelog may lead with a release-candidate heading while the tagged
release is already published; do not treat an unreleased branch as local
behavior.

## Verification checklist

```bash
./scripts/eprs doctor --capability live_coding
./scripts/eprs adapter list --available --capability audio_recording
ruby -c examples/sonic-pi/eprs-gentle-groove-v5.rb
PYTHONPATH=src python3 -m unittest tests.test_sonic_pi -v
```

After a real audition, also verify the recorded WAV and listen end-to-end:

```bash
ffprobe -v error -show_streams -show_format /path/to/sonic-pi-stem.wav
./scripts/eprs analyze /path/to/sonic-pi-stem.wav
```

The technical checks catch missing, silent, malformed, or unexpectedly short
audio. The listening note decides whether the music works.

## Review history

- 2026-08-11: verified local Sonic Pi `5.0.0`; reviewed upstream v5.0.0
  release notes and change log; added EPRS v5 routes, bounded starter source,
  adapter handoffs, and contract tests.
