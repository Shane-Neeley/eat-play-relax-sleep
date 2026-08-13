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

export const SignalWorld = (props: Props) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const texturePhase = seeded(props.spec.seed, frame) * props.spec.texture.grain;
  const World = props.spec.world === "ribbons" ? Ribbons : props.spec.world === "constellation" ? Constellation : Portal;
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
