import type { Manifest, BubbleNode, NodeDetail, Pipeline, KGData } from "./types";

const BASE = import.meta.env.BASE_URL; // "./" saat build, "/" saat dev

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}data/${path}`);
  if (!res.ok) throw new Error(`Gagal memuat ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

export const loadManifest = () => getJSON<Manifest>("manifest.json");
export const loadNodes = () => getJSON<BubbleNode[]>("coherence/nodes.json");
export const loadPipeline = () => getJSON<Pipeline>("pipeline.json");
export const loadKG = () => getJSON<KGData>("knowledge_graph.json");

// cache detail per K/L agar tidak fetch berulang
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
