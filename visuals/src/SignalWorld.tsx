import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {mean, rgba, seeded} from "./math";
import type {VisualSpec} from "./types";

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
    <div style={{font: "500 86px Georgia,serif", letterSpacing: "-.04em"}}>{spec.title}</div>
  </div>;
};
