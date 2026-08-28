# Audience-reaction simulation

EPRS can use simulated audiences to generate hypotheses about how people might
react to a joke, YouTube Short, title, thumbnail, opening, or song. It must not
present a synthetic crowd as a measured audience, a representative sample, or
an oracle for views.

## Why this belongs in the frontier loop

The relevant Latent Space episode is [“Simulation: the new Scaling Law”](https://podcasts.apple.com/us/podcast/latent-space-the-ai-engineer-podcast/id1674008350?i=1000784959326),
with Joon Sung Park, co-founder and CEO of Simile AI. The episode discusses
simulation, Simile AI, SimGym, and Fortune 100 clients. Park's work starts from
a different premise than ordinary persona role-play: ground simulated people
in qualitative interviews, behavioral data, and—when possible—causal evidence,
then test simulated responses against the real people or held-out human
studies they represent.

That makes Simile the directly relevant company for this research lane. Its
publicly described work is a research and commercial platform, not an EPRS
dependency or a popularity oracle. EPRS should borrow the evaluation idea—real
behavioral grounding, distributions, uncertainty, and calibration—without
claiming access to Simile's private systems or data.

[AI Town](https://github.com/a16z-infra/ai-town) remains a separate,
MIT-licensed open-source sandbox from a16z. It can give EPRS a concrete
laboratory for memory, movement, conversations, scheduled state updates, and
agent interaction, but it is not Simile and it does not establish that the
simulated characters predict real viewers.

The research boundary is important:

- Generative Agents shows how observation, memory, reflection, and planning can
  produce believable behavior in a small interactive world. Believability is
  not population-level predictive validity.
- Turing Experiments show a way to compare simulated participants with known
  human-study results, while also exposing systematic distortions in a model.
- Recent evaluation work finds that LLM conversations often underproduce the
  inconsistency, interruption, and uncooperative behavior seen in human
  conversations. A polished synthetic crowd is therefore suspiciously polite
  until calibrated.
- Social-media benchmarks such as SoMe provide task definitions for behavior
  prediction, emotion analysis, and comment simulation. They are useful
  evaluation scaffolds, not a direct answer to “will this song get views?”

The correct output is a calibrated hypothesis such as “this opening is more
likely to be understood by a curiosity-seeking viewer than by a music-first
viewer,” followed by a real test. It is not “the crowd liked it.”

## EPRS experiment design

Start with one observable outcome and one time horizon. Examples:

- Joke: setup comprehension, punchline recognition, laugh/share intent,
  confusion, or offense risk.
- YouTube Short: first-second stop intent, title promise comprehension,
  stayed-to-end intent, comment impulse, or replay intent.
- Song: first motif recognition, perceived groove, emotional direction, replay
  intent, and whether the ending feels earned. Text-only agents cannot hear the
  actual mix unless the audio is separately analyzed or presented to a human.

Then run this loop:

1. Freeze the exact stimulus, variant, prompt, model, seed, and persona packet.
2. Build a small, explicit audience panel from behaviors and constraints—not
   stereotypes or sensitive demographic guesses.
3. Ask each simulated participant for structured outputs: predicted action,
   probability or confidence band, reason, uncertainty, and the feature that
   changed its judgment.
4. Run multiple independent seeds, model families, and prompt orders. Do not
   let one model generate every persona and then judge its own predictions.
5. Compare variants under the same simulated population and preserve the full
   distribution, not only the mean score.
6. Calibrate against real human ratings, comments, retention, stayed-to-watch,
   or other platform outcomes when available.
7. Promote only robust directional findings into a creative revision or a
   small public experiment. Preserve failures and disagreement.

For EPRS, the most useful first experiment is not a giant town. It is a
controlled panel answering the same question about three title/opening/audio
variants, with a real human mini-panel used as the oracle. A Simile-style
grounding and evaluation design is useful even when the runner is local. AI
Town becomes valuable only when the question requires interaction, memory,
social diffusion, or turn-taking rather than a one-shot preference judgment.

## Tool and account map

### Start local and account-free

- EPRS Python runner plus JSONL/SQLite for frozen stimuli, persona packets,
  seeds, model outputs, and scoring.
- Ollama or another local OpenAI-compatible endpoint for private model sweeps.
- A small deterministic evaluator that checks schema, probability bounds,
  missing responses, seed coverage, and agreement/disagreement across models.
- Human ratings collected locally or through an explicitly approved form. Keep
  names, private messages, and raw personal data out of public EPRS artifacts.

### Add the AI Town sandbox when interaction matters

The official AI Town path uses TypeScript, npm, Convex, and an LLM provider. Its
README documents three useful deployment choices:

- local Docker/self-hosted Convex for an account-light experiment;
- a Convex account for the standard cloud development path;
- local Ollama, or an OpenAI-compatible provider such as OpenAI or Together,
  for the language model.

AI Town's architecture stores world, player, conversation, and agent state in
separate structures and advances the world in ticks. The documented limits
matter: the active state is intended to stay small, the engine is single
threaded, and the default interaction latency is not suitable for a
competitive real-time crowd. Use it as a transparent small-world laboratory,
not as a million-viewer simulator.

### Treat Simile as a research reference or external dependency

Simile is the company to watch for population and individual human-behavior
simulation. Public material describes a platform grounded in real-person
interviews and behavioral evidence, with validation against real responses.
Access, pricing, data rights, and reproducibility must be checked directly
before treating it as an available tool. No Simile account is assumed or
required for the local EPRS workflow.

### Connect reality only when needed

- YouTube Data API: public metadata and comments, subject to quota and OAuth
  boundaries.
- YouTube Analytics API: channel-owner OAuth and the correct analytics scopes
  for retention, stayed-to-watch, traffic, and audience metrics. EPRS currently
  has a 403 blocker on this lane, so raw public view counts remain confounded.
- Optional local analysis: DuckDB/SQLite, FFmpeg/FFprobe, and small Python
  plots for audio/video features and experiment receipts.

No new account should be created merely to produce a synthetic reaction score.
The recommended order is local panel → human calibration → optional
Simile-style grounding or AI Town interaction → real platform measurement.

## Safety and interpretation rules

- Never infer sensitive traits, identities, political views, health, or private
  attributes to make a persona feel realistic.
- Never scrape or upload private viewer data without explicit authorization.
- Never use simulated reactions to target vulnerable people or automate public
  persuasion.
- Never call a synthetic reaction “validated” until it predicts a held-out
  human or platform outcome better than a simple baseline.
- Report model, seed, population construction, prompt order, uncertainty,
  disagreement, and calibration data with every result.
- Keep the audience simulator downstream of creative quality review. It can
  identify a promising question or a likely comprehension failure; it cannot
  decide whether an EPRS song is good.

## Sources and research notes

- Podcast episode: [Simulation: the new Scaling Law — Joon Sung Park, Simile
  AI](https://podcasts.apple.com/us/podcast/latent-space-the-ai-engineer-podcast/id1674008350?i=1000784959326)
- Company: [Simile AI](https://simile.ai/) and [Joon Sung Park's research
  page](https://www.joonsungpark.com/)
- Direct grounding paper: [Generative Agent Simulations of 1,000
  People](https://arxiv.org/abs/2411.10109)
- Direct media-reaction benchmark: [SimTube: Generating Simulated Video
  Comments through Multimodal AI and User Personas](https://arxiv.org/abs/2411.09577)
- Optional interaction sandbox: [a16z-infra/ai-town README](https://github.com/a16z-infra/ai-town)
  and [AI Town architecture](https://github.com/a16z-infra/ai-town/blob/main/ARCHITECTURE.md)
- [Generative Agents: Interactive Simulacra of Human
  Behavior](https://arxiv.org/abs/2304.03442)
- [Using Large Language Models to Simulate Multiple Humans and Replicate Human
  Subject Studies](https://arxiv.org/abs/2208.10264)
- [CoCoEval: Evaluating LLM-Simulated Conversations](https://arxiv.org/abs/2603.17094)
- [SoMe: A Realistic Benchmark for LLM-based Social Media
  Agents](https://github.com/LivXue/SoMe)
