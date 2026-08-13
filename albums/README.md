# Album distribution

`albums/` is the small, private handoff surface for finished releases. Full
production work stays under `songs/`.

Do not symlink or copy a complete song workspace into an album. Do not put
drafts, stems, prompts, recipes, research, raw recordings, account details,
tax information, or credentials here.

## Folder contract

Keep every album and track shallow:

```text
albums/<album-slug>/
  README.md
  album.json
  <song-slug>/
    README.md
    <song-slug>.wav
    <song-slug>.mp4       # optional; for video delivery, not required by DSPs
    artwork.png
    metadata.json
```

Each track folder should contain only:

- the approved lossless WAV;
- the approved video, when one exists;
- square release artwork;
- minimal distribution metadata and checksums;
- a short human-readable README.

The canonical song workspace remains `songs/<song-slug>/`. If a release needs
to be revised, revise and approve it there, then replace the album handoff as a
new verified snapshot.

## Ranked distributors for EPRS

Ranking checked on 2026-08-12. Prices and policies change; recheck the linked
official page immediately before paying or submitting.

| Rank | Distributor | Current cost shape | Best fit | Main catch |
| ---: | --- | --- | --- | --- |
| **1** | **[LANDR Distribution](https://www.landr.com/music-distribution)** | From about $24/year; unlimited releases; 100% of master royalties | Best overall balance for a frequent one-artist EPRS catalog | Confirm the current plan and content review terms at checkout; bundled mastering is unnecessary when EPRS already has an approved master |
| **2** | **[DistroKid Musician Plus](https://distrokid.com/pricing/)** | About $44.99/year for scheduled dates and a custom label; unlimited uploads; 100% of earnings | Best fit for frequent releases and the clearest published policy accepting responsibly made AI-assisted music | Optional extras add cost; releases can be removed after cancellation unless each release has the paid Leave a Legacy extra |
| **3** | **[TuneCore Rising Artist](https://www.tunecore.com/pricing)** | About $24.99/year; unlimited releases to 150+ stores; 100% ownership | Strong mainstream alternative with scheduled dates, splits, and store coverage | Annual renewal; TuneCore states a 20% fee on social-platform revenue |
| **4** | **[CD Baby](https://cdbaby.com/cd-baby-cost/)** | $14.99 per album, one time; no annual subscription; CD Baby keeps 9% of digital-distribution revenue | Best for a small number of albums that should remain available without a yearly bill | The 9% revenue share continues for the life of the release; less economical for a large, active catalog |
| **5** | **[RouteNote Free](https://support.routenote.com/kb-article/how-much-does-routenote-cost/)** | No upfront fee; artist receives 85% of net revenue | Best zero-cash fallback or low-risk test release | Gives up 15% of revenue; Premium albums currently add an upfront fee and annual renewal |
| **6** | **[UnitedMasters DEBUT+](https://support.unitedmasters.com/hc/en-us/articles/29986962444179-How-much-does-a-UnitedMasters-membership-cost)** | $19.99/year; unlimited releases; 100% of royalties; 35+ services | Worth considering when its brand or sync opportunities matter | Narrower store count than the leading options; SELECT costs more |

### Recommendation

Start with **LANDR Distribution** for the CashForClankers catalog. It currently
combines low annual cost, unlimited releases, broad delivery, 100% of master
royalties, and a promise that released music stays live after cancellation.

Use **DistroKid Musician Plus** instead if its explicit AI-assisted-content
policy and high-frequency release workflow are more valuable than LANDR's
lower cost and live-after-cancellation policy. DistroKid permits music made
with AI tools when the uploader owns the rights, does not impersonate anyone,
does not infringe, and is not flooding stores with mass-generated spam:
[official policy](https://support.distrokid.com/hc/en-us/articles/41182362733715-Can-I-Upload-Music-Made-With-AI-Tools-to-DistroKid).

Choose one distributor for a release. Do not send the same album through
multiple distributors, because duplicate deliveries can create conflicting
metadata, identifiers, ownership claims, and takedowns.

## Required metadata

Before submission, `album.json` and each track's `metadata.json` must agree on:

- album, track title, artist name, track number, and release type;
- release date, genre, language, and explicit-content status;
- songwriter, producer, performer, and other real credits;
- copyright and phonographic-copyright lines;
- confirmed composition, recording, sample, voice, image, and artwork rights;
- WAV, artwork, and optional video filenames with SHA-256 checksums;
- ISRC and UPC/EAN, left `null` until assigned or verified.

A folder with blank credits, an unconfirmed rights field, or no release date is
organized for distribution but is not ready to submit.

## Release checks

1. Listen to the approved master from beginning to end.
2. Prefer a lossless 24-bit PCM WAV at the project's sample rate unless the
   selected distributor's current specification says otherwise.
3. Verify square artwork at 3000×3000 pixels or larger and confirm artwork
   rights.
4. Verify titles, artist spelling, track order, credits, explicit status, and
   release date across every file.
5. Confirm that every sample, synthetic voice, animal recording, and visual
   asset is cleared for the intended commercial release.
6. Run the local EPRS distribution check described in
   [`docs/DISTRIBUTION.md`](../docs/DISTRIBUTION.md).
7. Submit through one distributor and save its release ID, assigned ISRC/UPC,
   destinations, date, and receipt outside the immutable media files.
8. Inspect Spotify, Apple Music, YouTube Music, and the artist-page mapping
   after delivery.

## YouTube and direct sales

The distributor delivers audio to DSPs. Continue using the CashForClankers
YouTube channel for full videos, visual albums, and discovery. Bandcamp can be
added later for direct album sales, downloads, liner notes, and bonus files;
it does not replace Spotify/Apple distribution.

Do not enable YouTube Content ID automatically. The music is already published
on CashForClankers, so Content ID can claim the channel's own videos unless the
distributor supports allowlisting and the channel is configured correctly.

## Account boundary

Keep distributor login, payout, tax, identity, recovery, and two-factor details
in the account or password manager—not in Git or album metadata. External
submission and payment require explicit authorization; a locally complete
album folder is not proof that the release was submitted or distributed.
