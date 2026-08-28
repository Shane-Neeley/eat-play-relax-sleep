# Animal sound AI and communication research

Reviewed 2026-08-21. This is the research brief for the EPRS nature-first
music workflow. The [linked 21 August 2026 post](https://x.com/itsolelehmann/status/2090831992200020253)
is a useful lead list, not a source of record: it compresses results from
different years, species, evidence levels, and research programs into one
story.

## What the post gets right—and what EPRS should say instead

| Post theme | Evidence status | EPRS wording and action |
| --- | --- | --- |
| Elephants use individually specific, name-like calls | Supported by a 2024 *Nature Ecology & Evolution* study using machine learning plus playback; the result is not a decoded elephant word | Say “name-like individual addressing” and preserve the playback response as behavioral evidence. Do not write “the elephant said X.” ([Pardo et al.](https://pubmed.ncbi.nlm.nih.gov/38858512/)) |
| Marmosets vocally label group members | Supported by a 2024 *Science* study of directed phee calls and receiver-specific responses; the exact call count in social posts is not an EPRS fact unless checked against the paper/data | Track `caller`, `receiver`, family group, call features, and response separately. ([Oren et al.](https://pubmed.ncbi.nlm.nih.gov/39208084/)) |
| Egyptian fruit bat calls contain emitter, addressee, context, and behavior information | Supported by a 2016 study; this is important precedent, not new 2026 evidence | Use it as a design pattern for contextual labels, not as a claim that EPRS can translate bat arguments. ([Prat et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5178335/)) |
| Sperm whales have a rich combinatorial coda space | Supported by the 2024 *Nature Communications* analysis reporting at least 143 frequently realized combinations; “phonetic alphabet” is an analogy for acoustic dimensions, not a human-language dictionary | Model rhythm, tempo, ornamentation, and rubato as measurable features; keep semantics open. ([Sharma et al.](https://doi.org/10.1038/s41467-024-47221-8)) |
| AI held real-time vocal exchanges with zebra finches | Strong 2026 research signal: ZF-AIM used generative audio playback, behavioral recordings, and ablations to test timing and call-structure effects; it is a preprint and an animal-interaction protocol, not a song generator | Keep interactive playback research-only. EPRS may study the protocol and build offline response manifests, but must not run field playback from an ordinary music command. ([James et al.](https://doi.org/10.64898/2026.02.12.705387)) |
| DolphinGemma predicts and generates dolphin-like sequences | Official Google DeepMind project in development, trained with Wild Dolphin Project data | Keep sequence generation as a model hypothesis. No implied two-way conversation, field deployment, or shared vocabulary. ([Google DeepMind](https://deepmind.google/models/gemma/dolphingemma/)) |
| Crows use quiet calls around nest visits and chick care | Supported by a 2026 preprint combining crow-borne audio-loggers, nest cameras, machine learning, and social context; the “may coordinate” wording matters | Make multimodal context a first-class future record. Do not collapse a quiet-call cluster into a fixed meaning. ([Cusimano et al.](https://doi.org/10.64898/2026.04.02.715916)) |
| A robot bee sent a destination through the waggle dance | The cited robot-bee result is older work, not a 2026 discovery; later work continues to test how dance information is used | Treat this as a multimodal, embodied communication reference. Any EPRS version is a data-inspired audiovisual composition, not an audio translation. ([Landgraf et al.](https://arxiv.org/abs/1803.07126)) |

The governing evidence ladder is:

1. `measured`: values computed from the exact frozen recording;
2. `model_observation`: classification, embedding, caption, cluster, or generated continuation;
3. `behavioral_evidence`: a recorded response under a declared protocol;
4. `composition`: a human-authored musical response.

Only the first three can support a biological statement, and each has a
different strength. The fourth is art. EPRS must never silently promote a
model observation or a musical response into animal meaning or intent.

## 2026 research signals that change the EPRS plan

- **Interaction is the high-value frontier.** ZF-AIM shows why timing,
  response contingency, and call structure should be evaluated together. A
  plausible generated continuation is not evidence until an ethical experiment
  measures what an animal does afterward.
- **Context is part of the signal.** The crow work combines audio, individual
  tags, nest video, and social behavior. This argues for event records that
  preserve who, whom, where-at-coarse-scale, what-happened, and response—not
  just a spectrogram or species label.
- **Data-efficient models are practical.** The 2026 stereotyped-call detector
  uses physically motivated augmentation and transfer learning from a single
  exemplar; it reports strong results on its evaluated whale task, but those
  results do not make synthetic examples field evidence. ([Jancovich et al.](https://doi.org/10.1038/s41598-026-48308-6))
- **Foundation models need task-specific evaluation.** A 2026 comparative
  review finds meaningful differences across Perch 2.0, NatureLM-audio/BEATs,
  BirdMAE, and general audio encoders on BEANS and BirdSet. EPRS should choose
  by task, held-out evidence, and license—not by the phrase “foundation model.”
  ([comparative review](https://doi.org/10.1016/j.ecoinf.2026.103765))
- **Representation learning is expanding beyond bird ID.** animal2vec and
  MeerKAT point toward self-supervised, rare-event, and interpretable
  representations for sparse bioacoustic data. That is a better near-term
  fit for EPRS than promising a universal translator. ([animal2vec and MeerKAT](https://doi.org/10.1111/2041-210x.70218))
- **Enhancement and generation stay bounded.** BioSEN is a research candidate
  for comparing noisy-signal enhancement; generated or enhanced audio must be
  stored beside, never over, the immutable source. ([BioSEN](https://arxiv.org/abs/2605.12534))

## Current EPRS contract

The iNaturalist sound remains the auditable source. EPRS freezes its exact
bytes, observation URL, sound ID, attribution, license, retrieval time, and
checksum. `eprs inaturalist study` measures timing, energy, rough pitch, and a
brightness proxy, then creates five independent creative domains:

- beats: attack spacing and density become an authored grid idea;
- noises: energy/brightness contrast becomes a processing starting point;
- lyrics: taxon and ecology become human metaphor, not a translated message;
- vocals: contour and spacing become original syllable/prosody prompts; and
- tones: measured pitch, when present, becomes a reference for an authored key
  and scale.

The record is `eprs.inaturalist-creative-study/v1`. Model output belongs in a
separate evidence record or declared model-observation field; it must not
overwrite the source, measured study, taxon, context, or rights record. Run
`scripts/eprs inaturalist models` to see the current catalog, interaction-risk
labels, research tracks, and 2027 review plan.

For exact audio in a public or monetized song, clear the sound-level license
first. CC BY-NC, all-rights-reserved, and unknown sounds remain reference-only.
The safe creative default is: listen to the real call, measure it, then write
an original musical answer.

## From animal-themed music to response-capable stimuli

The next EPRS direction is not simply music about animals. It is music whose
species-relevant parameters are explicit enough that a researcher could later
test whether an animal or group changes behavior. This is a design target, not
an effectiveness claim.

Keep three layers separate:

1. **Signal representation:** the measured call, context, timing, spectrum,
   repetition, silence, and caller/receiver relationship.
2. **Musical translation:** a human-audible composition that makes selected
   structure expressive.
3. **Experimental stimulus:** a controlled, species-constrained artifact with
   a response hypothesis, matched control, welfare limits, and a playback plan.

The minimum offline record for layer 3 is a stimulus/response manifest: taxon,
source checksum, call class/context, feature set, stimulus variants, control,
target behavior, observation window, stop conditions, playback status, and
reviewer/permit fields. A response such as orientation, approach, avoidance,
call latency, call rate, turn-taking, repetition, or no response is more useful
than the vague claim that an animal “liked” the song.

EPRS may compose and render layers 1 and 2 locally. Layer 3 stays playback
`not-run` by default and requires researchers, permits, species expertise,
appropriate equipment, and welfare review. No model output or musical mapping
should be described as an animal message. The public wording should be
“research-inspired and designed for a future behavioral test,” unless actual
behavioral evidence exists.

## Discovery trail

- [NatureLM-audio](https://arxiv.org/abs/2411.07186) and its [open model](https://huggingface.co/EarthSpeciesProject/NatureLM-audio)
- [Perch 2.0](https://arxiv.org/abs/2508.04665) and [Google's cross-domain transfer report](https://research.google/blog/how-ai-trained-on-birds-is-surfacing-underwater-mysteries/)
- [BirdNET library](https://github.com/birdnet-team/birdnet)
- [BioME](https://arxiv.org/abs/2602.09970), a resource-efficient 2026 bioacoustic foundation-model candidate
- [Project CETI research](https://www.projectceti.org/research/index)
- [2027 communication and song roadmap](ANIMAL_COMMUNICATION_ROADMAP_2027.md)
