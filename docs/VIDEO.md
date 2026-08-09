# YouTube delivery video

The YouTube adapter supports two deliberate paths from one approved,
checksum-verified lossless master: a restrained built-in title card, or a
reviewed renderer-neutral picture whose guide audio is discarded and replaced
with the master. It never accepts a working mix, overwrites an existing render,
copies to `FINAL/`, uploads, or publishes.

## Render from a versioned recipe

```bash
cp templates/youtube.json songs/signal-garden/code/youtube.json
# Set title, intent, and the song-relative path to an approved master.
./scripts/eprs youtube songs/signal-garden/code/youtube.json \
  --song songs/signal-garden
```

The recipe uses `eprs.youtube/v1`. The renderer first rechecks the lossless
master, its source lineage, checksum, and full-listen approval. It then writes a
deterministically named MP4 and `eprs.youtube-render/v1` JSON sidecar under:

```text
songs/<song>/video/youtube/<video-title>/
```

The default is 1920×1080 progressive H.264 High Profile at 30 fps, yuv420p with
BT.709 tags, AAC-LC stereo at 48 kHz, and a front-loaded `moov` atom. Width,
height, and frame rate can be changed within the recipe for an intentional
delivery variant. The title-card text is passed through a temporary text file,
so punctuation is not interpreted as an FFmpeg filter expression.

## Assemble a reviewed picture without re-encoding it

Capture and review any renderer/editor output using the
[renderer-neutral picture handoff](PICTURE.md), then use an
`eprs.youtube/v2` recipe:

```bash
cp templates/youtube-picture.json songs/signal-garden/code/youtube-picture.json
./scripts/eprs youtube songs/signal-garden/code/youtube-picture.json \
  --song songs/signal-garden
```

The assembler rejects candidates that do not match the approved master's
duration or lack a complete-picture keep decision. It requires H.264,
progressive yuv420p BT.709 picture, proves packet-for-packet stream copying,
discards embedded guide audio, and proves the final AAC packets match a
temporary reference encoded only from the approved master.

## Review and approve

Rendering establishes technical validity, not creative approval. Watch the
complete file, including first and last frames, and inspect title spelling,
audio start/end, sync, unexpected silence, and picture behavior. Then record
that review:

```bash
./scripts/eprs youtube-approve \
  songs/signal-garden/video/youtube/<title>/<render>.mp4 \
  --song songs/signal-garden \
  --review-note "Watched end to end; title, first/last frames, and audio sync are approved."
```

Approval is bound to the video checksum and the unchanged approved-master
provenance. It updates only the JSON sidecar. `publication.uploaded` and
`publication.published` remain false.

Before FINAL packaging, author and separately review the exact thumbnail,
captions, chapters, and accessibility context with the
[YouTube publishing asset workflow](YOUTUBE_ASSETS.md). Those assets bind to
this approved video; they do not modify or approve it.

Use `./scripts/eprs status songs/signal-garden --verify` to find renders still
awaiting review or evidence that has drifted. Once a chosen file is approved,
package it with the exact approved master, credits, rights note, and proposed
metadata using a [local FINAL release package](RELEASES.md). Upload remains a
separate, explicitly authorized action.

For audio-reactive, promptable films rather than a title card, use the
[visual system](VISUALS.md), then capture its output through the renderer-neutral
picture contract. Remotion renders and external editor exports remain candidates
until picture review and final assembled picture-and-sync review are recorded.
