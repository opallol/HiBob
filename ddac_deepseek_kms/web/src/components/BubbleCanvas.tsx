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
  cx?: number;   // pusat cluster yang dituju (untuk forceX/forceY member)
  cy?: number;
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
    // Urut by total pagu desc — SAMA dengan AnomalyList, agar warna accent anchor
    // di peta cocok dengan warna cluster di daftar anomali (index → CLUSTER_ACCENT).
    const paguOf = (k: string) => groups.get(k)!.reduce((s, n) => s + n.pagu, 0);
    const keys = [...groups.keys()].sort((a, b) => paguOf(b) - paguOf(a));

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

      // Hub MENGAMBANG bebas (tanpa fx/fy): ditarik benang ke semua member,
      // sehingga otomatis duduk di centroid = tengah cluster, berapa pun jumlahnya.
      gnodes.push({
        id: `__hub_${k}`,
        hub: true,
        cluster: k,
        label: clusterLabel(k, mode, manifest),
        r: 6,
        color: accent,
        accent,
        count: members.length,
        cx,
        cy,
        x: cx,
        y: cy,
      });

      // Member di-init dekat pusat dengan sedikit acak → mekar (bloom) saat render.
      members.forEach((n) => {
        const ang = Math.random() * Math.PI * 2;
        const rad = 6 + Math.random() * 26;
        gnodes.push({
          id: n.id,
          cluster: k,
          label: n.nm,
          r: rOf(n.pagu),
          color: VERDICT_COLOR[n.v],
          accent,
          data: n,
          cx,
          cy,
          x: cx + Math.cos(ang) * rad,
          y: cy + Math.sin(ang) * rad,
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
    // center global dimatikan — tiap cluster di-anchor sendiri via forceX/forceY.
    fg.d3Force("center", null);
    // benang hub↔member: lemah & pendek; cukup untuk menyeret hub ke centroid,
    // tidak mendominasi posisi member.
    fg.d3Force("link")?.distance(24).strength(0.18);
    // hanya member yang saling tolak; hub tak menolak agar bisa diam di tengah.
    fg.d3Force("charge")?.strength((n: any) => (n.hub ? 0 : -22)).distanceMax(170);
    import("d3-force").then(({ forceX, forceY, forceCollide }) => {
      const fgr = fgRef.current;
      if (!fgr) return;
      // member ditarik lembut ke pusat cluster-nya; hub dibiarkan bebas (str 0).
      fgr.d3Force("x", forceX((n: any) => n.cx ?? 0).strength((n: any) => (n.hub ? 0 : 0.09)));
      fgr.d3Force("y", forceY((n: any) => n.cy ?? 0).strength((n: any) => (n.hub ? 0 : 0.09)));
      fgr.d3Force("collide", forceCollide((n: any) => n.r + 1.6).strength(0.85));
      fgr.d3ReheatSimulation();
    });
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
          onNodeClick={(n: any) => {
            if (!n.hub && n.data) onSelect(n.data);
            else if (n.hub && fgRef.current) {
              fgRef.current.centerAt(n.x, n.y, 600);
              fgRef.current.zoom(2.2, 600);
            }
          }}
          onRenderFramePost={(ctx: CanvasRenderingContext2D, scale: number) => {
            // Anchor cluster digambar SETELAH semua node → selalu di atas.
            // Bentuk ⊙ (target) + label berwarna accent, di posisi hub (= tengah cluster).
            ctx.save();
            const fs = Math.max(7, 12 / scale);
            ctx.font = `600 ${fs}px Inter, sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            for (const n of graph.nodes as any[]) {
              if (!n.hub || typeof n.x !== "number") continue;
              const x = n.x, y = n.y;

              // --- bentuk ⊙ (ring + titik tengah) ---
              const R = 6.5 / scale;
              ctx.beginPath();
              ctx.arc(x, y, R, 0, 2 * Math.PI);
              ctx.fillStyle = "rgba(10,14,26,0.92)";
              ctx.fill();
              ctx.lineWidth = 1.7 / scale;
              ctx.strokeStyle = n.accent;
              ctx.stroke();
              ctx.beginPath();
              ctx.arc(x, y, 2.4 / scale, 0, 2 * Math.PI);
              ctx.fillStyle = n.accent;
              ctx.fill();

              // --- label berwarna accent, di bawah ⊙ ---
              const name = n.label.length > 28 ? n.label.slice(0, 28) + "…" : n.label;
              const lbl = `${name}  ·  ${n.count}`;
              const ly = y + R + fs * 0.95;
              const tw = ctx.measureText(lbl).width;
              const pr = fs * 0.82;
              const hw = tw / 2;
              ctx.fillStyle = "rgba(6,10,20,0.82)";
              ctx.beginPath();
              ctx.arc(x - hw, ly, pr, Math.PI / 2, Math.PI * 1.5);
              ctx.arc(x + hw, ly, pr, -Math.PI / 2, Math.PI / 2);
              ctx.closePath();
              ctx.fill();
              ctx.fillStyle = n.accent;
              ctx.fillText(lbl, x, ly);
            }
            ctx.restore();
          }}
          nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(n.x, n.y, (n.r ?? 6) + 1, 0, 2 * Math.PI);
            ctx.fill();
          }}
          nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, scale: number) => {
            const selected = n.id === selectedId;
            // Anchor (hub) digambar di onRenderFramePost (⊙ + label, selalu di atas).
            if (n.hub) return;
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
