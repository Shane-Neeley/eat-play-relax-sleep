# Local FINAL release packages

`eprs release` closes the local production chain without crossing the network.
It accepts one fully listened, approved lossless master and one fully watched,
approved YouTube render made from that exact master. It copies verified bytes,
credits, rights notes, and proposed YouTube metadata into an atomic directory
under `FINAL/`.

It also refuses to package a raw performance on the strength of a filename or
free-text rights sentence. Known audio provenance is traversed from the master
through mix, comp, processing, and selection records to every immutable raw
take. Each raw take must belong to a verified recording session and be covered
by an approved recording-clearance record.

```bash
cp templates/release.json songs/signal-garden/code/release.json
# Replace every placeholder; point at the approved master, video, and clearances.
scripts/eprs release songs/signal-garden/code/release.json \
  --song songs/signal-garden
scripts/eprs status songs/signal-garden --verify
```

The `eprs.release/v1` recipe requires a title and intent, song-relative approved
media paths, explicit name/role credits, a rights note, and proposed YouTube
title, description, tags, and visibility intent. It also requires a
song-relative `clearances` list whenever raw recordings are present in lineage.
An optional song-relative `youtube_assets` path selects one separately reviewed
thumbnail/caption/chapter bundle made against the same approved video. Both
the generated title-card `eprs.youtube-render/v1` path and reviewed-picture
`eprs.youtube-render/v2` path are accepted. When
present, every asset is copied under FINAL, chapters and credits are assembled
into the upload description, and normalized paths/checksums are added to
`youtube-metadata.json`. See [YouTube publishing assets](YOUTUBE_ASSETS.md).
The resulting
`eprs.release-package/v1` manifest binds source provenance and every copied
artifact by checksum. `HANDOFF.md` is for people; `youtube-metadata.json` is for
a future uploader. Both state that upload and publication are false.

For each traced raw recording, release finds the exact session take, verifies
the clearance's session checksum, requires approved take rights and all linked
participant decisions, compares the clearance visibility limit with the
proposed YouTube visibility, and checks named/collective wording against the
release credits. Anonymous/no-credit decisions do not invent a public name.
Unrelated clearances are rejected so a package cannot imply permission from an
unused recording. The approved clearance and session JSON are copied into the
package's `clearances/` directory; raw audio itself remains in immutable intake.

Authored or synthesized audio without a supported adjacent provenance schema is
listed as an untraced leaf rather than guessed to be a performance. A raw file
cannot take that path: anything under `recordings/raw/` requires valid recording
provenance, a session link, and clearance before release.

Visibility is an intention, not an action. `private`, `unlisted`, or `public`
does not change any account or platform. Uploading and publishing require a
separate explicit user request, current platform checks, and account
authorization. Public permission is never inferred from a performance, family
recording, credit, or finished package.

To give a future authorized uploader exact immutable inputs, run
`eprs publication prepare <release> --song <song>`. It verifies the FINAL
package again and creates an unauthorized offline handoff under
`notes/publications/`; it still performs no upload. Record returned YouTube
state append-only with `eprs publication receipt`. See [offline publication
handoffs](PUBLICATION.md).

Packaging is deterministic and idempotent. Changed credits, rights text,
metadata, or source approvals produce a different release ID and directory.
Existing packages are never overwritten. A failed copy is removed before it
becomes visible; `status --verify` flags partial directories, invalid manifests,
missing artifacts, and checksum drift.
