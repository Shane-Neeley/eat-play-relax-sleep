import {mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {deflateSync} from "node:zlib";
import {effect, init, target} from "vgpu/node";

const SHADER = /* wgsl */ `
struct Params {
  resolution: vec4f,
  signal: vec4f,
  motion: vec4f,
  palette0: vec4f,
  palette1: vec4f,
  palette2: vec4f,
  palette3: vec4f,
  style: vec4f,
}

@group(0) @binding(0) var<uniform> params: Params;

fn hash2(point: vec2f) -> f32 {
  return fract(sin(dot(point, vec2f(127.1, 311.7))) * 43758.5453);
}

fn palette(index: f32) -> vec3f {
  let position = fract(index) * 3.0;
  if (position < 1.0) {
    return mix(params.palette0.xyz, params.palette1.xyz, position);
  }
  if (position < 2.0) {
    return mix(params.palette1.xyz, params.palette2.xyz, position - 1.0);
  }
  return mix(params.palette2.xyz, params.palette3.xyz, position - 2.0);
}

@fragment fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let resolution = params.resolution.xy;
  let time = params.signal.x;
  let bass = params.signal.y;
  let mids = params.signal.z;
  let highs = params.signal.w;
  let speed = params.motion.x;
  let feedback = params.motion.y;
  let rotation = params.motion.z;
  let turbulence = params.motion.w;
  let world = params.style.x;
  let motif = params.style.y;
  let seed = params.style.z;
  let frame = params.style.w;

  var point = (uv - vec2f(0.5, 0.5)) * vec2f(resolution.x / resolution.y, 1.0);
  let radius = length(point);
  let angle = atan2(point.y, point.x);
  let phase = time * speed * 0.7 + seed * 0.017;
  let grain = hash2(floor(point * 92.0 + phase)) - 0.5;
  var color = params.palette3.xyz * 0.09 + grain * 0.03 * (0.4 + turbulence);
  color += palette(0.04) * exp(-radius * 2.7) * (0.05 + 0.12 * bass + 0.04 * sin(time));

  if (world < 0.5) {
    let tunnel = abs(fract(radius * (7.0 + bass * 2.0) - phase * 0.55) - 0.5);
    let spokes = abs(sin(angle * 8.0 + radius * 14.0 - phase * 2.0));
    let ring = smoothstep(0.18, 0.0, tunnel) * (0.35 + 0.65 * spokes);
    color += palette(0.12 + tunnel + bass * 0.16) * ring * (0.5 + feedback);
    color += palette(0.62) * exp(-radius * 5.0) * (0.24 + mids * 0.46);
  } else if (world < 1.5) {
    let warped = point + vec2f(
      sin(point.y * 7.0 + phase * 1.7) * 0.08 * (1.0 + turbulence),
      cos(point.x * 5.0 - phase) * 0.05 * (1.0 + mids)
    );
    let ribbonA = exp(-abs(warped.y - sin(warped.x * 5.5 + phase) * 0.18) * (18.0 - highs * 5.0));
    let ribbonB = exp(-abs(warped.y + 0.26 - cos(warped.x * 3.0 - phase * 0.7) * 0.12) * 22.0);
    color += palette(0.05) * ribbonA * (0.28 + bass * 0.78);
    color += palette(0.54) * ribbonB * (0.2 + mids * 0.65);
    color += palette(0.82) * exp(-radius * 4.0) * highs * 0.26;
  } else if (world < 2.5) {
    let drift = vec2f(sin(phase * 0.8), cos(phase * 0.63)) * 0.12;
    let cellPoint = (point + drift) * 8.0;
    let cell = floor(cellPoint);
    let local = fract(cellPoint) - vec2f(0.5, 0.5);
    let star = max(0.0, hash2(cell + vec2f(seed, seed * 0.37)) - 0.28) * 1.38;
    let node = (1.0 - smoothstep(0.0, 0.18, length(local))) * star;
    let constellationLine = (1.0 - smoothstep(0.0, 0.035, abs(local.x + local.y * sin(seed)))) * star * 0.42;
    color += palette(0.18) * node * (1.1 + highs * 2.4);
    color += palette(0.66) * constellationLine * (0.55 + mids * 1.35);
    color += palette(0.92) * exp(-radius * 3.0) * (0.22 + bass * 0.48);
    let orbitA = vec2f(cos(phase * 0.72), sin(phase * 0.51)) * 0.38;
    let orbitB = vec2f(cos(phase * 0.43 + 2.1), sin(phase * 0.67 + 1.4)) * 0.26;
    color += palette(0.08) * exp(-length(point - orbitA) * 18.0) * (0.38 + highs * 0.95);
    color += palette(0.56) * exp(-length(point - orbitB) * 22.0) * (0.28 + mids * 0.85);
    let threadA = exp(-abs(point.y - sin(point.x * 5.0 + phase) * 0.22) * 34.0);
    let threadB = exp(-abs(point.x - cos(point.y * 4.0 - phase) * 0.2) * 42.0);
    color += palette(0.32) * threadA * (0.08 + highs * 0.28);
    color += palette(0.7) * threadB * (0.06 + mids * 0.22);
  } else {
    let sky = 1.0 - smoothstep(-0.22, 0.42, point.y);
    let ground = smoothstep(-0.08, 0.46, point.y);
    let daylight = mix(params.palette0.xyz * 0.36, params.palette1.xyz * 0.28, ground * 0.72);
    color = daylight + params.palette0.xyz * sky * 0.09;
    color += palette(0.23) * ground * 0.12;
    color += vec3f(0.018, 0.018, 0.012);
    let horizon = exp(-abs(point.y - 0.06) * 58.0);
    color += palette(0.58) * horizon * (0.10 + bass * 0.30);
    let bladeCell = floor((point.x + 1.4) * 18.0 + seed);
    let bladeX = fract((point.x + 1.4) * 18.0 + seed) - 0.5;
    let bladeLean = sin(bladeCell * 2.7 + phase) * 0.20;
    let blade = (1.0 - smoothstep(0.0, 0.038, abs(bladeX - bladeLean * (0.25 + 0.12 * sin(point.y * 4.0 + phase))))) * smoothstep(-0.20, 0.58, point.y);
    color += palette(0.38) * blade * (0.20 + mids * 0.38);
    let chirpCenterA = vec2f(-0.34 + sin(phase * 0.7) * 0.12, 0.05);
    let chirpRadiusA = length(point - chirpCenterA);
    let chirpBandA = smoothstep(0.025, 0.0, abs(chirpRadiusA - (0.14 + fract(time * 0.20) * 0.34)));
    color += palette(0.08) * chirpBandA * (0.18 + highs * 0.50);
    let chirpCenterB = vec2f(0.32 + cos(phase * 0.43) * 0.14, -0.03);
    let chirpRadiusB = length(point - chirpCenterB);
    let chirpBandB = smoothstep(0.018, 0.0, abs(chirpRadiusB - (0.10 + fract(time * 0.27 + 0.33) * 0.26)));
    color += palette(0.76) * chirpBandB * (0.14 + mids * 0.38);
    color += palette(0.22) * exp(-length(point - chirpCenterA) * 28.0) * (0.07 + highs * 0.28);
    color += palette(0.70) * exp(-length(point - chirpCenterB) * 34.0) * (0.05 + highs * 0.22);
  }

  if (motif > 0.5 && motif < 1.5) {
    let atlas = smoothstep(0.025, 0.0, abs(sin(angle * 5.0 + phase) * 0.18 + radius - 0.34));
    color += palette(0.28) * atlas * (0.15 + highs * 0.46);
  }
  if (motif > 1.5 && motif < 2.5) {
    color += palette(0.76) * exp(-abs(point.x + sin(time) * 0.18) * 13.0) * 0.08;
  }
  if (motif > 2.5 && motif < 3.5) {
    let grid = smoothstep(0.018, 0.0, abs(fract(point.x * 13.0) - 0.5));
    color += palette(0.45) * grid * 0.045;
  }
  if (motif > 3.5) {
    let print = step(0.7, hash2(floor(point * 24.0 + frame * 0.01)));
    color += palette(0.2) * print * 0.035;
  }
  if (motif > 4.5 && motif < 5.5) {
    let tickPhase = fract(time * 0.63 + seed * 0.009);
    let tick = step(0.84, fract(point.x * 15.0 + tickPhase * 2.0)) * smoothstep(0.55, -0.10, point.y);
    color += palette(0.98) * tick * (0.025 + highs * 0.08);
    let pulse = smoothstep(0.018, 0.0, abs(length(point - vec2f(sin(phase) * 0.22, 0.08)) - (0.20 + tickPhase * 0.27)));
    color += palette(0.05) * pulse * (0.10 + highs * 0.30);
  }
  if (motif > 5.5 && motif < 6.5) {
    let moonCenter = vec2f(-0.38 + sin(phase * 0.18) * 0.035, -0.08 + cos(phase * 0.21) * 0.025);
    let moonRadius = 0.285;
    let moonEdge = max(1.5 / resolution.y, 0.0018);
    let moonDistance = length(point - moonCenter);
    let moonDisk = 1.0 - smoothstep(moonRadius - moonEdge, moonRadius + moonEdge, moonDistance);
    let shadowCenter = moonCenter + vec2f(0.105 + sin(phase * 0.41) * 0.018, 0.012);
    let shadowDistance = length(point - shadowCenter);
    let shadowDisk = 1.0 - smoothstep(moonRadius - moonEdge, moonRadius + moonEdge, shadowDistance);
    let eclipseMask = min(moonDisk, shadowDisk);
    let innerMoon = 1.0 - smoothstep(moonRadius - 0.012, moonRadius - 0.005, moonDistance);
    let limb = max(moonDisk - innerMoon, 0.0);
    let eclipseHalo = exp(-abs(shadowDistance - moonRadius) * 72.0) * eclipseMask;
    color = mix(color, params.palette3.xyz * (0.65 + mids * 0.12), moonDisk * 0.88);
    color = mix(color, vec3f(0.030, 0.014, 0.045), eclipseMask * 0.985);
    color += palette(0.03) * limb * (0.12 + highs * 0.18);
    color += palette(0.28) * eclipseHalo * (0.05 + highs * 0.17);
    let eclipseTick = smoothstep(0.012, 0.0, abs(point.y - moonCenter.y - 0.34)) * smoothstep(0.72, 0.10, abs(point.x - moonCenter.x));
    color += palette(0.62) * eclipseTick * (0.02 + bass * 0.06);
  }
  if (motif > 6.5 && motif < 7.5) {
    // Paper pond: flat cut-paper shoreline, three moving ripple rings, reeds,
    // and one marker. The compression of the rings is a song metaphor for
    // shrinking loop time, not a scientific simulation or forecast.
    let shorelineY = -0.12 + sin(point.x * 3.6 + phase * 0.42) * 0.035;
    let shoreline = exp(-abs(point.y - shorelineY) * 58.0);
    let pondFill = smoothstep(0.34, -0.16, point.y) * 0.13;
    color += params.palette0.xyz * pondFill;
    color += palette(0.22) * shoreline * (0.24 + bass * 0.48);
    let rippleCenterA = vec2f(-0.30 + sin(phase * 0.44) * 0.10, -0.20);
    let rippleCenterB = vec2f(0.18 + cos(phase * 0.31) * 0.11, -0.26);
    let rippleCenterC = vec2f(0.46 + sin(phase * 0.24) * 0.08, -0.10);
    let distanceA = length(point - rippleCenterA);
    let distanceB = length(point - rippleCenterB);
    let distanceC = length(point - rippleCenterC);
    let ringA = smoothstep(0.018, 0.0, abs(distanceA - (0.08 + fract(time * 0.15) * 0.22)));
    let ringB = smoothstep(0.016, 0.0, abs(distanceB - (0.06 + fract(time * 0.19 + 0.31) * 0.18)));
    let ringC = smoothstep(0.014, 0.0, abs(distanceC - (0.05 + fract(time * 0.23 + 0.67) * 0.15)));
    color += palette(0.82) * ringA * (0.14 + highs * 0.46);
    color += palette(0.08) * ringB * (0.12 + mids * 0.42);
    color += palette(0.54) * ringC * (0.10 + bass * 0.34);
    let reedCell = floor((point.x + 1.35) * 13.0 + seed);
    let reedX = fract((point.x + 1.35) * 13.0 + seed) - 0.5;
    let reedLean = sin(reedCell * 1.9 + phase * 0.7) * 0.17;
    let reed = (1.0 - smoothstep(0.0, 0.028, abs(reedX - reedLean * (point.y + 0.26)))) * smoothstep(-0.02, 0.50, point.y);
    color += params.palette1.xyz * reed * (0.12 + mids * 0.34);
    let markerCenter = vec2f(0.04 + sin(phase * 0.18) * 0.28, -0.02 + cos(phase * 0.23) * 0.07);
    let marker = exp(-length(point - markerCenter) * 22.0);
    color += params.palette2.xyz * marker * (0.08 + bass * 0.34);
    let floorMark = smoothstep(0.012, 0.0, abs(point.y + 0.42)) * smoothstep(0.72, 0.08, abs(point.x + 0.12));
    color += palette(0.38) * floorMark * (0.018 + highs * 0.06);
  }
  if (motif > 7.5) {
    // Tide pool: bounded domain warp, signed-distance-style rings, separated
    // color fringes, and phase-shifted caustics. These are graphic techniques,
    // not a physical ocean simulation.
    let tidePhase = phase * 1.34;
    let warped = point + vec2f(
      sin(point.y * 7.0 + tidePhase * 1.6) * 0.045 * (0.7 + turbulence),
      cos(point.x * 8.0 - tidePhase) * 0.026 * (0.7 + mids)
    );
    let waterlineY = -0.08 + sin(warped.x * 7.0 + tidePhase * 0.65) * 0.035;
    let waterMask = smoothstep(0.18, -0.38, warped.y);
    let foamEdge = exp(-abs(warped.y - waterlineY) * 72.0);
    color = mix(color, color * 0.30 + params.palette0.xyz * 0.12, waterMask * 0.78);
    color += palette(0.62) * foamEdge * (0.08 + highs * 0.26);
    let basin = vec2f(sin(tidePhase * 0.21) * 0.045, -0.20 + cos(tidePhase * 0.27) * 0.025);
    let basinDistance = length(warped - basin);
    let compression = 0.07 + 0.19 * (0.5 + 0.5 * sin(tidePhase * 0.32));
    let ringA = smoothstep(0.020, 0.0, abs(basinDistance - compression));
    let ringB = smoothstep(0.017, 0.0, abs(basinDistance - (compression * 0.64 + 0.055)));
    let ringC = smoothstep(0.014, 0.0, abs(basinDistance - (compression * 0.34 + 0.028)));
    color += params.palette1.xyz * ringA * (0.15 + bass * 0.42);
    color += params.palette3.xyz * ringB * (0.12 + mids * 0.34);
    color += params.palette2.xyz * ringC * (0.10 + highs * 0.30);
    let fringeCenter = basin + vec2f(0.018, 0.0);
    let fringeDistance = length(warped - fringeCenter);
    let fringe = smoothstep(0.014, 0.0, abs(fringeDistance - (compression + 0.012)));
    color += params.palette3.xyz * fringe * (0.06 + highs * 0.20);
    let causticX = fract(warped.x * 9.0 + sin(tidePhase * 0.5) * 0.4);
    let causticY = fract(warped.y * 15.0 - cos(tidePhase * 0.37) * 0.3);
    let caustic = smoothstep(0.07, 0.0, abs(causticX - 0.5)) * smoothstep(0.13, 0.0, abs(causticY - 0.5));
    color += palette(0.90) * caustic * waterMask * (0.018 + highs * 0.08);
    let hotSpot = exp(-length(warped - basin) * 24.0);
    color += params.palette2.xyz * hotSpot * (0.018 + bass * 0.09);
    let tideTick = smoothstep(0.010, 0.0, abs(warped.y - 0.34)) * smoothstep(0.78, 0.14, abs(warped.x));
    color += params.palette0.xyz * tideTick * (0.018 + mids * 0.05);
    // Compress additive highlights before the shared vignette multiplier so
    // neon rings keep their hue instead of becoming a clipped white disk.
    color = (vec3f(1.0, 1.0, 1.0) - exp(-color * 0.80)) * 0.72;
  }

  let vignette = smoothstep(1.05, 0.18, radius);
  color *= vignette * 2.0;
  color = max(color, vec3f(0.0, 0.0, 0.0));
  return vec4f(color, 1.0);
}
`;

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) {
    throw new Error(`missing ${name}`);
  }
  return process.argv[index + 1];
}

