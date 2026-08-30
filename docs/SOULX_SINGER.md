# SoulX-Singer in EPRS

SoulX-Singer is the project’s score-conditioned singing lane. It is a zero-shot singing voice synthesis model: a short consented voice prompt supplies timbre, while a manually authored score supplies lyrics, phonemes, timing, and note targets. `control=score` makes the model synthesize a new sung performance around the requested notes; it is not the same operation as correcting an existing take with autotune.

The project uses the official Soul-AILab checkpoint and inference code locally:

- Code: `Soul-AILab/SoulX-Singer`, Apache-2.0, local commit `81aeb3ae772c70093c3de74dc23c92d983801ae4`.
- SVS checkpoint SHA-256: `447eaf41f91a6b6659d55e9ec3c9b809221724fb8592aebaec35a23751a5b500`.
- Config SHA-256: `d164c978dde6f57e1075bc21ef5f9b7b27895267f35b735cebe863418492be38`.
- Official sources: <https://github.com/Soul-AILab/SoulX-Singer> and <https://huggingface.co/Soul-AILab/SoulX-Singer>.

## How the local route works

1. Derive a 24 kHz mono prompt from the consented local Raon cue. The private reference remains outside the song workspace; the derived prompt is tracked only by its local manifest and checksum.
2. Write prompt metadata as one segment containing `time`, word-level `duration`, `text`, `phoneme`, `note_pitch`, and `note_type` fields.
3. Write target score metadata with the same fields. `note_pitch` uses MIDI note numbers; `0` is a rest. Keep the number and order of duration, phoneme, pitch, and note-type tokens identical.
4. Run the official CLI with `--control score`, an explicit phoneset, and the local MPS device. The output is a 24 kHz mono WAV.
5. Keep the raw generated render, score JSON, prompt lineage, model/config hashes, and a disclosure that this is synthetic score-conditioned singing. EPRS mixes resample the generated stem to the song’s 48 kHz clock without silently tuning, compressing, or normalizing it.

The reusable invocation is:

```bash
PYTHONPATH=.eprs-local/SoulX-Singer \
  .eprs-local/qwen3-tts/bin/python -m cli.inference \
  --device mps \
  --model_path .eprs-local/SoulX-Singer/pretrained_models/SoulX-Singer/model.pt \
  --config .eprs-local/SoulX-Singer/pretrained_models/SoulX-Singer/config.yaml \
  --prompt_wav_path <prompt.wav> \
  --prompt_metadata_path <prompt.json> \
  --target_metadata_path <target.json> \
  --phoneset_path .eprs-local/SoulX-Singer/soulxsinger/utils/phoneme/phone_set.json \
  --save_dir <generated-dir> \
  --auto_shift --pitch_shift 0 --control score
```

On this Mac, the local external checkout uses a small untracked compatibility patch in `soulxsinger/utils/audio_utils.py`: SoundFile plus torchaudio resampling is used instead of the TorchCodec-backed loader because the installed TorchCodec build does not match the available FFmpeg runtime. This is local environment state, not a project source change.

## Current project examples

- Natural Signal baseline: `songs/shane-s-natural-signal/audio/soulx-singer-v1/`.
- Howl Back prompt and score: `songs/howl-back/audio/soulx-singer-v1/`.
- Rhymed Chicko/Cuckoo story render: `songs/howl-back/audio/soulx-singer-v1/generated/chicko-rhymes/generated.wav`.
- Mix recipe: `songs/howl-back/code/howl-back-chicko-rhymes-mix.json`.

For Howl Back, the score is deliberately hand-aligned and note-led. The coyote recordings are not used as lyric or intent evidence; they are preserved iNaturalist sounds placed as call prompts, while the human response is authored in the score.

## Version watchlist

Checked 2026-08-19 before the Howl Back render. The official repository currently documents both score/F0-controlled SVS and a newer SoulX-Singer-SVC route for audio-to-audio singing voice conversion. The Hugging Face model page currently exposes both `model.pt` and `model-svc.pt`. The GitHub Releases page has no tagged releases, so “latest” must be determined from the official repository and model history rather than a release number.

Before every new singing pass:

1. Check the official GitHub README/commit history and the official Hugging Face model files.
2. Record any changed code commit, checkpoint checksum, config checksum, or new SVC/SVS capability in the song manifest.
3. Run a small A/B test on diction, note accuracy, timbre continuity, breath/phrase transitions, and artifacts before promoting a new version.
4. Preserve the current render as the comparison baseline; never replace it merely because a newer file exists.

The watchlist is intentionally a documented review gate, not an automatic downloader or publisher. No model update, upload, master, or YouTube publication is performed automatically.

## Consent and disclosure

Only the user’s consented local voice prompt is used for these project renders. Do not use SoulX-Singer to impersonate another person without authorization. Any public candidate should disclose that the lead is synthetic score-conditioned singing using a consented voice timbre prompt, and should keep animal-source attribution/provenance beside the release assets.
