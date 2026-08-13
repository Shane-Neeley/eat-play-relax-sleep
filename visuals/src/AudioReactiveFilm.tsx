import React from "react";
import {Audio} from "@remotion/media";
import {useAudioData, visualizeAudio} from "@remotion/media-utils";
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {SignalWorld, TitleTransmission} from "./SignalWorld";
import {normalizeSpec, type NaturalHistoryPhotograph, type PromptVisualProps} from "./types";

const NaturalHistoryLayer = ({photographs}: {photographs: NaturalHistoryPhotograph[]}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  if (!photographs.length) return null;
  const segment = durationInFrames / photographs.length;
  const activeIndex = Math.min(photographs.length - 1, Math.floor(frame / Math.max(1, segment)));
  return <AbsoluteFill style={{pointerEvents: "none", overflow: "hidden"}}>
    {photographs.map((photo, index) => {
      const start = index * segment;
      const end = (index + 1) * segment;
      const fade = Math.min(24, segment * 0.16);
      const opacity = interpolate(
        frame,
        [start - fade, start, Math.max(start, end - fade), end],
        [0, photo.opacity, photo.opacity, 0],
        {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
      );
      const travel = interpolate(frame, [start, end], [-1.8, 1.8], {
        extrapolateLeft: "clamp", extrapolateRight: "clamp",
      });
      return <Img
        key={`${photo.file}-${index}`}
        src={staticFile(photo.file)}
        style={{
          position: "absolute",
          inset: -Math.max(width, height) * 0.025,
          width: "105%",
          height: "105%",
          objectFit: "cover",
          opacity,
          mixBlendMode: photo.treatment,
          filter: "saturate(.82) contrast(1.08)",
          transform: `translate3d(${travel}%, ${-travel * 0.35}%, 0) scale(1.035)`,
        }}
      />;
    })}
    {photographs[activeIndex] ? <div style={{
      position: "absolute",
      left: 34,
      bottom: 28,
      maxWidth: "68%",
      padding: "8px 11px",
      color: "rgba(255,255,255,.72)",
      background: "rgba(0,0,0,.48)",
      font: "500 12px ui-monospace,monospace",
      letterSpacing: ".035em",
    }}>
      {photographs[activeIndex].label} · {photographs[activeIndex].attribution} · iNaturalist · {photographs[activeIndex].licenseCode}
    </div> : null}
  </AbsoluteFill>;
};

export const AudioReactiveFilm = ({audioFile, spec: candidate}: PromptVisualProps) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const spec = normalizeSpec(candidate);
  const audioSource = staticFile(audioFile);
  const audioData = useAudioData(audioSource, {sampleRate: 48_000});
  const spectrum = audioData ? visualizeAudio({audioData, frame, fps, numberOfSamples: 32, smoothing: true, optimizeFor: "accuracy"}) : new Array(32).fill(0);
  return <AbsoluteFill style={{background: spec.background}}>
    <Audio src={audioSource} />
    <SignalWorld spec={spec} spectrum={spectrum} />
    <NaturalHistoryLayer photographs={spec.photographs || []} />
    <TitleTransmission spec={spec} />
  </AbsoluteFill>;
};
