# Animal sound AI and creative use

Reviewed 2026-08-11. This is a compact research brief for the EPRS nature-first
music workflow. The links are primary papers, official model pages, or project
repositories. A Google Scholar query is included as a discovery trail, but
claims are grounded in the linked paper or project rather than in a search
snippet.

## What is useful now

| Project | What it contributes | EPRS use | Boundary |
| --- | --- | --- | --- |
| [NatureLM-audio](https://arxiv.org/abs/2411.07186), [ICLR paper](https://openreview.net/pdf?id=hJVdwBpWjt), and [open model](https://huggingface.co/EarthSpeciesProject/NatureLM-audio) | An audio-language foundation model for bioacoustic detection, classification, captioning, and embeddings across taxa | Optional future local annotator for iNaturalist references; keep its output as a model observation beside the measured study | A caption or species score is not an animal-intent translation; verify against the iNaturalist taxon and recording context |
| [Perch](https://github.com/google-research/perch), [Perch 2.0 paper](https://arxiv.org/abs/2508.04665), and [Google's transfer report](https://research.google/blog/how-ai-trained-on-birds-is-surfacing-underwater-mysteries/) | Broad bioacoustic embeddings/classification, with transfer from terrestrial recordings to underwater tasks and agile few-example classifier workflows | Good candidate for a future embedding/nearest-neighbor lane for finding similar calls before sound design | Model availability, code freshness, and each checkpoint's license must be checked before commercial use |
| [BirdNET library](https://github.com/birdnet-team/birdnet) | Practical bird identification and embeddings; the repository documents current model formats and a large species label set | Optional bird-only validation and motif discovery for iNaturalist bird sounds | The code and model terms differ; the repository says the models are CC BY-NC-SA 4.0, so do not treat a detection model as commercially cleared |
| [BioSEN](https://arxiv.org/abs/2605.12534) | A 2026 bioacoustic enhancement model aimed at noisy animal vocalizations | Candidate preprocessing comparison for noisy field recordings; never replace the immutable original | Enhancement can invent or suppress signal; retain original-vs-enhanced comparisons and human review |

## Research frontier in 2026

- [ZF-AIM](https://www.biorxiv.org/content/10.64898/2026.02.12.705387v3) uses an interactive generative audio model with zebra finches to test communication rules. The important production lesson is the interaction loop: patterns become evidence only when behavioral context and playback responses are measured, not when a model generates a plausible continuation.
- [Automated detection of stereotyped animal sounds](https://www.nature.com/articles/s41598-026-48308-6) reports an openly available model/code path for data-scarce stereotyped calls. This supports the EPRS preference for small, reproducible detectors over a theatrical “translation” layer.
- [Controllable bioacoustic generation](https://www.sciencedirect.com/science/article/pii/S1574954126003249) explores diffusion-based bird-call generation conditioned by acoustic and textual features. Synthetic calls are useful as sound-design material or augmentation experiments, but they must never be mixed back into ecological training/evaluation data as if they were field recordings.
- [DolphinGemma](https://deepmind.google/models/gemma/dolphingemma/) is an official Google DeepMind project trained with Wild Dolphin Project data to model recurring structure and generate dolphin-like sequences. The page describes it as in development and says it will be openly available on release; it is not an EPRS dependency today.
- [Project CETI](https://www.projectceti.org/) continues the sperm-whale communication program using robotics, machine learning, and behavioral/ecological context. EPRS treats CETI-style work as a reason to preserve context and ethics, not as permission to turn a classifier into lyrics claiming what a whale said.

## Operating rule for EPRS

The iNaturalist sound is the auditable source. EPRS measures timing, energy,
rough pitch, and a brightness proxy, then creates five independent creative
domains:

- beats: attack spacing and density become an explicitly authored grid idea;
- noises: energy/brightness contrast becomes a processing starting point;
- lyrics: taxon and ecology become human metaphor, not a translated message;
- vocals: contour and spacing become original syllable/prosody prompts; and
- tones: measured pitch, when present, becomes a reference for an authored key
  and scale.

The generated record is `eprs.inaturalist-creative-study/v1`. It carries the
iNaturalist observation, sound ID, URL, attribution, license, checksum, and
retrieval provenance through audio lineage. Every creative field is marked as
an inference. Model predictions from future NatureLM, Perch, BirdNET, or other
open models should be added as separate evidence and should not overwrite the
measured source record.

## Discovery trail

- [Google Scholar: animal sound decoding AI 2026](https://scholar.google.com/scholar?q=animal+sound+decoding+AI+2026)
- [Google Scholar: bioacoustic foundation models](https://scholar.google.com/scholar?q=bioacoustic+foundation+models)
- [Google Scholar: animal communication generative audio model](https://scholar.google.com/scholar?q=animal+communication+generative+audio+model)
