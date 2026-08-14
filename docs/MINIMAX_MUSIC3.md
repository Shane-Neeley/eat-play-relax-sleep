# MiniMax Music 3 in EPRS

MiniMax Music 3 is an optional structured-song instrument, not a replacement
for EPRS. It accepts tagged lyrics plus a detailed music description and can
generate a complete song with vocals and evolving arrangement. EPRS keeps the
model output as a source stem, then owns the creative comparison, mix, master,
visuals, credits, and release gates.

## Current hardware decision

The official checkpoint is about 31.9 GB before runtime overhead and the model
card currently requires CUDA. The official low-VRAM path still targets an 8 GB
CUDA card with aggressive offloading. The current EPRS machine is an Apple M4
Mac mini with 16 GB unified memory, so the checkpoint is not downloaded here.

The portable adapter is `scripts/minimax_music3_runner.py`. It calls an
explicitly operated CUDA sidecar at `http://127.0.0.1:8000/v1/audio/speech`
by default, or the URL in `EPRS_MINIMAX_MUSIC3_URL`. It does not download
weights, start a remote service, or handle credentials.

Example:

```bash
python3 scripts/minimax_music3_runner.py \
  --lyrics-file lyrics/music3-song.txt \
  --instructions "Global Metadata: ... Vocal Details: ... Arrangement: ..." \
  --out audio/minimax-music3.wav \
  --seed 20260814
```

The runner preserves a `.wav.json` manifest beside the output. The response
is expected to be 32 kHz, 16-bit stereo WAV; EPRS can then convert a derived
working stem to the project rate without changing the source bytes.

## Caption design

Use three layers in the `--instructions` text:

1. **Global Metadata:** genre, BPM, key, scale, emotional arc, listening
   situation, and production profile.
2. **Vocal Details:** fictional voice character, register, articulation,
   harmony, backing vocals, and effects.
3. **Arrangement:** section-by-section instruments, bass movement, drum pocket,
   transitions, negative space, and spatial treatment.

Keep lyric section tags on their own lines. The model card lists `[Intro]`,
`[Verse]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Instrumental]`, `[Solo]`,
and `[Outro]` as useful tags, but they remain generative controls rather than
strict guarantees.

## License and release

The model is distributed under the MiniMax-Music3 Community License. Preserve
the license with the project. The license requires prominent display of
“MiniMax-Music3” in a commercial product or service using the software and its
acceptable-use policy requires clear, prominent disclosure when machine-
generated content is placed in a public environment. Any public EPRS release
must carry the model disclosure and must separately clear lyrics, references,
voices, and samples.

Official references:

- [MiniMax Music 3 model card](https://huggingface.co/MiniMaxAI/MiniMax-Music3)
- [MiniMax Music 3 Community License](https://huggingface.co/MiniMaxAI/MiniMax-Music3/blob/main/LICENSE)
- [MiniMax Music 3 source repository](https://github.com/MiniMax-AI/MiniMax-Music3)

## EPRS fallback rule

When the CUDA sidecar is unavailable, continue with the local general-purpose
pipeline: Sonic Pi or BeatScript for the bed, Qwen3-TTS/Bark for short original
voice cues, and EPRS autotune only after source pitch and duration are measured.
Record the fallback honestly in the song manifest; do not claim that a local
render came from MiniMax Music 3.

## ComfyUI prompt-writing guide notes

Reviewed 2026-08-13 from the [ComfyUI MiniMax Music 3 guide](https://docs.comfy.org/tutorials/audio/minimax/minimax-music-3#prompt-writing-guide).

Reusable EPRS rules:

- Keep the caption in exactly three conceptual blocks: **Global Metadata**,
  **Vocal Details**, and **Arrangement**. Include genre, BPM, key/scale,
  emotional arc, listening situation, production profile, vocal character,
  harmony/effects, instruments, groove, bass, textures, and space.
- Put structure in tagged lyrics. Use tags such as `[Intro]`, `[Verse]`,
  `[Pre-Chorus]`, `[Chorus]`, `[Post-Chorus]`, `[Bridge]`, `[Instrumental]`,
  `[Solo]`, and `[Outro]`; keep prose instructions out of lyric lines.
- Treat `seed` as a reproducibility control and duration as a resource/shape
  control. Longer generations need more VRAM; tiled decode and INT8 are CUDA
  deployment options, not assumptions for this Mac.
- For animal songs, describe the animal recordings as field-source textures or
  cards, never as lyrics or animal language. Preserve the raw call first, then
  describe the tuned chord-tone response as an authored arrangement decision.
- Use the official demo tracks and MiniMax caption-rewriter skill as references
  for specificity, but keep EPRS's generality: the same schema must allow
  weird meters, new tools, instrumental tracks, and non-MiniMax fallbacks.

The current animal implementation is `songs/four-corners-call/`: four CC0
iNaturalist sources, measured creative studies, raw-to-tuned response stems,
structured caption, tagged lyrics, BeatScript bed, and Sonic Pi source.
