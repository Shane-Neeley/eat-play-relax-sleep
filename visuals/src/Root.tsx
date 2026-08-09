import React from "react";
import {Composition} from "remotion";
import {AudioReactiveFilm} from "./AudioReactiveFilm";
import type {PromptVisualProps} from "./types";

const defaultProps: PromptVisualProps = {
  audioFile: "media/demo.wav",
  durationInFrames: 300,
  spec: {
    schema: "eprs.visual/v1",
    title: "First Light",
    subtitle: "EAT · PLAY · RELAX · SLEEP",
    prompt: "Neon garage signal blooming before sunrise",
    world: "portal",
    seed: 310,
    palette: ["#ff7657", "#62c6cf", "#f2bd63", "#efe6d8"],
    background: "#090b10",
    motion: {speed: 0.72, feedback: 0.58, rotation: 0.34, turbulence: 0.42},
    reactivity: {bass: 1.2, mids: 0.78, highs: 0.64},
    texture: {grain: 0.18, scanlines: 0.13, bloom: 0.74},
    typography: {show: true, position: "center"},
    avoid: ["faces", "stock footage", "literal equalizer bars"],
  },
};

export const RemotionRoot = () => <Composition
  id="PromptVisual"
  component={AudioReactiveFilm}
  durationInFrames={defaultProps.durationInFrames}
  fps={30}
  width={1920}
  height={1080}
  defaultProps={defaultProps}
  calculateMetadata={({props}) => ({durationInFrames: props.durationInFrames})}
/>;
