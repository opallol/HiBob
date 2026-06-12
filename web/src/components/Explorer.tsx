import { useEffect, useMemo, useState } from "react";
import type { BubbleNode, Manifest, ModeKey, NodeDetail } from "../types";
import { loadDetail, loadAlignNodes, loadAlignDetail } from "../data";
import BubbleCanvas from "./BubbleCanvas";
import AnomalyList from "./AnomalyList";
import DetailCard from "./DetailCard";
import FilterBadge from "./FilterBadge";
import Legend from "./Legend";

interface Props {
  manifest: Manifest;
  nodes: BubbleNode[];
  embed?: boolean;
}

const ALIGN_MODES: { key: ModeKey; label: string }[] = [
  { key: "pat", label: "Jenis anomali" },
];

const SEM_PAT = new Set(["l1", "l2", "l1l2"]);

type CohFilter = "all" | "l3" | "sem";

const COH_FILTERS: { key: CohFilter; label: string }[] = [
  { key: "all", label: "Semua" },
  { key: "l3",  label: "L3 Komposisi Akun" },
  { key: "sem", label: "L1/L2 Semantik" },
];

export default function Explorer({ manifest, nodes, embed }: Props) {
  const [dataset, setDataset]       = useState<"coherence" | "alignment">("alignment");
  const [cohFilter, setCohFilter]   = useState<CohFilter>("all");
  const [alignNodes, setAlignNodes] = useState<BubbleNode[] | null>(null);
  const [alignErr, setAlignErr]     = useState<string | null>(null);

  const [mode, setMode]             = useState<ModeKey>("pat");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail]         = useState<NodeDetail | null>(null);
  const [loading, setLoading]       = useState(false);
  const [focusNonce, setFocusNonce] = useState(0);

  const cohNodes = useMemo(() => {
    if (cohFilter === "l3")  return nodes.filter(n => !SEM_PAT.has(n.pat));
    if (cohFilter === "sem") return nodes.filter(n =>  SEM_PAT.has(n.pat));
    return nodes;
  }, [nodes, cohFilter]);

  const activeNodes = dataset === "coherence" ? cohNodes : (alignNodes ?? []);
  const activeModes = dataset === "coherence" ? undefined : ALIGN_MODES;

  // Lazy-load alignment nodes saat pertama kali tab dipilih
  useEffect(() => {
    if (dataset === "alignment" && !alignNodes && !alignErr) {
      loadAlignNodes()
        .then(setAlignNodes)
        .catch((e) => setAlignErr(String(e)));
    }
  }, [dataset]); // eslint-disable-line react-hooks/exhaustive-deps

  async function select(n: BubbleNode, focus: boolean) {
    setSelectedId(n.id);
    if (focus) setFocusNonce((x) => x + 1);
    setLoading(true);
    setDetail(null);
    const d = dataset === "alignment"
      ? await loadAlignDetail(n.kl, n.id)
      : await loadDetail(n.kl, n.id);
    setDetail(d);
    setLoading(false);
  }

  function handleDataset(ds: "coherence" | "alignment") {
    if (ds === dataset) return;
    setDataset(ds);
    setMode("pat");
    setSelectedId(null);
    setDetail(null);
  }

  function handleCohFilter(f: CohFilter) {
    setCohFilter(f);
    setSelectedId(null);
    setDetail(null);
  }

  useEffect(() => {
    setSelectedId(null);
    setDetail(null);
  }, [mode]);

  const alignCount = manifest.align_totals?.alignment_nodes ?? null;
  const l3Count    = useMemo(() => nodes.filter(n => !SEM_PAT.has(n.pat)).length, [nodes]);
  const semCount   = useMemo(() => nodes.filter(n =>  SEM_PAT.has(n.pat)).length, [nodes]);

  return (
    <div className="flex h-full w-full flex-col">
      {/* Dataset toggle */}
      <div className="flex shrink-0 items-center gap-1 border-b border-ink-800 bg-ink-950 px-3 py-1.5">
        {(["alignment", "coherence"] as const).map((ds) => {
          const isActive = dataset === ds;
          const count    = ds === "coherence" ? nodes.length : (alignNodes?.length ?? alignCount);
          const label    = ds === "coherence" ? "Koherensi Akun" : "Keselarasan RPJMN/RKP";
          return (
            <button
              key={ds}
              onClick={() => handleDataset(ds)}
              className={`rounded-full px-3 py-1 text-[12px] font-medium transition-colors ${
                isActive
                  ? "bg-indigo-700/80 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {label}
              {count !== null && (
                <span className={`ml-1 tabular-nums text-[11px] ${isActive ? "text-indigo-300" : "text-ink-600"}`}>
                  ({count.toLocaleString()})
                </span>
              )}
            </button>
          );
        })}
        {dataset === "alignment" && alignErr && (
          <span className="ml-2 text-[11px] text-red-400">Gagal memuat: {alignErr}</span>
        )}
        {dataset === "alignment" && !alignNodes && !alignErr && (
          <span className="ml-2 text-[11px] text-slate-500">Memuat…</span>
        )}
      </div>

      {/* Sub-filter koherensi: Semua / L3 / Semantik */}
      {dataset === "coherence" && (
        <div className="flex shrink-0 items-center gap-1 border-b border-ink-800/60 bg-ink-950/70 px-3 py-1">
          {COH_FILTERS.map(({ key, label }) => {
            const count = key === "all" ? nodes.length : key === "l3" ? l3Count : semCount;
            const active = cohFilter === key;
            return (
              <button
                key={key}
                onClick={() => handleCohFilter(key)}
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
                  active
                    ? "bg-slate-700/70 text-slate-100"
                    : "text-ink-600 hover:text-slate-400"
                }`}
              >
                {label}
                <span className={`ml-1 tabular-nums ${active ? "text-slate-400" : "text-ink-700"}`}>
                  {count.toLocaleString()}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Canvas + daftar anomali */}
      <div className="flex min-h-0 flex-1">
        <div className="canvas-glow relative flex-1 overflow-hidden">
          <FilterBadge manifest={manifest} mode={mode} onChange={setMode} modes={activeModes} />
          <DetailCard
            detail={detail}
            loading={loading}
            manifest={manifest}
            onClose={() => { setSelectedId(null); setDetail(null); }}
          />
          <Legend manifest={manifest} />
          <BubbleCanvas
            nodes={activeNodes}
            mode={mode}
            manifest={manifest}
            selectedId={selectedId}
            focusNonce={focusNonce}
            onSelect={(n) => select(n, false)}
          />
          {!embed && (
            <div className="absolute bottom-4 right-4 z-10 text-[10px] text-ink-600">
              drag bubble · scroll zoom · klik untuk detail
            </div>
          )}
        </div>
        <AnomalyList
          nodes={activeNodes}
          mode={mode}
          manifest={manifest}
          selectedId={selectedId}
          onSelect={(n) => select(n, true)}
        />
      </div>
    </div>
  );
}