function color(value) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(value ?? "#ffffff"));
  if (!match) return [1, 1, 1, 1];
  return [
    Number.parseInt(match[1].slice(0, 2), 16) / 255,
    Number.parseInt(match[1].slice(2, 4), 16) / 255,
    Number.parseInt(match[1].slice(4, 6), 16) / 255,
    1,
  ];
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const kind = Buffer.from(type, "ascii");
  const body = Buffer.concat([kind, data]);
  const result = Buffer.alloc(12 + data.length);
  result.writeUInt32BE(data.length, 0);
  body.copy(result, 4);
  result.writeUInt32BE(crc32(body), 8 + data.length);
  return result;
}

function writePng(path, pixels, width, height) {
  const rowBytes = width * 4;
  const raw = Buffer.alloc((rowBytes + 1) * height);
  for (let row = 0; row < height; row += 1) {
    const sourceStart = row * rowBytes;
    const targetStart = row * (rowBytes + 1);
    raw[targetStart] = 0;
    Buffer.from(pixels.buffer, pixels.byteOffset + sourceStart, rowBytes).copy(raw, targetStart + 1);
  }
  const header = Buffer.from("89504e470d0a1a0a", "hex");
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  const png = Buffer.concat([
    header,
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, {level: 6})),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  writeFileSync(path, png);
}

