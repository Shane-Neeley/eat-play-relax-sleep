---
name: inaturalist-api
description: Discover, evaluate, freeze, and use attributed iNaturalist photos and organism sounds inside Eat Play Relax Sleep (EPRS). Use for nature or wildlife photos, cover art, thumbnails, video textures, visual references, field recordings, found-sound percussion, animal-call studies, bioacoustic inspiration, species evidence, media-license checks, iNaturalist URLs or observation IDs, and any EPRS task that needs real community-science media with safe provenance and release boundaries.
---

# Use iNaturalist with EPRS

Turn public iNaturalist observations into exact, checksum-bound EPRS reference
media. Treat real nature media as an intentional creative option when it adds
specificity; never insert it merely because it is available.

## Orient to the project

1. Work from the EPRS repository root and read `AGENTS.md`.
2. For an existing song, read its current handoff and run
   `scripts/eprs status SONG --verify` before consequential work.
3. Read [references/eprs-media.md](references/eprs-media.md) before modifying
   the iNaturalist integration, visual renderer, lineage, release gates, or
   publication metadata.
4. Keep all API work anonymous and read-only. Never publish, upload, or send.

## Choose the media route

- Choose a **photo** when a real organism, habitat, color, or texture is more
  truthful than stock footage or generic model imagery. Prefer it as one layer
  in an authored visual direction, not as an automatic full-frame treatment.
- Choose a **sound** when the recording creates a concrete musical question
  about pulse, spacing, timbre, phrasing, noise, tone, or call and response.
- Choose **observation evidence only** when the task needs species context but
  no media reuse. A public media URL is not permission to reuse its bytes.

## Discover narrowly

Run the bundled helper from the repository root. It makes one bounded API
request and returns exact observation, photo, and sound IDs with each media
item's own license and attribution.

Photo candidates for flexible public/commercial visual treatment:

```bash
node .agents/skills/inaturalist-api/scripts/query-inaturalist.mjs \
  --lat LAT --lng LNG --radius 40 --days 30 \
  --taxon "SCIENTIFIC OR COMMON NAME" \
  --photos --photo-license cc0,cc-by --quality research --limit 8
```

Sound candidates for flexible public/commercial audio treatment:

```bash
node .agents/skills/inaturalist-api/scripts/query-inaturalist.mjs \
  --lat LAT --lng LNG --radius 80 --days 365 \
  --taxon "SCIENTIFIC OR COMMON NAME" \
  --sounds --sound-license cc0,cc-by --quality research --limit 8
```

Confirm the scientific taxon and inspect the selected media record. Do not
assume an observation license applies to its photo or sound. Prefer one narrow
query over paging; do not retry throttling in a loop.

## Freeze exact bytes through EPRS

Do not turn a discovery URL into an ad hoc `curl` download. Let EPRS validate
the media host, license, attribution, IDs, bytes, and destination.

```bash
scripts/eprs inaturalist photo OBSERVATION_ID \
  --song SONG --role "VISUAL ROLE" --photo-id PHOTO_ID --size large \
  --note "WHY THIS REAL IMAGE SERVES THE VISUAL IDEA"

scripts/eprs inaturalist sound OBSERVATION_ID \
  --song SONG --role "MUSICAL ROLE" --sound-id SOUND_ID \
  --note "WHAT TO STUDY WITHOUT CLAIMING TRANSLATION"
```

Keep the generated file and adjacent JSON sidecar together. Photos live under
`references/inaturalist-photos/`; sounds live under
`references/inaturalist-audio/`. They are external evidence, never owned raw
recordings.

## Develop photos

For the built-in Remotion path, add up to four frozen photo references to an
`eprs.visual/v1` score using paths relative to that score:

```json
"photographs": [
  {
    "path": "../references/inaturalist-photos/role/observation-ID-photo-ID-large.jpg",
    "opacity": 0.3,
    "treatment": "soft-light"
  }
]
```

Use `normal`, `soft-light`, or `screen`; keep opacity intentional. The renderer
accepts only verified CC0/CC BY references, stages the exact local bytes,
embeds a restrained credit, and records photo provenance in the render sidecar.
Watch the render: technical success is not picture approval.

An exact frozen photo can enter `eprs youtube-assets` as a thumbnail only when
it also meets the platform's image, size, and 16:9 checks. EPRS then preserves
its source metadata and appends attribution to the release description. Treat
a crop, collage, extracted frame, or painted-over version as a new derivative;
carry the original sidecar as evidence and author its lineage and credit.

## Develop sounds

Study a frozen sound before assigning it a musical role:

```bash
scripts/eprs inaturalist study PATH_TO_FROZEN_SOUND \
  --song SONG --role "CREATIVE STUDY ROLE" \
  --key C --scale minor-pentatonic \
  --note "MEASURE THE RECORDING; INVENT THE MUSICAL RESPONSE"
```

Treat measured attack spacing, energy, rough pitch, and brightness as evidence.
Treat beat, noise, lyric, vocal, and tone mappings as authored hypotheses—not
animal-language translation. Preserve the original sound as the source of
truth. Run `scripts/eprs inaturalist models` before proposing bioacoustic model
work and keep model output as separate evidence.

Do not place a frozen sound into a public or monetized release unless its
sound-level license and audio lineage pass EPRS release checks. CC BY-NC,
unknown, and all-rights-reserved material remains reference-only.

## Protect evidence and wildlife

- Never infer or reveal precise locations, including for obscured or threatened
  observations. Link to the public observation instead.
- Never promise a current sighting. Research grade means community-vetted, not
  present now; zero results do not prove absence.
- Preserve contributor attribution, media ID, media license, observation URL,
  retrieval time, and checksum.
- Use a descriptive `User-Agent`; stay below roughly 60 requests/minute and
  10,000/day. Issue sequential calls and wait about 1.1 seconds in loops.
- Keep CC BY-SA, CC BY-ND, and noncommercial licenses out of the automatic
  public-ready visual route; they require narrower manual review.
- Credit real media without implying endorsement by the observer or iNaturalist.

## Verify the result

Match checks to the work performed:

- Re-run the exact EPRS freeze command and confirm it resolves idempotently.
- Confirm the sidecar's media ID, observation link, license, attribution, and
  SHA-256 match the frozen file.
- For photos, run the visual typecheck and render a short preview; inspect the
  photo treatment, crop, legibility, credit, first/last frames, and silence.
- For sounds, verify the creative study and downstream audio lineage; listen to
  any selection or experiment before keeping it.
- Run focused tests, then the repository's format/test/typecheck/build checks in
  proportion to the change. Report unrelated dirty-tree failures separately.
