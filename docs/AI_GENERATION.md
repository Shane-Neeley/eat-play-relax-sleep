# Optional AI music generation

Checked 2026-08-09. This is a production ranking, not a claim that a model is
original, rights-cleared, or musically useful. Re-check the exact code, weight,
dataset, input, and service terms before a public release.

EPRS treats a generator as one optional instrument. It receives one bounded
hypothesis and returns candidates plus provenance. It does not replace raw
recordings, taste, arrangement, listening, rights review, or the editable mix.

## Current ranking

| Rank | Method | Fit for this project | Main constraint |
| --- | --- | --- | --- |
| 1 | **ACE-Step 1.5 sidecar** | Best first pilot. The official project is MIT-licensed, exposes a local UI and REST server, accepts text and reference audio, supports cover/repaint/extract/complete workflows, records controllable random factors, and documents a core setup around 10 GB disk with low-memory modes. | The accelerated macOS package requires Apple Silicon. Intel macOS falls back to CPU and is likely too slow for a pleasant daily loop; use a deliberately operated GPU sidecar instead of silently installing a large stack. |
| 2 | **HeartMuLa 3B** | Apache-2.0 code and weights, strong lyric control, multilingual full songs, explicit temperature/top-k sampling, and a useful lyric transcriber/codec family. | The official repository still lists reference-audio conditioning and accelerated inference as unfinished; current inference is described around real time. Better for a lyric-generation comparison than the first mixed-input adapter. |
| 3 | **YuE** | Apache-2.0 full-song lyric-to-song generation, audio prompting, LoRA, and incremental community workflows. The project explicitly encourages artists to incorporate and monetize outputs with attribution. | Heavy: the official project recommends at least 80 GB GPU memory for longer multi-session songs and reports roughly six minutes on an RTX 4090 for 30 seconds of audio. Its older TODO still lists first-class seeding, so provenance and replay need extra care. |
| 4 | **Muse** | The strongest reproducibility research track: MIT code, public checkpoints, training/evaluation pipeline, and a released 116k-song dataset. Fine-grained segment-level style control could eventually map well to EPRS arrangement plans. | Young Linux/vLLM-oriented research stack with Python 3.10 and older dependency constraints. Audit dataset and checkpoint terms separately from the repository license before distribution. |
| hold | **SongGeneration 2 / LeVo 2** | Promising full-song quality, lyric accuracy, text direction, and audio prompting. | Uses custom Tencent terms. “Open source” in a project description is not enough to assume unrestricted commercial distribution. Keep out of the default production path pending an exact license review. |
| watch | **WanSong** | A July 2026 paper reports long songs with simultaneous vocal and backing stems, which is architecturally attractive for editable collaboration. | A paper is not an installable, licensed adapter. Wait for official code, weights, license, and hardware evidence. |

The immediate engineering decision is therefore to support ACE-Step as an
optional provider-neutral handoff, not to vendor a model or make it required.
Run:

```bash
./scripts/eprs doctor --workflow local-ai-collaboration
./scripts/eprs adapter show ace-step-local-generator --handoff brief-to-candidates
```

The adapter only describes the boundary. It does not start a server, download
weights, send recordings, or claim that output is approved.

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

- [ACE-Step 1.5 project and license](https://github.com/ace-step/ACE-Step-1.5)
  and [official installation/hardware guide](https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/INSTALL.md)
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
