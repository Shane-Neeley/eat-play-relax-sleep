# Research notes and design consequences

Reviewed 2026-08-11.

The chord-diagram research and the guitar/ukulele rendering contract now live
in [CHORD_DIAGRAMS.md](CHORD_DIAGRAMS.md), with a dedicated visual system in
[CHORD_DIAGRAM_DESIGN.md](CHORD_DIAGRAM_DESIGN.md). The practical consequence
is to author the progression and voicing separately from musical observations,
then let play-along visuals consume that same time map.

The nature-first audio research brief is maintained in
[Animal sound AI and creative use](ANIMAL_SOUND_AI_2026.md). It records the
2026 model landscape, open-model licensing boundaries, and the distinction
between measurable acoustic patterning and animal-language claims.

## Frontier watch as a reusable research loop

EPRS treats new scientific or technical breakthroughs as leads to investigate,
not as automatic facts or daily content prompts. An external adapter can freeze
the portable [`eprs.frontier-watch/v1`](../templates/frontier-watch.json)
contract. Validate it with `eprs frontier validate`, then carry one selected
lead through four separate questions:

1. What was actually reported, and what is the evidence stage?
2. What mechanism and new bottleneck would matter if it holds?
3. What smallest executable, mathematical, numerical, or independent test
   could falsify the exciting interpretation?
4. What small original musical or visual experiment exposes the relationship
   without pretending to prove the science?

The research loop is intentionally human-steered and machine-pressured. Let a
human choose the unusual conceptual direction—often through a thought
experiment or cross-domain analogy—then require the model to formalize it,
enumerate consequences, search counterexamples, and execute the cheapest
decisive checks. The collaboration is powerful because it filters creative
connections through mathematical and computational pressure; without that
filter, scaling speculation mostly scales pseudoscience.

Before claiming speed or a phase transition, classify the lead as
`compute-closed`, `data-constrained`, or `mixed`. Code and mathematics can
close a loop when the relevant objects and oracles are already available. They
can only prepare a data-constrained physics, biology, medical, or field claim;
new measurements and independent review still decide whether it corresponds
to reality. The portable frontier packet records this boundary alongside the
human direction and formal-pressure plan.

This is the EPRS version of a phase-transition watch: track when a capability
goes from hard to cheap or widely available, then look for the next scarce
resource and a concrete artifact. Generated explanations are not proofs,
benchmarks are not automatically discoveries, and a compelling song is not a
scientific result. Keep failed tests and unknowns visible. See
[`FRONTIER_WATCH.md`](FRONTIER_WATCH.md) for the daily-to-weekly loop and
privacy, rights, safety, and approval boundaries.

## Sound and acoustics research watch

Recent primary research about sound should remain a living input to EPRS. It
can suggest new source relationships, synthesis controls, spatial metaphors,
or visual behaviors, but it must not become a fixed EPRS style or a scientific
claim hidden inside a release. For each useful paper, preserve the DOI or
publisher URL, authors, publication and access dates, method/measurement,
important boundary conditions, rights note, and one original experiment. Keep
the paper's observation separate from EPRS's interpretation and from what a
listener might feel.

The current example is [Midair Single-Sided Acoustic Levitation in High-
Pressure Regions of Zero-Order Bessel Beams](https://doi.org/10.1103/pfkh-4x7j),
by Yusuke Koroyasu, Christopher Stone, Yoichi Ochiai, Takayuki Hoshi, Bruce W.
Drinkwater, and Tatsuki Fushimi (published 2026-08-24; accessed 2026-08-29),
which reports stable three-dimensional levitation in the high-pressure axial
core of a zero-order Bessel beam, controlled translation, simultaneous
multi-particle cases, and persistence beyond an obstruction. Its useful EPRS
translation is not “make levitation music”; it is a small study in a stable
audible center, independent slow controls, disturbance, and recovery. The
paper reports specific apparatus and physical conditions, so the resulting
music/video must be labeled an original research translation rather than a
physical simulation or demonstration. See the public [research translation
note](research/pressure-finds-a-center.md); song-bound production records stay
in the ignored local creative workspace.

The article is marked open access under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/);
EPRS uses attribution and the article's text-level observations only. Figures,
movies, and other components can have separate rights and are not copied into
the project.

For future daily research prompts, favor one current primary sound/acoustics
source plus one narrow, reversible EPRS test. Use supplemental data when it
changes the interpretation, search for competing or boundary-condition papers,
and stop when the translation would require unsupported claims, unlicensed
material, or a new always-on subsystem. This keeps scientific novelty,
creative variety, and agentic navigation connected without over-prescribing any
one result.

- Sonic Pi's official tutorial supports local WAV/AIFF/FLAC samples, directory indexing, MIDI, OSC, and multichannel audio. Consequence: Sonic Pi is a live-code/performance adapter, and portable recordings remain project assets rather than being embedded in generated code.
- Sonic Pi listens for local OSC on port 4560 by default; remote OSC requires an explicit preference. Consequence: localhost control can be prototyped safely, while network control is deliberately out of the default path.
- Sonic Pi v5.0.0 (released 2026-08-07) replaces scsynth with SuperSonic, adds live audio-device changes, separate volume/drive controls, MIDI-clock following, Ableton Link audio, game-controller input, session video recording, and richer runnable documentation. Consequence: EPRS exposes these as optional, human-operated capabilities and keeps lossless stem capture plus EPRS review as the release boundary. See [Sonic Pi in EPRS](SONIC_PI.md).
- Audacity's official manual supports macros and external scripting through `mod-script-pipe`, but explicitly warns that enabling it weakens local security and is unsuitable for a web service. Consequence: no automatic pipe enablement; file interchange is the baseline.
- FFmpeg's official filters include EBU R128 analysis and loudness normalization. Consequence: `analyze` records measurements, while normalization remains a delivery decision rather than an automatic creative edit.
- YouTube currently recommends MP4, progressive H.264 High Profile, 4:2:0, BT.709 SDR, native frame rate, AAC-LC/Opus stereo at 48 kHz, and fast-start metadata. Consequence: the video adapter encodes those properties but does not replace the lossless master.

