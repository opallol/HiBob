export type VerdictKey = "valid" | "review" | "fp" | "unclear";
export type ModeKey = "pat" | "v" | "kl";

export interface BubbleNode {
  id: string;
  kl: string;
  nm: string;
  pagu: number;
  v: VerdictKey;
  pat: string;
  dev: number;
  peer: number;
}

export interface Manifest {
  generated: string;
  title: string;
  totals: {
    anomaly_nodes: number;
    total_pagu: number;
    kl: number;
    patterns: number;
    verdict: Record<string, number>;
  };
  modes: { key: ModeKey; label: string }[];
  verdicts: { key: VerdictKey; label: string; color: string }[];
  patterns: Record<string, string>;
  kls: Record<string, string>;
  akun: Record<string, string>;
}

export interface MandatItem {
  c: string;
  n: string;
  r: string;
}

export interface NodeDetail {
  kl: string;
  kln: string;
  prog: string;
  keg: string;
  out: string;
  pagu: number;
  dev: number;
  pc: number;
  own: Record<string, number>;
  peer: Record<string, number>;
  v: VerdictKey;
  md: string;
  rs: string;
  mandat: MandatItem[];
}

export interface PipelinePhase {
  id: string;
  label: string;
  icon: string;
  steps: string[];
  metric: string;
}

export interface Pipeline {
  phases: PipelinePhase[];
  counts: Record<string, number>;
}

export interface KGNode {
  id: number;
  t: string;
  c: string;
  nm: string;
  p: string | null;
}
export interface KGData {
  nodes: KGNode[];
  edges: { s: number; t: number; e: string }[];
}
