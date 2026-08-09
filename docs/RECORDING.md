# Live and field recording workflow

## Capture

Record the cleanest honest signal available; do not chase loud waveforms. A practical starting point is 48 kHz/24-bit WAV when the interface supports it. Record 10–20 seconds of the room before and after a take, make a slate, and note instrument, player, microphone/interface, placement, monitoring, tempo/click state, tuning, and anything unusual.

Audacity is installed locally. Use it for hands-on capture and edits, but export or copy a WAV take before processing. Audacity scripting and macros are available as a future opt-in adapter; `mod-script-pipe` is not enabled by this repository because it broadens local control.

## Intake

```bash
scripts/eprs ingest /path/to/guitar-take-03.wav \
  --song songs/signal-garden \
  --role guitar \
  --rights-note "Recorded by the project owner; performer credit wording is not yet approved." \
  --note "Dynamic microphone, 8 inches off speaker, no click, room ambience"
```

Ingest copies rather than moves. It hashes the bytes, prefixes the stored filename with the checksum, probes the media, and writes a JSON provenance sidecar. Re-ingesting the same file is idempotent.

Rights and performer permission are never inferred from possession of a file.
If `--rights-note` is omitted, intake records that rights are unconfirmed and
publication is forbidden until clarified. A batch [production request](PRODUCTION_REQUESTS.md)
can give each supplied recording its own note.

The role names what the source can contribute, not what kind of professional
session it came from. `family voices`, `spoken lyric idea`, `boom-clap beat
idea`, `chimes`, and `room sound` are all valid. The compatibility alias
`--instrument` is still accepted.

## Capture a whole recording session

Single-file intake cannot remember that one guitar take, a family response, a
spoken pocket, and room tone shared a day, room, player cue, or microphone.
Record those relationships without locking the project to a DAW:

```bash
cp templates/recording-session.json \
  songs/signal-garden/code/porch-session.json
# Replace every example path and write only capture/permission facts you know.
scripts/eprs session add songs/signal-garden/code/porch-session.json \
  --song songs/signal-garden
scripts/eprs session show <session-directory-id> \
  --song songs/signal-garden
scripts/eprs status songs/signal-garden --verify
```

`eprs.recording-session/v1` records:

- session intent, an honest capture-time description, private-safe location
  context, room notes, and whether the players followed a click, breath, cue,
  free time, or another reference;
- pseudonymous participant IDs, musical roles, optional credit wording, and a
  required consent note—names and guardian details need not be stored;
- any microphone, phone, field recorder, interface, input, placement, or
  monitoring setup as plain capture-chain evidence; write `unknown` instead of
  inventing a device or coordinate;
- each take's musical role, participant/setup relationships, listening note,
  and take-specific rights boundary. A room-only take may have no participant.

All paths are validated before intake. External media is deduplicated into
immutable raw storage; a take already in `recordings/raw/` is referenced only
after its provenance is verified. The visible session manifest appears
atomically and has a deterministic identity, so repeating unchanged intake
returns the same verified record. Neither session intake nor `session show`
processes audio or grants permission to share, upload, or publish it.

Status and bounded agent context recheck the session relationships and raw
evidence, making capture intent and consent visible to later editing, research,
credit, mixing, and release agents. Possession of a file is still never treated
as consent.

## Record permission for a specific use

A session consent note describes what was known at intake; it is not release
permission. Before a raw take can enter a `FINAL/` package, create a separate
clearance for the exact intended use:

```bash
cp templates/recording-clearance.json \
  songs/signal-garden/code/private-clearance.json
scripts/eprs clearance add songs/signal-garden/code/private-clearance.json \
  --song songs/signal-garden
scripts/eprs clearance show \
  notes/clearances/<session>/<clearance>.json \
  --song songs/signal-garden
```

The clearance includes only the takes being considered, but it must include
every participant linked to those takes. Each take and participant decision is
`approved`, `declined`, or `unknown`; an approval requires who confirmed it,
when, and a permission note. Participant credit is separately `named`,
`collective`, `anonymous`, or `no-credit`, with exact approved wording for
named/collective credit. The visibility limit is `private`, `unlisted`, or
`public`; broader release intent cannot use narrower permission.

Clearance is evidence, not self-executing authority. It does not upload or
publish, and a pending/declined record is preserved rather than rewritten into
approval. Correct a mistake by creating a new record. Release packaging traces
the actual approved master back through mix, comp, processing, and selection
provenance, then requires clearance for every raw take in that known lineage.

Freeze an ingested take into a musical question without duplicating the raw
audio:

```bash
scripts/eprs experiment \
  --song songs/signal-garden \
  --source "boom-clap=songs/signal-garden/recordings/raw/boom-clap/<take>.wav" \
  --source "guitar=songs/signal-garden/recordings/raw/guitar/<take>.wav" \
  --hypothesis "Does the drummer-language backbeat leave the guitar pickup intact?"
```

The manifest holds checksummed, song-relative references to immutable raw
intake. Other source files are copied into the experiment so later edits cannot
rewrite the evidence behind a listening decision.

## Select and transform

Use `eprs select` to preserve an external take in raw intake and render a
checksummed, lossless working selection under `recordings/selected`. It can
repeat a phrase and optionally crossfade only the loop seams. It does not
normalize, quantize, tune, stretch, compress, or limit the performance.

Keep later processing reversible, write new versions, and preserve the
unprocessed selection. Align by musical landmarks before reaching for global
quantization. Test polarity and mono compatibility when combining microphones.
See [audio selections](SELECTIONS.md).

For a spoken `boom—clap`, tapped table, hand percussion, or other performed beat
idea, create a non-quantized [rhythm observation](RHYTHM.md) before deciding
whether BeatScript, a drummer chart, a MIDI sketch, or the original audio is the
right next representation.

When several takes could fill the same role, use a [performance-aware
comparison](PERFORMANCE_COMPARISON.md). It compares landmarks and phrase energy
without declaring a winner, then preserves listening notes and useful
alternates before selection or processing.

When the chosen phrase needs moments from several takes, build a
[reversible performance comp](COMPING.md). The edit score makes every region,
cut, preserved silence, and opt-in crossfade inspectable before any vocal or
instrument processing.

## Bring a take into BeatScript or Sonic Pi

BeatScript:

```beat
track guitar | x............... | ; sample=../recordings/selected/guitar.wav gain=0.6
```

Sonic Pi accepts WAV, AIFF, and FLAC by path and can index sample directories. Use an absolute path while exploring, then make the permitted project self-contained before sharing. OSC on localhost offers a future bridge between a visual controller/agent and Sonic Pi; network-receive stays off unless deliberately enabled.
