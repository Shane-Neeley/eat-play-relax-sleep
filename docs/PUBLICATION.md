# Offline YouTube publication handoffs

EPRS can prepare exact inputs for a future YouTube uploader and preserve what
that uploader reports afterward. It does not contact YouTube, authenticate an
account, authorize an upload, change visibility, or publish anything.

This boundary keeps three facts separate:

1. `FINAL/` is an immutable, locally verified release package.
2. A publication handoff identifies the exact video, metadata, checksums, and
   maximum intended visibility an uploader may be asked to use.
3. An append-only receipt records caller-declared external state after a
   separately authorized action; it does not rewrite the local release manifest.

## Prepare exact uploader inputs

After `eprs release` succeeds:

```bash
./scripts/eprs publication prepare \
  songs/signal-garden/FINAL/<release-directory> \
  --song songs/signal-garden
```

`eprs.youtube-publication-handoff/v1` lands at:

```text
songs/signal-garden/notes/publications/<release-id>/handoff.json
```

Preparation re-verifies the release recipe ID, every artifact checksum,
release verification flags, the approved YouTube video copy, and normalized
uploader metadata. When the release includes a reviewed YouTube asset bundle,
the handoff also binds the exact thumbnail, every caption track, chapters, and
bundle manifest under `recipe.upload_assets`. Artifact paths must remain inside
that exact FINAL package.
The resulting handoff is deterministic and idempotent.

Every handoff keeps both `upload_authorized` and `publication_authorized` false.
Those values never become true through this command. The handoff is private
project data and a technical input contract, not permission.

## External uploader contract

Only after explicit current-user authorization for the exact account, video,
metadata, and visibility may a separate authorized person, connector, browser
session, CLI, or future adapter:

- recheck the handoff and referenced checksums;
- upload the exact `video.path` bytes;
- apply the supplied title, description, tags, and no broader visibility than
  `metadata.visibility_intent`;
- avoid silently creating a second upload when a platform ID already exists;
- return the platform video ID, canonical HTTPS YouTube URL, actual visibility,
  upload time, actor, and authorization context.

Authentication, network policy, account selection, quotas, platform processing,
and the consequential upload action remain outside this local command set.

## Skill-aware YouTube operation

In a skill-aware agent host, use the environment-provided `youtube-channel`
skill for the separately authorized API or YouTube Studio operation. The skill
is an operator guide, not an EPRS capability, approval record, credential, or
authorization source. Its presence must not change the false authorization
flags in the handoff or bypass the explicit-current-user requirement above.

Before the skill uploads anything, give it the exact handoff and require it to:

- re-verify the visible destination channel at operation time;
- use only the handoff-bound video, metadata, thumbnail, captions, and chapters;
- apply no broader visibility than `metadata.visibility_intent`;
- verify upload, processing, checks, final visibility, and the resulting video
  ID rather than treating an open dialog or progress bar as success; and
- return the fields required by `eprs.youtube-publication-receipt/v1`.

Keep destination channel titles and IDs, account emails, OAuth project IDs,
browser-profile names, credential locations, tokens, and other operator-specific
state out of tracked EPRS files. Put machine-specific integration guidance in
ignored `.eprs-local/` data or in the external skill installation. Public
examples should say “the explicitly authorized channel” rather than naming a
real account. Do not add an account-specific publisher to `config/toolchain.json`
or `config/adapters/`: external publication remains a consequential operation,
not a detected local production capability.

## Record what happened

Copy and fill the receipt template only after the external action:

```bash
cp templates/publication-receipt.json /tmp/publication-receipt.json
./scripts/eprs publication receipt /tmp/publication-receipt.json \
  --song songs/signal-garden
```

The `eprs.youtube-publication-receipt/v1` input becomes an immutable
`eprs.youtube-publication-receipt-record/v1` under the handoff's `receipts/`
directory. The recorder verifies:

- the live handoff, FINAL release, video, and metadata checksums;
- an HTTPS `youtube.com/watch` URL matching the declared platform ID;
- actual visibility no broader than the release intent;
- timezone-aware upload/publication timestamps;
- public publication cannot precede upload;
- the same handoff cannot silently acquire a different platform ID.

Repeated identical receipts are idempotent. Later visibility changes for the
same video ID create new append-only receipts, preserving the earlier state.
Private and unlisted receipts cannot claim a public publication time.

The required `authorization_note` preserves what the caller says they relied
on; it is not independent proof that authorization was valid or that YouTube
currently reports the same state. `eprs status --verify` and `eprs context`
surface the local handoff/receipt history without contacting the platform.
