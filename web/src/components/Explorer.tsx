import { useEffect, useState } from "react";
import type { BubbleNode, Manifest, ModeKey, NodeDetail } from "../types";
import { loadDetail } from "../data";
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

export default function Explorer({ manifest, nodes, embed }: Props) {
  const [mode, setMode] = useState<ModeKey>("pat");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [focusNonce, setFocusNonce] = useState(0);

  async function select(n: BubbleNode, focus: boolean) {
    setSelectedId(n.id);
    if (focus) setFocusNonce((x) => x + 1);
    setLoading(true);
    setDetail(null);
    const d = await loadDetail(n.kl, n.id);
    setDetail(d);
    setLoading(false);
  }

  useEffect(() => {
    setSelectedId(null);
    setDetail(null);
  }, [mode]);

  return (
    <div className="flex h-full w-full">
      <div className="canvas-glow relative flex-1 overflow-hidden">
        <FilterBadge manifest={manifest} mode={mode} onChange={setMode} />
        <DetailCard detail={detail} loading={loading} manifest={manifest} onClose={() => { setSelectedId(null); setDetail(null); }} />
        <Legend manifest={manifest} />
        <BubbleCanvas
          nodes={nodes}
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
        nodes={nodes}
        mode={mode}
        manifest={manifest}
        selectedId={selectedId}
        onSelect={(n) => select(n, true)}
      />
    </div>
  );
}
