# YouTube publishing assets

An approved video is not yet a complete publishing package. `eprs youtube-assets`
prepares the upload-facing visual and accessibility files that belong to one
exact approved video, without changing that video or contacting YouTube.

## Create and review a bundle

```bash
cp templates/youtube-assets.json songs/signal-garden/code/youtube-assets.json
# Replace every placeholder and author every cue and chapter against the approved video.
./scripts/eprs youtube-assets add \
  songs/signal-garden/code/youtube-assets.json \
  --song songs/signal-garden

./scripts/eprs youtube-assets review \
  songs/signal-garden/video/youtube-assets/<title>/<bundle-id> \
  --song songs/signal-garden \
  --review-note "Checked the thumbnail at small size, every caption cue, every chapter, and the accessibility note."
```

The `eprs.youtube-assets/v1` recipe requires:

- an already approved `eprs.youtube-render/v1` video;
- a song-local JPG, PNG, or GIF thumbnail, literal alt text, and a visual review
  question;
- one or more explicitly authored caption tracks with language, completeness
  note, and non-overlapping cues inside the video duration;
- at least three authored chapters beginning at `00:00`, ascending, and at
  least ten seconds long; and
- an accessibility note describing what a reviewer must verify.

The command preserves the thumbnail bytes unchanged and generates plain UTF-8
SubRip `.srt` files plus `chapters.txt`. The bundle manifest binds the approved
video and provenance sidecar, thumbnail source, normalized timing recipe, and
every generated artifact by SHA-256. A changed source, timing record, generated
file, approval, or authority flag makes verification fail.

Creation records technical validity only. A separate review must check that the
thumbnail is truthful and legible, captions are complete and accurately timed,
chapter names are useful, and private material has not leaked. Review still
leaves upload and publication authorization false.

An exact frozen iNaturalist photo may be used as the thumbnail when it also
passes the platform crop and size checks. If the image has an adjacent
`eprs.inaturalist-photo/v1` sidecar, the bundle verifies its checksum and
requires CC0 or CC BY, preserves the observation/photo IDs and attribution, and
the release package appends that photo credit and public observation link to
the upload description. A crop, collage, extracted video frame, or other
derived thumbnail is a new asset: preserve the original photo sidecar as source
evidence and author the derived asset's credit/rights trail rather than implying
that adjacency proves its lineage.

## Current platform assumptions

The versioned platform contract was checked on 2026-08-03 against first-party
YouTube Help. It enforces a supported image format, minimum 640-pixel thumbnail
width, 16:9 aspect ratio, and the 50 MB desktop limit; it also records whether
the thumbnail fits the smaller 2 MB mobile limit. YouTube currently recommends
3840×2160 where practical. See [custom thumbnail guidance](https://support.google.com/youtube/answer/72431).

Captions are emitted as plain UTF-8 SubRip because YouTube lists it as a basic,
editable caption format. See [supported caption files](https://support.google.com/youtube/answer/2734698).
Chapters follow YouTube's documented `00:00`, three-entry, ascending, and
ten-second rules. See [video chapters](https://support.google.com/youtube/answer/9884579).

Those URLs and the check date live in every bundle recipe so a future agent can
identify when platform rules need revalidation. Account eligibility, policy
review, quotas, upload, and publication remain external and separately
authorized concerns.

Release also refuses an assembled title over 100 characters, a description
over 5000 UTF-8 bytes, forbidden angle brackets, or API-counted tags over 500
characters. These limits were checked against the current
[YouTube video resource](https://developers.google.com/youtube/v3/docs/videos)
and [upload guidance](https://support.google.com/youtube/answer/57407).

## FINAL and uploader handoff

Add the reviewed bundle's song-relative `bundle.json` path as `youtube_assets`
in `eprs.release/v1`. Release copies the bundle manifest, thumbnail, caption
tracks, and chapters under `FINAL/<release>/youtube-assets/`. It also appends
the exact chapter block and approved credits when the authored description does
not already contain those standalone section headings, and places normalized
asset references in `youtube-metadata.json`.

`eprs publication prepare` rechecks all of those FINAL checksums and includes
them in `recipe.upload_assets`. It still sets both authorization flags to
false. A future authorized uploader can therefore consume exact files without
guessing which thumbnail, captions, or chapter revision belongs to the video.

The command never performs speech-to-text, lyric transcription, chapter
inference, thumbnail generation, media processing, upload, or publication.
Agents may help author the recipe, but uncertain words, sounds, timing, visual
meaning, and rights remain explicit review questions rather than fabricated
facts.