## Finding papers like the groove study

For a musical question, search for the phenomenon, the measurable variable, and
the musical context together. Useful starting queries include:

- `groove rhythmic complexity 4/4`
- `urge to move syncopation meter`
- `pulse entropy groove perception`
- `swing microtiming groove perception`
- `bass low frequency rhythmic complexity groove`

Use Google Scholar, Crossref, PubMed, or Semantic Scholar for discovery, then
open the publisher or DOI record. Prefer peer-reviewed primary studies for
musical claims and official release notes or repositories for tool claims.
Verify the authors, publication date, method, participants, tempo, meter,
instrumentation, and outcome measure before translating a result into a song.

The most productive next step is citation chaining: follow the paper's
references for foundational work, then use cited-by and related-paper links for
replications, competing results, and boundary conditions. Search the boundary
terms explicitly when the original study does not match the proposed track—for
example `vocals`, `live performance`, `microtiming`, `swing`, or `bass`.

Record each useful paper as a compact card:

1. What question did it test?
2. Who or what was studied, and under what musical conditions?
3. What was directly observed or measured?
4. What limitation prevents overgeneralizing it?
5. What one small, original EPRS experiment follows from it?

Keep the source URL, publication/access dates, finding, limitation, and copying
boundary in the song's `code/research.json`. Treat any arrangement choice that
goes beyond the measured result as an interpretation. When the research needs
to be reused across agents or experiments, promote it through
[`eprs research add`](RESEARCH_RECORDS.md) into a frozen attributed record.

## Orthogonal directions worth exploring

1. **Room as control voltage:** extract a room or field-recording envelope or spectral centroid and map it to synthesis/visual parameters without replacing the recording.
2. **Call-and-response agent roles:** one agent proposes a groove, another only describes what the body hears, a third runs technical QA. Keep their artifacts separate so taste is not collapsed into metrics.
3. **Performance diff, not waveform diff:** compare two takes by landmarks, energy, and phrase intention rather than sample alignment.
4. **A rhythm microscope:** animate one bar at multiple representations—player language, count syllables, grid, event times, waveform—to build intuition between code and feel.
5. **Physical release controls:** use OSC from a small local controller to fade/remove algorithmic layers while a live performance remains unconstrained.
6. **Lineage as liner notes:** promote experiment provenance, instruments, rooms, and human decisions into credits and visual storytelling instead of treating metadata as bureaucracy.

## Primary sources

- [Sonic Pi official tutorial](https://sonic-pi.net/tutorial.html)
- [Audacity scripting manual](https://manual.audacityteam.org/man/scripting.html)
- [Audacity macros manual](https://manual.audacityteam.org/man/macros.html)
- [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html)
- [YouTube recommended upload encoding settings](https://support.google.com/youtube/answer/1722171?hl=en)

## Animal communication as a response-song research lane

For a song intended to be potentially testable with animals, search for the
behavioral mechanism first and the recording second. Useful query families:

- `species call playback response timing`
- `vocal turn taking [species]`
- `context dependent vocalization [species]`
- `animal communication contingent playback`
- `bioacoustics call response latency`
- `animal welfare playback acoustic experiment`
- `species-specific playback control stimulus`
- `ZF-AIM`, `DolphinGemma`, `elephant name-like calls`, `marmoset phee`

Use a primary communication or playback paper, a behavior/welfare source, and
then an iNaturalist recording only as a licensed sound reference. iNaturalist
can show what a call sounds like and where/when it was observed; it does not
establish what the call means. Record the exact observation, sound ID,
contributor, license, retrieval date, and checksum.

Before composing, write the response hypothesis in observable terms: what
would count as orientation, approach, avoidance, altered call rate, response
latency, turn-taking, repetition, or no response? Include a matched control
and stop conditions. Treat “vibe” as an artistic prompt, never as a result.

See [`docs/ANIMAL_SOUND_AI_2026.md`](ANIMAL_SOUND_AI_2026.md) and
[`docs/ANIMAL_COMMUNICATION_ROADMAP_2027.md`](ANIMAL_COMMUNICATION_ROADMAP_2027.md)
for the EPRS evidence ladder and the `not-run` playback boundary.

## Simulating audience reactions

For jokes, YouTube packaging, and songs, EPRS can run a synthetic audience
panel as a hypothesis generator. Freeze the exact stimulus and variants,
define one observable outcome, sample explicit behavior-based personas, run
multiple model families and seeds, and compare the distribution against a
small human panel or real platform outcome. Store disagreement and calibration
error, not just a flattering average.

The relevant research warns against treating believable agents as predictive
crowds: generative-agent architectures create memory and emergent interaction;
Turing Experiments compare simulated participants with known human studies; and
newer conversation evaluations find that LLM populations often underproduce
human inconsistency and interruption. See
[`AUDIENCE_SIMULATION.md`](AUDIENCE_SIMULATION.md) for the tool/account map and
the boundary between a local experiment and a real audience measurement.
