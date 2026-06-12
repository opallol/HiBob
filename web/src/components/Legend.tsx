import type { Manifest } from "../types";
import { VERDICT_COLOR, VERDICT_LABEL, VERDICT_ORDER } from "../theme";

export default function Legend({ manifest }: { manifest: Manifest }) {
  const counts = manifest.totals.verdict;
  return (
    <div className="absolute bottom-4 left-4 z-20 rounded-xl border border-ink-700 bg-ink-900/85 backdrop-blur px-3.5 py-2.5 shadow-lg">
      <div className="text-[10px] uppercase tracking-wider text-ink-600 mb-1.5">status anomali</div>
      <div className="flex flex-col gap-1.5">
        {VERDICT_ORDER.map((k) => (
          <div key={k} className="flex items-center gap-2 text-[11px]">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: VERDICT_COLOR[k] }} />
            <span className="text-slate-300">{VERDICT_LABEL[k]}</span>
            <span className="text-ink-600 tabular-nums ml-auto">{counts[k] ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
