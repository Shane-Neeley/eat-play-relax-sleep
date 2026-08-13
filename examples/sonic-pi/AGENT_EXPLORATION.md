# Sonic Pi agent exploration map

Start from one audible question. Choose one primary transformation axis and one
contrast axis; combining every technique usually produces an unreadable demo,
not a stronger beat.

## Query the installed system

The local catalog exposes the exact synths, FX, samples, functions, option
ranges, and built-in documentation shipped with this Sonic Pi installation:

```bash
./scripts/sonic-pi-catalog summary
./scripts/sonic-pi-catalog search "sample onset"
./scripts/sonic-pi-catalog search "phase offset" --kind synth
./scripts/sonic-pi-catalog show fx slicer
./scripts/sonic-pi-catalog list sample
```

Output is JSON so agents can inspect it without scraping the GUI or guessing
option names.

## Pick a route

| Musical question | Sonic Pi surface | Local study |
| --- | --- | --- |
| Can the groove survive changing bar sizes? | explicit finite cells, `spread`, ring rotation | `gravity-switchyard-v1.rb` |
| Can one break become a new rhythmic identity? | `slice:`, `num_slices:`, `onset:`, reverse `rate:` | `amen-prism-surgery-v1.rb` |
| Can two voices become harmony by drifting? | finite `in_thread`, unequal sleeps, `invert_around`, `phase_offset:` | `phase-mirror-garden-v1.rb` |
| Can randomness move smoothly instead of splattering? | seeded `use_random_source :perlin`, probability, fixed anchors | `probability-weather-station-v1.rb` |
| Can silence carry a slow beat? | sparse triggers, long envelopes, tiny ambient windows | `moth-court-radio-v1.rb` |
| Can fast motion retain a half-time body? | sectioned step patterns, rate mutation, register contrast | `neon-bone-machine-v1.rb` |
| Can real animal sounds form a complete kit? | onset selection, manual regions, carrier gating, provenance | `percussive-animal-custom-sample-test.rb` |

## High-value technique families

- **Time:** `sleep`, `with_swing`, `time_warp`, `at`, `density`, mixed cell
  lengths, phase drift, `cue`/`sync`.
- **Pattern:** rings, named ticks, `spread`, rotation, mirror/reflect, stretch,
  deterministic shuffle, and Sonic Pi 5's `invert_around`.
- **Samples:** `start:`/`finish:`, `slice:`/`num_slices:`, `onset:`, negative
  `rate:`, `rpitch:`, `beat_stretch:`, `duration:`, filters, and folder queries.
- **Synthesis:** contrast envelopes and register before adding layers; use
  `control` and slide opts to animate a small number of sustained nodes.
- **FX:** nest sparingly; route from inside out; capture an FX node and
  `control` its mix or timing so sections evolve instead of staying washed out.
- **Theory:** scales, chords, chord degrees, microtonal numeric notes, and the v5
  additions `:lydian_dominant`, `:altered`, `:phrygian_dominant`,
  `:double_harmonic`, `:minor_major7`, and `:maj13`.
- **Performance:** `live_loop`, MIDI, incoming MIDI clock, Ableton Link audio,
  game controllers, `live_audio`, and localhost OSC belong in explicitly live
  experiments because external state changes reproducibility.
- **Visual bridge:** emit semantic localhost OSC cues for sections and events;
  let recorded audio drive continuous visual response.

## Agent contract

1. State feel, form, player relationship, and the smallest hypothesis first.
2. Search the installed catalog before inventing a synth, FX, sample, or option.
3. Prefer a finite bar count, fixed BPM, fixed seed, conservative level, and
   built-in sounds for a portable first experiment.
4. Make sections materially different in density, register, orchestration, or
   expectation. Do not confuse more hits with development.
5. Run `ruby -c`, confirm every referenced built-in exists in the installed
   catalog, then run the source in Sonic Pi. Record a new lossless WAV, inspect
   it, and listen completely before calling the idea successful.
6. Keep microphones, external samples, MIDI, Link, controllers, remote OSC, and
   publication opt-in. Preserve source rights and external-state assumptions.

Primary references: the [official Sonic Pi tutorial](https://sonic-pi.net/tutorial.html)
and the [Sonic Pi 5.0.0 release](https://github.com/sonic-pi-net/sonic-pi/releases/tag/v5.0.0).
