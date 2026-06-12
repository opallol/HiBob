import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { Pipeline } from "../types";
import { loadPipeline } from "../data";

const ICONS: Record<string, JSX.Element> = {
  "file-text": <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8" />,
  sitemap: <path d="M3 3h6v4H3z M15 3h6v4h-6z M9 17h6v4H9z M6 7v4h12V7 M12 11v6" />,
  "vector-triangle": <path d="M5 4l7 14 7-14z M5 4h14" />,
  "git-compare": <path d="M6 3v12 M18 9v12 M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M18 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6z M9 18h6a3 3 0 0 0 3-3 M15 6H9a3 3 0 0 0-3 3" />,
  "stack-2": <path d="M12 2l9 5-9 5-9-5z M3 12l9 5 9-5 M3 17l9 5 9-5" />,
  "message-2": <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
};

const MODELS = [
  { name: "DeepSeek", scope: "Dokumen publik", note: "OCR cleaning RPJMN/RKP (cloud)", color: "#5b8def" },
  { name: "e5-small", scope: "Data internal DIPA", note: "Embedding lokal — tak keluar jaringan", color: "#46c2c2" },
  { name: "TreasurAI oss120b", scope: "Reasoning internal", note: "Verdict anomali di jaringan Kemenkeu", color: "#b07cf0" },
];

export default function PipelineSection() {
  const [pipe, setPipe] = useState<Pipeline | null>(null);
  useEffect(() => {
    loadPipeline().then(setPipe).catch(() => {});
  }, []);
  if (!pipe) return <div className="p-10 text-slate-500">Memuat alur…</div>;

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-10"
      >
        <h2 className="text-2xl font-semibold text-slate-100">Bagaimana anomali ini ditemukan</h2>
        <p className="mt-2 text-[15px] leading-relaxed text-slate-400">
          Enam fase dari dokumen kebijakan mentah hingga reasoning tiap anomali — dengan arsitektur tiga model yang
          menjaga data DIPA internal tidak pernah keluar jaringan.
        </p>
      </motion.div>

      <div className="mb-12 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {MODELS.map((m, i) => (
          <motion.div
            key={m.name}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.08 }}
            className="rounded-xl border border-ink-800 bg-ink-900/60 p-4"
          >
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: m.color }} />
              <span className="text-[14px] font-medium text-slate-100">{m.name}</span>
            </div>
            <div className="mt-1 text-[11px] uppercase tracking-wide text-ink-600">{m.scope}</div>
            <div className="mt-1.5 text-[12px] leading-snug text-slate-400">{m.note}</div>
          </motion.div>
        ))}
      </div>

      <div className="relative">
        <div className="absolute left-[19px] top-2 bottom-2 w-px bg-ink-800" />
        <div className="space-y-4">
          {pipe.phases.map((ph, i) => (
            <motion.div
              key={ph.id}
              initial={{ opacity: 0, x: -10 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="relative flex gap-4"
            >
              <div className="z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-ink-700 bg-ink-850 text-slate-300">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                  {ICONS[ph.icon]}
                </svg>
              </div>
              <div className="flex-1 rounded-xl border border-ink-800 bg-ink-900/50 px-4 py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="text-[15px] font-medium text-slate-100">
                    <span className="text-ink-600 mr-2 tabular-nums">{i + 1}</span>
                    {ph.label}
                  </h3>
                  <span className="text-[12px] tabular-nums text-emerald-400/90">{ph.metric}</span>
                </div>
                <ul className="mt-1.5 space-y-0.5">
                  {ph.steps.map((s) => (
                    <li key={s} className="text-[12px] text-slate-400">
                      <span className="text-ink-600 mr-1.5">›</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
