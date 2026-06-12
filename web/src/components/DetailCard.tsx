import { AnimatePresence, motion } from "framer-motion";
import type { NodeDetail, Manifest, VerdictKey } from "../types";
import { VERDICT_COLOR, VERDICT_LABEL, rupiahT } from "../theme";

interface Props {
  detail: NodeDetail | null;
  loading: boolean;
  manifest: Manifest;
  onClose: () => void;
}

function CompBars({ detail, akun }: { detail: NodeDetail; akun: Record<string, string> }) {
  const keys = [...new Set([...Object.keys(detail.own), ...Object.keys(detail.peer)])].sort();
  return (
    <div className="space-y-2">
      {keys.map((k) => {
        const own = (detail.own[k] ?? 0) * 100;
        const peer = (detail.peer[k] ?? 0) * 100;
        return (
          <div key={k}>
            <div className="flex justify-between text-[11px] text-ink-600/90 mb-1">
              <span className="text-slate-300">{akun[k] ?? `Akun ${k}`}</span>
              <span className="tabular-nums text-slate-400">
                {own.toFixed(0)}% <span className="text-ink-600">vs peer {peer.toFixed(0)}%</span>
              </span>
            </div>
            <div className="relative h-2 rounded-full bg-ink-800 overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 rounded-full"
                style={{ width: `${Math.min(100, own)}%`, background: "#5b8def" }}
              />
              <div
                className="absolute inset-y-0 w-[2px] bg-white/80"
                style={{ left: `${Math.min(100, peer)}%` }}
                title={`rata-rata peer ${peer.toFixed(0)}%`}
              />
            </div>
          </div>
        );
      })}
      <div className="text-[10px] text-ink-600">garis putih = rata-rata peer</div>
    </div>
  );
}

export default function DetailCard({ detail, loading, manifest, onClose }: Props) {
  return (
    <AnimatePresence>
      {(detail || loading) && (
        <motion.div
          initial={{ opacity: 0, y: -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.98 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
          className="scroll-thin absolute top-[72px] left-4 w-[300px] max-h-[calc(100%-92px)] overflow-y-auto z-20 rounded-xl border border-ink-700 bg-ink-900/95 backdrop-blur shadow-2xl"
          style={{ borderColor: detail ? `${VERDICT_COLOR[detail.v as VerdictKey]}66` : undefined }}
        >
          {loading && !detail ? (
            <div className="p-4 text-sm text-slate-400">Memuat detail…</div>
          ) : detail ? (
            <div className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-[15px] font-medium text-slate-100 leading-tight">
                    {detail.kl} · {detail.kln}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-0.5">{detail.out}</div>
                </div>
                <button onClick={onClose} aria-label="tutup" className="text-slate-500 hover:text-slate-200 text-lg leading-none">
                  ×
                </button>
              </div>

              {(() => {
                const isAlign = detail.dataset === "alignment";
                const isSem   = detail.nature === "l1" || detail.nature === "l2" || detail.nature === "l1l2";
                const semScore = isSem
                  ? Math.min(detail.own["l1"] ?? 100, detail.own["l2"] ?? 100)
                  : 0;
                const stats = isAlign
                  ? [
                      { v: `${(detail.own["skor"] ?? 0).toFixed(0)}/100`, l: "keselarasan" },
                      { v: rupiahT(detail.pagu).replace("Rp ", ""), l: "pagu" },
                      { v: `${detail.dev.toFixed(0)}`, l: "skor anomali" },
                    ]
                  : isSem
                  ? [
                      { v: `${semScore.toFixed(0)}/100`, l: "koherensi" },
                      { v: rupiahT(detail.pagu).replace("Rp ", ""), l: "pagu" },
                      { v: (detail.nature ?? "").toUpperCase(), l: "level" },
                    ]
                  : [
                      { v: `${detail.dev.toFixed(0)}%`, l: "deviasi" },
                      { v: rupiahT(detail.pagu).replace("Rp ", ""), l: "pagu" },
                      { v: String(detail.pc), l: "peer" },
                    ];
                return (
                  <div className="grid grid-cols-3 gap-1.5 mt-3">
                    {stats.map((s) => (
                      <div key={s.l} className="rounded-lg bg-ink-800 px-1 py-2 text-center">
                        <div className="text-[13px] font-medium text-slate-100 tabular-nums">{s.v}</div>
                        <div className="text-[9px] text-ink-600 uppercase tracking-wide">{s.l}</div>
                      </div>
                    ))}
                  </div>
                );
              })()}

              <div className="mt-3 flex items-center gap-2">
                <span
                  className="text-[11px] font-medium px-2.5 py-0.5 rounded-full"
                  style={{ background: `${VERDICT_COLOR[detail.v]}22`, color: VERDICT_COLOR[detail.v] }}
                >
                  {VERDICT_LABEL[detail.v]}
                </span>
                <span className="text-[10px] text-ink-600">model {detail.md}</span>
              </div>

              {detail.nature && detail.dataset === "alignment" && (
                <div className="mt-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-ink-800 text-slate-400">
                    {detail.nature === "policy_orphan" ? "policy orphan" : detail.nature.replace("_", " ")}
                  </span>
                </div>
              )}

              <p className="mt-3 text-[12px] leading-relaxed text-slate-300">{detail.rs}</p>

              {detail.dataset !== "alignment" && detail.nature !== "l1" && detail.nature !== "l2" && detail.nature !== "l1l2" && (
                <div className="mt-4">
                  <div className="text-[11px] text-slate-400 mb-2">Komposisi akun</div>
                  <CompBars detail={detail} akun={manifest.akun} />
                </div>
              )}

              {detail.mandat.length > 0 && (
                <div className="mt-4">
                  <div className="text-[11px] text-slate-400 mb-1.5">
                    {detail.dataset === "alignment" ? "KP RPJMN/RKP terdekat" : "Mandat RPJMN/RKP terkait"}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {detail.mandat.slice(0, 5).map((mn) => (
                      <span
                        key={mn.c}
                        className="text-[10px] text-slate-300 bg-ink-800 rounded-full px-2 py-0.5"
                        title={mn.n}
                      >
                        {detail.dataset === "alignment" ? `${mn.c} (${mn.r})` : `KP ${mn.c}`}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
