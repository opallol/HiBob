import { useMemo, useState } from "react";
import type { BubbleNode, Manifest, ModeKey } from "../types";
import { VERDICT_COLOR, rupiahShort, CLUSTER_ACCENT } from "../theme";

interface Props {
  nodes: BubbleNode[];
  mode: ModeKey;
  manifest: Manifest;
  selectedId: string | null;
  onSelect: (n: BubbleNode) => void;
}

function keyOf(n: BubbleNode, mode: ModeKey): string {
  if (mode === "v") return n.v;
  if (mode === "kl") return n.kl;
  return n.pat;
}
function labelOf(key: string, mode: ModeKey, m: Manifest): string {
  if (mode === "v") return m.verdicts.find((x) => x.key === key)?.label ?? key;
  if (mode === "kl") return `${key} ${m.kls[key] ?? ""}`.trim();
  return m.patterns[key] ?? key;
}

export default function AnomalyList({ nodes, mode, manifest, selectedId, onSelect }: Props) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const groups = useMemo(() => {
    const map = new Map<string, BubbleNode[]>();
    for (const n of nodes) {
      const k = keyOf(n, mode);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(n);
    }
    const arr = [...map.entries()].map(([k, list]) => ({
      key: k,
      list: list.sort((a, b) => b.pagu - a.pagu),
      pagu: list.reduce((s, n) => s + n.pagu, 0),
    }));
    arr.sort((a, b) => b.pagu - a.pagu);
    return arr;
  }, [nodes, mode]);

  const totalPagu = manifest.totals.total_pagu;

  const query = q.trim().toLowerCase();
  const searchHits = useMemo(() => {
    if (!query) return null;
    return nodes
      .filter(
        (n) =>
          n.id.toLowerCase().includes(query) ||
          n.nm.toLowerCase().includes(query) ||
          (manifest.kls[n.kl] ?? "").toLowerCase().includes(query)
      )
      .sort((a, b) => b.pagu - a.pagu)
      .slice(0, 80);
  }, [query, nodes, manifest]);

  const Row = ({ n, rank }: { n: BubbleNode; rank?: number }) => (
    <button
      onClick={() => onSelect(n)}
      className={`flex w-full items-center gap-2 px-3 py-1.5 text-left transition-colors ${
        selectedId === n.id ? "bg-ink-700/70" : "hover:bg-ink-800/60"
      }`}
    >
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: VERDICT_COLOR[n.v] }} />
      {rank !== undefined && <span className="text-[10px] text-ink-600 tabular-nums w-5">#{rank}</span>}
      <span className="flex-1 truncate text-[12px] text-slate-200">
        {n.kl} {manifest.kls[n.kl]?.split(" ").slice(0, 2).join(" ") ?? ""} · {n.nm.split("·")[1]?.trim() ?? n.nm}
      </span>
      <span className="text-[11px] tabular-nums text-slate-400">{rupiahShort(n.pagu)}</span>
    </button>
  );

  return (
    <div className="flex h-full w-[300px] shrink-0 flex-col border-l border-ink-800 bg-ink-900/80">
      <div className="px-3.5 pt-3.5 pb-2">
        <div className="flex items-center justify-between">
          <h2 className="text-[14px] font-medium text-slate-100">Daftar anomali</h2>
          <span className="text-[11px] text-ink-600 tabular-nums">{nodes.length}</span>
        </div>
        <div className="mt-2 flex items-center gap-2 rounded-lg bg-ink-800 px-2.5 py-1.5">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#6b7799" strokeWidth="2">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4-4" strokeLinecap="round" />
          </svg>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="cari K/L atau output…"
            className="w-full bg-transparent text-[12px] text-slate-200 placeholder:text-ink-600 outline-none"
          />
        </div>
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto pb-4">
        {searchHits ? (
          <div>
            <div className="px-3.5 py-1.5 text-[10px] uppercase tracking-wider text-ink-600">
              {searchHits.length} hasil
            </div>
            {searchHits.map((n, i) => (
              <Row key={n.id} n={n} rank={i + 1} />
            ))}
          </div>
        ) : (
          groups.map((g, gi) => {
            const isOpen = open.has(g.key);
            const accent = CLUSTER_ACCENT[gi % CLUSTER_ACCENT.length];
            return (
              <div key={g.key}>
                <button
                  onClick={() =>
                    setOpen((s) => {
                      const ns = new Set(s);
                      ns.has(g.key) ? ns.delete(g.key) : ns.add(g.key);
                      return ns;
                    })
                  }
                  className="flex w-full items-center gap-2 px-3.5 py-2 text-left hover:bg-ink-800/40"
                >
                  <span className="h-2 w-2 rounded-full" style={{ background: accent }} />
                  <span className="flex-1 truncate text-[12px] text-slate-200">{labelOf(g.key, mode, manifest)}</span>
                  <span className="text-[10px] text-ink-600 tabular-nums">{g.list.length}</span>
                  <span className="text-[11px] tabular-nums" style={{ color: accent }}>
                    {((g.pagu / totalPagu) * 100).toFixed(0)}%
                  </span>
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="#6b7799"
                    strokeWidth="2"
                    className={`transition-transform ${isOpen ? "rotate-180" : ""}`}
                  >
                    <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                {isOpen &&
                  g.list.map((n, i) => <Row key={n.id} n={n} rank={i + 1} />)}
              </div>
            );
          })
        )}
      </div>

      <div className="border-t border-ink-800 px-3.5 py-2 text-[10px] text-ink-600">
        {groups.length} cluster · total {rupiahShort(totalPagu)}
      </div>
    </div>
  );
}
