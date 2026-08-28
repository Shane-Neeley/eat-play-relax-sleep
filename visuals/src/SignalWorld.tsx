import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {mean, rgba, seeded} from "./math";
import type {AtlasCard, VisualSpec} from "./types";

type Props = {
  spec: VisualSpec;
  spectrum: number[];
};

const Portal = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const centerX = width * (0.5 + Math.sin(time * 0.21) * 0.035 * spec.motion.turbulence);
  const centerY = height * (0.5 + Math.cos(time * 0.17) * 0.028 * spec.motion.turbulence);
  const rings = Array.from({length: 18}, (_, index) => index);
  const particles = Array.from({length: 90}, (_, index) => index);

  return <AbsoluteFill style={{overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <radialGradient id="room" cx="50%" cy="48%" r="72%">
          <stop offset="0%" stopColor={rgba(spec.palette[1], 0.13 + bass * 0.1)} />
          <stop offset="48%" stopColor={rgba(spec.palette[0], 0.04 + mids * 0.05)} />
          <stop offset="100%" stopColor={spec.background} />
        </radialGradient>
        <filter id="bloom"><feGaussianBlur stdDeviation={10 + spec.texture.bloom * 12} /></filter>
        <linearGradient id="signal" x1="0" x2="1">
          {spec.palette.map((color, index) => <stop key={color} offset={`${index * 33.33}%`} stopColor={color} />)}
        </linearGradient>
      </defs>
      <rect width={width} height={height} fill="url(#room)" />

      {Array.from({length: 13}, (_, index) => {
        const y = height * 0.58 + index * height * 0.045;
        const spread = (index + 1) ** 1.38;
        return <line key={`floor-${index}`} x1={centerX - width * 0.12 - spread * 12} x2={centerX + width * 0.12 + spread * 12} y1={y} y2={y} stroke={rgba(spec.palette[1], 0.05 + highs * 0.11)} strokeWidth={1.5} />;
      })}

      <g transform={`translate(${centerX} ${centerY}) rotate(${time * 9 * spec.motion.rotation})`}>
        {rings.map((index) => {
          const progress = ((time * 0.12 * spec.motion.speed + index / rings.length) % 1);
          const size = 90 + progress * Math.min(width, height) * 0.82 + bass * 90;
          const echo = 1 - progress;
          const wobble = Math.sin(time * 1.3 + index * 0.71) * mids * 24;
          return <rect key={index} x={-size / 2 + wobble} y={-size / 2 - wobble * 0.25} width={size} height={size} rx={size * (0.18 + spec.motion.feedback * 0.24)} fill="none" stroke={spec.palette[index % 3]} strokeOpacity={0.05 + echo * 0.34} strokeWidth={1.5 + bass * 8 * echo} />;
        })}
        <circle r={120 + bass * 160} fill={rgba(spec.palette[0], 0.12 + bass * 0.15)} filter="url(#bloom)" />
      </g>

      <path d={Array.from({length: 49}, (_, index) => {
        const x = (index / 48) * width;
        const bin = spectrum[index % spectrum.length] || 0;
        const wave = Math.sin(index * 0.54 + time * 2.2 * spec.motion.speed);
        const y = height * 0.53 + wave * (26 + mids * 120) + (bin - 0.15) * 160;
        return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ")} fill="none" stroke="url(#signal)" strokeWidth={2 + mids * 7} strokeOpacity={0.55 + mids * 0.35} />

      {particles.map((index) => {
        const orbit = seeded(spec.seed, index) * Math.PI * 2 + time * (0.05 + seeded(spec.seed + 9, index) * 0.22) * spec.motion.speed;
        const radius = (0.12 + seeded(spec.seed + 18, index) * 0.58) * Math.min(width, height);
        const x = centerX + Math.cos(orbit) * radius * 1.4;
        const y = centerY + Math.sin(orbit) * radius * 0.72;
        const size = 0.8 + seeded(spec.seed + 27, index) * 3.5 + highs * 8;
        return <circle key={index} cx={x} cy={y} r={size} fill={spec.palette[index % 4]} opacity={0.12 + highs * 0.8} />;
      })}
    </svg>
  </AbsoluteFill>;
};

const Ribbons = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const energy = mean(spectrum);
  return <AbsoluteFill style={{background: spec.background, overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs><filter id="soft"><feGaussianBlur stdDeviation={4 + spec.texture.bloom * 8} /></filter></defs>
      {Array.from({length: 14}, (_, ribbon) => {
        const points = Array.from({length: 65}, (_, index) => {
          const x = index / 64 * width;
          const band = spectrum[(index + ribbon * 3) % spectrum.length] || 0;
          const y = height * (0.12 + ribbon / 17) + Math.sin(index * 0.22 + time * spec.motion.speed + ribbon) * (30 + band * 170) + energy * ribbon * 4;
          return `${index ? "L" : "M"}${x},${y}`;
        }).join(" ");
        return <path key={ribbon} d={points} fill="none" stroke={spec.palette[ribbon % 4]} strokeWidth={2 + energy * 8} opacity={0.13 + (ribbon % 3) * 0.08} filter={ribbon % 4 === 0 ? "url(#soft)" : undefined} />;
      })}
    </svg>
  </AbsoluteFill>;
};

const CloudBraidOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const progress = frame / Math.max(1, durationInFrames - 1);
  const energy = mean(spectrum);
  const bridge = progress > 0.50 && progress < 0.625;
  const returnPhase = progress > 0.625 ? 1 : 0;
  const strands = Array.from({length: 7}, (_, index) => index);
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <filter id="cloud-braid-soft"><feGaussianBlur stdDeviation={3 + spec.texture.bloom * 4} /></filter>
      </defs>
      {strands.map((index) => {
        const missing = bridge && index === 2;
        const baseY = height * (0.22 + index * 0.082) + (index % 2 ? height * 0.025 : -height * 0.012);
        const path = Array.from({length: 49}, (_, point) => {
          const x = width * (point / 48);
          const braid = Math.sin(point * 0.34 + time * (0.72 + index * 0.035) * spec.motion.speed + index * 0.81) * (height * (0.045 + energy * 0.06));
          const diagonal = (index - 3) * width * 0.014 + Math.sin(time * 0.16 + index) * width * 0.025;
          const turn = returnPhase ? Math.sin(point * 0.18 + index) * height * 0.028 : 0;
          const y = baseY + braid + diagonal + turn;
          return `${point ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
        return <path key={`cloud-strand-${index}`} d={path} fill="none" stroke={spec.palette[index % 4]} strokeWidth={missing ? 0 : 11 + energy * 15 + (index % 3) * 3} strokeLinecap="round" opacity={missing ? 0 : 0.45 + (index % 2) * 0.10} filter={index === 0 ? "url(#cloud-braid-soft)" : undefined} />;
      })}
      <path d={`M ${width * 0.08} ${height * 0.86} Q ${width * 0.34} ${height * (0.80 - energy * 0.08)} ${width * 0.62} ${height * 0.86} T ${width * 0.94} ${height * 0.82}`} fill="none" stroke={spec.palette[3]} strokeWidth={3} opacity={0.26} />
    </svg>
  </AbsoluteFill>;
};

const Constellation = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const energy = mean(spectrum);
  const nodes = Array.from({length: 72}, (_, index) => ({
    x: seeded(spec.seed, index) * width,
    y: seeded(spec.seed + 5, index) * height,
    phase: seeded(spec.seed + 12, index) * Math.PI * 2,
  }));
  return <AbsoluteFill style={{background: `radial-gradient(circle at 50% 50%, ${rgba(spec.palette[2], 0.1)}, ${spec.background} 68%)`}}>
    <svg width={width} height={height}>
      {nodes.map((node, index) => {
        const x = node.x + Math.sin(time * 0.2 * spec.motion.speed + node.phase) * 34;
        const y = node.y + Math.cos(time * 0.16 * spec.motion.speed + node.phase) * 28;
        const next = nodes[(index + 11) % nodes.length];
        return <g key={index}>
          <line x1={x} y1={y} x2={next.x} y2={next.y} stroke={rgba(spec.palette[index % 4], 0.035 + energy * 0.14)} />
          <circle cx={x} cy={y} r={1.5 + (spectrum[index % spectrum.length] || 0) * 13} fill={spec.palette[index % 4]} opacity={0.2 + energy * 0.7} />
        </g>;
      })}
    </svg>
  </AbsoluteFill>;
};

const Meadow = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const horizon = height * (0.54 - mids * 0.035);
  const groundY = height * 0.77;
  const grass = Array.from({length: 72}, (_, index) => {
    const x = ((index * 0.137 + seeded(spec.seed, index) * 0.08) % 1) * width;
    const lean = Math.sin(time * (0.55 + seeded(spec.seed + 10, index) * 0.25) + index) * width * 0.012;
    const top = groundY - height * (0.045 + seeded(spec.seed + 20, index) * 0.16) * (0.82 + mids * 0.42);
    return {x, top, lean, width: 1.2 + seeded(spec.seed + 30, index) * 2.3};
  });
  const fireflies = Array.from({length: 24}, (_, index) => ({
    x: width * (0.10 + seeded(spec.seed + 40, index) * 0.80),
    y: height * (0.20 + seeded(spec.seed + 50, index) * 0.40),
    phase: seeded(spec.seed + 60, index) * Math.PI * 2,
  }));
  return <AbsoluteFill style={{background: spec.background, overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id="meadow-sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={spec.palette[0]} stopOpacity={0.78} />
          <stop offset="56%" stopColor={spec.palette[1]} stopOpacity={0.52} />
          <stop offset="100%" stopColor={spec.background} />
        </linearGradient>
        <linearGradient id="meadow-ground" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={spec.palette[1]} stopOpacity={0.58} />
          <stop offset="100%" stopColor={spec.palette[3]} stopOpacity={0.92} />
        </linearGradient>
        <filter id="meadow-glow"><feGaussianBlur stdDeviation={7 + highs * 12} /></filter>
      </defs>
      <rect width={width} height={height} fill="url(#meadow-sky)" />
      <circle cx={width * (0.77 + Math.sin(time * 0.12) * 0.025)} cy={height * 0.22} r={height * (0.075 + bass * 0.018)} fill={spec.palette[0]} opacity={0.30 + bass * 0.15} filter="url(#meadow-glow)" />
      <circle cx={width * 0.77} cy={height * 0.22} r={height * (0.035 + bass * 0.012)} fill={spec.palette[0]} opacity={0.76} />
      <path d={`M 0 ${horizon + height * 0.05} Q ${width * 0.22} ${horizon - height * 0.06} ${width * 0.45} ${horizon + height * 0.03} T ${width} ${horizon - height * 0.02} L ${width} ${height} L 0 ${height} Z`} fill={rgba(spec.palette[1], 0.42)} />
      <path d={`M 0 ${groundY} Q ${width * 0.22} ${groundY - height * 0.07} ${width * 0.48} ${groundY + height * 0.01} T ${width} ${groundY - height * 0.06} L ${width} ${height} L 0 ${height} Z`} fill="url(#meadow-ground)" />
      <path d={`M 0 ${horizon} Q ${width * 0.22} ${horizon - height * 0.045} ${width * 0.50} ${horizon + height * 0.012} T ${width} ${horizon - height * 0.02}`} fill="none" stroke={spec.palette[0]} strokeOpacity={0.38 + mids * 0.18} strokeWidth={2 + mids * 3} />
      {grass.map((blade, index) => <path key={`blade-${index}`} d={`M ${blade.x} ${groundY + height * 0.04} Q ${blade.x + blade.lean} ${(groundY + blade.top) / 2} ${blade.x + blade.lean * 1.5} ${blade.top}`} fill="none" stroke={index % 3 === 0 ? spec.palette[0] : spec.palette[3]} strokeOpacity={0.40 + mids * 0.34} strokeWidth={blade.width} strokeLinecap="round" />)}
      {fireflies.map((fly, index) => {
        const x = fly.x + Math.sin(time * 0.32 + fly.phase) * width * 0.018;
        const y = fly.y + Math.cos(time * 0.41 + fly.phase) * height * 0.020;
        const glow = 0.18 + (0.5 + 0.5 * Math.sin(time * 2.1 + fly.phase)) * (0.28 + highs * 0.42);
        return <circle key={`fly-${index}`} cx={x} cy={y} r={1.5 + highs * 2.5} fill={index % 2 ? spec.palette[0] : spec.palette[2]} opacity={glow} />;
      })}
    </svg>
  </AbsoluteFill>;
};

const CricketPulseOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const centers = [
    [width * 0.31, height * 0.55],
    [width * 0.66, height * 0.48],
  ];
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {centers.map(([cx, cy], centerIndex) => Array.from({length: 4}, (_, index) => {
        const phase = (time * (0.17 + centerIndex * 0.035) + index * 0.23 + centerIndex * 0.41) % 1;
        const radius = Math.min(width, height) * (0.035 + phase * (0.13 + bass * 0.08));
        return <circle key={`chirp-ring-${centerIndex}-${index}`} cx={cx} cy={cy} r={radius} fill="none" stroke={spec.palette[(index + centerIndex) % 3]} strokeWidth={1.2 + highs * 2.4} opacity={(1 - phase) * (0.16 + highs * 0.30)} />;
      }))}
      <path d={`M ${width * 0.12} ${height * 0.84} Q ${width * 0.30} ${height * (0.78 - bass * 0.05)} ${width * 0.48} ${height * 0.84} T ${width * 0.88} ${height * (0.79 - bass * 0.04)}`} fill="none" stroke={spec.palette[0]} strokeOpacity={0.22 + highs * 0.18} strokeWidth={2 + highs * 2} strokeDasharray="2 18" />
    </svg>
  </AbsoluteFill>;
};

const MagneticDustOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const progress = frame / Math.max(1, durationInFrames - 1);
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const collapse = progress > 0.60 && progress < 0.70;
  const cx = width * (0.5 + Math.sin(time * 0.17) * 0.035);
  const cy = height * (0.5 + Math.cos(time * 0.13) * 0.025);
  const particles = Array.from({length: 68}, (_, index) => {
    const phase = seeded(spec.seed + 22, index) * Math.PI * 2;
    const orbit = phase + time * (0.08 + seeded(spec.seed + 31, index) * 0.16) * spec.motion.speed;
    const radius = Math.min(width, height) * (0.05 + seeded(spec.seed + 42, index) * 0.36);
    const split = 1 + (index % 3) * 0.12 + mids * 0.06;
    return {
      x: cx + Math.cos(orbit) * radius * split * (collapse ? 0.55 : 1),
      y: cy + Math.sin(orbit) * radius * 0.66 * (collapse ? 0.55 : 1),
      r: 2 + seeded(spec.seed + 54, index) * 6 + highs * 9,
      color: spec.palette[index % 3],
    };
  });
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs><filter id="magnetic-glow"><feGaussianBlur stdDeviation={8 + highs * 12} /></filter></defs>
      <circle cx={cx} cy={cy} r={Math.min(width, height) * (0.18 + bass * 0.05)} fill={rgba(spec.palette[2], collapse ? 0.02 : 0.10 + bass * 0.08)} filter="url(#magnetic-glow)" />
      {Array.from({length: 5}, (_, index) => {
        const radius = Math.min(width, height) * (0.10 + index * 0.07 + bass * 0.02);
        return <ellipse key={`orbit-${index}`} cx={cx} cy={cy} rx={radius * 1.45} ry={radius * 0.66} fill="none" stroke={spec.palette[index % 3]} strokeWidth={1.5 + bass * 2} opacity={collapse ? 0.06 : 0.14 + highs * 0.12} transform={`rotate(${time * (4 + index) + index * 19} ${cx} ${cy})`} />;
      })}
      {particles.map((particle, index) => <circle key={`dust-${index}`} cx={particle.x} cy={particle.y} r={particle.r} fill={particle.color} opacity={collapse ? 0.16 : 0.38 + highs * 0.45} />)}
      <circle cx={cx} cy={cy} r={10 + bass * 24} fill={spec.palette[0]} opacity={collapse ? 0.18 : 0.70} />
      <circle cx={cx} cy={cy} r={3 + highs * 7} fill={spec.palette[1]} opacity={collapse ? 0.24 : 0.96} />
      <g fill={spec.palette[1]} opacity={collapse ? 0.18 : 0.58} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.20em">
        <text x={width * 0.07} y={height * 0.10}>ATTRACTOR / {collapse ? "LOW FIELD" : "LIVE"}</text>
        <text x={width * 0.76} y={height * 0.10}>{String(Math.floor(progress * 40) + 1).padStart(2, "0")} / 40</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const PullMeInOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const barLength = (60 / 112) * 4;
  const bar = Math.min(31, Math.floor(time / barLength));
  const section = bar < 4 ? "tease" : bar < 12 ? "pocket" : bar < 16 ? "lift" : bar < 20 ? "drop" : bar < 28 ? "hook" : "final";
  const barProgress = (time % barLength) / barLength;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const centerX = width * 0.5;
  const horizon = height * (section === "drop" ? 0.52 : 0.46 - mids * 0.025);
  const opening = section === "tease" ? 0.13 + barProgress * 0.12 : section === "pocket" ? 0.28 : section === "lift" ? 0.44 + barProgress * 0.10 : section === "drop" ? 0.08 : section === "hook" ? 0.72 + bass * 0.14 : 0.58;
  const pulse = 1 + bass * (section === "hook" ? 0.18 : 0.08);
  const floorLines = Array.from({length: 12}, (_, index) => index);
  const wallLines = Array.from({length: 9}, (_, index) => index);
  const rays = Array.from({length: section === "hook" || section === "final" ? 28 : 12}, (_, index) => index);

  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <radialGradient id="pull-core" cx="50%" cy="48%" r="60%">
          <stop offset="0%" stopColor={spec.palette[2]} stopOpacity={0.22 + opening * 0.25} />
          <stop offset="42%" stopColor={spec.palette[1]} stopOpacity={0.04 + opening * 0.12} />
          <stop offset="100%" stopColor={spec.background} stopOpacity={0} />
        </radialGradient>
        <filter id="pull-glow"><feGaussianBlur stdDeviation={8 + highs * 16} /></filter>
      </defs>
      <rect width={width} height={height} fill="url(#pull-core)" opacity={section === "drop" ? 0.42 : 1} />

      <g opacity={section === "drop" ? 0.34 : 0.62 + mids * 0.16}>
        {floorLines.map((index) => {
          const depth = (index + 1) / floorLines.length;
          const y = horizon + depth * depth * height * 0.58;
          const spread = width * (0.04 + depth * 0.62) * (0.45 + opening * 0.8);
          return <line key={`floor-${index}`} x1={centerX - spread} x2={centerX + spread} y1={y} y2={y} stroke={spec.palette[index % 4]} strokeOpacity={0.10 + depth * 0.24} strokeWidth={1 + bass * depth * 2} />;
        })}
        {wallLines.map((index) => {
          const side = index / (wallLines.length - 1) * 2 - 1;
          return <line key={`wall-${index}`} x1={centerX} x2={centerX + side * width * (0.07 + opening * 0.46)} y1={horizon} y2={height * 0.98} stroke={spec.palette[(index + 1) % 4]} strokeOpacity={0.10 + Math.abs(side) * 0.13} strokeWidth={1.5} />;
        })}
      </g>

      {rays.map((index) => {
        const angle = index / rays.length * Math.PI * 2 + time * 0.18 * spec.motion.speed;
        const inner = Math.min(width, height) * (0.05 + opening * 0.06);
        const outer = Math.min(width, height) * (0.20 + opening * 0.48 + bass * 0.12);
        const x1 = centerX + Math.cos(angle) * inner;
        const y1 = horizon + Math.sin(angle) * inner * 0.72;
        const x2 = centerX + Math.cos(angle) * outer;
        const y2 = horizon + Math.sin(angle) * outer * 0.72;
        return <line key={`ray-${index}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={spec.palette[index % 4]} strokeOpacity={0.06 + (section === "hook" ? 0.22 : 0.08) + highs * 0.12} strokeWidth={1 + highs * 3} />;
      })}

      <g transform={`translate(${centerX} ${horizon}) scale(${pulse})`}>
        <circle r={Math.min(width, height) * (0.05 + opening * 0.14)} fill={spec.palette[1]} opacity={0.10 + bass * 0.14} filter="url(#pull-glow)" />
        <circle r={Math.min(width, height) * (0.035 + opening * 0.10)} fill={spec.palette[2]} opacity={0.24 + opening * 0.26} />
        <path d={`M ${-width * (0.02 + opening * 0.12)} ${-height * (0.07 + opening * 0.13)} L ${width * (0.02 + opening * 0.12)} ${-height * (0.07 + opening * 0.13)} L ${width * (0.035 + opening * 0.18)} ${height * (0.07 + opening * 0.12)} L ${-width * (0.035 + opening * 0.18)} ${height * (0.07 + opening * 0.12)} Z`} fill="none" stroke={spec.palette[3]} strokeWidth={2 + bass * 4} strokeOpacity={0.42 + opening * 0.32} />
        {section === "drop" ? <circle r={Math.min(width, height) * 0.022} fill={spec.palette[3]} opacity={0.56} /> : null}
      </g>

      {section === "hook" || section === "final" ? <g transform={`translate(${centerX} ${horizon}) rotate(${time * (section === "final" ? 12 : 5)})`}>
        <rect x={-width * 0.19} y={-height * 0.19} width={width * 0.38} height={height * 0.38} fill="none" stroke={spec.palette[0]} strokeOpacity={0.18 + bass * 0.14} strokeWidth={3 + bass * 5} transform="rotate(45)" />
        <circle r={Math.min(width, height) * (0.18 + bass * 0.06)} fill="none" stroke={spec.palette[2]} strokeOpacity={0.32 + highs * 0.18} strokeWidth={2 + mids * 3} strokeDasharray={section === "final" ? "8 18" : "2 22"} />
      </g> : null}

      <g fill={spec.palette[3]} opacity={0.42} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.22em">
        <text x={width * 0.07} y={height * 0.10}>SIGNAL / {section.toUpperCase()}</text>
        <text x={width * 0.76} y={height * 0.10}>{String(bar + 1).padStart(2, "0")} / 32</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const OctopusInkOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const centerX = width * 0.5;
  const centerY = height * 0.60;
  const pulse = 1 + bass * 0.16;
  const armPaths = Array.from({length: 8}, (_, index) => {
    const angle = -Math.PI * 0.92 + index * (Math.PI * 1.84 / 7);
    const sx = centerX + Math.cos(angle) * width * 0.06;
    const sy = centerY + Math.sin(angle) * height * 0.055 + height * 0.03;
    const ex = centerX + Math.cos(angle) * width * (0.16 + 0.018 * Math.sin(time * 1.7 + index));
    const ey = centerY + height * 0.19 + Math.sin(time * 1.4 + index) * height * 0.028;
    const bend = Math.sin(time * 1.1 + index * 0.8) * width * 0.045;
    return `M ${sx} ${sy} Q ${sx + bend} ${(sy + ey) / 2} ${ex} ${ey}`;
  });
  const cloud = Array.from({length: 16}, (_, index) => {
    const angle = index * Math.PI * 2 / 16 + time * 0.08;
    const radius = Math.min(width, height) * (0.13 + (index % 4) * 0.018 + bass * 0.05);
    const x = centerX + Math.cos(angle) * radius * 1.45;
    const y = centerY + Math.sin(angle) * radius * 0.72;
    const r = Math.min(width, height) * (0.025 + (index % 3) * 0.008 + mids * 0.012);
    return <circle key={`cloud-${index}`} cx={x} cy={y} r={r} fill={spec.palette[2]} opacity={0.11 + bass * 0.08} />;
  });
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <g opacity={0.86}>
        <circle cx={centerX} cy={centerY} r={Math.min(width, height) * (0.24 + bass * 0.05)} fill="none" stroke={spec.palette[0]} strokeWidth={3 + bass * 8} strokeDasharray="12 24" opacity={0.36 + bass * 0.16} />
        {cloud}
        <g fill="none" stroke={spec.palette[1]} strokeWidth={Math.max(5, width * 0.005)} strokeLinecap="round" opacity={0.78}>
          {armPaths.map((d, index) => <path key={`arm-${index}`} d={d} />)}
        </g>
        <ellipse cx={centerX} cy={centerY - height * 0.025} rx={width * 0.105 * pulse} ry={height * 0.105 * pulse} fill={spec.palette[2]} fillOpacity={0.44} stroke={spec.palette[1]} strokeWidth={5} />
        <ellipse cx={centerX} cy={centerY - height * 0.032} rx={width * 0.074} ry={height * 0.066} fill={spec.background} fillOpacity={0.86} />
        <circle cx={centerX - width * 0.028} cy={centerY - height * 0.052} r={width * 0.009} fill={spec.palette[3]} />
        <circle cx={centerX + width * 0.028} cy={centerY - height * 0.052} r={width * 0.009} fill={spec.palette[3]} />
        <path d={`M ${centerX - width * 0.026} ${centerY - height * 0.005} Q ${centerX} ${centerY + height * 0.018} ${centerX + width * 0.026} ${centerY - height * 0.005}`} fill="none" stroke={spec.palette[0]} strokeWidth={4} strokeLinecap="round" opacity={0.85} />
      </g>
      <g fill="none" stroke={spec.palette[3]} strokeWidth={3} opacity={0.34}>
        <path d={`M ${width * 0.17} ${height * 0.10} q ${width * 0.05} ${height * 0.04} 0 ${height * 0.15} l ${width * 0.05} ${height * 0.08}`} />
        <path d={`M ${width * 0.83} ${height * 0.10} q ${-width * 0.05} ${height * 0.04} 0 ${height * 0.15} l ${-width * 0.05} ${height * 0.08}`} />
      </g>
      <g fill={spec.palette[3]} opacity={0.48} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.013)} letterSpacing="0.18em">
        <text x={width * 0.08} y={height * 0.12}>CURIOUS HAND</text>
        <text x={width * 0.68} y={height * 0.12}>BOUNDARY SIGNAL</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const PillowFightOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const centerX = width * 0.5;
  const centerY = height * 0.52;
  const pillowCount = 7;
  const pillows = Array.from({length: pillowCount}, (_, index) => {
    const lane = index - (pillowCount - 1) / 2;
    const phase = time * (0.62 + index * 0.05) * spec.motion.speed + index * 0.88;
    const arc = Math.sin(phase) * height * (0.15 + highs * 0.05);
    const x = centerX + lane * width * 0.08 + Math.cos(phase * 0.8) * width * 0.035;
    const y = centerY + arc + Math.cos(phase * 1.6) * height * 0.025;
    const rotate = Math.sin(phase * 1.2) * 18;
    const scale = 1 + bass * 0.18 + (index % 2) * 0.04;
    return {x, y, rotate, scale, index};
  });
  const stars = Array.from({length: 38}, (_, index) => {
    const angle = seeded(spec.seed + 40, index) * Math.PI * 2 + time * 0.06;
    const radius = Math.min(width, height) * (0.16 + seeded(spec.seed + 53, index) * 0.44);
    return {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius * 0.62,
      size: 3 + seeded(spec.seed + 67, index) * 11 + highs * 8,
      color: spec.palette[index % 4],
    };
  });
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <filter id="pillow-shadow"><feDropShadow dx="0" dy="18" stdDeviation="18" floodColor="#000000" floodOpacity="0.38" /></filter>
        <linearGradient id="sheet-grid" x1="0" x2="1">
          <stop offset="0%" stopColor={rgba(spec.palette[3], 0.05)} />
          <stop offset="100%" stopColor={rgba(spec.palette[1], 0.13 + mids * 0.08)} />
        </linearGradient>
      </defs>
      <rect x={width * 0.08} y={height * 0.18} width={width * 0.84} height={height * 0.66} rx={18} fill="url(#sheet-grid)" stroke={rgba(spec.palette[3], 0.28)} strokeWidth={3} />
      {Array.from({length: 10}, (_, index) => (
        <line key={`sheet-x-${index}`} x1={width * (0.12 + index * 0.085)} x2={width * (0.12 + index * 0.085)} y1={height * 0.2} y2={height * 0.82} stroke={rgba(spec.palette[2], 0.12)} strokeWidth={2} />
      ))}
      {Array.from({length: 7}, (_, index) => (
        <line key={`sheet-y-${index}`} x1={width * 0.1} x2={width * 0.9} y1={height * (0.24 + index * 0.085)} y2={height * (0.24 + index * 0.085)} stroke={rgba(spec.palette[2], 0.12)} strokeWidth={2} />
      ))}
      {stars.map((star, index) => (
        <path key={`star-${index}`} d={`M ${star.x} ${star.y - star.size} L ${star.x + star.size * 0.28} ${star.y - star.size * 0.28} L ${star.x + star.size} ${star.y} L ${star.x + star.size * 0.28} ${star.y + star.size * 0.28} L ${star.x} ${star.y + star.size} L ${star.x - star.size * 0.28} ${star.y + star.size * 0.28} L ${star.x - star.size} ${star.y} L ${star.x - star.size * 0.28} ${star.y - star.size * 0.28} Z`} fill={star.color} opacity={0.18 + highs * 0.36} />
      ))}
      {pillows.map((pillow) => (
        <g key={`pillow-${pillow.index}`} transform={`translate(${pillow.x} ${pillow.y}) rotate(${pillow.rotate}) scale(${pillow.scale})`} filter="url(#pillow-shadow)">
          <rect x={-width * 0.055} y={-height * 0.038} width={width * 0.11} height={height * 0.076} rx={20} fill={pillow.index % 2 ? spec.palette[3] : spec.palette[1]} stroke={spec.palette[pillow.index % 4]} strokeWidth={4} />
          <path d={`M ${-width * 0.047} 0 C ${-width * 0.028} ${-height * 0.028} ${width * 0.028} ${-height * 0.028} ${width * 0.047} 0 C ${width * 0.024} ${height * 0.03} ${-width * 0.026} ${height * 0.03} ${-width * 0.047} 0`} fill="none" stroke={rgba(spec.background, 0.42)} strokeWidth={2} />
        </g>
      ))}
      <g fill={spec.palette[2]} opacity={0.68} fontFamily="Impact, Arial Black, sans-serif" fontSize={Math.max(24, width * 0.032)}>
        <text x={width * 0.12} y={height * 0.18}>SOLO ROUND</text>
        <text x={width * 0.62} y={height * 0.82}>SETTLE THE ROOM</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const JamaicaReggaeOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const pulse = 1 + bass * 0.08;
  const flagWidth = width * 0.18;
  const flagHeight = flagWidth * 0.5;
  const flag = (x: number, y: number, rotation: number, opacity: number, key: string) => (
    <g key={key} transform={`translate(${x} ${y}) rotate(${rotation} ${flagWidth / 2} ${flagHeight / 2}) scale(${pulse})`} opacity={opacity}>
      <rect width={flagWidth} height={flagHeight} rx={10} fill="#009b3a" stroke="#fed100" strokeWidth={3} />
      <polygon points={`0,0 0,${flagHeight} ${flagWidth / 2},${flagHeight / 2}`} fill="#000000" />
      <polygon points={`${flagWidth},0 ${flagWidth},${flagHeight} ${flagWidth / 2},${flagHeight / 2}`} fill="#000000" />
      <line x1="0" y1="0" x2={flagWidth} y2={flagHeight} stroke="#fed100" strokeWidth={flagHeight * 0.17} />
      <line x1={flagWidth} y1="0" x2="0" y2={flagHeight} stroke="#fed100" strokeWidth={flagHeight * 0.17} />
      <line x1="0" y1="0" x2={flagWidth} y2={flagHeight} stroke="#fed100" strokeWidth={flagHeight * 0.05} />
      <line x1={flagWidth} y1="0" x2="0" y2={flagHeight} stroke="#fed100" strokeWidth={flagHeight * 0.05} />
    </g>
  );
  const bars = Array.from({length: 9}, (_, index) => index);
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <filter id="jamaica-glow"><feGaussianBlur stdDeviation={5 + highs * 9} /></filter>
      </defs>
      <g filter="url(#jamaica-glow)" opacity={0.2 + mids * 0.3}>
        <rect x={width * 0.05} y={height * 0.16} width={width * 0.9} height={height * 0.68} fill="none" stroke="#009b3a" strokeWidth={10 + bass * 18} />
      </g>
      {flag(width * 0.07, height * 0.1 + Math.sin(time * 0.7) * height * 0.01, -3, 0.58 + mids * 0.18, "flag-left")}
      {flag(width * 0.75, height * 0.12 + Math.cos(time * 0.65) * height * 0.012, 3, 0.58 + mids * 0.18, "flag-right")}
      <g opacity={0.22 + bass * 0.32}>
        {bars.map((index) => {
          const barHeight = height * (0.08 + ((spectrum[(index * 5) % spectrum.length] || 0) * 0.32));
          const x = width * 0.23 + index * width * 0.068;
          return <rect key={index} x={x} y={height * 0.78 - barHeight} width={width * 0.035} height={barHeight} fill={index % 2 ? "#fed100" : "#009b3a"} rx={6} />;
        })}
      </g>
      <g fill="#fed100" opacity={0.55 + highs * 0.2} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.013)} letterSpacing="0.24em">
        <text x={width * 0.08} y={height * 0.91}>ONE DROP / DUB RESPONSE</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const PaperScoreOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const progress = Math.min(1, frame / Math.max(1, durationInFrames - 1));
  const energy = mean(spectrum);
  const cards = [
    {label: "ROOM", x: 0.17, y: 0.24, angle: -5, at: 0.02},
    {label: "QUESTION", x: 0.68, y: 0.20, angle: 4, at: 0.16},
    {label: "LATE", x: 0.22, y: 0.66, angle: 3, at: 0.40},
    {label: "ARRIVAL", x: 0.69, y: 0.67, angle: -4, at: 0.68},
  ];
  const cardWidth = width * 0.24;
  const cardHeight = height * 0.22;
  const visible = (at: number) => interpolate(progress, [at, at + 0.07], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs><filter id="paper-shadow"><feDropShadow dx="0" dy="18" stdDeviation="16" floodColor="#000" floodOpacity="0.42" /></filter></defs>
      <g opacity={0.18 + energy * 0.18}>
        {Array.from({length: 9}, (_, index) => (
          <line key={`grid-x-${index}`} x1={width * (0.12 + index * 0.095)} x2={width * (0.12 + index * 0.095)} y1={height * 0.12} y2={height * 0.88} stroke={spec.palette[1]} strokeWidth={1} />
        ))}
        {Array.from({length: 7}, (_, index) => (
          <line key={`grid-y-${index}`} x1={width * 0.10} x2={width * 0.90} y1={height * (0.18 + index * 0.11)} y2={height * (0.18 + index * 0.11)} stroke={spec.palette[1]} strokeWidth={1} />
        ))}
      </g>
      {cards.map((card, index) => {
        const opacity = visible(card.at);
        const pulse = 1 + (spectrum[(index * 7) % spectrum.length] || 0) * 0.06;
        return <g key={card.label} transform={`translate(${width * card.x} ${height * card.y}) rotate(${card.angle + Math.sin(time * 0.18 + index) * 0.6}) scale(${pulse})`} opacity={opacity} filter="url(#paper-shadow)">
          <rect x={-cardWidth / 2} y={-cardHeight / 2} width={cardWidth} height={cardHeight} rx={8} fill={spec.palette[3]} fillOpacity={0.92} stroke={spec.palette[index % 3]} strokeWidth={4} />
          <path d={`M ${-cardWidth * 0.35} ${-cardHeight * 0.18} Q 0 ${-cardHeight * 0.25} ${cardWidth * 0.34} ${-cardHeight * 0.16}`} fill="none" stroke={spec.palette[1]} strokeWidth={3} opacity={0.65} />
          <text x={-cardWidth * 0.35} y={cardHeight * 0.16} fill={spec.background} fontFamily="ui-monospace,monospace" fontSize={Math.max(18, width * 0.016)} letterSpacing="0.16em">{card.label}</text>
          <circle cx={cardWidth * 0.34} cy={-cardHeight * 0.24} r={6 + energy * 10} fill={spec.palette[index % 3]} />
        </g>;
      })}
      <rect x={width * 0.38} y={height * 0.39} width={width * 0.24} height={height * 0.22} fill="none" stroke={spec.palette[0]} strokeWidth={3 + energy * 4} strokeDasharray="12 18" opacity={0.20 + energy * 0.34} transform={`rotate(${Math.sin(time * 0.13) * 2} ${width * 0.5} ${height * 0.5})`} />
      <g fill={spec.palette[3]} opacity={0.62} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.20em">
        <text x={width * 0.08} y={height * 0.92}>LEAVE ONE THING UNFINISHED</text>
        <text x={width * 0.78} y={height * 0.92}>{String(Math.round(progress * 64)).padStart(2, "0")} / 64</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const RareSignalAtlasOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const progress = Math.min(1, frame / Math.max(1, durationInFrames - 1));
  const energy = mean(spectrum);
  const cards: AtlasCard[] = spec.cards?.length ? spec.cards : [
    {label: "WILD SIGNAL", region: "FIELD CARD", note: "DORIAN"},
  ];
  const cardWidth = width * 0.31;
  const cardHeight = height * 0.205;
  const positions = [
    [0.20, 0.26], [0.80, 0.26], [0.20, 0.72], [0.80, 0.72],
    [0.50, 0.18], [0.50, 0.82], [0.34, 0.50], [0.66, 0.50],
  ];
  const visible = (index: number) => {
    const revealAt = cards.length <= 1 ? 0 : index * 0.82 / (cards.length - 1);
    return interpolate(progress, [revealAt, revealAt + 0.08], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  };
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <filter id="atlas-shadow"><feDropShadow dx="0" dy="16" stdDeviation="15" floodColor="#000" floodOpacity="0.45" /></filter>
        <radialGradient id="atlas-core" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor={spec.palette[2]} stopOpacity={0.20 + energy * 0.20} />
          <stop offset="100%" stopColor={spec.background} stopOpacity={0} />
        </radialGradient>
      </defs>
      <rect width={width} height={height} fill="url(#atlas-core)" />
      {Array.from({length: 10}, (_, index) => (
        <line key={`atlas-grid-${index}`} x1={width * 0.08} x2={width * 0.92} y1={height * (0.13 + index * 0.085)} y2={height * (0.13 + index * 0.085)} stroke={spec.palette[1]} strokeOpacity={0.08 + energy * 0.05} />
      ))}
      <g transform={`translate(${width * 0.5} ${height * 0.5}) rotate(${time * 3})`}>
        <circle r={Math.min(width, height) * (0.13 + energy * 0.05)} fill="none" stroke={spec.palette[0]} strokeWidth={3 + energy * 6} strokeDasharray="5 15" opacity={0.52 + energy * 0.18} />
        <circle r={Math.min(width, height) * (0.20 + energy * 0.04)} fill="none" stroke={spec.palette[2]} strokeWidth={2} strokeDasharray="1 22" opacity={0.46} />
        <path d={Array.from({length: 33}, (_, index) => {
          const angle = index / 32 * Math.PI * 2;
          const radius = Math.min(width, height) * (0.085 + (spectrum[index % spectrum.length] || 0) * 0.05);
          const x = Math.cos(angle) * radius;
          const y = Math.sin(angle) * radius;
          return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ")} fill="none" stroke={spec.palette[3]} strokeWidth={3 + energy * 5} opacity={0.70} />
      </g>
      {cards.map((card, index) => {
        const [x, y] = positions[index % positions.length];
        const opacity = visible(index);
        const pulse = 1 + (spectrum[(index * 9) % spectrum.length] || 0) * 0.08;
        const accent = card.accent || spec.palette[index % 4];
        return <g key={`${card.label}-${index}`} transform={`translate(${width * x} ${height * y}) rotate(${index % 2 ? 2.5 : -2.5}) scale(${pulse})`} opacity={opacity} filter="url(#atlas-shadow)">
          <rect x={-cardWidth / 2} y={-cardHeight / 2} width={cardWidth} height={cardHeight} rx={12} fill={spec.background} fillOpacity={0.88} stroke={accent} strokeWidth={4} />
          <rect x={-cardWidth / 2} y={-cardHeight / 2} width={cardWidth * 0.035} height={cardHeight} rx={8} fill={accent} />
          <circle cx={cardWidth * 0.37} cy={-cardHeight * 0.27} r={7 + energy * 10} fill={accent} />
          <text x={-cardWidth * 0.39} y={-cardHeight * 0.08} fill={spec.palette[3]} fontFamily="ui-monospace,monospace" fontSize={Math.max(17, width * 0.015)} letterSpacing="0.08em">{card.label.toUpperCase()}</text>
          <text x={-cardWidth * 0.39} y={cardHeight * 0.23} fill={accent} fontFamily="ui-monospace,monospace" fontSize={Math.max(13, width * 0.0105)} letterSpacing="0.12em">{card.region.toUpperCase()} · {card.note.toUpperCase()}</text>
        </g>;
      })}
      <g fill={spec.palette[3]} opacity={0.64} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.20em">
        <text x={width * 0.08} y={height * 0.095}>RARE SIGNAL ATLAS / REAL CALL → CHORD TONE</text>
        <text x={width * 0.77} y={height * 0.925}>FIELD STUDY {String(Math.round(progress * 100)).padStart(3, "0")}%</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const FivePaneDoorOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const time = frame / fps;
  const barSeconds = (60 / 108) * 5;
  const bar = Math.floor(time / barSeconds);
  const barProgress = (time % barSeconds) / barSeconds;
  const section = bar < 8 ? "HINGE" : bar < 24 ? "ASSEMBLE" : bar < 40 ? "TURN" : bar < 44 ? "BLACK SPACE" : "RETURN";
  const drop = section === "BLACK SPACE";
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const cx = width * 0.5;
  const cy = height * 0.52;
  const opening = drop ? 0.10 : section === "HINGE" ? 0.22 + barProgress * 0.12 : section === "ASSEMBLE" ? 0.38 + (bar - 8) / 16 * 0.18 : section === "TURN" ? 0.64 + Math.sin(barProgress * Math.PI) * 0.08 : 0.82;
  const rotation = (section === "TURN" ? 1 : -1) * (time * 5.5 + (bar >= 24 ? 12 : 0)) * spec.motion.rotation;
  const panes = Array.from({length: 5}, (_, index) => index);
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs><filter id="door-glow"><feGaussianBlur stdDeviation={7 + highs * 14} /></filter></defs>
      <g opacity={drop ? 0.18 : 0.24 + mids * 0.18}>
        {Array.from({length: 12}, (_, index) => <line key={`grid-${index}`} x1={width * 0.08} x2={width * 0.92} y1={height * (0.14 + index * 0.066)} y2={height * (0.14 + index * 0.066)} stroke={spec.palette[1]} strokeWidth={1} />)}
        {Array.from({length: 16}, (_, index) => <line key={`grid-v-${index}`} x1={width * (0.08 + index * 0.056)} x2={width * (0.08 + index * 0.056)} y1={height * 0.14} y2={height * 0.86} stroke={spec.palette[1]} strokeWidth={1} />)}
      </g>
      <g transform={`translate(${cx} ${cy}) rotate(${rotation})`}>
        <rect x={-width * 0.20 * opening} y={-height * 0.26 * opening} width={width * 0.40 * opening} height={height * 0.52 * opening} fill={drop ? "none" : rgba(spec.palette[2], 0.05 + bass * 0.07)} stroke={spec.palette[2]} strokeWidth={2 + bass * 5} opacity={0.35 + opening * 0.45} filter={drop ? undefined : "url(#door-glow)"} />
        {panes.map((index) => {
          const angle = -0.62 + index * 0.31 + (section === "TURN" ? Math.sin(time * 0.7 + index) * 0.045 : 0);
          const paneW = width * (0.052 + opening * 0.026);
          const paneH = height * (0.24 + opening * 0.16);
          const x = (index - 2) * width * (0.066 + opening * 0.018);
          const color = spec.palette[index % 4];
          return <g key={`pane-${index}`} transform={`translate(${x} 0) rotate(${angle * 40})`} opacity={drop ? 0.12 : 0.48 + (index === (bar % 5) ? 0.24 : 0) + highs * 0.14}>
            <rect x={-paneW / 2} y={-paneH / 2} width={paneW} height={paneH} fill={rgba(color, 0.10 + mids * 0.08)} stroke={color} strokeWidth={2 + highs * 3} />
            <line x1={-paneW / 2} x2={paneW / 2} y1={0} y2={0} stroke={spec.palette[3]} strokeOpacity={0.35} />
          </g>;
        })}
      </g>
      <g fill={spec.palette[3]} opacity={drop ? 0.55 : 0.7} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.20em">
        <text x={width * 0.08} y={height * 0.10}>DOORWAY / {section}</text>
        <text x={width * 0.78} y={height * 0.10}>5 COUNT · {String((bar % 5) + 1).padStart(2, "0")}</text>
      </g>
    </svg>
  </AbsoluteFill>;
};

const ScreenPrintCountOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const barSeconds = (60 / 92) * 4;
  const bar = Math.min(47, Math.floor(time / barSeconds));
  const scene = Math.min(7, Math.floor(bar / 6));
  const sceneProgress = (time % (barSeconds * 6)) / (barSeconds * 6);
  const numerals = ["1", "2", "3", "4", "5", "6", "8?", "7"];
  const numeral = numerals[scene];
  const energy = mean(spectrum);
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const enter = interpolate(sceneProgress, [0, 0.12, 0.88, 1], [-0.12, 0, 0, 0.12], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const x = width * (0.47 + enter + Math.sin(time * 0.42 + scene) * 0.012);
  const y = height * (0.64 + Math.cos(time * 0.31 + scene) * 0.018);
  const scale = 1 + energy * 0.06 + (scene === 7 ? 0.08 : 0);
  const stopFade = interpolate(frame, [durationInFrames - fps * 0.35, durationInFrames - 1], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const commas = Array.from({length: scene + 2}, (_, index) => {
    const side = index % 2 ? 1 : -1;
    const baseX = side < 0 ? width * (0.07 + index * 0.035) : width * (0.93 - index * 0.035);
    const drift = Math.sin(time * (0.36 + index * 0.025) + index) * width * 0.018;
    return {x: baseX + drift, y: height * (0.18 + ((index * 0.137 + scene * 0.071) % 0.64)), side};
  });
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden", opacity: stopFade}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <pattern id="screenprint-dots" width="18" height="18" patternUnits="userSpaceOnUse">
          <circle cx="4" cy="4" r={1.5 + highs * 1.2} fill={spec.palette[3]} opacity={0.13} />
        </pattern>
        <filter id="ink-rough"><feTurbulence baseFrequency="0.018" numOctaves="2" seed={spec.seed + scene} result="noise" /><feDisplacementMap in="SourceGraphic" in2="noise" scale="5" /></filter>
      </defs>
      <rect width={width} height={height} fill={spec.background} />
      <rect width={width} height={height} fill="url(#screenprint-dots)" />
      <g transform={`translate(${x} ${y}) scale(${scale})`} filter="url(#ink-rough)">
        <text x={-width * 0.016} y={height * 0.018} textAnchor="middle" fill={spec.palette[2]} opacity={0.62} fontFamily="Arial Black,Impact,sans-serif" fontSize={height * 0.82} fontWeight={900}>{numeral}</text>
        <text x={width * 0.012} y={-height * 0.010} textAnchor="middle" fill={spec.palette[0]} opacity={0.76} fontFamily="Arial Black,Impact,sans-serif" fontSize={height * 0.82} fontWeight={900}>{numeral}</text>
        <text x="0" y="0" textAnchor="middle" fill={spec.palette[3]} fontFamily="Arial Black,Impact,sans-serif" fontSize={height * 0.82} fontWeight={900}>{numeral}</text>
      </g>
      {commas.map((comma, index) => (
        <g key={`comma-${index}`} transform={`translate(${comma.x} ${comma.y}) rotate(${comma.side * (12 + index * 7)})`} opacity={0.52 + energy * 0.22}>
          <ellipse rx={width * 0.032} ry={height * 0.022} fill={spec.palette[(index + 1) % 3]} />
          <path d={`M 0 ${height * 0.010} Q ${comma.side * width * 0.030} ${height * 0.052} ${comma.side * width * 0.006} ${height * 0.080}`} fill={spec.palette[(index + 1) % 3]} />
        </g>
      ))}
      <g transform={`translate(${width * 0.17} ${height * 0.89}) rotate(-90)`} fill={spec.palette[3]} opacity={0.72} fontFamily="Arial,sans-serif" letterSpacing="0.22em">
        <text fontSize={Math.max(15, width * 0.011)}>CLOUDS LEARN TO COUNT</text>
      </g>
      <text x={width * 0.77} y={height * 0.91} textAnchor="middle" fill={scene === 6 ? spec.palette[2] : spec.palette[1]} fontFamily="Arial Black,Impact,sans-serif" fontSize={Math.max(18, width * 0.022)} opacity={0.75}>
        {scene === 6 ? "MISCOUNT" : scene === 7 ? "CORRECTION" : "OVERHEAD"}
      </text>
    </svg>
  </AbsoluteFill>;
};

const SquirrelPinesOverlay = ({spec, spectrum}: Props) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const time = frame / fps;
  const progress = frame / Math.max(1, durationInFrames - 1);
  const barSeconds = (60 / 112) * 4;
  const bar = Math.floor(time / barSeconds);
  const section = bar < 4 ? "DAWN" : bar < 16 ? "FORAGE" : bar < 20 ? "CLIMB" : bar < 28 ? "HOOK" : bar < 32 ? "CHASE" : bar < 44 ? "FORAGE" : bar < 48 ? "DROP" : bar < 60 ? "HOOK" : "HOME";
  const bass = mean(spectrum.slice(0, 5)) * spec.reactivity.bass;
  const mids = mean(spectrum.slice(5, 18)) * spec.reactivity.mids;
  const highs = mean(spectrum.slice(18)) * spec.reactivity.highs;
  const centerX = width * (0.50 + Math.sin(time * 0.21) * 0.025);
  const groundY = height * 0.76;
  const leap = section === "CHASE" ? Math.sin(time * 2.4) * height * 0.065 : section === "DROP" ? 0 : Math.sin(time * 0.65) * height * 0.018;
  const squirrelX = centerX + Math.sin(time * 0.52) * width * 0.14;
  const squirrelY = groundY - height * 0.10 + leap;
  const scale = 1 + bass * 0.10;
  const cones = Array.from({length: 11}, (_, index) => {
    const phase = seeded(spec.seed + 30, index) * Math.PI * 2;
    const drift = (time * (0.08 + seeded(spec.seed + 42, index) * 0.06) + seeded(spec.seed + 50, index)) % 1;
    return {
      x: width * (0.08 + ((index * 0.097 + drift * 0.24) % 0.84)),
      y: height * (0.18 + ((index * 0.071 + Math.sin(time * 0.4 + phase) * 0.025 + 0.42) % 0.48)),
      rotate: Math.sin(time * 0.7 + phase) * 24,
      size: height * (0.018 + (index % 3) * 0.004 + highs * 0.004),
    };
  });
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id="pine-sky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={rgba(spec.palette[1], 0.20 + highs * 0.07)} />
          <stop offset="68%" stopColor={rgba(spec.palette[2], 0.06 + mids * 0.04)} />
          <stop offset="100%" stopColor={spec.background} />
        </linearGradient>
        <filter id="pine-glow"><feGaussianBlur stdDeviation={8 + spec.texture.bloom * 8} /></filter>
      </defs>
      <rect width={width} height={height} fill="url(#pine-sky)" />
      <circle cx={width * 0.78} cy={height * 0.23} r={height * (0.08 + bass * 0.025)} fill={spec.palette[2]} opacity={0.12 + bass * 0.10} filter="url(#pine-glow)" />
      {Array.from({length: 7}, (_, index) => {
        const x = width * (0.08 + index * 0.145);
        const top = height * (0.30 + (index % 3) * 0.06);
        const sway = Math.sin(time * 0.30 + index) * width * 0.012;
        return <g key={`pine-${index}`} opacity={0.22 + (index % 2) * 0.08}>
          <path d={`M ${x} ${groundY + height * 0.07} L ${x + sway} ${top} M ${x + sway} ${top + height * 0.10} L ${x - width * 0.06} ${top + height * 0.22} M ${x + sway} ${top + height * 0.16} L ${x + width * 0.06} ${top + height * 0.28}`} stroke={spec.palette[1]} strokeWidth={3 + mids * 2} fill="none" strokeLinecap="round" />
          <path d={`M ${x - width * 0.07} ${top + height * 0.22} Q ${x} ${top + height * 0.13} ${x + width * 0.07} ${top + height * 0.22}`} stroke={spec.palette[2]} strokeWidth={2} fill="none" opacity={0.65} />
        </g>;
      })}
      <path d={`M 0 ${groundY + height * 0.09} Q ${width * 0.25} ${groundY - height * 0.03} ${width * 0.50} ${groundY + height * 0.05} T ${width} ${groundY}`} fill="none" stroke={spec.palette[3]} strokeOpacity={0.30} strokeWidth={3 + bass * 2} />
      {cones.map((cone, index) => <g key={`cone-${index}`} transform={`translate(${cone.x} ${cone.y}) rotate(${cone.rotate})`} opacity={0.52 + highs * 0.26}>
        <path d={`M 0 ${-cone.size} L ${cone.size * 0.72} ${cone.size * 0.64} Q 0 ${cone.size * 1.08} ${-cone.size * 0.72} ${cone.size * 0.64} Z`} fill={spec.palette[index % 2 === 0 ? 2 : 0]} stroke={spec.palette[3]} strokeWidth={1.5} />
        <path d={`M ${-cone.size * 0.38} ${-cone.size * 0.18} L ${cone.size * 0.38} ${-cone.size * 0.18} M ${-cone.size * 0.46} ${cone.size * 0.18} L ${cone.size * 0.46} ${cone.size * 0.18}`} stroke={spec.palette[3]} strokeOpacity={0.55} strokeWidth={1.2} />
      </g>)}
      <g transform={`translate(${squirrelX} ${squirrelY}) scale(${scale})`}>
        <path d={`M ${-width * 0.045} ${height * 0.005} C ${-width * 0.17} ${-height * 0.10} ${-width * 0.16} ${-height * 0.25} ${-width * 0.07} ${-height * 0.21} C ${-width * 0.01} ${-height * 0.18} ${width * 0.005} ${-height * 0.10} ${width * 0.01} ${-height * 0.04}`} fill="none" stroke={spec.palette[0]} strokeWidth={height * 0.045} strokeLinecap="round" opacity={0.82} />
        <ellipse cx={0} cy={0} rx={width * 0.055} ry={height * 0.060} fill={spec.palette[0]} opacity={0.94} />
        <circle cx={width * 0.055} cy={-height * 0.048} r={height * 0.037} fill={spec.palette[2]} stroke={spec.palette[0]} strokeWidth={3} />
        <path d={`M ${width * 0.041} ${-height * 0.078} L ${width * 0.050} ${-height * 0.112} L ${width * 0.068} ${-height * 0.078} M ${width * 0.067} ${-height * 0.073} L ${width * 0.079} ${-height * 0.103} L ${width * 0.091} ${-height * 0.068}`} fill={spec.palette[2]} stroke={spec.palette[0]} strokeWidth={2} />
        <circle cx={width * 0.072} cy={-height * 0.053} r={height * 0.006} fill={spec.background} />
        <path d={`M ${width * 0.074} ${-height * 0.027} Q ${width * 0.098} ${-height * 0.018} ${width * 0.112} ${-height * 0.028}`} fill="none" stroke={spec.palette[3]} strokeWidth={2} strokeLinecap="round" />
        <path d={`M ${-width * 0.018} ${height * 0.040} L ${-width * 0.044} ${height * 0.082} M ${width * 0.024} ${height * 0.040} L ${width * 0.048} ${height * 0.078}`} stroke={spec.palette[0]} strokeWidth={height * 0.014} strokeLinecap="round" />
      </g>
      <g fill={spec.palette[3]} opacity={0.64} fontFamily="ui-monospace,monospace" fontSize={Math.max(14, width * 0.012)} letterSpacing="0.18em">
        <text x={width * 0.07} y={height * 0.10}>PINECONE FREE / {section}</text>
        <text x={width * 0.70} y={height * 0.10}>WANT · NEED · RUN</text>
      </g>
      <text x={width * 0.08} y={height * 0.91} fill={spec.palette[2]} opacity={0.72} fontFamily="Georgia,serif" fontSize={Math.max(22, width * 0.026)}>find the stash / feel the beat / be free</text>
      <path d={`M ${width * 0.07} ${height * 0.94} Q ${width * 0.50} ${height * (0.90 - progress * 0.02)} ${width * 0.93} ${height * 0.94}`} fill="none" stroke={spec.palette[1]} strokeOpacity={0.18 + mids * 0.12} strokeWidth={2} />
    </svg>
  </AbsoluteFill>;
};

export const SignalWorld = (props: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const texturePhase = seeded(props.spec.seed, frame) * props.spec.texture.grain;
  const World = props.spec.world === "meadow" ? Meadow : props.spec.world === "ribbons" ? Ribbons : props.spec.world === "constellation" ? Constellation : Portal;
  return <AbsoluteFill style={{background: props.spec.background}}>
    <World {...props} />
    <AbsoluteFill style={{pointerEvents: "none", opacity: props.spec.texture.scanlines, backgroundImage: "repeating-linear-gradient(0deg,transparent 0,transparent 3px,rgba(0,0,0,.45) 4px)"}} />
    <AbsoluteFill style={{pointerEvents: "none", opacity: texturePhase * 0.34, backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.78' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.8'/%3E%3C/svg%3E\")", mixBlendMode: "soft-light"}} />
    <div style={{position: "absolute", inset: 0, boxShadow: "inset 0 0 180px rgba(0,0,0,.72)"}} />
    {props.spec.motif === "pull-me-in" ? <PullMeInOverlay {...props} /> : null}
    {props.spec.motif === "octopus-ink" ? <OctopusInkOverlay {...props} /> : null}
    {props.spec.motif === "pillow-fight" ? <PillowFightOverlay {...props} /> : null}
    {props.spec.motif === "jamaica-reggae" ? <JamaicaReggaeOverlay {...props} /> : null}
    {props.spec.motif === "paper-score" ? <PaperScoreOverlay {...props} /> : null}
    {props.spec.motif === "rare-signal-atlas" ? <RareSignalAtlasOverlay {...props} /> : null}
    {props.spec.motif === "five-pane-door" ? <FivePaneDoorOverlay {...props} /> : null}
    {props.spec.motif === "magnetic-dust" ? <MagneticDustOverlay {...props} /> : null}
    {props.spec.motif === "cloud-braid" ? <CloudBraidOverlay {...props} /> : null}
    {props.spec.motif === "screenprint-count" ? <ScreenPrintCountOverlay {...props} /> : null}
    {props.spec.motif === "squirrel-pines" ? <SquirrelPinesOverlay {...props} /> : null}
    {props.spec.motif === "cricket-pulse" ? <CricketPulseOverlay {...props} /> : null}
    {props.spec.typography.show ? <div style={{position: "absolute", right: 44, bottom: 32, color: rgba(props.spec.palette[3], 0.45), font: "500 14px ui-monospace,monospace", letterSpacing: "0.18em"}}>{Math.floor(frame / fps).toString().padStart(3, "0")} · {props.spec.seed}</div> : null}
  </AbsoluteFill>;
};

export const TitleTransmission = ({spec}: {spec: VisualSpec}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  if (!spec.typography.show) return null;
  const entrance = interpolate(frame, [0, fps * 0.6, fps * 2.8, fps * 4], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const exit = interpolate(frame, [durationInFrames - fps * 4, durationInFrames - fps * 2.8, durationInFrames - fps * 0.5, durationInFrames], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const opacity = Math.max(entrance, exit);
  const lower = spec.typography.position === "lower-left";
  return <div style={{position: "absolute", left: lower ? 80 : "50%", bottom: lower ? 72 : "50%", transform: lower ? undefined : "translate(-50%, 50%)", width: lower ? "auto" : "100%", textAlign: lower ? "left" : "center", opacity, color: spec.palette[3], textShadow: `0 0 36px ${rgba(spec.palette[0], .65)}`}}>
    <div style={{font: "600 22px ui-monospace,monospace", letterSpacing: ".32em", marginBottom: 18}}>{spec.subtitle}</div>
    <div style={{font: "500 86px Georgia,serif", letterSpacing: "0"}}>{spec.title}</div>
  </div>;
};
