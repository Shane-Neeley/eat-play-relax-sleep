export const voices = ["kick", "snare", "hat", "perc"];

export const presets = {
  pocket: {
    title: "Porchlight Pocket", tempo: 94, swing: 0.54,
    patterns: {kick: "X.....x.....x...", snare: "....X.......X...", hat: "x.x.x.x.x.x.x.x.", perc: "..........g....."},
  },
  broken: {
    title: "Broken Steps", tempo: 108, swing: 0.51,
    patterns: {kick: "X..x......x..x..", snare: "....X..g....X...", hat: "x.xxx.x.x.x...x.", perc: "..g.....x.....g."},
  },
  sleep: {
    title: "Sleep Circuit", tempo: 72, swing: 0.62,
    patterns: {kick: "X.............x.", snare: "........X.......", hat: "x.....g.x.......", perc: "............g..."},
  },
};

export const kidsPresets = {
  spooky: {
    title: "Friendly Haunted House", tempo: 104, swing: 0.56,
    patterns: {kick: "X.......X.......", snare: "....x.......x...", hat: "x.x.x.x.x.x.x.x.", perc: "..g.....x...g..."},
  },
  jungle: {
    title: "Jungle Jump", tempo: 116, swing: 0.58,
    patterns: {kick: "X.....x.X.....x.", snare: "....x.......x...", hat: "x.x.xx..x.x.xx..", perc: "..x...g...x...g."},
  },
  dino: {
    title: "Tiny Dinosaur Parade", tempo: 92, swing: 0.5,
    patterns: {kick: "X...x...X...x...", snare: "....X.......X...", hat: "x...x...x...x...", perc: "..g...x...g...x."},
  },
  moon: {
    title: "Moon Robot Dance", tempo: 128, swing: 0.52,
    patterns: {kick: "X..x....X..x....", snare: "....X.......X...", hat: "x.x.x.x.x.x.x.x.", perc: "..x...x...g.x..."},
  },
};

export const kidVoiceNames = {
  kick: "Monster stomp",
  snare: "Ghost boo",
  hat: "Bat flap",
  perc: "Frog pop",
};

export function velocity(symbol) {
  return ({X: 1, x: 0.72, g: 0.34, o: 0.84})[symbol] || 0;
}

export function cycle(symbol) {
  return ({".": "x", x: "X", X: "g", g: "."})[symbol] || ".";
}

export function stepTime(index, tempo, swing) {
  const step = 60 / tempo / 4;
  return index * step + (index % 2 ? (swing - 0.5) * 2 * step : 0);
}

export function toBeatScript(state) {
  const lines = [
    `title "${state.title.replaceAll('"', "'")}"`, `tempo ${state.tempo}`, "meter 4/4",
    "resolution 16", "bars 8", `swing ${Number(state.swing).toFixed(2)}`, `seed ${state.seed}`, "",
  ];
  for (const voice of voices) {
    const chunks = state.patterns[voice].match(/.{1,4}/g).join(" ");
    lines.push(`track ${voice.padEnd(6)} | ${chunks} | ; gain=${voice === "hat" ? "0.20" : "0.60"}`);
  }
  return `${lines.join("\n")}\n`;
}

export function mutatePattern(pattern, random = Math.random, amount = 0.1) {
  return [...pattern].map((symbol, index) => {
    if (index === 0 || random() >= amount) return symbol;
    if (symbol === ".") return random() < 0.72 ? "g" : "x";
    return random() < 0.55 ? "." : symbol;
  }).join("");
}
