# Turn a spoken beat into a drummer-facing audition

`eprs groove add` turns one verified, result-bound
`eprs.rhythm-observation/v2` into a single
explicit musical interpretation. It is the step where a person or agent may
say “hear the round boom as the grounded call on 1 and 3, and let the brighter
clap answer on 2 and 4.” The earlier observation remains non-quantized and does
not assign those roles.

The resulting BeatScript prototype is explicitly grid-quantized. What EPRS
refuses is *automatic* quantization: every event disposition and grid position
must be authored and remains distinguishable from the performed timing.

Start by listening to the source and reading its observation. Then copy the
template and author the musical proposal:

```bash
cp templates/groove.json songs/signal-garden/code/porch-pocket.json
./scripts/eprs groove add songs/signal-garden/code/porch-pocket.json \
  --song songs/signal-garden
```

The command creates a deterministic directory under
`notes/grooves/<title>/<groove-id>/` containing:

- `groove.json`, the source-bound interpretation and listening history;
- `prototype.beat`, a readable BeatScript score whose comments retain the
  player-facing idea and source observation;
- `prototype.wav`, a 48 kHz stereo synthesized audition.

It does not process, replace, align, or copy the performed recording into the
prototype.

## Say what the drummer should hear

Every `player_brief` states:

- meter and tempo relationship, including uncertainty about half/double time;
- primary subdivision and feel;
- backbeat or answering voice;
- bass-drum or low-voice phrasing;
- timekeeping voice, including deliberately having none;
- dynamics, orchestration, phrase shape, and pocket;
- what must survive, what to avoid, and one listening question.

This vocabulary is intentionally required before the pattern. A pattern such
as `X.......x.......` cannot explain whether it should feel grounded, urgent,
late, conversational, sparse, or free.

## Account for every observed attack

`event_interpretations` must cover every observation event exactly once. Each
event is explicitly:

- mapped to one audible voice, bar, and zero-based step with a drummer count;
- retained as a `pickup` outside the prototype grid; or
- deliberately `omit`ted with a musical explanation.

The chosen anchor event defines the proposed grid origin. EPRS calculates each
event's performed time relative to that anchor, its nominal grid time, and
`performed_minus_nominal_grid_ms`. Those differences remain evidence. They are
not automatically applied as corrections or copied into `humanize_ms`.

Voice-wide `offset_ms`, `swing`, and seeded `humanize_ms` are separate authored
prototype controls. If used, explain the pocket in player language. Seeded
variation is not a reconstruction of the original performance.

## Keep other interpretations alive

At least one materially different alternative is required. A four-attack
`boom—clap—boom—clap` phrase might support 120 BPM quarter-note landmarks, a
60 BPM half-time hearing, or a free call that a drummer answers only afterward.
The rendered option does not erase those alternatives.

Supported prototype voices are deliberately small and synthetic: kick, snare,
clap, hat, shaker, stick, tom, percussion, ride, and crash. External samples are
not accepted by this contract, so an audition cannot silently turn a family
recording or unlicensed sound into a drum replacement.

## Listen before carrying it forward

Rendering is technical evidence, not approval. Compare the complete prototype
with the original spoken or played idea, then record a decision:

```bash
./scripts/eprs groove review \
  songs/signal-garden/notes/grooves/<title>/<groove-id> \
  --song songs/signal-garden \
  --decision keep \
  --listening-note "The low-high exchange and its empty space carry the spoken phrase; no added timekeeper is needed yet."
```

Use `change` when a new immutable interpretation should supersede this one, and
`stop` when the grid itself is the wrong representation. `eprs status --verify`
and `eprs context --verify` recheck the observation, raw source, recipe-derived
identity, BeatScript, WAV, review state, and false authority flags.

The lightweight audition renderer may lower an overloaded synthetic sum before
16-bit output. Its playback level is not a mix decision, and the prototype is
never a master, `FINAL/` artifact, upload authorization, or publication
authorization.
