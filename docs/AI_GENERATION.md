# Optional AI audio generation

Mid-2026 update, researched 2026-08-10. This is a production ranking, not a
claim that a model is original, rights-cleared, or musically useful. Re-check
the exact code, weight, dataset, input, and service terms before a public
release.

EPRS treats a generator as one optional instrument. It receives one bounded
hypothesis and returns candidates plus provenance. It does not replace raw
recordings, taste, arrangement, listening, rights review, or the editable mix.

## Current ranking

| Rank | Method | Fit for this project | Main constraint |
| --- | --- | --- | --- |
| 1 for voices | **Qwen3-TTS 1.7B / 0.6B** | Best immediate voice upgrade for this Mac: Apache-2.0 models with VoiceDesign, CustomVoice, instruction-level emotion/prosody control, 10 languages, and a documented 3-second cloning path. The v2 song uses CustomVoice with a built-in speaker; VoiceDesign remains available for described synthetic characters. | The model is speech-first, not a singing model; keep cues short and arrange them as authored samples. Voice cloning still requires explicit consent and rights for the reference. |
| 1 for whole songs | **ACE-Step 1.5** | MIT-licensed whole-song model with text/lyrics, reference audio, cover/repaint/extract/complete modes, 48 kHz variable-length output, and a consumer-GPU-oriented stack. It now has a real local M4 result: a seeded 20-second E-major instrumental completed through native MLX/MPS in planner-free turbo mode. | The first environment download is large and slow; the tested 8-step render took 35.2s for diffusion plus 10.6s for VAE decode. Output still needs listening, provenance, and rights review. Keep it optional and do not upload private voices. |
| 2 for singing | **Seed-VC v1 f0-conditioned** | Real local MPS result: zero-shot singing conversion completed on an EPRS vocal at 10 diffusion steps, 44.1 kHz, about 3.5× realtime. It is a useful vocal-layer experiment rather than a song generator. | GPL-3.0; keep it isolated until release-licensing implications are accepted. The Mac path needed a float32 pitch cast and a SoundFile WAV-export workaround. Do not treat a converted synthetic voice as a performer identity. |
| 2 for singing | **SoulX-Singer** | Apache-2.0 zero-shot singing voice synthesis with melody/F0 or MIDI conditioning; architecturally closer to a controllable sung hook than ordinary TTS. | Separate preprocessing models and a Python 3.10 environment; not installed in this Mac pass. Treat it as an explicit future singing-voice experiment. |
| 3 for voices | **Fish Audio S2 Pro** | 5B multilingual TTS with inline free-form prosody/emotion tags, multi-speaker/multi-turn support, and streaming-oriented architecture. | Fish Audio Research License permits research/non-commercial use free; commercial use needs a separate license. Do not use it for release-bound voices without that clearance. |
| research | **UniVoice / X-Voice / PFluxTTS** | Mid-2026 research shows a clear direction toward unified speech+singer models, smaller multilingual cloning, and flow-matching voice synthesis. These are useful design signals for future adapters. | A paper is not an installable, licensed, reproducible project asset. Wait for official code/weights and hardware evidence before adding them to the default path. |
| research | **HeartMuLa / Muse / YuE / WanSong** | Stronger candidates for lyric-to-song or long-form research, with useful structure, tags, or stem ideas. | Hardware, license, conditioning, or reproducibility constraints keep them out of this local voice pass. |

### Implemented in EPRS

The shared registry now declares an optional `local_voice_generation` capability
and a Qwen3-TTS adapter. `scripts/qwen3_tts_voice.py` supports bounded
VoiceDesign or CustomVoice batches and writes a checksum-bearing render manifest.
It can also preserve raw cues and pass them through the optional, local
[formant-aware pitch processor](VOCALS.md). It does not start a service, upload
audio, clone a person, or promote output to a master.

The immediate engineering decision is therefore to support Qwen3-TTS as the
optional local voice path and ACE-Step as the optional whole-song path, not to
vendor either model or make either one required.
Run:

```bash
./scripts/eprs doctor --workflow local-ai-collaboration
./scripts/eprs adapter show ace-step-local-generator --handoff brief-to-candidates
PATH=.eprs-local/qwen3-tts/bin:$PATH ./scripts/eprs doctor --workflow local-voice-collaboration
./scripts/eprs adapter show qwen3-tts-local-voice --handoff brief-to-voice-cues
```

The adapters only describe the boundary. They do not start a server, download
weights, send recordings, or claim that output is approved.

## 2026-08-13 local model-lab evidence

Two candidates crossed the “actually ran on this 16 GB M4” threshold in an
isolated cache. ACE-Step 1.5 generated a 20-second, 48 kHz stereo instrumental
with `acestep-v15-turbo`, native MLX DiT/VAE, 8 steps, seed `4242`, E major,
102 BPM, and no language-model planner. Seed-VC converted a 14.8-second EPRS
vocal with the f0-conditioned singing model at 10 steps and wrote a valid
44.1 kHz mono WAV after a portable float32/SoundFile compatibility fix.

These are evidence artifacts, not release defaults. Keep the environments under
an isolated model lab, preserve exact settings and checksums, and compare the
result against an authored EPRS control before adding either model to a public
song. The ACE-Step planner is not required for the tested instrumental route;
the partially downloaded planner should not be mistaken for a completed
planner benchmark.

## Suno: collaboration, credits, and API reality

