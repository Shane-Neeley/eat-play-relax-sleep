import {cycle, kidVoiceNames, kidsPresets, mutatePattern, presets, stepTime, toBeatScript, velocity, voices} from "./beat-core.mjs";

let state = {...structuredClone(presets.pocket), seed: 1977};
let context;
let playing = false;
let timer;
let cursor = 0;
let kidsMode = false;
let grownupState = structuredClone(state);
let kidState = {...structuredClone(kidsPresets.spooky), seed: 2026};

const grid = document.querySelector("#grid");
const tempo = document.querySelector("#tempo");
const swing = document.querySelector("#swing");
const code = document.querySelector("#code");
const play = document.querySelector("#play");
const presetSelect = document.querySelector("#presets");
const soundboard = document.querySelector("#soundboard");
const modeToggle = document.querySelector("#mode-toggle");

const kidSymbols = {".": "·", x: "●", X: "★", g: "👻", o: "◉"};

function fillPresets() {
  const choices = kidsMode ? kidsPresets : presets;
  presetSelect.replaceChildren();
  for (const [value, preset] of Object.entries(choices)) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = preset.title;
    option.selected = preset.title === state.title;
    presetSelect.append(option);
  }
}

function render() {
  grid.replaceChildren();
  for (const voice of voices) {
    const label = document.createElement("div");
    label.className = "voice";
    label.textContent = kidsMode ? kidVoiceNames[voice] : voice;
    grid.append(label);
    [...state.patterns[voice]].forEach((symbol, index) => {
      const button = document.createElement("button");
      button.className = `step v-${symbol === "." ? "rest" : symbol}`;
      button.dataset.voice = voice;
      button.dataset.index = index;
      button.textContent = kidsMode ? kidSymbols[symbol] : symbol;
      const voiceName = kidsMode ? kidVoiceNames[voice] : voice;
      button.ariaLabel = `${voiceName}, step ${index + 1}, ${symbol === "." ? "rest" : symbol}`;
      button.addEventListener("click", async () => {
        const items = [...state.patterns[voice]];
        items[index] = cycle(items[index]);
        state.patterns[voice] = items.join("");
        const nextSymbol = items[index];
        render();
        if (kidsMode && nextSymbol !== ".") {
          await ensureAudio();
          synth(voice, context.currentTime + 0.01, velocity(nextSymbol), true);
        }
      });
      grid.append(button);
    });
  }
  tempo.value = state.tempo;
  swing.value = state.swing;
  document.querySelector("#tempo-value").textContent = `${state.tempo} BPM`;
  document.querySelector("#swing-value").textContent = Number(state.swing).toFixed(2);
  code.value = toBeatScript(state);
}

function renderMode() {
  document.body.classList.toggle("kids-mode", kidsMode);
  soundboard.hidden = !kidsMode;
  modeToggle.ariaPressed = String(kidsMode);
  modeToggle.innerHTML = kidsMode ? '<span aria-hidden="true">🎛️</span> Grown-up studio' : '<span aria-hidden="true">✨</span> Kids studio';
  document.querySelector("#studio-title").textContent = kidsMode ? "Creature Beat Club" : "Beat Lab";
  document.querySelector("#studio-lede").textContent = kidsMode
    ? "Tap a creature, paint a beat, and make friendly ghosts dance. There are no wrong sounds here."
    : "Hear code as touch, tension, and time. Click a step to cycle rest → hit → accent → ghost.";
  document.querySelector("#grid-title").textContent = kidsMode ? "Build a one-bar creature beat" : "One bar · sixteenth notes";
  document.querySelector("#count-guide").textContent = kidsMode ? "Count it: 1 · 2 · 3 · 4 — then loop it!" : "1 e & a · 2 e & a · 3 e & a · 4 e & a";
  document.querySelector("#mutate").textContent = kidsMode ? "🎲 Silly remix" : "One mutation";
  document.querySelector("#copy").textContent = kidsMode ? "Copy my beat code" : "Copy BeatScript";
  document.querySelector("#footer-copy").textContent = kidsMode
    ? "Start quietly, then turn it up with a grown-up. Your ears are more important than monster volume."
    : "Use headphones at a comfortable level. Measurements can catch errors; your body decides whether the pocket works.";
  document.querySelector("#theme-color").content = kidsMode ? "#32145f" : "#0d0f13";
  fillPresets();
  render();
}

