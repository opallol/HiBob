import type { Manifest } from "../types";
import { rupiahT } from "../theme";

interface Props {
  manifest: Manifest;
  view: "map" | "pipeline";
  onView: (v: "map" | "pipeline") => void;
  activeDataset: "coherence" | "alignment";
}

export default function Header({ manifest, view, onView, activeDataset }: Props) {
  return (
    <header className="flex shrink-0 items-center justify-between border-b border-ink-800 bg-ink-900/80 px-5 py-3 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-sm font-semibold tracking-tight text-white">
          SN
        </div>
        <div>
          <div className="flex items-baseline gap-2 leading-tight">
            <span className="text-[15px] font-semibold tracking-tight text-slate-100">SENTINEL</span>
            <span className="hidden text-[10px] text-ink-600 sm:inline">
              Spending Intelligence for National Alignment Review
            </span>
          </div>
          <div className="text-[11px] text-ink-600">
            {activeDataset === "alignment"
              ? `${(manifest.align_totals?.alignment_nodes ?? 0).toLocaleString()} anomali · ${rupiahT(manifest.align_totals?.total_pagu ?? 0)} · ${manifest.align_totals?.kl ?? "—"} K/L`
              : `${manifest.totals.anomaly_nodes.toLocaleString()} anomali · ${rupiahT(manifest.totals.total_pagu)} · ${manifest.totals.kl} K/L`
            }
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1 rounded-lg border border-ink-800 bg-ink-850 p-0.5">
        {([
          { k: "map", label: "Peta anomali" },
          { k: "pipeline", label: "Alur pipeline" },
        ] as const).map((t) => (
          <button
            key={t.k}
            onClick={() => onView(t.k)}
            className={`rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${
              view === t.k ? "bg-ink-700 text-slate-100" : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </header>
  );
}
