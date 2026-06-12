import type { VerdictKey } from "./types";

export const VERDICT_COLOR: Record<VerdictKey, string> = {
  valid: "#f04747",
  review: "#f6a821",
  fp: "#28c76f",
  unclear: "#7a8aa8",
};

export const VERDICT_LABEL: Record<VerdictKey, string> = {
  valid: "Anomali valid",
  review: "Perlu review",
  fp: "False positive",
  unclear: "Belum jelas",
};

// urutan kepentingan: valid (fokus) → review → fp → unclear
export const VERDICT_ORDER: VerdictKey[] = ["valid", "review", "fp", "unclear"];

// warna aksen lembut per cluster (untuk benang & label hub) — bukan untuk bubble
export const CLUSTER_ACCENT = [
  "#5b8def",
  "#46c2c2",
  "#b07cf0",
  "#e8915b",
  "#d96b9a",
  "#7ec06a",
  "#e0c356",
  "#6a78d0",
  "#cd6f6f",
  "#4fb3a0",
];

export function rupiahT(v: number): string {
  const t = v / 1e12;
  if (t >= 1) return `Rp ${t.toFixed(2)} T`;
  const m = v / 1e9;
  return `Rp ${m.toFixed(1)} M`;
}

export function rupiahShort(v: number): string {
  const t = v / 1e12;
  if (t >= 1) return `${t.toFixed(1)}T`;
  return `${(v / 1e9).toFixed(0)}M`;
}
