# Production patterns — Five Steps to the Glow (2026-08-25)

This note records reusable production lessons from the ChatGPT Scheduler EPRS run. It is intentionally public-safe: the daily reading spark is abstracted, and no source wording, personal details, or private context is repeated.

## Creative pattern

- A 104 BPM 5/4 BeatScript grouped 3+2 made the hook feel playable by stating the first three steps plainly and leaving a small breath before the two-step answer.
- One true eight-bar subtraction (kick and bass out, lead retained) gave the form a visible and audible quiet corner. The F# minor turn and late octave lift made the return feel earned instead of looped.
- The video used four procedural comet trails on a deep-plum field. Heads grew, crossed, braided around the center, and separated into a short coda. This silhouette is distinct from recent EPRS arches, planes, dials, marbles, rails, banners, and single-filament line art.

## Technical pattern

- `resolution 16` expands to 20 steps for 5/4; declaring `resolution 20` is rejected by BeatScript. Odd-meter note lengths should be inspected by creative preflight and explicitly approved when the off-grid push is intentional.
- Render sparse geometry at 960x540/24 fps, then keep a unique source path through EPRS picture capture and YouTube assembly. This keeps the render bounded while preserving BT.709 H.264 delivery.
- Picture capture resolves source/evidence paths from the repository root while approved-master paths remain song-relative. Prefix those fields deliberately and run the capture gate before packaging.
- The browser-first Studio picker accepted the FINAL MP4 and completed copyright checks. UI metadata interactions briefly reverted to the filename-derived title; reapply exact title/description last, verify “All changes saved,” and use the authorized API update once if Studio state stalls. This avoided a duplicate upload.
- Studio subtitle picker did not complete through the UI bridge, so the authored English SRT was uploaded once with the authorized API helper. No generative-AI media was used; YouTube disclosure was set to No.

## Frontier watch

The official FFmpeg page reports 9.0.1 (2026-08-12). A local FFmpeg 8.0.1 blend oracle passed with a preserved 64x64 artifact; the public renderer stayed Pillow-only until cross-version behavior is verified. Packet: `/Users/bestrobot/.openclaw/workspace/eprs-frontier-five-steps-20260825.json`.

## Verification and handoff

The public URL is `https://www.youtube.com/watch?v=XDcnQX8D-X0`; watch and thumbnail HTTP checks returned 200, and yt-dlp matched the CashForClankers channel, channel ID, title, public state, and 232-second duration. EPRS receipt: `songs/five-steps-to-the-glow/notes/publications/426deceeab2e55e6eaad40dee2b2ae097ad9df2a07ed105808827934d1398f41/receipts/xdcnqx8d-x0-6eb69b8304.json`.

The targeted checks passed. `make test-fast` still has one unrelated pre-existing failure in `tests/test_quality.py::test_public_release_refuses_to_self_certify_without_report` caused by a macOS temporary-path `ValueError` before the expected assertion; no production asset depended on that test.
