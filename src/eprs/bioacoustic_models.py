"""Small, explicit catalog of bioacoustic AI integrations and boundaries."""

from __future__ import annotations


MODEL_CATALOG_SCHEMA = "eprs.bioacoustic-model-catalog/v1"

_MODELS = (
    {
        "id": "naturelm-audio",
        "label": "NatureLM-audio",
        "status": "optional-open-model",
        "tasks": ["classification", "captioning", "embeddings"],
        "taxa": "multi-taxa",
        "license_note": "Check the current checkpoint and dataset terms before redistribution or commercial use.",
        "source": "https://huggingface.co/EarthSpeciesProject/NatureLM-audio",
    },
    {
        "id": "perch-2",
        "label": "Perch 2.0",
        "status": "optional-open-research-tool",
        "tasks": ["classification", "embeddings", "few-example-search"],
        "taxa": "birds-and-broader-bioacoustics",
        "license_note": "Code, checkpoints, and datasets can have different terms; inspect the selected checkpoint.",
        "source": "https://github.com/google-research/perch",
    },
    {
        "id": "birdnet",
        "label": "BirdNET",
        "status": "optional-open-tool",
        "tasks": ["bird-classification", "embeddings"],
        "taxa": "birds",
        "license_note": "The repository documents model terms separately from code; the current model terms are noncommercial/share-alike.",
        "source": "https://github.com/birdnet-team/birdnet",
    },
    {
        "id": "biosen",
        "label": "BioSEN",
        "status": "2026-research-candidate",
        "tasks": ["bioacoustic-enhancement"],
        "taxa": "animal-vocalizations",
        "license_note": "Research candidate; compare every enhancement with the immutable source.",
        "source": "https://arxiv.org/abs/2605.12534",
    },
    {
        "id": "dolphingemma",
        "label": "DolphinGemma",
        "status": "in-development",
        "tasks": ["sequence-modeling", "sound-generation"],
        "taxa": "dolphins",
        "license_note": "Not an EPRS dependency; official release status and terms must be checked before use.",
        "source": "https://deepmind.google/models/gemma/dolphingemma/",
    },
    {
        "id": "zf-aim",
        "label": "ZF-AIM",
        "status": "2026-research-prototype",
        "tasks": ["interactive-playback", "sequence-modeling"],
        "taxa": "zebra-finches",
        "license_note": "Research prototype; playback experiments require animal-welfare and behavioral review.",
        "source": "https://www.biorxiv.org/content/10.64898/2026.02.12.705387v3",
    },
)


def bioacoustic_model_catalog() -> dict:
    """Return a copy so callers cannot mutate the shared registry."""
    return {
        "schema": MODEL_CATALOG_SCHEMA,
        "reviewed_at": "2026-08-11",
        "models": [dict(model, tasks=list(model["tasks"])) for model in _MODELS],
        "interpretation_boundary": "A model classification, embedding, caption, or continuation is not proof of animal intent or a translation.",
    }
