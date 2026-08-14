# ChatCut integration

ChatCut is an optional visual-editing lane for EPRS. It may help with process videos, Shorts, captions, motion graphics, thumbnails, and editable timeline/XML handoffs. It is not part of the local music, mastering, provenance, rights, or YouTube source of truth.

## Current boundary

EPRS integrates with ChatCut through a local handoff bridge:

```sh
./scripts/eprs chatcut prepare songs/my-song \
  --video video/reviewed-candidate.mp4 \
  --audio masters/my-song-master.wav \
  --prompt "Create a restrained process-video cut with musical section changes..."
```

The command creates `songs/my-song/chatcut/disposable-preview-<id>/` containing:

- `assets/preview-video.mp4`: a bounded, re-encoded derivative;
- `assets/guide-audio.m4a`: an optional short guide copy;
- optional captions and thumbnail copies;
- `handoff.json`: source checksums, exact prompt, listed assets, and explicit authority flags;
- `README.md`: the operator checklist and remote boundary.

The bridge is intentionally local-only. It does not install ChatCut, log in, call the ChatCut API/MCP endpoint, upload media, edit a timeline, download an export, or publish anything.

## Safe operating flow

1. Finish a local EPRS picture candidate and keep the approved WAV/master separate.
2. Run `eprs chatcut prepare` with song-relative paths only. Raw paths and paths outside the song workspace are rejected.
3. Inspect `handoff.json`, watch the full preview, and check the exact prompt and asset list.
4. If the result is worth trying, operate ChatCut manually. Use only the listed disposable assets. Do not upload the full repository, raw takes, masters, credentials, private recordings, or identifiable source text.
5. Treat any returned render as an untrusted picture candidate. Save it as a new local candidate, run `ffprobe`/media checks, inspect captions and visible text, and complete EPRS picture review.
6. Rebuild the release from the local approved master and reviewed picture. ChatCut never receives YouTube publication authority.

## Two upstream surfaces

The current ChatCut materials describe two related but distinct paths:

- The current `@chatcut/skill` documentation describes a Claude Code skill/CLI that can submit listed local assets to ChatCut's hosted service. A submission can upload the named media and may be billable.
- The public agent-plugin repository contains a separate Codex package using ChatCut's hosted MCP endpoint. Its authentication is host-operated, not an EPRS credential.

EPRS does not assume these surfaces are interchangeable or silently configure either one. Check the current upstream documentation and account scope before every remote operation.

## Privacy, rights, and release notes

ChatCut's current terms say user media is not used to train AI models, but the service is still account-connected and cloud-based. The privacy policy and terms can change. Keep private or identifying source material local unless the user has made a specific, informed decision to upload it. Record any licenses and third-party media credits in the local EPRS release record.

The clean rule is: ChatCut can propose pictures; EPRS owns the audio, evidence, rights, mastering, final assembly, and publication decision.

## References checked 2026-08-14

- [ChatCut agent-plugin documentation](https://chatcut.io/docs/agent-plugin)
- [ChatCut agent-plugin repository](https://github.com/ChatCut-Inc/agent-plugin)
- [ChatCut terms](https://chatcut.io/terms/)
- [ChatCut privacy policy](https://chatcut.io/privacy)
- [ChatCut demo](https://youtu.be/QeiVz_P6F5c)
