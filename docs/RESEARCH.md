# Research notes and design consequences

Reviewed 2026-08-11.

The nature-first audio research brief is maintained in
[Animal sound AI and creative use](ANIMAL_SOUND_AI_2026.md). It records the
2026 model landscape, open-model licensing boundaries, and the distinction
between measurable acoustic patterning and animal-language claims.

- Sonic Pi's official tutorial supports local WAV/AIFF/FLAC samples, directory indexing, MIDI, OSC, and multichannel audio. Consequence: Sonic Pi is a live-code/performance adapter, and portable recordings remain project assets rather than being embedded in generated code.
- Sonic Pi listens for local OSC on port 4560 by default; remote OSC requires an explicit preference. Consequence: localhost control can be prototyped safely, while network control is deliberately out of the default path.
- Sonic Pi v5.0.0 (released 2026-08-07) replaces scsynth with SuperSonic, adds live audio-device changes, separate volume/drive controls, MIDI-clock following, Ableton Link audio, game-controller input, session video recording, and richer runnable documentation. Consequence: EPRS exposes these as optional, human-operated capabilities and keeps lossless stem capture plus EPRS review as the release boundary. See [Sonic Pi in EPRS](SONIC_PI.md).
- Audacity's official manual supports macros and external scripting through `mod-script-pipe`, but explicitly warns that enabling it weakens local security and is unsuitable for a web service. Consequence: no automatic pipe enablement; file interchange is the baseline.
- FFmpeg's official filters include EBU R128 analysis and loudness normalization. Consequence: `analyze` records measurements, while normalization remains a delivery decision rather than an automatic creative edit.
- YouTube currently recommends MP4, progressive H.264 High Profile, 4:2:0, BT.709 SDR, native frame rate, AAC-LC/Opus stereo at 48 kHz, and fast-start metadata. Consequence: the video adapter encodes those properties but does not replace the lossless master.

## Orthogonal directions worth exploring

1. **Room as control voltage:** extract a room or field-recording envelope or spectral centroid and map it to synthesis/visual parameters without replacing the recording.
2. **Call-and-response agent roles:** one agent proposes a groove, another only describes what the body hears, a third runs technical QA. Keep their artifacts separate so taste is not collapsed into metrics.
3. **Performance diff, not waveform diff:** compare two takes by landmarks, energy, and phrase intention rather than sample alignment.
4. **A rhythm microscope:** animate one bar at multiple representations—player language, count syllables, grid, event times, waveform—to build intuition between code and feel.
5. **Physical release controls:** use OSC from a small local controller to fade/remove algorithmic layers while a live performance remains unconstrained.
6. **Lineage as liner notes:** promote experiment provenance, instruments, rooms, and human decisions into credits and visual storytelling instead of treating metadata as bureaucracy.

## Primary sources

- [Sonic Pi official tutorial](https://sonic-pi.net/tutorial.html)
- [Audacity scripting manual](https://manual.audacityteam.org/man/scripting.html)
- [Audacity macros manual](https://manual.audacityteam.org/man/macros.html)
- [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html)
- [YouTube recommended upload encoding settings](https://support.google.com/youtube/answer/1722171?hl=en)
