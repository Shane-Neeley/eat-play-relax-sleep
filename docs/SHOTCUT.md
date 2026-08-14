# Shotcut integration

Shotcut is EPRS's optional open-source visual-editing lane. It is the local
alternative to a hosted editor such as ChatCut: no account, MCP login, cloud
upload, remote render, or publishing authority is required; there is no ChatCut account.

The installed Mac currently reports Shotcut `26.8.1` and MLT `7.41.0`. This is
also the current upstream release researched on 2026-08-14; it adds the
Elements asset panel and Shake filter and fixes subtitle timing, Motion Tracker
keyframes, rotated proxy behavior, and macOS `.mlt` opening. The EPRS handoff
stays version-neutral: the JSON score is the source of truth, while `project.mlt`
is an editable projection for the installed Shotcut version.

[26.8.1]: https://www.shotcut.org/blog/new-release-26.8.1/

## What EPRS now does

`eprs shotcut compile` creates a real local MLT timeline instead of merely
opening an MP4. The generated project uses original song-local media references,
a separate guide/master audio track, editable Shotcut annotations, section-level
looks and animated transforms, qtext title cards, an optional accent track, and
Shotcut-recognized blend transitions. It rejects raw or external paths.

`eprs shotcut prepare` remains as a compact repeatable `--segment` interface;
it preserves an equivalent structured score and calls the same compiler.
`eprs shotcut render` uses Shotcut's bundled `melt` with a non-overwriting
H.264/AAC output and checksum sidecar. Its AAC track is guide audio only; final
delivery discards it and replaces it with the separately approved master.
`eprs shotcut open` launches the exact
project with isolated app data and does not authenticate or contact a service.

For headless renders, keep the consumer invocation minimal: the generated MLT
already carries the project profile. Adding ad-hoc FFmpeg flags such as
`+faststart`, an explicit size, or a second codec selection can make the
bundled macOS MLT reach 99% and fail to finalize the MP4 `moov` atom. EPRS
therefore records the exact bundled `melt` command and lets the project
profile choose H.264/AAC; verify the resulting file with `ffprobe` before
creative review.

Example:

```sh
./scripts/eprs shotcut compile songs/my-song/code/shotcut-score.json \
  --song songs/my-song

./scripts/eprs shotcut render \
  shotcut/my-project-a1b2c3d4e5/my-project.mlt \
  --song songs/my-song \
  --out video/my-project-shotcut-v1.mp4 \
  --quality full

./scripts/eprs shotcut open \
  shotcut/my-project-a1b2c3d4e5/my-project.mlt \
  --song songs/my-song
```

Use the generated `.mlt` in Shotcut. The adjacent `project.json` records the
score, source hashes, exact application/MLT versions, services, null-render
validation, GUI-open state, and authority boundary.

## Learned music-video workflow

The productive Shotcut pattern is simple and deliberately general:

1. **Hook first.** Put the strongest visual identity in the first 1–4 bars.
   Use hard cuts during the opening if the beat is fast; do not hide a weak
   opening under transitions.
2. **Pocket, lift, payoff.** Use longer holds after the hook, then shorter
   cuts or a keyframed push-in during the lift. Let the payoff breathe instead
   of cutting constantly.
3. **Markers are the contract.** Add identity, pocket, lift, drop, hook, and
   turnaround markers. Keep bar/beat timing in `timeline.json`; manually add
   colored markers in Shotcut when doing subjective work.
4. **Motion follows energy.** Use `Size, Position & Rotate` keyframes with
   smooth interpolation for a musical camera move; use linear or hold changes
   for deliberate hits. Keep the animal or subject inside the safe area.
5. **Separate roles.** Name and organize tracks as `V1 HERO`, `V2 OVERLAYS`,
   `V3 LYRICS`, `A1 MUSIC`, `A2 SFX`, and `A3 VOX`. Keep the master WAV
   separate from embedded source-video audio.
6. **Use proxies only for review.** Proxy Editing and Preview Scaling are for
   responsive editing. Final export must use the original media, not preview
   scaling.
7. **Review creative and technical separately.** First watch at normal speed
   for pull and clarity. Then check captions, frame rate, audio mapping, loudness,
   credits, private text, and rights with local tools.

Shotcut does not currently provide one-click automatic audio ducking. For a
voice, animal call, or lyric moment, use a Gain/Volume filter with four manual
keyframes: normal → duck → hold → restore. Keep the EPRS mastered WAV as the
audio source of truth; Shotcut is the picture and review lane.

## Shotcut operations worth practicing

- `M`: add a timeline marker.
- `Shift+S`: split at the playhead; lock the music track before splitting only
  picture when appropriate.
- `Cmd+7`: open Keyframes on macOS.
- `F4`: toggle Proxy Editing.
- `F6`–`F9`: adjust Preview Scaling.
- `Cmd+E`: open Export.
- `File > Open MLT XML as Clip`: reuse a tested intro, title sequence, or
  visualizer as a nested editable building block.

For lyric videos, choose one caption route: keep an editable SRT, burn it in
with Subtitle Burn In, or create a deliberate text-on-timeline layer. Do not
stack all three accidentally.

MLT `qtext` uses Qt's eight-digit `#AARRGGBB` color order, not CSS
`#RRGGBBAA`. For example, a translucent warning-red background is
`#b0b00000`; treating that value as CSS RGBA renders an unintended blue block.

## Local test and export loop

```sh
./scripts/eprs shotcut open shotcut/my-project/project.mlt \
  --song songs/my-song

./scripts/eprs shotcut render shotcut/my-project/project.mlt \
  --song songs/my-song --out video/shotcut-candidate.mp4 --quality full

# Verify the candidate before EPRS picture review.
ffprobe -v error -show_streams -show_format -of json \
  songs/my-song/video/shotcut-candidate.mp4
```

The MLT export is a render check; creative approval still requires watching
the result in Shotcut or a local player. Never overwrite a master, raw asset,
prior candidate, provenance record, or FINAL package. Save every revision under
the song's `shotcut/` directory with a new name.

## Safety and boundaries

- Only derived, already-reviewed media belongs in a shared visual project.
- The adapter does not install, authenticate, upload, download, edit remotely,
  or publish.
- MLT files are descriptors, not self-contained media packages. Keep the
  original song-local media, checksums, score, and `project.json` together.
- Human edits are subjective. Treat the generated MLT as a version-specific
  convenience layer, not as the canonical musical arrangement.

## Official learning references checked 2026-08-14

- [Shotcut tutorials](https://www.shotcut.org/tutorials/)
- [Shotcut User Guide](https://shotcut.org/stockmedia/Shotcut%20User%20Guide.pdf)
- [Keyboard shortcuts](https://www.shotcut.org/howtos/keyboard-shortcuts/)
- [MLT XML documentation](https://mltframework.org/docs/mltxml/)
- [Shotcut MLT XML annotations](https://www.shotcut.org/notes/mltxml-annotations/)
- [Shotcut command-line options](https://www.shotcut.org/notes/command-line-options/)
- [MLT property animation](https://www.mltframework.org/docs/propertyanimation/)
- [Keyframe types and easing](https://forum.shotcut.org/t/keyframe-types-and-easing/42271/1)
- [Timeline markers](https://forum.shotcut.org/t/timeline-markers/30535/1)
- [Proxy Editing](https://forum.shotcut.org/t/settings-proxy-editing/18517/1)
- [Audio ducking discussion](https://forum.shotcut.org/t/audio-ducking-again/51727)
