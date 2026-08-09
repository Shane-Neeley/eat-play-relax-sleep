# Renderer-neutral picture handoff

EPRS can carry a finished picture from Remotion, a DAW video lane, an editor,
a live-visual recorder, a command-line renderer, or another agent tool without
making that tool the permanent project format. Capture preserves the rendered
video bytes, records what is known and unknown, and keeps subjective picture
review separate from final YouTube sync review.

## Capture any finished picture

Export the picture against the approved master from time zero. Embedded audio
may be a guide, but it is never trusted as the delivery master.

```bash
cp templates/picture.json songs/signal-garden/code/picture.json
./scripts/eprs picture add songs/signal-garden/code/picture.json \
  --song songs/signal-garden
```

`eprs.picture/v1` requires one approved lossless master; a rendered video whose
duration matches within frame tolerance; `master-time-zero`; the fixed
`replace-with-approved-master` audio policy; tool/version/session and operator;
consequential visual changes; explicit unknowns; rights; and optional editable
scores, projects, prompts, timelines, or other evidence.

The resulting `eprs.picture-candidate/v1` lives under
`video/pictures/<title>/`. Source picture bytes and evidence files are copied
without conversion and bound by SHA-256. External absolute paths are not
persisted; only a portable source scope/name, checksum, media properties, and
the preserved copy become provenance.

Capture accepts any decodable video format. The stricter final assembler
currently requires H.264, yuv420p, progressive BT.709 picture with even
dimensions so it can preserve the picture stream without another lossy encode.

## Review the picture

```bash
./scripts/eprs picture review \
  songs/signal-garden/video/pictures/<title>/<picture>.mp4 \
  --song songs/signal-garden \
  --decision keep \
  --review-note "Watched every frame; motion, framing, visual events, first/last frames, and master-time-zero intent are keepers."
```

Use `change` when the renderer should make another pass and `stop` when the
direction should not continue. Review never changes picture bytes or grants
FINAL, upload, or publication authority. YouTube assembly requires an exact
`keep` decision with a complete-picture note.

## Assemble the final YouTube file

```bash
cp templates/youtube-picture.json songs/signal-garden/code/youtube-picture.json
./scripts/eprs youtube songs/signal-garden/code/youtube-picture.json \
  --song songs/signal-garden

./scripts/eprs youtube-approve \
  songs/signal-garden/video/youtube/<title>/<youtube-video>.mp4 \
  --song songs/signal-garden \
  --review-note "Watched end to end; approved-master audio, picture sync, and first/last frames are approved."
```

`eprs.youtube/v2` maps only the candidate's first video stream and audio only
from the approved master. FFmpeg stream-copies H.264 picture packets, encodes
the master once to 48 kHz stereo AAC, and creates a fast-start MP4.

Verification hashes every source and output video packet and requires the
output sequence to be an unchanged prefix of the reviewed source. It also
encodes a temporary audio-only reference from the approved master and requires
the assembled audio packet hashes to match exactly. The reference is removed
after verification. Technical success still does not approve picture/sync;
`youtube-approve` remains a separate full-watch gate.

The older `eprs.youtube/v1` title-card path remains useful when a restrained
still image serves the music. Both versions are release-compatible and neither
uploads or publishes.
