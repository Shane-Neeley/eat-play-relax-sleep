# Animal percussion in Sonic Pi

The useful model is an ensemble, not “one animal sample equals drums.” Give
different recordings different musical jobs based on what the audio actually
does: transient knocks, wet clicks, low calls, ratchets, or sustained carriers.

[`percussive-animal-custom-sample-test.rb`](percussive-animal-custom-sample-test.rb)
uses five roles and a 32-bar arrangement. Its source candidates and exact
sound-level rights are recorded in
[`animal-percussion-pack.example.json`](animal-percussion-pack.example.json).

## Prepare a pack

Create or choose a song workspace, then freeze each listed observation through
EPRS. Example:

```bash
./scripts/eprs inaturalist sound 154194637 \
  --song songs/YOUR-SONG --role "pileated wood percussion" --sound-id 637789 \
  --note "Wooden roll and fill candidate; preserve natural spacing."

./scripts/eprs inaturalist study \
  songs/YOUR-SONG/references/inaturalist-audio/pileated-wood-percussion/observation-154194637-sound-637789.wav \
  --song songs/YOUR-SONG --role "pileated wood percussion study" \
  --key D --scale minor-pentatonic --tempo-bpm 112
```

Repeat for the five manifest entries. Run `eprs rhythm` when the performed
spacing itself matters. Convert unsupported containers such as M4A into new
lossless WAV derivatives under `audio/animal-percussion-pack/`; never overwrite
the frozen reference. Preserve sample rate unless a deliberate project-wide
conversion is chosen.

Use the filenames expected by the Sonic Pi source:

```text
audio/animal-percussion-pack/
  bullfrog-low.wav
  woodpecker-roll.wav
  cricket-frog-rim.wav
  katydid-ratchet.wav
  cicada-carrier.wav
```

Listen while selecting regions. The measured example offers starting points,
not automatic edit commands. Level-match derivatives only through an explicit,
documented processing choice; the woodpecker and katydid recordings can be much
quieter than the cricket frog.

## Composition rules that help

- Preserve contrast: low animal, wood animal, wet animal, ratchet, carrier.
- Rotate onset indices so a living gesture does not become one repeated click.
- Gate sustained insects; do not invent nonexistent discrete attacks.
- Keep at least one section where each animal is heard clearly before stacking.
- Use synthetic reinforcement sparingly and label it. The animals should remain
  perceptible as the percussion identity.
- Keep observation URL, sound ID, contributor, sound license, and retrieval
  evidence with the immutable bytes. Public availability is not reuse permission.