Suno now exposes an [official developer platform](https://platform.suno.com/)
that describes a REST API for original songs, covers, and mashups. This changes
the earlier recommendation: investigate the official platform before any
reseller. Its public signed-out page does not expose an API credit schedule, so
EPRS still must not estimate or spend official API credits until the account
console provides a current quote and terms.

[APIFrame's Suno endpoint](https://apiframe.ai/docs/music/suno) could help as a
replaceable experimental provider: it documents text/custom-lyric generation,
asynchronous jobs/webhooks, follow-up operations, WAV downloads, and stem
separation. Rank it behind the official API. APIFrame is an additional data,
rights, billing, and availability boundary, and its own current marketing is
internally inconsistent: the same page says Suno has no official API even
though Suno's platform is live, and displays different free/paid credit counts
in its pricing cards and FAQ. Treat the console quote—not a landing-page
estimate—as authoritative.

The official pricing page currently displays annual-billing-equivalent prices
of **$8/month for Pro** and **$24/month for Premier** (taxes extra), with 2,500
and 10,000 monthly credits respectively. The free tier supplies 50 credits
daily but has no commercial use. Suno's help center describes 50 credits as
enough for 10 songs, so its own rough conversion implies about 500 songs per
Pro allotment or 2,000 per Premier allotment; editing, stems, model choice, and
future pricing can change the actual burn. Purchased top-ups require an active
subscription.

For this project:

1. Start with **one month of Pro**, manually, only when there is a specific
   comparison experiment. It is ample for a small A/B pilot and grants
   commercial-use rights to new songs made while the paid subscription is
   active.
2. Export the highest-quality audio and available stems manually, preserve the
   Suno link/id, subscription tier, creation date, prompt, uploaded-source
   checksums, and terms check date, then capture the result as external
   evidence. Never call a Suno result an EPRS master until it passes the normal
   mix/master/listening/rights gates.
3. Do **not upload family voices, private recordings, or anyone's likeness or
   voice** without explicit informed consent for Suno's current terms. Those
   terms grant Suno a broad, perpetual license over submitted content and voice
   models for service, monetization, promotion, marketing, and model
   improvement. A generic “okay to make a song” is not the same permission.
4. Pilot the **official Suno API first**, with an explicit user-operated
   credential, a small prepaid ceiling, private-by-default jobs, exact request
   and response capture, downloaded outputs, and per-operation cost receipts.
   Do not put a key in a song, runner profile, Git, log, or dispatch packet.
5. If APIFrame is tested, use it only behind the same provider-neutral boundary.
   Its July 2026 guide quotes **11 APIFrame credits per action** and two tracks
   from an initial generation. At its quoted $0.01 top-up rate, a narrow pilot
   of 20 generation actions plus 10 extend/stem actions would be 330 credits,
   or roughly **$3.30**. This is a planning example, not a current price
   guarantee; verify the console because the public pages conflict.
6. Keep family voices and private recordings local unless each performer (and a
   guardian where applicable) gives separate informed permission for the exact
   provider and current terms. APIFrame says it transmits necessary inputs to
   the underlying model provider and keeps API request logs for 90 days; using
   a reseller does not avoid Suno's submission terms.

Paid commercial-use rights do not guarantee copyright protection, uniqueness,
or non-infringement. Preserve substantial human authorship—performances,
lyrics, arrangement, editing, mix choices, and visual direction—and keep a
clear contribution log.

## Primary sources

- [Qwen3-TTS official repository](https://github.com/QwenLM/Qwen3-TTS),
  [Qwen3-TTS Hugging Face collection](https://huggingface.co/collections/Qwen/qwen3-tts),
  and [Qwen3-TTS technical report](https://arxiv.org/abs/2601.15621)
- [ACE-Step 1.5 project and license](https://github.com/ace-step/ACE-Step-1.5)
  and [ACE-Step 1.5 Hugging Face model card](https://huggingface.co/ACE-Step/Ace-Step1.5)
- [Seed-VC official repository](https://github.com/Plachtaa/seed-vc)
  and [Seed-VC GPL-3.0 license](https://github.com/Plachtaa/seed-vc/blob/main/LICENSE)
- [SoulX-Singer model card](https://huggingface.co/Soul-AILab/SoulX-Singer)
  and [SoulX-Singer paper](https://arxiv.org/abs/2602.07803)
- [Fish Audio S2 Pro model card](https://huggingface.co/fishaudio/s2-pro)
  and [Fish Audio technical report](https://arxiv.org/abs/2603.08823)
- [UniVoice paper](https://arxiv.org/abs/2606.05852),
  [X-Voice paper](https://arxiv.org/abs/2605.05611), and
  [PFluxTTS paper](https://arxiv.org/abs/2602.04160)
- [HeartMuLa official repository](https://github.com/HeartMuLa/heartlib)
- [YuE official repository](https://github.com/multimodal-art-projection/YuE)
- [Muse official repository](https://github.com/yuhui1038/Muse)
- [SongGeneration official repository](https://github.com/tencent-ailab/SongGeneration)
- [WanSong technical report](https://arxiv.org/abs/2607.14749)
- [Suno pricing](https://suno.com/pricing), [plan credit allotments](https://help.suno.com/en/articles/2410049),
  [paid-plan rights](https://help.suno.com/en/articles/9601665), and
  [terms of service](https://about.suno.com/terms)
- [Suno official API platform](https://platform.suno.com/)
- [APIFrame Suno documentation](https://apiframe.ai/docs/music/suno),
  [APIFrame API guide and action pricing](https://apiframe.ai/guides/suno-api-guide),
  [terms](https://apiframe.ai/terms), and [privacy policy](https://apiframe.ai/privacy)
