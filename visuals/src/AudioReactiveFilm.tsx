import React from "react";
import {Audio} from "@remotion/media";
import {useAudioData, visualizeAudio} from "@remotion/media-utils";
import {AbsoluteFill, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {SignalWorld, TitleTransmission} from "./SignalWorld";
import {normalizeSpec, type PromptVisualProps} from "./types";

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
    <TitleTransmission spec={spec} />
  </AbsoluteFill>;
};
