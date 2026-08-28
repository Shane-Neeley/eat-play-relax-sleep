# Animal communication roadmap: late 2026–2027

This roadmap turns the 2026 research brief into bounded EPRS work. It is a
research-and-composition plan, not a promise that EPRS will decode animal
language or conduct animal experiments.

## Product boundary

EPRS has three separate lanes:

| Lane | Allowed output | Not allowed |
| --- | --- | --- |
| Evidence | Frozen iNaturalist sound, provenance, measurements, context notes, model observations | Unverified coordinates, license assumptions, or model output replacing the source |
| Communication research | Offline event tables, embeddings, call clusters, response hypotheses, review manifests | Field playback, synthetic calls presented as natural calls, or “translation” claims |
| Songs | Human lyrics, authored rhythms, synths, vocals, visuals, and clearly credited reference use | Lyrics claiming what an animal said, public use of uncleared audio, or pretending a model response is animal intent |

The high-level data shape for future work is:

```text
source recording
  → individual / caller / receiver / context evidence
  → measured acoustic features
  → model observation (separately labeled)
  → behavioral-response hypothesis or reviewed playback manifest
  → authored musical response
```

## Work plan

### Late 2026: freeze the foundation

- Keep `eprs.inaturalist-audio/v1` and `eprs.inaturalist-creative-study/v1`
  backward-compatible.
- Keep the model catalog descriptive: source URL, task, taxon coverage,
  evidence mode, interaction risk, and license note.
- Add golden fixtures for one bird, one mammal, one insect or amphibian, and
  one sustained/low-frequency sound. Test zero attacks, overlapping calls,
  multiple sound IDs, failed downloads, and noncommercial licenses.
- Record a research observation separately from a creative study. A study may
  use the catalog, but a catalog entry is not a prediction.

### 2027 Q1: context and identity

Design an additive `eprs.animal-communication-event/v1` record, without
requiring model weights:

- recording checksum and time window;
- taxon plus confidence and source URL;
- caller and receiver IDs only when independently known;
- social or ecological context with an explicit source;
- acoustic features and model observations as separate namespaces;
- response window, behavior, and observer confidence;
- ethics, consent/permit, and playback status;
- unknown/ambiguous fields instead of guessed labels.

First implementation target: import a hand-reviewed event table and validate
its lineage. Do not start with automatic translation.

### 2027 Q2: optional descriptive models

Build adapters only where a real local or explicitly authorized runtime exists:

1. embeddings and nearest-neighbor search for similar calls;
2. individual/caller/context classification with held-out splits;
3. rare-call detection using conservative augmentation;
4. optional enhancement comparison that always retains the original.

Each adapter should emit model ID, checkpoint, version, input checksum,
runtime, output checksum, confidence, evaluation split, and license. Unknown
or out-of-distribution audio should be a valid result.

### 2027 Q3: interaction protocol, research-only

Prepare offline stimulus/response manifests inspired by ZF-AIM, DolphinGemma,
CETI, and the crow multimodal work. A manifest may describe timing, level,
species, context, and stop conditions, but it does not authorize playback.

Any real experiment is outside ordinary EPRS production and requires the
appropriate researchers, permits, welfare review, equipment, and operator. The
default EPRS state is `playback: not-run`.

### 2027 Q4: communication-informed song season

Make a small, distinct body of songs. Every song should answer one musical
question, keep the actual animal source reference-only unless cleared, and
include a liner-note sentence such as: “This is an authored response inspired
by measured call structure; it is not a translation.”

## Song slate

These are composition briefs, not claims about animal meaning.

### 1. “Names in the Low Air” — elephant addressing

- Source idea: individual-specific, name-like rumble structure.
- Musical rule: two low-register motifs, `caller` and `addressee`, with the
  second motif changing its contour rather than copying the first.
- Arrangement: sparse sub/rattle pulse, long air around the response, human
  chorus only after the call-and-response is established.
- Visual: two distant signal fields converge; no elephant sample is required.

### 2. “Phee Address” — marmoset turn-taking

- Source idea: directed phee calls, family-level acoustic accommodation, and
  response timing.
- Musical rule: short vocal cells trade across stereo positions; vary the
  answer when the “receiver” changes.
- Arrangement: conversational pocket, occasional missed entry, then a tighter
  ensemble response. Lyrics use names as human poetic devices only.
- Visual: small bright nodes hand off a pulse through a dense canopy.

### 3. “143 Windows” — sperm-whale combinatorics

- Source idea: rhythm, tempo, ornamentation, rubato, and recurring coda
  combinations.