function noiseBuffer(seconds = 0.25) {
  const buffer = context.createBuffer(1, context.sampleRate * seconds, context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  return buffer;
}

function kidSynth(voice, when, amount) {
  const output = context.createGain();
  output.gain.value = 0.62;
  output.connect(context.destination);
  if (voice === "kick") {
    const osc = context.createOscillator();
    const thump = context.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(105, when);
    osc.frequency.exponentialRampToValueAtTime(38, when + 0.16);
    thump.gain.setValueAtTime(0.58 * amount, when);
    thump.gain.exponentialRampToValueAtTime(0.001, when + 0.42);
    osc.connect(thump).connect(output); osc.start(when); osc.stop(when + 0.44);
  } else if (voice === "snare") {
    const ghost = context.createOscillator();
    const wobble = context.createOscillator();
    const wobbleDepth = context.createGain();
    const breath = context.createGain();
    ghost.type = "sine"; ghost.frequency.setValueAtTime(510, when); ghost.frequency.exponentialRampToValueAtTime(210, when + 0.42);
    wobble.frequency.value = 7; wobbleDepth.gain.value = 26; wobble.connect(wobbleDepth).connect(ghost.frequency);
    breath.gain.setValueAtTime(0.28 * amount, when); breath.gain.exponentialRampToValueAtTime(0.001, when + 0.46);
    ghost.connect(breath).connect(output); ghost.start(when); wobble.start(when); ghost.stop(when + 0.48); wobble.stop(when + 0.48);
  } else if (voice === "hat") {
    for (const offset of [0, 0.045]) {
      const source = context.createBufferSource();
      const filter = context.createBiquadFilter();
      const wing = context.createGain();
      source.buffer = noiseBuffer(); filter.type = "highpass"; filter.frequency.value = 4800;
      wing.gain.setValueAtTime(0.1 * amount, when + offset); wing.gain.exponentialRampToValueAtTime(0.001, when + offset + 0.045);
      source.connect(filter).connect(wing).connect(output); source.start(when + offset); source.stop(when + offset + 0.06);
    }
  } else {
    const frog = context.createOscillator();
    const croak = context.createGain();
    frog.type = "square"; frog.frequency.setValueAtTime(155, when); frog.frequency.exponentialRampToValueAtTime(78, when + 0.09); frog.frequency.exponentialRampToValueAtTime(132, when + 0.17);
    croak.gain.setValueAtTime(0.16 * amount, when); croak.gain.exponentialRampToValueAtTime(0.001, when + 0.22);
    frog.connect(croak).connect(output); frog.start(when); frog.stop(when + 0.24);
  }
}

function synth(voice, when, amount, playful = kidsMode) {
  if (playful) return kidSynth(voice, when, amount);
  const gain = context.createGain();
  gain.connect(context.destination);
  if (voice === "kick") {
    const osc = context.createOscillator();
    osc.frequency.setValueAtTime(150, when);
    osc.frequency.exponentialRampToValueAtTime(45, when + 0.09);
    gain.gain.setValueAtTime(0.55 * amount, when);
    gain.gain.exponentialRampToValueAtTime(0.001, when + 0.35);
    osc.connect(gain); osc.start(when); osc.stop(when + 0.4);
  } else {
    const source = context.createBufferSource();
    const filter = context.createBiquadFilter();
    source.buffer = noiseBuffer();
    filter.type = voice === "hat" ? "highpass" : "bandpass";
    filter.frequency.value = voice === "hat" ? 6000 : (voice === "snare" ? 1700 : 900);
    gain.gain.setValueAtTime((voice === "hat" ? 0.12 : 0.22) * amount, when);
    gain.gain.exponentialRampToValueAtTime(0.001, when + (voice === "hat" ? 0.08 : 0.2));
    source.connect(filter).connect(gain); source.start(when); source.stop(when + 0.24);
  }
}

async function ensureAudio() {
  context ||= new AudioContext();
  await context.resume();
}

function creatureSound(name, when) {
  if (name === "ghost") return kidSynth("snare", when, 1);
  if (name === "frog") return kidSynth("perc", when, 1);
  if (name === "thunder") {
    const source = context.createBufferSource(); const low = context.createBiquadFilter(); const gain = context.createGain();
    source.buffer = noiseBuffer(0.9); low.type = "lowpass"; low.frequency.value = 260;
    gain.gain.setValueAtTime(0.22, when); gain.gain.exponentialRampToValueAtTime(0.001, when + 0.8);
    source.connect(low).connect(gain).connect(context.destination); source.start(when); source.stop(when + 0.85); return;
  }
  const notes = {
    owl: [[420, 260], [370, 230]], cat: [[520, 780], [780, 440]], robot: [[220, 440], [440, 330]],
    dino: [[95, 46], [72, 38]], magic: [[520, 1040], [780, 1560]],
  }[name] || [[330, 220]];
  notes.forEach(([from, to], index) => {
    const osc = context.createOscillator(); const gain = context.createGain(); const start = when + index * 0.13;
    osc.type = name === "robot" ? "square" : name === "magic" ? "sine" : "triangle";
    osc.frequency.setValueAtTime(from, start); osc.frequency.exponentialRampToValueAtTime(to, start + 0.2);
    gain.gain.setValueAtTime(name === "dino" ? 0.13 : 0.09, start); gain.gain.exponentialRampToValueAtTime(0.001, start + 0.24);
    osc.connect(gain).connect(context.destination); osc.start(start); osc.stop(start + 0.25);
  });
}

function scheduleBar() {
  if (!playing) return;
  const now = context.currentTime + 0.035;
  for (let index = 0; index < 16; index++) {
    const when = now + stepTime(index, state.tempo, state.swing);
    for (const voice of voices) {
      const amount = velocity(state.patterns[voice][index]);
      if (amount) synth(voice, when, amount);
    }
  }
  const duration = 60 / state.tempo * 4;
  clearTimeout(timer);
  timer = setTimeout(scheduleBar, duration * 1000 - 10);
}

play.addEventListener("click", async () => {
  if (playing) {
    playing = false; clearTimeout(timer); play.textContent = "Play loop"; return;
  }
  await ensureAudio();
  playing = true; play.textContent = "Stop"; scheduleBar();
});

tempo.addEventListener("input", () => { state.tempo = Number(tempo.value); render(); });
swing.addEventListener("input", () => { state.swing = Number(swing.value); render(); });
document.querySelector("#mutate").addEventListener("click", () => {
  state.seed += 1;
  for (const voice of voices) state.patterns[voice] = mutatePattern(state.patterns[voice]);
  render();
});
document.querySelector("#copy").addEventListener("click", async () => {
  await navigator.clipboard.writeText(code.value);
  document.querySelector("#copy").textContent = "Copied";
  setTimeout(() => document.querySelector("#copy").textContent = kidsMode ? "Copy my beat code" : "Copy BeatScript", 1200);
});
presetSelect.addEventListener("change", event => {
  const choices = kidsMode ? kidsPresets : presets;
  state = {...structuredClone(choices[event.target.value]), seed: state.seed + 1}; render();
});

modeToggle.addEventListener("click", () => {
  if (kidsMode) kidState = structuredClone(state); else grownupState = structuredClone(state);
  kidsMode = !kidsMode;
  state = structuredClone(kidsMode ? kidState : grownupState);
  renderMode();
});

document.querySelectorAll(".sound-pad").forEach(button => button.addEventListener("click", async () => {
  await ensureAudio();
  creatureSound(button.dataset.sound, context.currentTime + 0.01);
  document.querySelector("#kid-message").textContent = `${button.querySelector("strong").textContent} joined the band!`;
  button.classList.remove("pop");
  requestAnimationFrame(() => button.classList.add("pop"));
}));

renderMode();
