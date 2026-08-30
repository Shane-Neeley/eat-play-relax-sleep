# The Listening Field — EPRS album and growth sprint

Date: 2026-08-30  
Status: working brief; no publication authorization

## North star

Build an eight-track EPRS album about animal communication as a sequence of
human-authored responses, not translations:

`announce → warn → seek → invite → coordinate → remember → wait → answer`

Every track should have:

- a real, audible field-recording anchor whose source, license, and exact
  lineage are preserved;
- a call → listening gap → authored reply → changed return;
- a memorable human hook by roughly the third second;
- a recurring listening motif that evolves across the record; and
- a crisp visual system that makes signal, pause, and response legible.

Playback to animals remains `not-run`. Public copy should say “authored
response inspired by measured call structure,” never “animal translation” or
an animal-intent claim.

## Album shape

Working title: **The Listening Field**  
Target length: roughly 30–40 minutes  
Recurring motif: a three-note E-centered cell, introduced as a single knock and
expanded into the final ensemble response.

| # | Function / working title | Source and musical rule | Hook / identity | Visual and reply mechanic |
|---:|---|---|---|---|
| 1 | **Announce — Knock on the Green** | Pileated Woodpecker candidate; reverify exact source, license, and call region. Dry drumming becomes a 2/4 guitar knock. | “Knock on the green—let the whole tree know.” E major/mixolydian, 112 BPM. | Tree-ring grid; source roll → two-note guitar answer → chorus downbeat. |
| 2 | **Warn — Quiet Means Look** | American Crow candidate; keep context and silence audible rather than treating the call as a fixed alarm dictionary. 4/4, 86 BPM. | “Quiet means look—don’t miss the edge.” C# minor, muted breakbeat. | One amber alert cell; crow fragment → two-beat gap → human answer. |
| 3 | **Seek — Find Me in the Open** | Common Marmoset candidate; use directed-call/receiver timing as an authored stereo conversation. 3/4, 92 BPM. | “Find me in the open.” B minor, bright guitar and hand percussion. | Two nodes move toward center; left source → right reply → shared center. |
| 4 | **Invite — Come This Way** | Western Honey Bee candidate; buzz is the anchor, while angle/pan and distance/phrase length are explicitly authored sonification. 4/4, 78 BPM. | “Come this way, there’s room in the light.” E major, warm guitar/marimba. | Clean compass/vector route; buzz → bass path → band invitation. |
| 5 | **Coordinate — Pass the Corner** | Zebra Finch candidate; make turn-taking and contingency musical without claiming a codebook. 3+3+2/8, 104 BPM. | “Pass the corner till the room locks in.” D major, interlocking percussion. | Three signal lanes pass one pulse; each phrase waits for the next. |
| 6 | **Remember — Say My Shape** | African Savanna Elephant candidate; two low motifs address and change contour on return. 6/8, 72 BPM. | “Say my shape—I know the way home.” E minor, open guitar and sub-air. | Two contours recover a shared shape; rumble → identity motif → altered return. |
| 7 | **Wait — Leave a Window** | Sperm Whale candidate; use measured coda variation as spacing, not whale semantics. 5/4, 96 BPM. | “Leave a window, let the answer arrive.” F# minor, sparse low drums/piano. | Underwater score grid with one blank measure; coda → full-bar gap → changed answer. |
| 8 | **Answer — One More Whistle** | Bottlenose Dolphin only after a rights-cleared source is found. No synthetic or uncleared substitute. | “One more whistle, then I answer.” E mixolydian, 118 BPM, full-band lift. | Eight stations converge into one ring; album motif returns as EPRS ensemble, not dolphin reply. |

### Pilot

Start with **Knock on the Green**. It has the cleanest first experiment: a
recognizable percussive source, a tap-friendly pocket, a guitar-forward E lane,
and a hook that can land immediately. Before production, freeze the source,
recheck its license, measure the call-bearing region, and write the one-song
hypothesis in a song-local brief.

The first three-song arc is:

1. **Knock on the Green** — announce / immediate percussive discovery.
2. **Quiet Means Look** — warn / contrast through silence and context.
3. **Find Me in the Open** — seek / first explicit stereo conversation.

Do not force Nepal flood releases into this album. Keep them standalone unless
a separate memorial/current-events collection is deliberately designed.

## YouTube rollout

The channel is still in discovery-without-habit territory. The local baseline
is 6 subscribers, 1,840 views, and 124 videos. The provisional Aug. 23–30
Analytics query returned 468 views, 184 engaged views, 82 estimated watch
minutes, and 0 subscribers; rows currently lag through Aug. 28. The Aug. 1–28
Studio snapshot showed 1,067 views, 5.3 watch hours, +2 subscribers, Shorts at
33.5% stayed-to-watch, and long-form at 3.0% CTR with 0:37 average duration.
Use these as small-sample baselines, not verdicts.

