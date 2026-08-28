export type VisualWorld = "portal" | "ribbons" | "constellation" | "meadow";

const VISUAL_MOTIFS = [
  "octopus-ink", "pillow-fight", "pull-me-in", "jamaica-reggae",
  "paper-score", "rare-signal-atlas", "five-pane-door", "magnetic-dust", "cloud-braid",
  "screenprint-count", "squirrel-pines", "cricket-pulse",
] as const;

export type VisualMotif = typeof VISUAL_MOTIFS[number];

export type AtlasCard = {
  label: string;
  region: string;
  note: string;
  accent?: string;
};

export type NaturalHistoryPhotograph = {
  file: string;
  opacity: number;
  treatment: "soft-light" | "screen" | "normal";
  attribution: string;
  licenseCode: string;
  sourceUrl: string;
  label: string;
};

export type VisualSpec = {
  schema: "eprs.visual/v1";
  title: string;
  subtitle: string;
  prompt: string;
  world: VisualWorld;
  motif?: VisualMotif;
  cards?: AtlasCard[];
  photographs?: NaturalHistoryPhotograph[];
  seed: number;
  palette: [string, string, string, string];
  background: string;
  motion: {
    speed: number;
    feedback: number;
    rotation: number;
    turbulence: number;
  };
  reactivity: {
    bass: number;
    mids: number;
    highs: number;
  };
  texture: {
    grain: number;
    scanlines: number;
    bloom: number;
  };
  typography: {
    show: boolean;
    position: "center" | "lower-left";
  };
  avoid: string[];
};

export type PromptVisualProps = {
  audioFile: string;
  durationInFrames: number;
  spec: VisualSpec;
};

const numberIn = (value: unknown, fallback: number, low = 0, high = 2) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.max(low, Math.min(high, value))
    : fallback;

export const normalizeSpec = (candidate: Partial<VisualSpec>): VisualSpec => {
  const palette: [string, string, string, string] = Array.isArray(candidate.palette) && candidate.palette.length >= 4
    ? candidate.palette.slice(0, 4) as [string, string, string, string]
    : ["#ff7657", "#62c6cf", "#f2bd63", "#efe6d8"];
  return {
    schema: "eprs.visual/v1",
    title: candidate.title || "Untitled Signal",
    subtitle: candidate.subtitle || "EAT · PLAY · RELAX · SLEEP",
    prompt: candidate.prompt || "A patient signal growing in a dark room",
    world: ["portal", "ribbons", "constellation", "meadow"].includes(candidate.world || "")
      ? candidate.world as VisualWorld : "portal",
    motif: VISUAL_MOTIFS.includes(candidate.motif as VisualMotif)
      ? candidate.motif as VisualMotif
      : undefined,
    cards: Array.isArray(candidate.cards)
      ? candidate.cards.filter((card): card is AtlasCard => Boolean(card && typeof card.label === "string" && typeof card.region === "string" && typeof card.note === "string")).slice(0, 8)
      : undefined,
    photographs: Array.isArray(candidate.photographs)
      ? candidate.photographs.filter((photo): photo is NaturalHistoryPhotograph => Boolean(
        photo
        && typeof photo.file === "string"
        && typeof photo.attribution === "string"
        && typeof photo.licenseCode === "string"
        && typeof photo.sourceUrl === "string"
        && typeof photo.label === "string"
      )).slice(0, 4).map((photo) => ({
        ...photo,
        opacity: numberIn(photo.opacity, 0.34, 0.05, 0.85),
        treatment: ["soft-light", "screen", "normal"].includes(photo.treatment)
          ? photo.treatment
          : "soft-light",
      }))
      : undefined,
    seed: Number.isInteger(candidate.seed) ? candidate.seed as number : 1,
    palette,
    background: candidate.background || "#090b10",
    motion: {
      speed: numberIn(candidate.motion?.speed, 0.7),
      feedback: numberIn(candidate.motion?.feedback, 0.55, 0, 1),
      rotation: numberIn(candidate.motion?.rotation, 0.35, -2, 2),
      turbulence: numberIn(candidate.motion?.turbulence, 0.45, 0, 1),
    },
    reactivity: {
      bass: numberIn(candidate.reactivity?.bass, 1.15),
      mids: numberIn(candidate.reactivity?.mids, 0.8),
      highs: numberIn(candidate.reactivity?.highs, 0.65),
    },
    texture: {
      grain: numberIn(candidate.texture?.grain, 0.16, 0, 1),
      scanlines: numberIn(candidate.texture?.scanlines, 0.12, 0, 1),
      bloom: numberIn(candidate.texture?.bloom, 0.72, 0, 1.5),
    },
    typography: {
      show: candidate.typography?.show ?? true,
      position: candidate.typography?.position === "lower-left" ? "lower-left" : "center",
    },
    avoid: candidate.avoid || ["faces", "stock footage", "literal equalizer bars"],
  };
};
