# Production pattern: shader window inside an editorial UI

Date: 2026-08-29
Project: Everybody Gets the Downbeat

This release records a deliberate break from recent full-frame procedural films. A straight 2/4, 132 BPM spoken electro-funk pocket is paired with a 1920x1080 original cream/editorial shell. The shell contains a 1280x720 vGPU shader viewport, so the moving shader reads as a musical instrument/session window while the surrounding cards explain state, meter, tempo, and arrangement.

## What worked

- The shell gives the shader a strong silhouette and makes the visual contract legible before motion is considered.
- vGPU 0.3.1 headless WebGPU on local Metal passed `vgpu doctor` and a bounded draft/full render.
- A meadow/eclipsed-disc WGSL world supplies motion without another lantern, waterline, ribbon, particle, shoe, or instrument lane.
- Small sans UI labels are more useful here than a poster headline; the thumbnail remains a truthful video frame.
- The hard-stop ending gives the 103-second package a decisive last state instead of another ambient fade.

## Guardrails

The UI is an original Pillow adaptation inspired by broad editorial principles from [Beautiful UI](https://www.beautifului.dev/), not a copied interface or brand asset. The shader, music, speech cues, shell, thumbnail, captions, and composite are deterministic local work. YouTube disclosure is **No** for this package because no generative-AI asset or meaningful AI alteration is used.

## vGPU watch list

The official [vgpu README](https://github.com/vercel-labs/vgpu/blob/main/README.md), [CHANGELOG](https://github.com/vercel-labs/vgpu/blob/main/CHANGELOG.md), and [release history](https://github.com/vercel-labs/vgpu/releases) were checked on 2026-08-29. The local package is `vgpu@0.3.1`, currently latest. Future probes should test watched WGSL imports, bounded pre-warm/in-place updates, bundle/replay paths, and portability without changing approved assets. A small regression fixture should compare renderer hash, controls sidecar, frame count, and final audio duration together.

## Reuse rule

Keep this pattern as a single successful experiment, not a template. Hard-ban the exact 2/4 × 132 BPM spoken electro-funk × cream UI/eclipsed-shader triple for the next run; change meter, sound source, emotional temperature, and visual medium.
