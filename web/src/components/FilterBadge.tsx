import type { Manifest, ModeKey } from "../types";

interface Props {
  manifest: Manifest;
  mode: ModeKey;
  onChange: (m: ModeKey) => void;
}

export default function FilterBadge({ manifest, mode, onChange }: Props) {
  const active = manifest.modes.find((m) => m.key === mode);
  return (
    <div className="absolute top-4 left-4 z-20">
      <div className="flex items-center gap-2.5 rounded-xl border border-ink-700 bg-ink-900/90 backdrop-blur px-3 py-2 shadow-lg">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-ink-800 text-slate-300">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 6h16M7 12h10M10 18h4" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <div className="text-[9px] uppercase tracking-wider text-ink-600">cluster mengikuti</div>
          <select
            value={mode}
            onChange={(e) => onChange(e.target.value as ModeKey)}
            className="bg-transparent text-[13px] font-medium text-slate-100 outline-none cursor-pointer -ml-0.5"
          >
            {manifest.modes.map((m) => (
              <option key={m.key} value={m.key} className="bg-ink-850 text-slate-100">
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {active && (
        <div className="mt-1 ml-1 text-[10px] text-ink-600">
          warna = status anomali · ukuran = pagu
        </div>
      )}
    </div>
  );
}
