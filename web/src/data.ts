import type { Manifest, BubbleNode, NodeDetail, Pipeline, KGData } from "./types";

const BASE = import.meta.env.BASE_URL; // "./" saat build, "/" saat dev

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}data/${path}`);
  if (!res.ok) throw new Error(`Gagal memuat ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const loadManifest    = () => getJSON<Manifest>("manifest.json");
export const loadNodes       = () => getJSON<BubbleNode[]>("coherence/nodes.json");
export const loadAlignNodes  = () => getJSON<BubbleNode[]>("alignment/nodes.json");
export const loadPipeline    = () => getJSON<Pipeline>("pipeline.json");
export const loadKG          = () => getJSON<KGData>("knowledge_graph.json");

// cache detail koherensi per K/L
const detailCache = new Map<string, Record<string, NodeDetail>>();

export async function loadDetail(kl: string, id: string): Promise<NodeDetail | null> {
  if (!detailCache.has(kl)) {
    try {
      const data = await getJSON<Record<string, NodeDetail>>(`coherence/details/${kl}.json`);
      detailCache.set(kl, data);
    } catch {
      return null;
    }
  }
  return detailCache.get(kl)?.[id] ?? null;
}

// cache detail alignment per K/L
const alignDetailCache = new Map<string, Record<string, NodeDetail>>();

export async function loadAlignDetail(kl: string, id: string): Promise<NodeDetail | null> {
  if (!alignDetailCache.has(kl)) {
    try {
      const data = await getJSON<Record<string, NodeDetail>>(`alignment/details/${kl}.json`);
      alignDetailCache.set(kl, data);
    } catch {
      return null;
    }
  }
  return alignDetailCache.get(kl)?.[id] ?? null;
}
