# Live and GUI adapters

The offline visual score remains the source of truth. Adapters exchange audio, cues, or textures without letting a GUI session become the only reproducible copy.

## Sonic Pi

Copy selected calls from `sonic-pi-visual-cues.rb` into a composition. They send semantic OSC events to localhost port 57121. FFT analysis should drive continuous texture; OSC should carry authored meaning that the spectrum cannot infer. A future Hydra/Three/p5 receiver can map `/eprs/visual` events to scene changes.

Do not enable remote OSC reception merely to make the local setup work. Record a lossless Sonic Pi stem and use it as the deterministic Remotion input when preparing a final video.

## Audacity

Use Audacity for recording, selection, and reversible hands-on editing. Export a new WAV into a song's `stems`, `mixes`, or `masters`, then pass that derivative to `eprs visual-render`. Preserve the AUP3 project and every raw take.

Audacity macros can make repeatable export chains. External scripting through `mod-script-pipe` stays opt-in because it expands local control; this repository does not enable it automatically.

## FFmpeg

FFmpeg probes every render and creates delivery copies. It can also turn approved garage footage, contact sheets, scanned paper, or feedback captures into loopable texture layers. Record the source and license in the visual brief before adding a texture adapter.