function paramsFor(spec, controls, index, width, height) {
  const control = controls.frames[index] ?? controls.frames[controls.frames.length - 1];
  const motion = spec.motion ?? {};
  const reactivity = spec.reactivity ?? {};
  const palette = spec.palette ?? ["#ff7657", "#62c6cf", "#f2bd63", "#efe6d8"];
  const worldIds = {portal: 0, ribbons: 1, constellation: 2, meadow: 3};
  const motifIds = {
    "rare-signal-atlas": 1,
    "cloud-braid": 2,
    "paper-score": 3,
    "screenprint-count": 4,
    "cricket-pulse": 5,
    "eclipse-shadow": 6,
    "paper-pond": 7,
    "tide-pool": 8,
  };
  return {
    resolution: [width, height, 1 / width, 1 / height],
    signal: [
      control.time,
      Math.min(1, control.bass * Number(reactivity.bass ?? 1)),
      Math.min(1, control.mids * Number(reactivity.mids ?? 1)),
      Math.min(1, control.highs * Number(reactivity.highs ?? 1)),
    ],
    motion: [
      Number(motion.speed ?? 0.72),
      Number(motion.feedback ?? 0.58),
      Number(motion.rotation ?? 0.34),
      Number(motion.turbulence ?? 0.42),
    ],
    palette0: color(palette[0]),
    palette1: color(palette[1]),
    palette2: color(palette[2]),
    palette3: color(palette[3]),
    style: [
      worldIds[spec.world] ?? 0,
      motifIds[spec.motif] ?? 0,
      Number(spec.seed ?? 1),
      index,
    ],
  };
}

