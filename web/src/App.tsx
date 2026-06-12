import { useEffect, useState } from "react";
import type { BubbleNode, Manifest } from "./types";
import { loadManifest, loadNodes } from "./data";
import Header from "./components/Header";
import Explorer from "./components/Explorer";
import PipelineSection from "./components/PipelineSection";

// mode embed: ?embed=1 → tanpa header (untuk iframe di web rekan)
// ?view=pipeline → buka langsung ke seksi alur
const params = new URLSearchParams(window.location.search);
const isEmbed = params.get("embed") === "1";
const initialView = params.get("view") === "pipeline" ? "pipeline" : "map";

export default function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [nodes, setNodes] = useState<BubbleNode[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [view, setView] = useState<"map" | "pipeline">(initialView);

  useEffect(() => {
    Promise.all([loadManifest(), loadNodes()])
      .then(([m, n]) => {
        setManifest(m);
        setNodes(n);
      })
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-slate-400">
        <div>
          <div className="text-slate-200">Gagal memuat data</div>
          <div className="mt-1 text-[12px] text-ink-600">{err}</div>
        </div>
      </div>
    );
  }

  if (!manifest || !nodes) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-ink-700 border-t-indigo-400" />
          <span className="text-[13px]">Memuat peta anomali…</span>
        </div>
      </div>
    );
  }

  if (isEmbed) {
    return (
      <div className="h-full w-full">
        {view === "pipeline" ? (
          <div className="scroll-thin h-full overflow-y-auto">
            <PipelineSection />
          </div>
        ) : (
          <Explorer manifest={manifest} nodes={nodes} embed />
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col">
      <Header manifest={manifest} view={view} onView={setView} />
      <main className="min-h-0 flex-1 overflow-hidden">
        {view === "map" ? (
          <Explorer manifest={manifest} nodes={nodes} />
        ) : (
          <div className="scroll-thin h-full overflow-y-auto">
            <PipelineSection />
          </div>
        )}
      </main>
    </div>
  );
}
