# Complete-word singing with a consented voice

Use a real, consented human recording as the reference when available. Avoid a
clone-of-clone reference: it adds another model's artifacts and weakens the
connection to the speaker. Keep that recording and its transcript in ignored
operator storage. Speech references do not establish convincing singing likeness;
review the generated performance separately.

SoulX-Singer supports explicit score conditioning. Its English tokens contain a
whole word's hyphen-separated ARPABET phones. `note_type=2` starts a word;
`note_type=3` continues **the same word** over another note. It does not mean
emphasis, a long word, or a long note. Marking a new word as type 3 creates
contradictory conditioning and can damage pronunciation. The upstream MIDI parser
and note transcription code define this convention.

`scripts/render_soulx.py` uses `eprs.singing_score` to validate array lengths,
ordered phrase windows, duration sums, rest markers and continuations before
loading the model. Give phrase-final words enough authored duration and reserve
an explicit trailing rest of at least 300 ms. The renderer saves every raw phrase
and assembles additively without truncating generated samples to fixed slots.
Render in the final key and tempo; avoid unnecessary whole-vocal transposition.

Run the adapter with an installed SoulX/Torch runtime:

```sh
python scripts/render_soulx.py \
  --runtime .eprs-local/SoulX-Singer \
  --model .eprs-local/SoulX-Singer/pretrained_models/SoulX-Singer/model.pt \
  --config .eprs-local/SoulX-Singer/soulxsinger/config/soulxsinger.yaml \
  --reference .eprs-local/voice-reference/selected.wav \
  --reference-score .eprs-local/voice-reference/aligned.json \
  --score songs/example/code/vocal-score.json \
  --output songs/example/audio/singing-v1 --device mps --steps 32 --consent
```

The reference must be one aligned phrase starting at zero; its duration must
match the audio. Derive word boundaries from an actual transcription/alignment,
inspect them, and estimate pitches from the recording instead of inventing a
constant pitch for every reference word. Only load trusted model checkpoints:
the upstream loader uses Torch pickle loading. This adapter does not install a
runtime, fetch weights, or upload private voice material.

Compare raw old/new phrase transcriptions without supplying the expected lyrics
to the recognizer. Check complete line-ending words again in the full mix, with
signal measurements for silence, clipping, releases and masking. ASR recovery
supports intelligibility; it is not a substitute for listening or evidence that
the clone sounds like the person. Document that limitation in producer reviews.

Current alternatives remain available: SoulX-Singer-SVC converts existing sung
audio, while ACE-Step 1.5 can generate and transform complete music. Neither
should be declared better for a particular voice without a controlled listening
comparison. A verified conditioning fix can be more appropriate than replacing
an already current model.

Sources:
- https://github.com/Soul-AILab/SoulX-Singer
- https://github.com/Soul-AILab/SoulX-Singer/blob/main/preprocess/tools/midi_parser.py
- https://ace-step.github.io/ACE-Step-1.5/en/