async function main() {
  const props = JSON.parse(readFileSync(argument("--props"), "utf8"));
  const controls = JSON.parse(readFileSync(props.controlsPath, "utf8"));
  mkdirSync(props.framesDir, {recursive: true});
  const adapter = process.env.VGPU_ADAPTER;
  const gpu = adapter && adapter !== "auto" ? await init({adapter}) : await init();
  try {
    const colorTarget = target(gpu, {
      size: [props.width, props.height],
      format: "rgba8unorm",
      label: "eprs-vgpu-frame",
    });
    const scene = effect(gpu, SHADER, {
      label: "eprs-vgpu-signal-world",
      set: {params: paramsFor(props.spec, controls, 0, props.width, props.height)},
    });
    await scene.compile(colorTarget);
    for (let index = 0; index < props.frames; index += 1) {
      scene.set({params: paramsFor(props.spec, controls, index, props.width, props.height)});
      scene.draw(colorTarget);
      await gpu.settled();
      const pixels = await colorTarget.read();
      const filename = `${props.framesDir}/frame-${String(index).padStart(6, "0")}.png`;
      writePng(filename, pixels, props.width, props.height);
    }
    process.stderr.write(JSON.stringify({
      adapter: gpu.adapter,
      frames: props.frames,
      width: props.width,
      height: props.height,
    }) + "\n");
  } finally {
    gpu.dispose();
  }
}

main().catch((error) => {
  process.stderr.write(`${error?.stack ?? error}\n`);
  process.exitCode = 1;
});
