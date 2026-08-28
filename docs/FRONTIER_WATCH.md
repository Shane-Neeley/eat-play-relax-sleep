# Frontier watch and capability loop

EPRS should keep looking toward the next useful edge: newly reported results,
new tools, newly open questions, and capability changes that could alter what
is possible in science, music, or ordinary life. This is a scouting loop, not a
belief system and not a license to turn hype into fact.

The public repository does not choose a news source, browse a private site, or
claim that a breakthrough is real. An external adapter can freeze a dated
[`eprs.frontier-watch/v1`](../templates/frontier-watch.json) packet, and EPRS
can validate its shape before an agent or human continues the work:

```bash
./scripts/eprs frontier validate /tmp/frontier-watch-2026-01-01.json
```

The packet is deliberately split into four layers:

1. **Lead** — what was reported, by whom, and where.
2. **Mechanism** — why it might work and what bottleneck or second-order effect
   would follow if it holds.
3. **Capability test** — the smallest reproducible task with an oracle,
   constraints, and a preserved artifact. Code execution, numerical checks,
   counterexample searches, proof obligations, and independent comparisons are
   stronger than fluent explanations.
4. **Creative test** — one bounded original translation into sound, image,
   interaction, or another medium. This is an experiment, not evidence that the
   underlying science is true.

## Human direction, formal pressure, and the closed loop

The most useful collaboration is asymmetric. A human supplies the strange
direction: a thought experiment, cross-domain analogy, physical intuition, or
question that would not be selected by a narrow search routine. The model then
does the unglamorous pressure-testing: formalizes the idea, explores its
consequence-space, runs code and numerical experiments, searches for
counterexamples, and keeps the provenance legible.

A useful shorthand is **Einstein → Dirac**: intuition steers the search, then
formal structure is allowed to push back and lead where it points. This is not
a claim that either historical figure maps neatly onto a modern model. It is a
division of labor:

1. **Human direction** — propose the unusual bridge and the thought experiment.
2. **Formal translation** — turn it into a precise object, model, derivation,
   executable test, or proof obligation.
3. **Consequence-space exploration** — derive special cases, predictions,
   useful transformations, and failure modes.
4. **Oracle pressure** — run the fastest decisive check available, including
   counterexamples and independent implementations.
5. **Reality boundary** — state what computation established and what still
   requires measurement, experiment, peer review, or domain expertise.
6. **Iteration** — revise the intuition or abandon it, preserving the failed
   path instead of laundering it into a discovery story.

Cross-domain creativity is valuable precisely because many analogies are
wrong. More speculation without a filter mostly produces more pseudoscience.
The code/math combination matters because it lowers the cost and cycle time of
being wrong; it does not remove the need for an oracle.

## Compute-closed versus data-constrained questions

Classify a lead before making a strong prediction:

- **Compute-closed** — the relevant objects and rules are already available,
  so proof search, symbolic work, exhaustive checks, simulation, or existing
  data can settle a meaningful part of the question. Math is the clearest
  example.
- **Data-constrained** — the next decisive fact requires a new observation,
  physical experiment, clinical study, field recording, or instrument. Code can
  narrow the search and expose consequences, but it cannot manufacture the
  missing evidence.
- **Mixed** — formal work can solve the synthesis while reality still has to
  test boundary conditions or predictions. Much of physics belongs here.

The expected pace of progress differs across these classes. Do not turn a
compute-closed capability gain into a claim that every empirical bottleneck is
about to disappear. Record the boundary explicitly in
`candidate.empirical_boundary`.

## Consequence chains and markets

When a frontier lead could affect markets, keep the market story downstream of
the science and separate from the evidence:

`result → capability → adoption → new bottleneck → value capture → failure cases`

That chain is a scenario map, not proof of a stock outcome. Price movement,
market excitement, and a compelling narrative cannot validate a theorem or a
physical theory. EPRS may preserve the chain as a research consequence, but it
does not turn it into an investment recommendation or a substitute for
independent technical review.

## Daily-to-weekly operating loop

Each day, find a small number of genuinely new leads from primary papers,
preprints, datasets, official releases, or credible independent replications.
Do not force novelty when there is no signal. Select one lead and ask:

- What changed: knowledge, capability, cost, speed, or access?
- What is directly shown, what is inferred, and what remains unknown?
- What becomes newly scarce if the capability becomes cheap and widespread?
- What is the smallest test that could falsify the exciting interpretation?
- What can EPRS make that exposes the mechanism without pretending to prove it?

At the end of the week, review the preserved artifacts. Promote only results
that survived an independent check or a clearly stated negative result. Keep a
separate record of failed tests; a useful frontier loop learns from dead ends
instead of rewriting them as progress.

## Scientific and creative boundaries

- “Nobel-tier,” “phase transition,” and “Terry Tao-level” are hypotheses or
  aspirations unless a source and independent validation support the wording.
- Peer review is useful evidence, not a substitute for checking the method,
  code, data, or boundary conditions.
- Generated prose is not a proof. A benchmark gain is not automatically a new
  discovery. A compelling song is not a scientific result.
- Keep source rights, personal material, credentials, and private adapter logic
  outside public EPRS packets.
- When a result touches animals, people, medicine, or safety, add the relevant
  welfare, consent, legal, and domain-expert gates before any real-world test.
- Do not publish or upload a frontier-inspired EPRS artifact until it passes
  the normal research, rights, creative-quality, and human-approval gates.

The intended rhythm is: **human intuition → formal pressure → oracle → reality
boundary → one original thing → preserved failure or result**. The daily watch
still begins with new primary evidence, and the weekly review decides which
leads earned another cycle.