- Musical rule: one motif has several timed/ornamented realizations; do not
  map 143 patterns to 143 meanings.
- Arrangement: low percussion, sub pressure, long pauses, and a late section
  where the same cell returns at altered tempo.
- Visual: a restrained underwater grid with no fake “translation” captions.

### 4. “Nest Visit” — crow context and quiet calls

- Source idea: quiet close-range calls, family care, and audio/video context.
- Musical rule: quiet sounds become the form; the loud chorus arrives only when
  the visual context says the group has assembled.
- Arrangement: found-percussion-like clicks made from authored synthesis, camera
  cue markers, and a human hook about showing up.
- Visual: nest-camera-inspired framing without using sensitive locations.

### 5. “Next Sound” — dolphin sequence hypothesis

- Source idea: next-token prediction and recurring structure, not a dolphin
  dictionary.
- Musical rule: each phrase predicts one transformation of the previous phrase
  while the bass remains stable.
- Arrangement: water-like synthesis, one memorable human vocal line, and an
  explicit model-disclosure note if a model actually renders any audio.

### 6. “Waggle Vector” — embodied bee communication

- Source idea: direction/distance information carried by a multimodal dance.
- Musical rule: angle controls pan, distance controls phrase length, and food
  quality controls density; all mappings are authored sonification.
- Arrangement: bright, precise, danceable, with a short process-story visual
  explaining the mapping instead of claiming to speak bee.

## Definition of done for each song

- iNaturalist sound is frozen with its own license and attribution, or the
  work uses only newly authored sound;
- the exact source is studied before musical roles are assigned;
- model observations, if any, are separately labeled and reproducible;
- raw source remains immutable and any public audio lineage is cleared;
- lyrics and description state “inspired response,” not translation;
- a complete listen/review records whether the song kept the research idea
  audible without becoming a science-fiction claim.

## New north star: response-capable songs, not animal-themed songs

Shane's current goal is to make research-backed musical stimuli that an
animal's behavior could respond to in a real, ethical test. "Vibe" is useful
creative shorthand, but it is not an evidence category. EPRS must never claim
that an animal likes, understands, or answers a song unless a qualified study
measures that behavior.

### What a response-capable song means

A response-capable song is designed around documented species-relevant
features and a falsifiable response hypothesis. It is not a claim that the
animal will enjoy human music, and it is not an animal-language translation.
At minimum, the design records:

- species, population/context, and the exact source or paper;
- measured call features such as interval timing, repetition, spectral range,
  amplitude envelope, duty cycle, turn-taking, and silence;
- the proposed target behavior: orientation, approach/avoidance, attention,
  call rate, response latency, turn-taking, repetition, or no response;
- a control or sham stimulus and pre-registered stop conditions;
- playback status, which remains `not-run` unless researchers, permits,
  equipment, and welfare review are present.

### Staged path from paper to possible response test

1. Select a species with documented communication structure and relevant
   playback/behavior literature.
2. Freeze an actual licensed recording or paper-derived feature set. Measure
   the signal before making any musical transformation.
3. Compose two related artifacts: a human-audible musical translation and a
   species-constrained stimulus whose parameters are explicit.
4. Build an offline stimulus/response manifest with controls, target behaviors,
   timing, and stop rules. Do not play it to an animal from the normal EPRS
   workflow.
5. If a qualified research partner later runs playback, publish null results,
   welfare observations, and uncertainty alongside any positive response.

### Response-song ideas

- **Reply Window** — zebra finch: call-then-silence timing and contingent
  turn-taking, with a non-contingent control. The musical version can make the
  timing legible; the test version should not assume a human melody.
- **Name / Not Name** — elephant or marmoset: compare an individual-directed
  signal pattern with a matched generic pattern. No semantic translation.
- **Quiet Address** — American crow: use context-labeled, low-duty-cycle call
  windows and silence rather than a looped field recording; target orientation
  or call response, not “crow groove.”
- **Coda / Countercoda** — sperm whale: explore inter-coda timing and
  ornamentation as an expert-only research concept, not an ordinary playback
  track.
- **No Song Yet** — a null/control composition with matched loudness and
  novelty but no species-specific cue, so any future response is not
  automatically attributed to the “song.”

### First-contact framing

Animal communication is a practical place to rehearse the humility of first
contact with another intelligence, whether biological, artificial, or
imagined. The art can make the bridge visible; the evidence must still come
from species-specific behavior. EPRS should say “designed for a future
behavioral test,” not “animals will vibe with this.” The current crow Short is
therefore an audience-facing curiosity/demo piece, not an animal-response
experiment; a future **Crow Reply Window** should be treated as a separate,
research-gated artifact.
