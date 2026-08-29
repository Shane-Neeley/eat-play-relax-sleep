# Optional Music Lanes

EPRS stays a general production platform. These tools are swappable experiments, not a preferred sound, a required dependency, or a new house style. A lane may be absent, replaced, or used for one song and then removed without changing the core workflow.

## Capability map

| Lane | Role | Current local posture |
| --- | --- | --- |
| ACE-Step 1.5 | Bed and candidate generation | Tested on the 16 GB M4 with native MLX/MPS; keep optional |
| Seed-VC | Singing voice conversion | Tested on the 16 GB M4 in singing mode; keep optional |
| OpenVPI GAME | Animal/vocal contour to MIDI | Declared and probe-only; not installed in this environment |
| Basic Pitch | Lightweight pitch and bend extraction | Declared and probe-only; not installed |
| DiffSinger | Note- and phoneme-controlled singing | Declared and probe-only; exact singer/vocoder license must be checked |
| Amphion Vevo1.5 | Higher-upside prosody/timbre transfer | Declared and probe-only; hardware and model stack are not verified |
| Demucs | Reversible stem laboratory | Declared and probe-only; preserve bleed and parent mix |
| SuperCollider / scsynth | Richer local synthesis, granular/sample work, and algorithmic composition | Installed as an optional macOS cask; adapter-only and not a core render dependency |
| OpenCV headless | Objective frame-quality and thumbnail evidence for picture candidates | Installed as an optional Python extra; bounded QA only, never creative approval |
| Sonic Pi / BeatScript | Deterministic groove, bass, fills, and structure | Core-compatible authoring options; never the only musical path |

## Experiment contract

Every optional lane must:

1. Preserve the original recording byte-for-byte and write new candidates elsewhere.
2. Record model/tool version, backend/hardware, seed, prompts or controls, source checksums, and the listening decision.
3. Keep technical success separate from musical approval, originality, rights clearance, and publication approval.
4. Provide a fallback path: Sonic Pi/BeatScript for beds, Qwen or Seed-VC for voices, note-aware retuning for responses, and FFmpeg/manual edits when a model is unavailable.
5. Make a short real song before promoting the lane into a reusable release workflow.

## Animal-to-melody pattern

The raw call remains the character. An analyzer such as GAME or Basic Pitch may propose notes, bends, or a contour; EPRS can then quantize or retune a separate response into the song key. The response should answer the call, not erase it. Confidence, silence handling, and false notes belong in the project record.

## Voice pattern

Start with a short phrase. Compare the unprocessed source, Seed-VC conversion, Qwen/TTS plus autotune, and any note-controlled singer. Keep the singer model optional. Do not imitate a living artist by name, clone a voice without permission, or publish a candidate until the exact model and vocoder rights are understood.

## Stem pattern

Demucs-style separation is a laboratory, not a guarantee of clean stems. Keep the parent mix, common time zero, model/version, bleed, artifacts, and reconstruction result. Use a separated bass or vocal only when it answers a specific arrangement question.

## Rights watch

Software and model weights do not share one license. Some community DiffSinger vocoder weights are non-commercial/share-alike, while AudioCraft model weights are CC-BY-NC. Check the exact model and vocoder files before monetized or public releases. If the rights are unclear, keep the experiment local and label it as such.

## Current proof songs

The option-garden benchmark projects are intentionally small and reversible. They combine tested ACE-Step and Seed-VC outputs with Sonic Pi, animal material, and manual/FFmpeg mixing. They are evidence that optional lanes can collaborate without collapsing the general platform into one model or genre.
