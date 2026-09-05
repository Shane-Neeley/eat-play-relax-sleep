"""Small, explicit catalog of bioacoustic AI integrations and boundaries.

The catalog is deliberately a research registry, not an inference runner.  It
helps a study choose a bounded descriptive tool and makes interactive or
generative work visible without implying that EPRS has validated it.
"""

from __future__ import annotations

from copy import deepcopy


MODEL_CATALOG_SCHEMA = "eprs.bioacoustic-model-catalog/v1"

_MODELS = (
    {
        "id": "birdcode-sed",
        "label": "BirdCODE SED",
        "status": "optional-open-tool",
        "tasks": ["frame-level-sound-event-detection", "bird-classification"],
        "taxa": "birds",
        "evidence_mode": "descriptive-soft-prior",
        "interaction_risk": "none",
        "license_note": "Inspect the selected checkpoint and dataset terms before redistribution or commercial use.",
        "source": "https://huggingface.co/EarthSpeciesProject/sed-birdcode",
    },
    {
        "id": "naturelm-audio",
        "label": "NatureLM-audio",
        "status": "optional-open-model",
        "tasks": ["classification", "captioning", "embeddings"],
        "taxa": "multi-taxa",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "Check the current checkpoint and dataset terms before redistribution or commercial use.",
        "source": "https://huggingface.co/EarthSpeciesProject/NatureLM-audio",
    },
    {
        "id": "perch-2",
        "label": "Perch 2.0",
        "status": "optional-open-research-tool",
        "tasks": ["classification", "embeddings", "few-example-search"],
        "taxa": "birds-and-broader-bioacoustics",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "Code, checkpoints, and datasets can have different terms; inspect the selected checkpoint.",
        "source": "https://github.com/google-research/perch",
    },
    {
        "id": "birdnet",
        "label": "BirdNET",
        "status": "optional-open-tool",
        "tasks": ["bird-classification", "embeddings"],
        "taxa": "birds",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "The repository documents model terms separately from code; the current model terms are noncommercial/share-alike.",
        "source": "https://github.com/birdnet-team/birdnet",
    },
    {
        "id": "biosen",
        "label": "BioSEN",
        "status": "2026-research-candidate",
        "tasks": ["bioacoustic-enhancement"],
        "taxa": "animal-vocalizations",
        "evidence_mode": "descriptive-preprocessing",
        "interaction_risk": "none",
        "license_note": "Research candidate; compare every enhancement with the immutable source.",
        "source": "https://arxiv.org/abs/2605.12534",
    },
    {
        "id": "dolphingemma",
        "label": "DolphinGemma",
        "status": "in-development",
        "tasks": ["sequence-modeling", "sound-generation"],
        "taxa": "dolphins",
        "evidence_mode": "sequence-hypothesis",
        "interaction_risk": "high",
        "license_note": "Not an EPRS dependency; official release status and terms must be checked before use.",
        "source": "https://deepmind.google/models/gemma/dolphingemma/",
    },
    {
        "id": "zf-aim",
        "label": "ZF-AIM",
        "status": "2026-research-prototype",
        "tasks": ["interactive-playback", "sequence-modeling", "real-time-response"],
        "taxa": "zebra-finches",
        "evidence_mode": "interactive-hypothesis",
        "interaction_risk": "high",
        "license_note": "Research prototype; playback experiments require animal-welfare and behavioral review.",
        "source": "https://doi.org/10.64898/2026.02.12.705387",
    },
    {
        "id": "animal2vec-meerkat",
        "label": "animal2vec + MeerKAT",
        "status": "2026-research-candidate",
        "tasks": ["self-supervised-embeddings", "rare-event-detection", "interpretable-representation"],
        "taxa": "multi-taxa",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "Treat the paper, reference dataset, implementation, and checkpoints as separate terms.",
        "source": "https://doi.org/10.1111/2041-210x.70218",
    },
    {
        "id": "biome",
        "label": "BioME",
        "status": "2026-research-candidate",
        "tasks": ["embeddings", "classification", "edge-inference"],
        "taxa": "multi-domain-bioacoustics",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "Research candidate; verify implementation, checkpoint, and dataset terms before use.",
        "source": "https://arxiv.org/abs/2602.09970",
    },
    {
        "id": "rare-call-transfer-detector",
        "label": "Stereotyped-call transfer detector",
        "status": "2026-open-code-path",
        "tasks": ["few-shot-detection", "data-augmentation", "transfer-learning"],
        "taxa": "stereotyped-animal-sounds",
        "evidence_mode": "descriptive",
        "interaction_risk": "none",
        "license_note": "Use held-out recordings and report precision/recall; synthetic augmentation is not field evidence.",
        "source": "https://doi.org/10.1038/s41598-026-48308-6",
    },
)


_RESEARCH_TRACKS = (
    {
        "id": "contextual-communication",
        "label": "Contextual communication evidence",
        "question": "Who produced the signal, for whom, in what context, and what changed afterward?",
        "next_2027_step": "Add a human-reviewed event table that can bind audio, individual, receiver, behavior, and response without claiming a translation.",
    },
    {
        "id": "interactive-playback",
        "label": "Interactive playback",
        "question": "Does a bounded, welfare-reviewed response change the animal's timing, structure, or behavior?",
        "next_2027_step": "Keep playback out of ordinary EPRS production; prepare only offline stimulus/response manifests and review gates.",
    },
    {
        "id": "communication-to-song",
        "label": "Communication-informed composition",
        "question": "How can measured timing, turn-taking, identity, or context become an authored song constraint?",
        "next_2027_step": "Create songs from response rules and acoustic features while keeping the source call reference-only unless rights are explicitly cleared.",
    },
)


def bioacoustic_model_catalog() -> dict:
    """Return a copy so callers cannot mutate the shared registry."""
    return {
        "schema": MODEL_CATALOG_SCHEMA,
        "reviewed_at": "2026-08-31",
        "models": deepcopy(_MODELS),
        "research_tracks": deepcopy(_RESEARCH_TRACKS),
        "2027_plan": {
            "priority": [
                "preserve source and context",
                "run descriptive models with held-out validation",
                "separate interactive playback from composition",
                "turn measured structure into authored songs",
            ],
            "release_boundary": "No EPRS song, caption, or model record may present a classification, generated continuation, or musical response as a translation of animal meaning or intent.",
            "review_triggers": [
                "new checkpoint or license terms",
                "new playback or animal-interaction protocol",
                "new evidence about individual, addressee, context, or response",
            ],
        },
        "interpretation_boundary": "A model classification, embedding, caption, or continuation is not proof of animal intent or a translation.",
    }
