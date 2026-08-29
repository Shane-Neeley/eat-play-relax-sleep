# EPRS voice-source policy

**Effective 2026-08-29 — hard rule:** EPRS must never use macOS `say`, any
Apple system TTS command, or any built-in Mac system voice (including Samantha,
Alex, and the other bundled voices). This is a permanent production
prohibition, not a preference or a fallback.

When a release needs a voice, use one of these routes instead:

- a Hugging Face TTS or singing checkpoint whose code, weights, license, and
  local reproducibility have been checked; or
- Shane's explicitly authorized cloned voice, kept outside the public repo and
  accompanied by a private consent/provenance record. For a melodic or sung
  result, run the clone through the EPRS autotune path with the key, scale,
  preset, and sidecar preserved. Autotune is a musical treatment, not a
  substitute for consent or a voice source.

Every voice-bearing candidate must preserve the raw cue, rendered/tuned cue,
model or clone provenance, checkpoint/source hash, version, license, consent
boundary, exact settings, and review decision. Do not imitate a named artist
or present a cloned voice as one. If the final media contains a generative TTS,
singing, or cloned voice, apply YouTube's altered/synthetic-content disclosure
according to the actual asset; deterministic DSP or autotune alone does not
trigger that setting.

Older EPRS notes and releases may accurately mention macOS Samantha because
they predate this rule. Those references are archival history only and must
not be copied into a new arrangement, adapter, release, or public metadata.
