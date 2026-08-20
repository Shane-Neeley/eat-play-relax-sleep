# Production pattern: Counterweight Choir

This note records a reusable production lesson from the 2026-08-20 ChatGPT Scheduler EPRS run. It is intentionally public-safe: source inspiration was abstracted rather than quoted, and no operator or account credentials are included.

## Creative pattern

The starting spark was a ShaneNeeley.com passage about a chaotic group making room for a small solo moment. The release transformed that idea into a counterweight call-and-answer: a four-note bronze hook arrives immediately, the arrangement interlocks, a one-bell solo briefly removes the crowd, and the sub-bass inherits the hook before an open coda.

## Method

- Audio: 100 BPM 4/4 deterministic BeatScript, 35 tracks, built-in synth/percussion voices, handpan-like tones, bronze bell, and controlled sub-bass handoff.
- Study: a bounded Sonic Pi cue/sync sketch tested concurrent arrivals as a compositional prompt; it was not used as the final renderer.
- Mix/master: EPRS mix, mix-review, master, and master-approve gates; approved 24-bit/48 kHz stereo master at -20.8 LUFS and -2.1 dBFS true peak.
- Video: original Python/Pillow/FFmpeg procedural animation, 1.90:1 1280x674 source at 25 fps, with five suspended oxidized-brass/verdigris weights on lateral arcs. The small amber bell is the visual solo cue. Final YouTube assembly uses the approved master and BT.709-compatible H.264/AAC packaging.
- Thumbnail: a truthful frame from the video, padded to 1280x720; no title card, face, logo, stock media, or waveform.

## What worked

1. An immediate four-note hook made the instrumental identifiable before the pocket filled in.
2. A real reduction followed by sub-bass inheritance gave the form a clear musical hinge without vocals or external recordings.
3. A wide suspended-weight silhouette changed the catalog shape without repeating portals, tiles, shutters, paper, prism bands, or line fields.
4. Keeping the Sonic Pi idea as a documented bounded study preserved exploration while keeping the release portable and deterministic.
5. Public verification used the returned video ID, oEmbed title/channel readback, thumbnail HTTP 200, and an immutable EPRS receipt. The final media contains no generative-AI audio, video, images, voice, or meaningful AI alteration; the YouTube disclosure is No.

## Operational lesson

The browser-extension Studio tab accepted the upload dialog but did not expose its native picker to the visible Computer Use window (`chooser.setFiles` returned `Not allowed`). After one bounded native-picker attempt, the authorized YouTube Data API helper completed the upload and thumbnail operation without a duplicate upload. Telegram report delivery succeeded; the first WAV attachment timed out once, then succeeded on one bounded retry, and the video attachment succeeded.

## Evidence

- Song project: `songs/counterweight-choir/`
- Final release: `songs/counterweight-choir/FINAL/counterweight-choir-public-youtube-release-8ae36564c3/`
- Public receipt: `songs/counterweight-choir/notes/publications/8ae36564c37db37df91e42caeb66f7ff56e47877e4fbe21f13c8102dfa2ab0c7/receipts/0tvluyxtgrq-acac299182.json`
- Public video: https://www.youtube.com/watch?v=0TvLUyXtGRQ
- Source spark: https://www.shaneneeley.com/blog/coaching-basketball/
