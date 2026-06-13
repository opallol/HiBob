import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { BubbleNode, Manifest, ModeKey } from "../types";
import { VERDICT_COLOR, VERDICT_LABEL, CLUSTER_ACCENT, rupiahT } from "../theme";

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

// --- util warna untuk bola mengkilap (gradient + highlight) ---
function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function mix([r, g, b]: [number, number, number], to: [number, number, number], t: number): string {
  return `rgb(${Math.round(r + (to[0] - r) * t)},${Math.round(g + (to[1] - g) * t)},${Math.round(b + (to[2] - b) * t)})`;
}
const WHITE: [number, number, number] = [255, 255, 255];
const BLACK: [number, number, number] = [0, 0, 0];

function clusterKey(n: BubbleNode, mode: ModeKey): string {
  if (mode === "v") return n.v;
  if (mode === "kl") return n.kl;
  return n.pat;
}

function clusterLabel(key: string, mode: ModeKey, m: Manifest): string {
  if (mode === "v") return VERDICT_LABEL[key as keyof typeof VERDICT_LABEL] ?? key;
  if (mode === "kl") return `${key} ${m.kls[key] ?? ""}`.trim();
  return m.patterns[key] ?? m.align_patterns?.[key] ?? key;
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// kartu tooltip HTML saat kursor menyentuh bubble / hub
function nodeTooltip(n: any, m: Manifest): string {
  if (n.hub) {
    return (
      `<div style="max-width:300px;padding:7px 10px;border-radius:8px;background:#0d1426;` +
      `border:1px solid #2a3350;color:#dbe2f2;font:500 12px Inter,sans-serif;` +
      `box-shadow:0 8px 28px rgba(0,0,0,.45)">${esc(n.label)} · ${n.count} output</div>`
    );
  }
  const d = n.data as BubbleNode;
  const klName = esc(m.kls[d.kl] ?? "");
  return (
    `<div style="max-width:300px;padding:8px 11px;border-radius:9px;background:#0d1426;` +
    `border:1px solid #2a3350;color:#dbe2f2;font:400 12px Inter,sans-serif;line-height:1.45;` +
    `box-shadow:0 8px 28px rgba(0,0,0,.45)">` +
    `<div style="color:#8b97b5;font-size:10px;margin-bottom:2px">${esc(d.kl)} · ${klName}</div>` +
    `<div style="font-weight:500;color:#eef2fb">${esc(d.nm)}</div>` +
    `<div style="margin-top:5px;display:flex;gap:6px;align-items:center;color:#aeb9d4">` +
    `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${VERDICT_COLOR[d.v]}"></span>` +
    `${rupiahT(d.pagu)} · ${VERDICT_LABEL[d.v]}</div></div>`
  );
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
          nodeLabel={(n: any) => nodeTooltip(n, manifest)}
          linkColor={(l: any) => `${l.accent}22`}
          linkWidth={0.6}
          onNodeDragEnd={(n: any) => {
            if (n.hub) {
              // d3 clears fx/fy synchronously after this callback fires,
              // so we re-pin AFTER d3 finishes via setTimeout
              const x = n.x, y = n.y;
              setTimeout(() => { n.fx = x; n.fy = y; }, 0);
            }
          }}
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
            // --- bubble member: bola mengkilap (glow + radial gradient + highlight) ---
            const rgb = hexToRgb(n.color);
            const r = n.r;

            // 1. halo glow di belakang bola
            ctx.save();
            ctx.shadowColor = n.color;
            ctx.shadowBlur = (selected ? r * 1.5 : r * 0.55) ;
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = mix(rgb, BLACK, 0.15);
            ctx.fill();
            ctx.restore();

            // 2. isi bola dengan gradient radial (terang kiri-atas → gelap kanan-bawah)
            const body = ctx.createRadialGradient(
              n.x - r * 0.36, n.y - r * 0.42, r * 0.05,
              n.x, n.y, r
            );
            body.addColorStop(0, mix(rgb, WHITE, 0.55));
            body.addColorStop(0.5, n.color);
            body.addColorStop(1, mix(rgb, BLACK, 0.42));
            ctx.beginPath();
            ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = body;
            ctx.fill();

            // 3. rim tipis di tepi
            ctx.lineWidth = (selected ? 2.2 : 0.8) / scale;
            ctx.strokeStyle = selected ? "#ffffff" : "rgba(255,255,255,0.16)";
            ctx.stroke();

            // 4. titik kilau (specular) di kiri-atas
            const hx = n.x - r * 0.32;
            const hy = n.y - r * 0.4;
            const hl = ctx.createRadialGradient(hx, hy, 0, hx, hy, r * 0.55);
            hl.addColorStop(0, "rgba(255,255,255,0.5)");
            hl.addColorStop(1, "rgba(255,255,255,0)");
            ctx.beginPath();
            ctx.arc(hx, hy, r * 0.55, 0, 2 * Math.PI);
            ctx.fillStyle = hl;
            ctx.fill();

            // label hanya saat zoom dekat & bubble cukup besar
            if (scale > 2.4 && n.r > 8) {
              const fs = 9 / scale;
              ctx.font = `500 ${fs}px Inter, sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "middle";
              ctx.fillStyle = "rgba(255,255,255,0.95)";
              ctx.fillText(n.data.kl, n.x, n.y);
            }
          }}
        />
      )}
    </div>
  );
}
