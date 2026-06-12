import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { BubbleNode, Manifest, ModeKey } from "../types";
import { VERDICT_COLOR, CLUSTER_ACCENT } from "../theme";

interface Props {
  nodes: BubbleNode[];
  mode: ModeKey;
  manifest: Manifest;
  selectedId: string | null;
  focusNonce: number;
  onSelect: (n: BubbleNode) => void;
}

interface GNode {
  id: string;
  hub?: boolean;
  cluster: string;
  label: string;
  r: number;
  color: string;
  accent: string;
  data?: BubbleNode;
  count?: number;
  fx?: number;
  fy?: number;
  x?: number;
  y?: number;
}

function clusterKey(n: BubbleNode, mode: ModeKey): string {
  if (mode === "v") return n.v;
  if (mode === "kl") return n.kl;
  return n.pat;
}

function clusterLabel(key: string, mode: ModeKey, m: Manifest): string {
  if (mode === "v") return m.verdicts.find((x) => x.key === key)?.label ?? key;
  if (mode === "kl") return `${key} ${m.kls[key] ?? ""}`.trim();
  return m.patterns[key] ?? key;
}

function useElementSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}

export default function BubbleCanvas({ nodes, mode, manifest, selectedId, focusNonce, onSelect }: Props) {
  const { ref, size } = useElementSize();
  const fgRef = useRef<any>(null);

  const maxP = useMemo(() => Math.max(1, ...nodes.map((n) => n.pagu)), [nodes]);
  const rOf = (p: number) => 4 + 34 * Math.pow(p / maxP, 0.4);

  const graph = useMemo(() => {
    const groups = new Map<string, BubbleNode[]>();
    for (const n of nodes) {
      const k = clusterKey(n, mode);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(n);
    }
    const keys = [...groups.keys()].sort((a, b) => groups.get(b)!.length - groups.get(a)!.length);

    const cols = Math.ceil(Math.sqrt(keys.length));
    const spacing = 380;
    const accentOf = new Map<string, string>();

    const gnodes: GNode[] = [];
    const glinks: { source: string; target: string; accent: string }[] = [];

    keys.forEach((k, i) => {
      const accent = CLUSTER_ACCENT[i % CLUSTER_ACCENT.length];
      accentOf.set(k, accent);
      const col = i % cols;
      const row = Math.floor(i / cols);
      const cx = col * spacing;
      const cy = row * spacing;
      const members = groups.get(k)!;

      gnodes.push({
        id: `__hub_${k}`,
        hub: true,
        cluster: k,
        label: clusterLabel(k, mode, manifest),
        r: 7,
        color: accent,
        accent,
        count: members.length,
        fx: cx,
        fy: cy,
      });

      members.forEach((n, j) => {
        const ang = (j / members.length) * Math.PI * 2;
        gnodes.push({
          id: n.id,
          cluster: k,
          label: n.nm,
          r: rOf(n.pagu),
          color: VERDICT_COLOR[n.v],
          accent,
          data: n,
          x: cx + Math.cos(ang) * 60,
          y: cy + Math.sin(ang) * 60,
        });
        glinks.push({ source: n.id, target: `__hub_${k}`, accent });
      });
    });

    return { nodes: gnodes, links: glinks };
  }, [nodes, mode, manifest, maxP]);

  // konfigurasi gaya force tiap kali graf berubah
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("link")?.distance((l: any) => (l.target.r ?? 7) + 30).strength(0.5);
    fg.d3Force("charge")?.strength(-26).distanceMax(180);
    const collide = fg.d3Force("collide");
    if (!collide) {
      // tambah collision agar bubble tidak tumpang tindih
      import("d3-force").then(({ forceCollide }) => {
        fgRef.current?.d3Force("collide", forceCollide((n: any) => n.r + 1.5).strength(0.85));
        fgRef.current?.d3ReheatSimulation();
      });
    }
    fg.d3ReheatSimulation?.();
  }, [graph]);

  // fokus kamera ke node terpilih dari daftar
  useEffect(() => {
    if (!selectedId || !fgRef.current) return;
    const target = graph.nodes.find((n) => n.id === selectedId);
    if (target && typeof target.x === "number") {
      fgRef.current.centerAt(target.x, target.y, 700);
      fgRef.current.zoom(3.2, 700);
    }
  }, [focusNonce]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div ref={ref} className="absolute inset-0">
      {size.w > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={size.w}
          height={size.h}
          graphData={graph}
          backgroundColor="rgba(0,0,0,0)"
          d3VelocityDecay={0.34}
          cooldownTicks={220}
          onEngineStop={() => fgRef.current?.zoomToFit(500, 70)}
          enableNodeDrag={true}
          nodeRelSize={1}
          nodeVal={(n: any) => n.r}
          linkColor={(l: any) => `${l.accent}22`}
          linkWidth={0.6}
          onNodeClick={(n: any) => {
            if (!n.hub && n.data) onSelect(n.data);
            else if (n.hub && fgRef.current) {
              fgRef.current.centerAt(n.fx, n.fy, 600);
              fgRef.current.zoom(2.2, 600);
            }
          }}
          nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, (n.r ?? 6) + 1, 0, 2 * Math.PI);
            ctx.fill();
          }}
          nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
            const selected = n.id === selectedId;
            if (n.hub) {
              ctx.beginPath();
              ctx.arc(n.x, n.y, 7, 0, 2 * Math.PI);
              ctx.fillStyle = "#0a0e1a";
              ctx.fill();
              ctx.lineWidth = 2 / scale;
              ctx.strokeStyle = n.accent;
              ctx.stroke();
              ctx.beginPath();
              ctx.arc(n.x, n.y, 2.5, 0, 2 * Math.PI);
              ctx.fillStyle = n.accent;
              ctx.fill();
              const fs = Math.min(13, 11 / scale + 3);
              ctx.font = `500 ${fs}px Inter, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = "#aeb9d4";
              const lbl = n.label.length > 30 ? n.label.slice(0, 30) + "…" : n.label;
              ctx.fillText(`${lbl}  ·  ${n.count}`, n.x, n.y + 11);
              return;
            }
            // bubble member
            ctx.beginPath();
            ctx.arc(n.x, n.y, n.r, 0, 2 * Math.PI);
            ctx.fillStyle = n.color;
            ctx.globalAlpha = selected ? 1 : 0.92;
            ctx.fill();
            ctx.globalAlpha = 1;
            if (selected) {
              ctx.lineWidth = 2.5 / scale;
              ctx.strokeStyle = "#ffffff";
              ctx.stroke();
            } else {
              ctx.lineWidth = 0.7 / scale;
              ctx.strokeStyle = "rgba(255,255,255,0.18)";
              ctx.stroke();
            }
            // label hanya saat zoom dekat & bubble cukup besar
            if (scale > 2.4 && n.r > 8) {
              const fs = 9 / scale;
              ctx.font = `400 ${fs}px Inter, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "rgba(255,255,255,0.9)";
              ctx.fillText(n.data.kl, n.x, n.y);
            }
          }}
        />
      )}
    </div>
  );
}