The 30-day plan is deliberately sparse:

- Days 1–4: finish the album map, create the **The Listening Field** playlist,
  and lock one thumbnail grammar.
- Days 5–11: release the pilot full song, then one discovery Short and one
  process Short.
- Days 12–18: release song two with the same funnel but a different species,
  meter, and visual world.
- Days 19–25: release song three and its two Shorts.
- Days 26–30: publish the album destination only if the remaining tracks pass
  their own creative, rights, and technical gates; otherwise publish a trailer
  or checkpoint.

Maximum: **3 singles, 6 Shorts, and 1 album destination** in 30 days.

For every single:

`discovery Short → full song/video → process clip → album playlist`

Put the real signal in the first second, the human hook by about second three,
and one clear visual technique on screen. Keep the same audience promise—
“documented signal + human musical response”—while varying species, groove,
performance, and visual medium.

### Tests

| Test | Control and variant | Primary decision metric |
|---|---|---|
| Long-form packaging | Species-first, question-first, and music-first title/thumbnail variants on one eligible 16:9 video. | Native YouTube watch-time winner; CTR and first-30-second retention are diagnostics. |
| Short opening | Raw signal first vs. question first vs. signal → beat. | Stayed-to-watch, with average percentage viewed as a guardrail. |
| Search bridge | Plain-language animal/function title vs. abstract music title. | Search-sourced engaged minutes per 1,000 views. |
| Funnel CTA | Short with related-video link vs. matched Short without it. | Full-song starts per 1,000 Short views and full-song 30-second retention. |
| Series order | Short → full → process vs. process → full. | Seven-day return rate, next-release starts, and subscribers per 1,000 engaged views. |

At 48 hours, inspect stayed-to-watch/swipes, engaged views, average percentage
viewed, first-30-second retention, traffic source, related-video clicks, and
subscribers. At 7 days, inspect watch minutes per impression, Short-to-full
starts, subscribers per 1,000 engaged views, playlist continuation, and
returning viewers. Do not call a raw view spike a win.

YouTube changed public view counting on 2026-08-27 so a view can count when
playback begins; engaged views and most core performance measures remain the
quality signal. Preserve both fields in future reports.

## Feature garden

| Decision | Feature | First bounded experiment |
|---|---|---|
| Adopt next | FFmpeg `blurdetect` + `freezedetect`; use `ssim`/`xpsnr` only for aligned reference/delivery comparisons. | Run no-reference blur/freeze checks on one known-sharp and one soft candidate, then compare one lossless render to its delivery encode. Evidence only, never creative approval. |
| Adopt next | YouTube audience-retention report using `elapsedVideoTimeRatio`, `audienceWatchRatio`, `relativeRetentionPerformance`, `startedWatching`, and `stoppedWatching`. | Read one Short and one full song over the same seven-day window and map drops to the local cue/timeline map. |
| Trial | Remotion `@remotion/captions` parsing and word/page timing. | Render a 10–15 second burn-in from an existing SRT while keeping the SRT authoritative. |
| Trial | FFmpeg `afir` with a project-owned impulse response. | Try a low-wet, short IR on one field-call stem; reject it if the first-second source loses identity. |
| Trial | Apple `h264_videotoolbox` for previews only. | Compare wall time, size, full decode, and SSIM/XPSNR against canonical `libx264`. |
| Hold | Metal, Faust, Skia, OpenTimelineIO, WhisperKit, BirdNET, Essentia, Godot, and new generative-music lanes. | Revisit only when a measured bottleneck or concrete song brief makes the extra surface worthwhile. |

The portable EPRS source, provenance, review gates, and software `libx264`
delivery remain canonical. Optional tools must not become hidden authorities.

## Source and implementation references

- `docs/ANIMAL_COMMUNICATION_ROADMAP_2027.md`
- `docs/YOUTUBE_ANALYTICS.md`
- `docs/TECHNOLOGY_GAPS_20260829.md`
- `src/eprs/release.py` and `tests/test_release.py`
- `scripts/youtube_analytics_report.py`

Official capability references checked for this sprint:

- [YouTube title and thumbnail A/B testing](https://support.google.com/youtube/answer/16391400?hl=en)
- [Related videos in Shorts](https://support.google.com/youtube/answer/14075157?hl=en)
- [Clickable and non-clickable YouTube links](https://support.google.com/youtube/answer/13748639)
- [YouTube end screens](https://support.google.com/youtube/answer/6388789?hl=en)
- [YouTube Analytics audience-retention report](https://developers.google.com/youtube/analytics/channel_reports)
- [YouTube Analytics revision history](https://developers.google.com/youtube/analytics/revision_history)
- [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html)
