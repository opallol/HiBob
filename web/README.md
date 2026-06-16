# SENTINEL — Spending Intelligence for National Alignment Review

Web visualisasi interaktif hasil analisis keselarasan belanja negara (DIPA) terhadap
RPJMN/RKP. Gaya konstelasi (bubblemaps): bubble dikelompokkan per cluster, warna = status
anomali, ukuran = pagu. Klik bubble → reasoning TreasurAI oss120b + komposisi akun + mandat RPJMN/RKP.

Data **statis** (sudah beku) — tidak butuh backend. Cukup host folder `dist/`.

## Pengembangan

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # hasil → dist/
npm run preview    # uji hasil build
```

Data JSON di-generate dari database oleh `../scripts/16_export_web.py`
(menulis ke `public/data/`). Jalankan ulang skrip itu bila data berubah.

## Struktur data (`public/data/`)

| File | Isi |
|------|-----|
| `manifest.json` | totals, mode cluster, legenda verdict, kamus K/L & pola |
| `coherence/nodes.json` | 608 bubble anomali koherensi: 276 L3 + 332 L1/L2 (ringan, tanpa reasoning) |
| `coherence/details/<kl>.json` | detail per output (reasoning, komposisi, mandat) — lazy-load |
| `knowledge_graph.json` | struktur RPJMN/RKP (PN/PP/KP + edge) |
| `pipeline.json` | 6 fase pipeline + angka kunci |

## Embed ke web lain

Data & UI terisolasi via iframe, jadi aman ditempel di situs mana pun.

**Cara 1 — iframe langsung:**

```html
<iframe src="https://HOST/index.html?embed=1"
        style="width:100%;height:640px;border:0;border-radius:14px"></iframe>
```

**Cara 2 — custom element (drop-in):**

```html
<script src="https://HOST/embed.js"></script>
<sentinel-map src="https://HOST/" height="640"></sentinel-map>
```

Parameter URL: `?embed=1` (tanpa header), `?view=pipeline` (buka ke seksi alur).

## Deploy

Karena statis, bisa di host mana pun (GitHub Pages, Netlify, server internal Kemenkeu).
`vite.config.ts` memakai `base: "./"` sehingga semua aset relatif — taruh `dist/` di
subfolder mana pun tanpa konfigurasi tambahan.
