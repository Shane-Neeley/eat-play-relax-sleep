# Sonic Pi composition

Use Sonic Pi when live-coded patterns, synthesis, sample manipulation, generative behavior, or performance fit the user's idea. Do not assume it is only for beats or grid-based songs.

Write readable `.rb` files in a location that fits the project. Document only the musical and technical choices needed to understand or reproduce the piece, such as tempo when one is used, tuning, external samples, randomness, control inputs, or performance cues. Keep initial levels conservative.

For a loop-based idea, a minimal starting shape may be:

```ruby
use_bpm 100

live_loop :drums do
  sample :bd_haus, amp: 0.7
  sleep 1
  sample :sn_dub, amp: 0.5
  sleep 1
end
```

Open the file in Sonic Pi, press Run, and use Sonic Pi's Record button to capture a WAV stem. Stop loops before recording acoustic tracks to prevent monitoring bleed.

Adapt the structure freely. Use one-shot sequences, cues and sync, functions, rings, external MIDI/OSC, irregular timing, evolving processes, or silence when they better suit the piece. Avoid forcing named live loops, a fixed BPM, a key, or conventional song sections.

Use local WAV samples by absolute path only while experimenting. Before sharing a project, copy permitted samples into the project and update the code to document their origin and license.

Avoid claiming that Sonic Pi rendered successfully unless the resulting audio exists and has been inspected with an appropriate tool; `scripts/analyze_audio.sh` is one option. GUI interaction may still require the user to press Run and Record.
