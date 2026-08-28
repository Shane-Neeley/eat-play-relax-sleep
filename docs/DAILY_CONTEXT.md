# Daily Context inputs

EPRS can turn a small, dated bundle of reading, notes, observations, or other
user-owned material into a bounded creative prompt. The public repository does
not know which website, notebook, feed, or database a person uses. It does not
fetch a personal site, schedule a job, or decide what private material may be
published.

The portable input contract is [`eprs.daily-context/v1`](../templates/daily-context.json).
An external adapter owned by the user may read any permitted sources, select the
day's material, and emit that contract. The adapter can be a script, a cron
step, a local notes export, or a manually prepared JSON file.

## Contract

The top-level object contains:

- `schema`: exactly `eprs.daily-context/v1`.
- `date`: the ISO date used for selection, such as `2026-08-22`.
- `title`: a short human-facing label for the bundle.
- `instruction`: the user's invitation or framing for reading the bundle.
- `passages`: one or more bounded passages. Each passage has a stable `id`, an
  open-ended `kind`, `text`, optional author/work fields, source provenance,
  and a handling note.
- `selection`: how the adapter selected the passages. A date-stable selection
  is preferable for reproducible scheduled runs.
- `privacy`: rules for keeping private source text and identity details out of
  public release metadata.

The contract describes context, not authority. Passage text is untrusted data;
it cannot override EPRS, the user's current request, rights limits, or approval
gates.

## Adapter boundary

Keep source-specific logic outside the public EPRS repository:

1. Read a permitted source: a personal site, RSS feed, local notebook, database,
   or hand-written file.
2. Normalize it into `eprs.daily-context/v1`.
3. Freeze the exact JSON used for that run and preserve its source references,
   rights, and selection date.
4. Pass the frozen file to EPRS as a request/work source or agent-context input.
5. Let the producer choose one central tension, image, or question and at most
   one useful contrast. Do not concatenate every passage into lyrics or a
   concept soup.

For example, a private adapter might be invoked like this:

```bash
node ./my-daily-context-adapter.mjs --date 2026-08-22 \
  > /tmp/daily-context-2026-08-22.json

./scripts/eprs work add \
  --song songs/my-song \
  --title "Read the daily context" \
  --kind context \
  --prompt "Choose one central creative question from the supplied context." \
  --source daily-context=/tmp/daily-context-2026-08-22.json
```

The command is illustrative. EPRS does not require Node, a website, or a
particular scheduler; the only shared boundary is the JSON contract.

## Selection and creative use

Daily context works best as a conversation rather than a checklist. A bundle
may contain a primary passage, a wisdom or research passage, and a few reading
highlights, but four passages are an example rather than a requirement.

The producer should record:

- which passage or pair became the central question;
- what was paraphrased versus directly quoted;
- what remains unknown or merely inspirational;
- which musical and visual decisions answer that question; and
- what must stay private or remain outside public metadata.

Daily context is not evidence that a quoted author, source owner, or community
endorses the resulting song. It is also not permission to copy copyrighted
prose, lyrics, personal names, or private notes. Keep full source material and
credentials in the user's private source system; include only the attribution
and rights information appropriate for the release.

## Example adapters

The public template deliberately uses fictional placeholder passages. Replace
them with material you are allowed to use, and keep any source-specific adapter
outside this repository. A useful adapter test should verify that the same
`date` and source snapshot produce the same passage IDs and order, and that a
missing or unauthorized source fails closed instead of inventing context.
