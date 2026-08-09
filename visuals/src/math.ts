export const clamp = (value: number, low = 0, high = 1) =>
  Math.max(low, Math.min(high, value));

export const mean = (values: number[]) =>
  values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;

export const seeded = (seed: number, index: number) => {
  const value = Math.sin(seed * 19.19 + index * 91.77) * 43758.5453123;
  return value - Math.floor(value);
};

export const rgba = (hex: string, alpha: number) => {
  const value = hex.replace("#", "");
  const normalized = value.length === 3
    ? value.split("").map((part) => part + part).join("") : value;
  const parsed = Number.parseInt(normalized, 16);
  const red = (parsed >> 16) & 255;
  const green = (parsed >> 8) & 255;
  const blue = parsed & 255;
  return `rgba(${red},${green},${blue},${alpha})`;
};
