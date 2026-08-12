# Sonic Pi experiments

These examples are intentionally small and human-readable. They are source
artifacts, not automatic release renders. Open them in the installed Sonic Pi
app, run the smallest useful audition, use Sonic Pi's Record control for a WAV
stem, then inspect and review that stem through EPRS before mixing or publishing.

## Start here

[`eprs-gentle-groove-v5.rb`](eprs-gentle-groove-v5.rb) is a bounded, deterministic
12-bar groove. It uses only built-in Sonic Pi instruments/samples, conservative
levels, no network control, and no infinite loop. It is a safe first check that
Sonic Pi can make a useful bed for vocals, guitar, or found sound.

[`eprs-pull-me-in-v1.rb`](eprs-pull-me-in-v1.rb) is the next step when a loop is
technically correct but musically flat. It is a finite 32-bar arrangement with
a teaser motif, broken pocket, lift, deliberate drop, hook payoff, and final
turnaround. The motif returns in changed rhythms and registers while the drums,
bass, harmony, and density evolve.

### Engagement checks

Before calling a bed release-ready, ask:

- Does something recognizable arrive in the first two bars?
- Does the first full groove earn its entrance by withholding information first?
- Is there a real contrast section or drop before the final payoff?
- Does the last bar answer or transform the hook instead of simply stopping?

If the answer is no, change the arrangement and motif before adding more effects
or louder mastering. Loud repetition is still repetition.

```bash
./scripts/eprs doctor --capability live_coding
./scripts/eprs adapter show sonic-pi-live-code --handoff develop-live-code
ruby -c examples/sonic-pi/eprs-gentle-groove-v5.rb
```

The Ruby syntax check does not prove Sonic Pi semantics or audio quality. The
source still needs to be run in the intended Sonic Pi version and the resulting
WAV needs technical inspection plus a complete listen.

## Four useful EPRS routes

1. **Coded bed:** use finite sections, built-in synths, and explicit timing to
   answer an arrangement question quickly. This is the default route for a
   repeatable drum/bass/melody bed.
2. **Sample instrument:** use `sample` with a permitted, song-relative WAV,
   AIFF, or FLAC. Keep the original file and license/attribution note outside
   the live buffer; do not make an absolute personal path part of shareable
   source.
3. **Performance adapter:** use `live_loop`, `sync`, `cue`, MIDI, or a human
   controller when the musical point is interaction. Record the performance as
   evidence; it is not automatically a deterministic render.
4. **Visual/control bridge:** use semantic OSC cues for authored moments such as
   `hook_enter` or `drop_machine`, while continuous visual motion comes from the
   recorded audio. Keep OSC on localhost unless remote control is explicitly
   chosen and documented.

Sonic Pi v5 adds two promising but optional routes: `use_bpm :midi` for an
   incoming MIDI clock and `link_audio` for live audio from an Ableton Link peer.
Both require external state, so they belong in a clearly labelled experiment
before they become part of a portable release source.

## Gentle defaults

- Begin with `set_volume!` at a modest value such as `0.55`. In v5 this is a
  `0..1` fader after the limiter; old v4 values such as `set_volume! 2` are not
  portable. Leave `set_drive!` at its default unless extra drive is the actual
  musical hypothesis.
- Keep individual layers quiet enough that the arrangement has headroom. Avoid
  stacking loud samples and FX to make a waveform look impressive.
- Prefer finite `times` sections for recorded beds. Stop live loops before
  bringing acoustic tracks into the room so monitoring does not print into the
  take.
- Use `use_random_seed` whenever randomness is part of the idea and the take
  needs to be repeatable. Preserve the seed in the source/manifest.
- Keep remote OSC, network peers, controllers, microphones, and external MIDI
  opt-in. A connected device is not automatically part of the project.
- Save the editable source or `.sonicpi` set, record a lossless WAV, inspect it
  with `ffprobe`/`scripts/eprs analyze`, and listen end-to-end. A successful Run
  button is not a verified render.

## v5 source and change map

The current local app and Homebrew cask are both `5.0.0`. Upstream's v5 release
replaced scsynth with SuperSonic and added live audio-device changes, lower-
latency limiting, separate volume/drive controls, MIDI-clock following,
Ableton Link audio, controller input, session video recording, Syphon/Spout
streaming, runnable docs/examples, Sets, and richer code completion.

The release also has behavior changes worth keeping visible in code review:

- `set_volume!` now expects `0..1`; use `set_drive!` when intentional saturation
  is wanted.
- The mixer/limiter/FX order changed, so a v4 piece may sound different in v5.
- v5 keeps separate configuration from v4; preferences do not automatically
  carry over.
- The load/save toolbar meanings changed; use the named menu actions when in
  doubt (`Load into Buffer...` and `Save Buffer As...`).

The upstream source map is useful when a new feature matters:

- [Sonic Pi source tree](https://github.com/sonic-pi-net/sonic-pi)
- [v5.0.0 release notes](https://github.com/sonic-pi-net/sonic-pi/releases/tag/v5.0.0)
- [upstream change log](https://github.com/sonic-pi-net/sonic-pi/blob/dev/CHANGELOG.md)
- [language core source](https://github.com/sonic-pi-net/sonic-pi/blob/v5.0.0/app/server/ruby/lib/sonicpi/lang/core.rb)
- [official tutorial: samples, MIDI, OSC, and recording](https://sonic-pi.net/tutorial.html)

The upstream `dev` branch can describe unreleased work, so release-specific
claims should be checked against the tagged release page. This file records the
last review date in the repository history rather than silently treating a
future branch as installed behavior.

## EPRS handoff

Use the adapter guide for the exact handoff boundary:

```bash
./scripts/eprs adapter show sonic-pi-live-code --handoff record-lossless-stem
./scripts/eprs adapter show sonic-pi-live-code --handoff sync-midi-or-link
./scripts/eprs adapter show sonic-pi-live-code --handoff drive-local-visuals
```

Sonic Pi supplies a musical source/performance and a lossless stem. EPRS owns
the provenance, analysis, mix/master, picture review, neutral public metadata,
and release handoff. Sonic Pi's session video and live streaming are valuable
experiments, but they do not replace that release path.
