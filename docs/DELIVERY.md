# Final delivery workflow

Every song workspace has one obvious handoff location:

```text
songs/<song-name>/FINAL/
```

`FINAL/` answers “which files are ready?” It is not a render cache, experiment folder, or substitute for editable sources.

Each song's root `README.md` points to the current release package and its main
deliverables. The package directory inside `FINAL/` contains the approved
master, approved platform video, metadata, handoff notes, and checksum manifest.
Use `video/README.md` when you need to distinguish a visual source, a reviewed
picture candidate, a delivery render, or a preview.

## Working folders versus final delivery

| Folder | Purpose | Ready to hand off? |
|---|---|---|
| `experiments/` | Narrow tests, frozen inputs, measurements, decisions | No |
| `stems/` | Reusable instrument or processing layers | No |
| `mixes/` | Audition mixes and revisions | No |
| `masters/` | Lossless working masters and mastering revisions | Not by location alone |
| `video/` | Video drafts and production renders | Not by location alone |
| `FINAL/` | Approved, verified delivery copies and delivery notes | Yes |

## Promotion checklist

Before copying a file into `FINAL/`:

1. Confirm the creative version and intended destination.
2. Inspect duration, streams, sample rate or frame rate, peaks, truncation, sync, and unexpected silence as applicable.
3. Listen to or watch the complete deliverable when possible.
4. Trace the chosen master to its raw takes; confirm checksum-bound session,
   take/participant clearance, proposed visibility, approved credit wording,
   licenses, artwork, and source provenance.
5. Give the file a descriptive, versioned name such as `signal-garden-master-v1.wav`.
6. Copy it into `FINAL/`; retain the editable source in its working folder.
7. Add concise `delivery-notes.md` when formats, versions, credits, or unresolved caveats need explanation.

Useful technical inspection:

```bash
./scripts/eprs analyze songs/<song-name>/masters/<candidate>.wav
./scripts/eprs analyze songs/<song-name>/video/<candidate>.mp4
```

Record a full creative listen separately from technical rendering:

```bash
./scripts/eprs master-approve songs/<song-name>/masters/<title>/<master>.wav \
  --song songs/<song-name> \
  --listening-note "Listened end to end; this is the intended balance, dynamics, and silence."
```

Approval updates only the checksum-bound master provenance. It does not copy to
`FINAL/`, encode video, publish, or upload.

Prepare and separately approve a YouTube listening video from that approved
master:

```bash
cp templates/youtube.json songs/<song-name>/code/youtube.json
./scripts/eprs youtube songs/<song-name>/code/youtube.json --song songs/<song-name>
./scripts/eprs youtube-approve songs/<song-name>/video/youtube/<title>/<video>.mp4 \
  --song songs/<song-name> \
  --review-note "Watched end to end; title, first/last frames, and sync are approved."
```

The video sidecar keeps technical verification, picture-and-sync approval,
FINAL promotion, upload, and publication as distinct states. See
[YouTube delivery video](VIDEO.md).

When the music needs more than a title card, capture any Remotion, editor,
DAW-video, live-visual, or other renderer output with `eprs picture add`, record
a complete `picture review`, then assemble it with `eprs.youtube/v2`. The final
assembler stream-copies reviewed picture and takes audio only from the approved
master. See [renderer-neutral picture handoff](PICTURE.md).

Prepare the remaining upload-facing files as a separate reviewed bundle:

```bash
cp templates/youtube-assets.json songs/<song-name>/code/youtube-assets.json
./scripts/eprs youtube-assets add songs/<song-name>/code/youtube-assets.json \
  --song songs/<song-name>
./scripts/eprs youtube-assets review \
  songs/<song-name>/video/youtube-assets/<title>/<bundle-id> \
  --song songs/<song-name> \
  --review-note "Checked thumbnail, captions, chapters, and accessibility context."
```

See [YouTube publishing assets](YOUTUBE_ASSETS.md). The supplied thumbnail is
preserved unchanged; no command infers speech, lyrics, chapters, or approval.

`FINAL/` remains private-by-default under the repository's `songs/` ignore rule. No command publishes, uploads, or sends its contents without a separate explicit request.

`eprs publication prepare` can turn one verified FINAL package into exact
offline uploader inputs while keeping authorization false. After a separately
authorized external upload, `eprs publication receipt` records the returned
YouTube state without mutating FINAL. See [offline publication
handoffs](PUBLICATION.md).

Use `eprs release` rather than a manual copy when raw performances are involved.
It follows known audio provenance and refuses packaging until every raw take has
a verified recording-session link and an approved clearance broad enough for
the proposed visibility. See [local FINAL release packages](RELEASES.md).

Declarative `eprs mix` output is 32-bit float working audio. Resolve its
listening notes and any over-zero headroom warning before creating an integer or
delivery master; float headroom is not evidence that a platform encode is safe.
See [lossless mastering](MASTERING.md) for the refusal-first conversion.
