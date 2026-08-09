# Spotify and Apple Music handoffs

EPRS prepares an immutable local package for a distributor. It does not create
platform accounts, buy identifiers, submit a release, or claim that a release
is live. [Spotify directs artists to deliver through a
distributor](https://support.spotify.com/artists/article/getting-music-on-spotify/),
and Apple's current delivery requirements are defined in its [Apple Music
Specification](https://help.apple.com/itc/musicspec/en.lproj/static.html).
Those account and submission steps remain external and separately authorized.

## Package a release

Start from an approved, fully listened-through lossless master. Artwork must be
JPEG or PNG, square, and at least 3000 by 3000 pixels. Copy and edit the recipe:

```bash
cp templates/distribution.json songs/<song>/code/distribution.json
./scripts/eprs distribution songs/<song>/code/distribution.json --song songs/<song>
```

The command refuses unapproved masters, undersized or non-square artwork,
unconfirmed rights, malformed dates or identifiers, and raw performances that
do not have session-linked public clearance. A successful package is shallow:

```text
FINAL/<title>-dsp-<package-id>/
  <title>-master.wav
  <title>-artwork.png
  metadata.json
  HANDOFF.md
  release.json
  clearances/       # when recordings are present
```

`release.json` binds source checksums, approvals, public-clearance evidence,
normalized metadata, and copied artifacts. `metadata.json` deliberately records
`submitted: false` and `distributed: false`. A distributor may request more
fields or transformations, so compare its current form with this package before
submission and record external state outside the immutable package.

## Identifiers and metadata

Leave ISRC and UPC/EAN null when they have not been assigned. Do not invent
them. A distributor can often assign identifiers. Credits should name the
actual primary artist, writers, producers, performers, and other required roles.
The explicit-content choice is one of `not-explicit`, `explicit`, or `clean`.

The rights confirmation is a human gate, not a prediction. Confirm composition,
recording, sample, performer, voice, image, and artwork rights before setting
`rights.confirmed` to true. Any raw recording traced into the master additionally
requires an EPRS recording session and public recording clearance.
