# Attributed research records

Research can shape a song without turning another artist, video, book, or idea
into a template to copy. `eprs research` freezes what was consulted, what was
directly observed, what was interpreted, what remains uncertain, and the
smallest original musical questions worth hearing.

The command is local and deterministic. It does not browse, search YouTube,
download a page, transcribe media, or grant permission to reuse source material.
A person or authorized agent performs the research and supplies source metadata
and, when useful and lawful, a local evidence file.

## Create a record

Start with the editable example:

```bash
cp templates/research.json songs/signal-garden/code/call-response-research.json
# Replace every placeholder. Remove `work` for standalone research, or bind it
# to one completed research work run.
./scripts/eprs research add \
  songs/signal-garden/code/call-response-research.json \
  --song songs/signal-garden
```

The normalized `eprs.research-record/v1` is written under:

```text
songs/<song>/notes/research/<title>-<research-id>/
  research.json
  evidence/                 # only when local evidence_path files were supplied
```

Running the same spec again returns the same record. Source evidence is copied
and checksummed without changing the original. URLs are stored as attribution;
they are not fetched. `local` and `local-file` sources require
`evidence_path`. Other source kinds are open text so books, interviews, liner
notes, performances, papers, philosophies, and future media can share the same
contract. A `youtube` source must use a YouTube URL.

## Evidence, inference, and open questions

Every finding has one of three explicit kinds:

- `observation`: something directly heard, seen, or read; it must cite at least
  one source.
- `interpretation`: a proposed meaning or causal reading; it must cite at least
  one source and should use honest confidence.
- `open-question`: an unresolved question; it may have no source.

Confidence is `direct`, `supported`, `tentative`, or `unknown`. Every finding
also requires:

- `musical_consequence`: how the idea might affect this project's own music;
- `copying_boundary`: what must not be reproduced from the reference.

Do not paste long quotations, lyrics, transcripts, screenshots, downloaded
audio, or video into a record merely because a URL is public. Record concise
source-grounded statements and the rights context. Freeze local evidence only
when the current authorization and source rights allow it.

## Turn research into sound

Research experiments are proposals, not decisions. Each one connects finding
IDs to a hypothesis, the smallest test, and a listening question. Promote only
one narrow relationship at a time:

```bash
./scripts/eprs experiment \
  --song songs/signal-garden \
  --source "research=notes/research/<record>/research.json" \
  --source "family voices=recordings/raw/family-voices/<take>.wav" \
  --hypothesis "Can one late chime extend the family breath without closing the guitar invitation?" \
  --seed 23
```

When research began in the work queue, use the optional `work` object in the
research spec to bind the record to one completed run. The record snapshots the
request, completion decision, agent, and every checksummed result through the
shared `eprs.completed-work-origin/v1` contract. A changed or
missing work result invalidates verification. `eprs work promote` remains useful
when all selected work-run results should enter an experiment together.

## Inspect and hand off

```bash
./scripts/eprs research show <research-directory> --song songs/signal-garden
./scripts/eprs status songs/signal-garden --verify
./scripts/eprs context songs/signal-garden --verify --format markdown
```

Status counts sources, findings, experiment ideas, completed-work origins, and
invalid records. Context includes bounded source attribution, observation versus
interpretation, confidence, musical consequence, copying boundaries, and small
experiment ideas. It never embeds frozen source evidence or external media.
