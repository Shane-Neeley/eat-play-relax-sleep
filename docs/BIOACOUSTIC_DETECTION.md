# Bioacoustic event detection

EPRS now has a review-only animal-sound region ranker:

```bash
uv sync --extra bioacoustic
PYTHONPATH=src uv run --extra bioacoustic eprs bioacoustic detect SOURCE.wav \
  --species-table BirdCODE_predictions/SOURCE.txt \
  --reference KNOWN_GOOD.wav \
  --behavior pulse-train \
  --out detection-report.json
```

The ranker combines high-resolution spectral flux, broadband/transient
morphology, optional BirdCODE frame evidence, and handcrafted nearest-event
morphology relative to a same-taxon reference. The reference calculation is
not a learned Perch or BioME embedding. It never modifies the source, writes a
clip, or turns a score into an animal-intent or publication claim.

When `--species-table` is supplied, an event outside every matching target
interval is rejected instead of merely losing a small bonus. `--behavior
pulse-train` also requires at least four strong impulses separated by 25–220
ms. Use the default `--behavior transient` for isolated animal sounds such as
calls, snaps, clicks, or single impacts.

The detector is taxon-agnostic. Choose behavior from the waveform shape, then
use `--species` only to match the label in an external classifier or annotation
table:

```bash
# Whale song, wolf/coyote howl, frog tone, or another sustained call.
eprs bioacoustic detect SOURCE.m4a \
  --behavior sustained-call --sustained-min-snr-db 6 \
  --species "Megaptera novaeangliae" --species-table predictions.csv

# Cricket/katydid chirps or a slower cetacean click sequence.
eprs bioacoustic detect SOURCE.m4a \
  --behavior pulse-train --pulse-min-count 4 \
  --pulse-min-gap 0.025 --pulse-max-gap 0.5 --pulse-min-flux-z 3
```

Pulse timing is recording-specific, not a taxonomic rule. Keep the stricter
defaults for woodpecker drumming; expand the gap or lower the flux threshold
only while reviewing the extra false positives. Selection tables may use
BirdCODE/Raven columns or generic `Start, End, Taxon, Confidence` headings.
WAV/FLAC/OGG files use libsndfile; compressed sources such as the M4A files
commonly attached to iNaturalist observations are decoded in memory through
FFmpeg while retaining the original sample rate. The input bytes remain
untouched.

Analysis is bounded both by `--max-duration-seconds` (120 seconds maximum) and
by 1.5 million decoded samples per channel. High-sample-rate recordings may
therefore require a shorter lossless review region. Reports use portable paths,
hash every source/reference/table, refuse to overwrite an existing file, and
cannot be written into a song's immutable `recordings/raw/` or `FINAL/` lanes.

The report preserves every detected event for audit, but `target_segments`
is the usable review shortlist. Repeated impulses from the same pulse train
are grouped into one padded time range so downstream clipping does not treat
every hit as a separate candidate.

## Model bake-off

The following Hugging Face candidates were installed or exercised in the
isolated `.eprs-local` lab environment and ranked for the specific task of
finding a Pileated Woodpecker knock inside a noisy recording:

1. **BirdCODE SED** — best task fit. [Earth Species Project model](https://huggingface.co/EarthSpeciesProject/sed-birdcode)
   emits frame-level, time-aligned predictions across thousands of bird
   species. It is installed and usable through its official CLI. On the target
   recording it was too permissive: threshold 0.5 produced long Pileated
   regions, while threshold 0.8 retained only a 130 ms region. It is therefore
   a species prior, not the final waveform selector.
2. **BirdNET ONNX** — useful bird classifier and embedding backbone. [ONNX
   checkpoint](https://huggingface.co/justinchuby/BirdNET-onnx) was exercised
   with 3-second windows. It provides useful broad context but is too coarse
   for isolating individual knocks.
3. **Perch 2 ONNX** — useful general bird classifier/embedding model. [ONNX
   checkpoint](https://huggingface.co/justinchuby/Perch-onnx) was exercised with
   10-second windows. It can support reference search, but its temporal and
   class output is not a knock segmenter.
4. **BioME Edge** — promising compact encoder. [Model](https://huggingface.co/Hguimaraes/biome_edge_bio)
   was loaded locally and produced embeddings, but it has no ready-made
   Pileated-knock classification head, so it needs labeled examples first.

The earlier fused shortlist for the present recording was invalid. Its #1
event at 7.147 s had no overlap with a Pileated interval, and missing species
evidence was accidentally renormalized out of the score. The available coarse
BirdCODE table also marks most of the file as Pileated, so it cannot localize
drumming by itself. With the pulse-train gate, this recording has no qualifying
four-impulse target sequence and is reported as `no-target-candidates`. That
is a useful negative result: choose a better source instead of clipping more
background. The separate known-good reference remains calibration evidence,
not publishable media.

## Design boundary

Classification answers “what may be present in this window?” Segmentation
answers “where does a short acoustic event begin and end?” These are separate
problems. EPRS keeps both signals visible and requires a human listening gate
before any derivative is selected for a song or release.

## Cross-taxon verification

Automated tests cover these deliberately different acoustic regimes:

- an 80 Hz sustained whale-like call at 4 kHz sample rate;
- a 420 Hz canid howl at 8 kHz;
- 5 kHz insect chirps at 16 kHz with 300 ms spacing;
- compressed M4A decoding without source mutation;
- the original woodpecker pulse-train positive and noisy-source negative.

A real-recording smoke pass also decoded current iNaturalist M4A references for
humpback whale, coyote, and field cricket. Those files remain reference-only;
an observation taxon is not proof that every detected region contains that
animal, so external classifier intervals and listening review are still
required before clipping.
