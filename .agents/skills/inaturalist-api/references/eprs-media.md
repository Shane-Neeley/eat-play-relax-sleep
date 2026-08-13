# EPRS iNaturalist media reference

Read this file when changing EPRS iNaturalist code or carrying frozen media
into visual, audio, thumbnail, picture, release, or publication workflows.

## Command and contract map

| Need | EPRS command or file | Durable result |
|---|---|---|
| Freeze one photo | `eprs inaturalist photo` | `eprs.inaturalist-photo/v1` sidecar beside exact image bytes |
| Freeze one sound | `eprs inaturalist sound` | `eprs.inaturalist-audio/v1` sidecar beside exact audio bytes |
| Study one sound | `eprs inaturalist study` | `eprs.inaturalist-creative-study/v1` measurement and five-domain creative map |
| List model options | `eprs inaturalist models` | Boundary-aware bioacoustic model catalog |
| Render photos | `eprs visual-render` | `eprs.visual-render/v1` video sidecar with photo provenance and rights summary |
| Preserve any renderer | `eprs picture add` | Renderer-neutral `eprs.picture-candidate/v1` with declared evidence and rights |
| Package thumbnail | `eprs youtube-assets add` | Checksum-bound publishing assets; exact iNaturalist source is detected from its adjacent sidecar |

Implementation entry points:

- `src/eprs/inaturalist_photo.py`: safe photo URL, license classification,
  download, byte signature, sidecar, verification.
- `src/eprs/inaturalist_audio.py`: sound selection, download, rights, sidecar.
- `src/eprs/inaturalist_study.py`: measurements and creative hypotheses.
- `src/eprs/lineage.py`: external audio lineage and visibility restrictions.
- `src/eprs/visuals.py`: photo-score validation, staging, render provenance.
- `visuals/src/AudioReactiveFilm.tsx`: crossfade, movement, treatment, visible
  attribution.
- `src/eprs/youtube_assets.py`: exact-source thumbnail recognition.
- `src/eprs/release.py`: release-description photo credit.

## License routing

Evaluate each media item's own `license_code`; never substitute the observation
or taxon license.

| License | Freeze as reference | Automatic public-ready visual use | Flexible public/monetized audio use |
|---|---:|---:|---:|
| CC0 | yes | yes | yes |
| CC BY | yes, preserve attribution | yes, preserve attribution | yes, preserve attribution |
| CC BY-SA | yes | manual share-alike review | manual review |
| CC BY-ND | yes | manual no-derivatives review | manual review |
| CC BY-NC variants | yes, reference-only | no | no |
| Unknown or all rights reserved | photo refused; sound may freeze reference-only | no | no |

The conservative automatic route is deliberately narrower than every use that
might be lawful. Do not widen it without tests, documentation, and explicit
downstream enforcement.

## Photo workflow details

1. Discover an observation with an exact reusable photo ID.
2. Freeze it with `--photo-id`; use `--size large` for ordinary visual work and
   `original` only when the added resolution is justified.
3. Inspect the sidecar and image before authoring a visual score.
4. Add the photo as a low-opacity layer when it serves the song. Keep the
   existing signal world, movement, and typography under creative control.
5. Render a short draft. Inspect crop, contrast, subject truthfulness, visible
   attribution, and whether the image reads as evidence rather than decoration.
6. Render full picture only after choosing the direction. Capture and review it
   through `eprs picture`; include the visual score and render provenance as
   evidence when they materially shaped the result.
7. For a thumbnail, prefer a reviewed 16:9 derivative or frame. If it is not the
   exact frozen photo, explicitly preserve source lineage; adjacency detection
   applies only to unchanged frozen bytes.

The photo sidecar omits `place_guess`. Do not reintroduce locality into visual
metadata unless the user needs a coarse, ethically safe regional statement.

## Audio workflow details

1. Query `sounds=true` and retain one record per sound ID.
2. Freeze the selected sound under `references/inaturalist-audio/`; never place
   it in `recordings/raw/`.
3. Run `eprs inaturalist study`. Use its timing and spectral proxies to form a
   listening question, not to declare biological meaning.
4. For transient material, consider woodpecker drumming, frogs, crickets,
   katydids, cicadas, or other verified pulse-producing taxa. For sustained
   carriers, try manual regions or amplitude gates when onset detection is not
   musically informative.
5. If using exact audio, create a checksum-bound selection and retain external
   lineage. If only studying it, make a new authored sound or rhythm and keep
   the source out of release audio lineage.
6. Listen, review, and clear the exact lineage before mastering or release.

## Failure behavior

- Do not overwrite a good frozen reference or cache with a failed request.
- Require explicit photo/sound IDs when an observation contains more than one.
- Reject unsafe hosts, non-HTTPS public links, mismatched IDs, empty downloads,
  oversized media, byte-format mismatch, checksum drift, and sidecar drift.
- Treat API failure as unavailable evidence, not zero biodiversity.
- If throttled, report it and stop; never retry in a loop.

## Focused verification

For photo changes:

```bash
PYTHONPATH=src python3 -m unittest -v \
  tests.test_inaturalist_photo tests.test_visuals tests.test_youtube_assets
npm --prefix visuals run typecheck
```

For sound changes:

```bash
PYTHONPATH=src python3 -m unittest -v \
  tests.test_inaturalist_audio tests.test_inaturalist_study tests.test_lineage
```

Then run `make check`, `make test`, and `make public-check` when the scope and
available media dependencies make those checks practical.
