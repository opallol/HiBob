"""
16_export_web.py
Ekspor agregat hasil pipeline ke JSON statis untuk web visualisasi (bubblemaps).
Data sudah beku → tanpa backend; frontend cukup fetch file statis ini.

Output: web/public/data/
  manifest.json              ringkasan, daftar mode cluster, legenda, kamus K/L & pola
  coherence/nodes.json       1.101 output anomali L3 (bubble) — ringan, tanpa reasoning
  coherence/details/<kl>.json detail per output (reasoning, komposisi, mandat) — lazy-load
  knowledge_graph.json       struktur RPJMN/RKP (PN/PP/KP + edge)
  pipeline.json              15 langkah pipeline + angka kunci untuk seksi alur progres

Usage:  python scripts/16_export_web.py
"""
import os, json, sys
from collections import defaultdict

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from common.db import get_connection
from common.config import TABLE_PAGU_AKUN, TABLE_ANOMALY, TABLE_COHERENCE, TABLE_COHERENCE_AKUN

T_PAGU     = TABLE_PAGU_AKUN
T_ANOMALY  = TABLE_ANOMALY
T_COH      = TABLE_COHERENCE
T_COH_AKUN = TABLE_COHERENCE_AKUN

OUT_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "public", "data")
COH_DIR  = os.path.join(OUT_DIR, "coherence")
DET_DIR  = os.path.join(COH_DIR, "details")

CAT = {
    "51": "Belanja Pegawai", "52": "Belanja Barang", "53": "Belanja Modal",
    "54": "Belanja Bunga Utang", "55": "Belanja Subsidi",
    "57": "Belanja Bantuan Sosial", "58": "Belanja Lain-lain",
}

VERDICT_MAP = {
    "valid": "valid", "false_positive": "fp",
    "manual_review": "review", "unclear": "unclear",
}

VERDICTS = [
    {"key": "valid",   "label": "Anomali valid",          "color": "red"},
    {"key": "review",  "label": "Perlu review",           "color": "amber"},
    {"key": "fp",      "label": "False positive",          "color": "green"},
    {"key": "unclear", "label": "Tidak ditemukan anomali", "color": "slate"},
]

ALIGN_PATTERN_LABELS = {
    "orphan": "Policy Orphan",
    "weak":   "Keselarasan Lemah",
}


def jparse(s):
    try:
        return json.loads(s) if isinstance(s, str) else (s or {})
    except Exception:
        return {}


def pattern_of(own, peer):
    """Tentukan pola komposisi: akun dominan K/L ini vs akun dominan peer."""
    if not own or not peer:
        return "other", "Lainnya"
    od = max(own, key=own.get)
    pd = max(peer, key=peer.get)
    if od == pd:
        return "balanced", "Mendekati pola peer"
    key   = "o%s_p%s" % (od, pd)
    label = "%s tinggi · peer %s" % (CAT.get(od, "Akun " + od), CAT.get(pd, "Akun " + pd))
    return key, label


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def build_mandat_index(cur):
    """Mandat RPJMN/RKP per K/L (top KP by confidence) untuk chip di kartu detail."""
    cur.execute("""
        SELECT a.kddept, n.node_code, n.node_name, a.role, a.confidence
        FROM deepseek_policy_kl_assignments a
        JOIN deepseek_policy_nodes n ON n.id = a.node_id
        ORDER BY a.confidence DESC
    """)
    idx = defaultdict(list)
    for kddept, code, name, role, conf in cur.fetchall():
        if kddept is None:
            continue
        try:
            kl = "%03d" % int(str(kddept).strip())
        except ValueError:
            kl = str(kddept).strip().zfill(3)
        if len(idx[kl]) < 6:
            idx[kl].append({"c": code, "n": (name or "")[:90], "r": role})
    return idx


SEM_PATTERNS = {
    "l1":   "Semantik Program-Kegiatan",
    "l2":   "Semantik Kegiatan-Output",
    "l1l2": "Semantik Program+Kegiatan+Output",
}


def export_coherence(cur, mandat_idx):
    """Node bubble + detail per output anomali L3 + L1/L2 semantik."""
    cur.execute(f"""
        SELECT
            ca.kementerian_kode, ca.program_kode, ca.kegiatan_kode, ca.outputkro_kode,
            ca.akun_komposisi_score, ca.peer_count, ca.akun_detail,
            MAX(c.kementerian_uraian), MAX(c.program_uraian),
            MAX(c.kegiatan_uraian),   MAX(c.outputkro_uraian),
            SUM(c.total_pagu),
            MAX(c.treasurai_verdict), MAX(c.llm_model), MAX(c.llm_reasoning)
        FROM {T_COH_AKUN} ca
        JOIN {T_COH} c
          ON  c.kementerian_kode = ca.kementerian_kode
          AND c.program_kode     = ca.program_kode
          AND c.kegiatan_kode    = ca.kegiatan_kode
          AND c.outputkro_kode   = ca.outputkro_kode
        WHERE ca.akun_komposisi_score >= 40
        GROUP BY ca.kementerian_kode, ca.program_kode, ca.kegiatan_kode,
                 ca.outputkro_kode, ca.akun_komposisi_score,
                 ca.peer_count, ca.akun_detail
        ORDER BY SUM(c.total_pagu) DESC
    """)
    rows = cur.fetchall()

    nodes      = []
    details_by_kl = defaultdict(dict)
    patterns   = {}
    kl_names   = {}

    for (kl, prog, keg, out, score, peer_cnt, akun_json,
         kl_name, prog_name, keg_name, out_name,
         pagu, verdict, model, reasoning) in rows:

        d    = jparse(akun_json)
        own  = d.get("own", {})
        peer = d.get("peer", {})
        pkey, plabel = pattern_of(own, peer)
        patterns[pkey] = plabel
        kl_names[kl]   = (kl_name or "")[:60]

        nid = "%s-%s-%s-%s" % (kl, prog, keg, out)
        v   = VERDICT_MAP.get((verdict or "").strip(), "unclear")

        nodes.append({
            "id":   nid,
            "kl":   kl,
            "nm":   ("%s · %s" % (out, (out_name or "")[:48])).strip(),
            "pagu": round(float(pagu or 0), 2),
            "v":    v,
            "pat":  pkey,
            "dev":  round(float(score or 0), 1),
            "peer": int(peer_cnt or 0),
        })

        details_by_kl[kl][nid] = {
            "kl":   kl,
            "kln":  (kl_name or "")[:80],
            "prog": ("%s · %s" % (prog, (prog_name or "")[:70])).strip(),
            "keg":  ("%s · %s" % (keg,  (keg_name or "")[:70])).strip(),
            "out":  ("%s · %s" % (out,  (out_name or "")[:70])).strip(),
            "pagu": round(float(pagu or 0), 2),
            "dev":  round(float(score or 0), 1),
            "pc":   int(peer_cnt or 0),
            "own":  {k: round(float(v2), 3) for k, v2 in own.items()},
            "peer": {k: round(float(v2), 3) for k, v2 in peer.items()},
            "v":    v,
            "md":   model or "oss120b",
            "rs":   (reasoning or "")[:1600],
            "mandat": mandat_idx.get(kl, []),
        }

    # --- L1/L2 semantik: output yang belum masuk L3 ---
    cur.execute(f"""
        SELECT
            kementerian_kode, program_kode, kegiatan_kode, outputkro_kode,
            MAX(kementerian_uraian), MAX(program_uraian),
            MAX(kegiatan_uraian),   MAX(outputkro_uraian),
            SUM(total_pagu),
            ROUND(MIN(prog_keg_coherence), 1),
            ROUND(MIN(keg_out_coherence),  1),
            MAX(CASE WHEN JSON_CONTAINS(anomaly_flags, '"level1_program_kegiatan_lemah"') THEN 1 ELSE 0 END),
            MAX(CASE WHEN JSON_CONTAINS(anomaly_flags, '"level2_kegiatan_output_lemah"')  THEN 1 ELSE 0 END),
            MAX(treasurai_verdict), MAX(llm_model), MAX(llm_reasoning)
        FROM {T_COH}
        WHERE JSON_CONTAINS(anomaly_flags, '"level1_program_kegiatan_lemah"')
           OR JSON_CONTAINS(anomaly_flags, '"level2_kegiatan_output_lemah"')
        GROUP BY kementerian_kode, program_kode, kegiatan_kode, outputkro_kode
        HAVING MAX(CASE WHEN JSON_CONTAINS(anomaly_flags, '"level3_akun_tidak_lazim"') THEN 1 ELSE 0 END) = 0
        ORDER BY SUM(total_pagu) DESC
    """)
    l12_rows = cur.fetchall()
    existing_ids = {n["id"] for n in nodes}

    for (kl, prog, keg, out,
         kl_name, prog_name, keg_name, out_name,
         pagu, l1_score, l2_score, has_l1, has_l2,
         verdict, model, reasoning) in l12_rows:

        nid = "%s-%s-%s-%s" % (kl, prog, keg, out)
        if nid in existing_ids:
            continue
        existing_ids.add(nid)

        if has_l1 and has_l2:
            pkey = "l1l2"
        elif has_l1:
            pkey = "l1"
        else:
            pkey = "l2"

        sem_score = min(s for s in [l1_score, l2_score] if s is not None)
        v = VERDICT_MAP.get((verdict or "").strip(), "unclear")
        kl_names[kl] = (kl_name or "")[:60]
        patterns[pkey] = SEM_PATTERNS[pkey]

        nodes.append({
            "id":   nid,
            "kl":   kl,
            "nm":   ("%s · %s" % (out or "-", (out_name or "")[:48])).strip(),
            "pagu": round(float(pagu or 0), 2),
            "v":    v,
            "pat":  pkey,
            "dev":  round(float(sem_score or 0), 1),
            "peer": 0,
        })

        details_by_kl[kl][nid] = {
            "kl":     kl,
            "kln":    (kl_name or "")[:80],
            "prog":   ("%s · %s" % (prog, (prog_name or "")[:70])).strip(),
            "keg":    ("%s · %s" % (keg,  (keg_name or "")[:70])).strip(),
            "out":    ("%s · %s" % (out or "-", (out_name or "")[:70])).strip(),
            "pagu":   round(float(pagu or 0), 2),
            "dev":    round(float(sem_score or 0), 1),
            "pc":     0,
            "own":    {
                **({"l1": float(l1_score)} if l1_score is not None else {}),
                **({"l2": float(l2_score)} if l2_score is not None else {}),
            },
            "peer":   {},
            "v":      v,
            "md":     model or "oss120b",
            "rs":     (reasoning or "")[:1600],
            "mandat": mandat_idx.get(kl, []),
            "nature": pkey,
        }

    write_json(os.path.join(COH_DIR, "nodes.json"), nodes)
    for kl, det in details_by_kl.items():
        write_json(os.path.join(DET_DIR, "%s.json" % kl), det)

    n_l12 = sum(1 for n in nodes if n["pat"] in SEM_PATTERNS)
    print("  coherence: %d node (%d L3 + %d L1/L2), %d K/L detail, %d pola" % (
        len(nodes), len(nodes) - n_l12, n_l12, len(details_by_kl), len(patterns)))
    return nodes, patterns, kl_names, CAT


def export_knowledge_graph(cur):
    cur.execute("SELECT id, node_type, node_code, node_name, parent_code FROM deepseek_policy_nodes")
    nodes = []
    for nid, ntype, code, name, parent in cur.fetchall():
        nodes.append({
            "id": nid, "t": ntype, "c": code,
            "nm": (name or "")[:120], "p": parent,
        })
    cur.execute("SELECT parent_node_id, child_node_id, edge_type FROM deepseek_policy_edges")
    edges = [{"s": s, "t": t, "e": e} for s, t, e in cur.fetchall()]
    write_json(os.path.join(OUT_DIR, "knowledge_graph.json"), {"nodes": nodes, "edges": edges})
    print("  knowledge_graph: %d node, %d edge" % (len(nodes), len(edges)))


def _breakdown(align_nodes, coh_nodes):
    """Rincian kategori per analisis, dihitung dari node yang BENAR-BENAR ditampilkan
    (jadi angkanya selalu cocok dengan peta). Dipakai seksi pipeline di web."""
    SEM = {"l1", "l2", "l1l2"}

    def vc(nodes, v):
        return sum(1 for n in nodes if n["v"] == v)

    a_weak   = sum(1 for n in align_nodes if n["pat"] == "weak")
    a_orphan = sum(1 for n in align_nodes if n["pat"] == "orphan")
    c_l3  = sum(1 for n in coh_nodes if n["pat"] not in SEM)
    c_sem = sum(1 for n in coh_nodes if n["pat"] in SEM)

    return {
        "alignment": {
            "title": "Keselarasan RPJMN/RKP",
            "total": len(align_nodes),
            "desc": "Apakah belanja DIPA selaras dengan Kegiatan Prioritas RPJMN/RKP.",
            "jenis": [
                {"label": "Weak alignment", "n": a_weak,
                 "desc": "Ada KP terdekat tapi kemiripan semantik lemah — sering hanya beda nomenklatur."},
                {"label": "Policy orphan", "n": a_orphan,
                 "desc": "Tidak ada KP relevan sama sekali (skor < 40). Tahun 2026: tidak ditemukan."},
            ],
            "verdict": [
                {"label": "False positive", "n": vc(align_nodes, "fp"),
                 "desc": "Terjelaskan oleh mandat/nomenklatur — bukan masalah."},
                {"label": "Perlu review", "n": vc(align_nodes, "review"),
                 "desc": "Belum bisa dipastikan, perlu telaah manusia."},
                {"label": "Valid", "n": vc(align_nodes, "valid"),
                 "desc": "Belanja benar-benar di luar prioritas nasional — perlu tindak lanjut."},
            ],
        },
        "coherence": {
            "title": "Koherensi Akun",
            "total": len(coh_nodes),
            "desc": "Apakah struktur dan pola belanja internal DIPA konsisten.",
            "jenis": [
                {"label": "L3 Komposisi Akun", "n": c_l3,
                 "desc": "Pola belanja (akun) janggal dibanding K/L lain dengan output sejenis."},
                {"label": "L1/L2 Semantik", "n": c_sem,
                 "desc": "Nama program–kegiatan–output tidak saling konsisten secara makna."},
            ],
            "verdict": [
                {"label": "Valid", "n": vc(coh_nodes, "valid"),
                 "desc": "Deviasi tak dapat dijustifikasi — perlu tindak lanjut."},
                {"label": "False positive", "n": vc(coh_nodes, "fp"),
                 "desc": "Terjustifikasi mandat atau sifat program — bukan masalah."},
                {"label": "Perlu review", "n": vc(coh_nodes, "review"),
                 "desc": "Bukti belum cukup untuk memutuskan."},
            ],
        },
    }


def export_pipeline(cur, align_nodes, coh_nodes):
    def scalar(q):
        cur.execute(q)
        return cur.fetchone()[0]

    counts = {
        "documents":   scalar("SELECT COUNT(*) FROM deepseek_policy_documents"),
        "chunks":      scalar("SELECT COUNT(*) FROM deepseek_policy_chunks"),
        "nodes_kb":    scalar("SELECT COUNT(*) FROM deepseek_policy_nodes"),
        "edges_kb":    scalar("SELECT COUNT(*) FROM deepseek_policy_edges"),
        "dipa_lines":  scalar(f"SELECT COUNT(*) FROM {T_PAGU}"),
        "anomaly":     scalar(f"SELECT COUNT(*) FROM {T_ANOMALY} WHERE anomaly_type IN ('policy_orphan','weak_alignment')"),
        "coherence":   scalar(f"SELECT COUNT(*) FROM {T_COH_AKUN} WHERE akun_komposisi_score>=40"),
        "reasoned":    scalar(f"SELECT COUNT(*) FROM {T_COH} WHERE llm_reasoning IS NOT NULL"),
    }

    phases = [
        {"id": "ingest", "label": "Ingest dokumen", "icon": "file-text",
         "steps": ["Ekstraksi 17 PDF RPJMN/RKP", "Chunking + AI OCR cleaning (dokumen publik)"],
         "metric": "%s dokumen · %s chunk" % (counts["documents"], format(counts["chunks"], ","))},
        {"id": "kg", "label": "Knowledge graph", "icon": "sitemap",
         "steps": ["Ekstraksi node PN/PP/KP", "Bangun edge hierarki prioritas"],
         "metric": "%s node · %s edge" % (counts["nodes_kb"], counts["edges_kb"])},
        {"id": "embed", "label": "Embedding", "icon": "vector-triangle",
         "steps": ["e5-small lokal embed DIPA + knowledge graph", "Vektor dihitung runtime, tak disimpan (privasi)"],
         "metric": "%s KP + %s baris DIPA · e5-small" % (
             format(counts["nodes_kb"], ","),
             ("%.1f jt" % (counts["dipa_lines"] / 1e6)) if counts["dipa_lines"] >= 1e6
             else format(counts["dipa_lines"], ","))},
        {"id": "align", "label": "Alignment DIPA↔RPJMN", "icon": "git-compare",
         "steps": ["Skor kemiripan semantik", "Deteksi policy_orphan & weak_alignment"],
         "metric": "%s anomali alignment" % format(counts["anomaly"], ",")},
        {"id": "coherence", "label": "Koherensi internal", "icon": "stack-2",
         "steps": ["L1/L2 semantik program-kegiatan-output", "L3 komposisi akun vs peer"],
         "metric": "%s anomali L3" % format(counts["coherence"], ",")},
        {"id": "reasoning", "label": "Reasoning TreasurAI", "icon": "message-2",
         "steps": ["oss120b enrich mandat RPJMN per K/L", "Verdict + rekomendasi tiap anomali"],
         "metric": "%s output ber-reasoning" % format(counts["reasoned"], ",")},
    ]
    breakdown = _breakdown(align_nodes, coh_nodes)
    write_json(os.path.join(OUT_DIR, "pipeline.json"),
               {"phases": phases, "counts": counts, "breakdown": breakdown})
    print("  pipeline: %d fase" % len(phases))
    return counts


def export_alignment(cur, mandat_idx):
    """Node bubble + detail per output anomali policy alignment (orphan + weak_alignment)."""
    cur.execute(f"""
        SELECT
            a.kementerian_kode, a.program_kode, a.kegiatan_kode, p.outputkro_kode,
            a.kementerian_uraian, p.program_uraian,
            p.kegiatan_uraian,   p.outputkro_uraian,
            a.total_pagu,
            a.alignment_score, a.anomaly_type,
            a.anomaly_score,   a.spending_nature,
            a.treasurai_verdict, a.llm_model, a.llm_reasoning,
            a.top3_matches
        FROM {T_ANOMALY} a
        JOIN {T_PAGU} p ON a.pagu_id = p.id
        WHERE a.anomaly_type IN ('policy_orphan', 'weak_alignment')
        ORDER BY a.total_pagu DESC
    """)
    rows = cur.fetchall()

    nodes         = []
    details_by_kl = defaultdict(dict)
    kl_names      = {}

    for (kl, prog, keg, out,
         kl_name, prog_name, keg_name, out_name,
         pagu, align_score, anomaly_type, anomaly_score,
         spending_nature, verdict, model, reasoning, top3_json) in rows:

        kl_names[kl] = (kl_name or "")[:60]
        pat = "orphan" if anomaly_type == "policy_orphan" else "weak"
        v   = VERDICT_MAP.get((verdict or "").strip(), "unclear")
        nid = "%s-%s-%s-%s" % (kl, prog, keg, out or "-")

        nodes.append({
            "id":   nid,
            "kl":   kl,
            "nm":   ("%s · %s" % ((out or "-"), (out_name or "")[:48])).strip(),
            "pagu": round(float(pagu or 0), 2),
            "v":    v,
            "pat":  pat,
            "dev":  round(float(anomaly_score or 0), 1),
            "peer": 0,
        })

        top3 = []
        try:
            t3 = json.loads(top3_json) if isinstance(top3_json, str) else (top3_json or [])
            for m in (t3 if isinstance(t3, list) else []):
                top3.append({
                    "c": str(m.get("code", "")),
                    "n": (m.get("name", "") or "")[:90],
                    "r": str(round(float(m.get("score", 0)), 1)),
                })
        except Exception:
            pass

        details_by_kl[kl][nid] = {
            "kl":      kl,
            "kln":     (kl_name or "")[:80],
            "prog":    ("%s · %s" % (prog, (prog_name or "")[:70])).strip(),
            "keg":     ("%s · %s" % (keg,  (keg_name or "")[:70])).strip(),
            "out":     ("%s · %s" % (out,  (out_name or "")[:70])).strip(),
            "pagu":    round(float(pagu or 0), 2),
            "dev":     round(float(anomaly_score or 0), 1),
            "pc":      0,
            "own":     {"skor": round(float(align_score or 0), 1)},
            "peer":    {},
            "v":       v,
            "md":      model or "oss120b",
            "rs":      (reasoning or "")[:1600],
            "mandat":  top3,
            "dataset": "alignment",
            "nature":  spending_nature or "substantive",
        }

    ALIGN_DIR = os.path.join(OUT_DIR, "alignment")
    ALIGN_DET = os.path.join(ALIGN_DIR, "details")
    write_json(os.path.join(ALIGN_DIR, "nodes.json"), nodes)
    for kl, det in details_by_kl.items():
        write_json(os.path.join(ALIGN_DET, "%s.json" % kl), det)

    print("  alignment: %d node, %d K/L" % (len(nodes), len(details_by_kl)))
    return nodes, kl_names


def main():
    conn = get_connection()
    cur  = conn.cursor()
    print("=" * 60)
    print("16_export_web.py → %s" % OUT_DIR)
    print("=" * 60)

    mandat_idx = build_mandat_index(cur)
    nodes, patterns, kl_names, cat = export_coherence(cur, mandat_idx)
    align_nodes, align_kl_names    = export_alignment(cur, mandat_idx)
    export_knowledge_graph(cur)
    counts = export_pipeline(cur, align_nodes, nodes)

    total_pagu       = sum(n["pagu"] for n in nodes)
    align_total_pagu = sum(n["pagu"] for n in align_nodes)
    vcount = defaultdict(int)
    for n in nodes:
        vcount[n["v"]] += 1

    # Gabung kamus K/L dari kedua dataset
    all_kl_names = {**kl_names, **align_kl_names}

    manifest = {
        "generated": "2026-06-12",
        "title": "SENTINEL",
        "totals": {
            "anomaly_nodes": len(nodes),
            "total_pagu":    round(total_pagu, 2),
            "kl":            len(kl_names),
            "patterns":      len(patterns),
            "verdict":       dict(vcount),
        },
        "modes": [
            {"key": "pat", "label": "Pola komposisi akun"},
            {"key": "v",   "label": "Status verdict"},
        ],
        "verdicts":      VERDICTS,
        "patterns":      patterns,
        "kls":           all_kl_names,
        "akun":          cat,
        "align_patterns": ALIGN_PATTERN_LABELS,
        "align_totals": {
            "alignment_nodes": len(align_nodes),
            "total_pagu":      round(align_total_pagu, 2),
            "kl":              len(align_kl_names),
        },
    }
    write_json(os.path.join(OUT_DIR, "manifest.json"), manifest)
    print("  manifest: %d koherensi, %d alignment, %d K/L" % (
        len(nodes), len(align_nodes), len(all_kl_names)))
    print("\nSelesai. Koherensi Rp %.1f T · Alignment Rp %.1f T" % (
        total_pagu / 1e12, align_total_pagu / 1e12))
    conn.close()


if __name__ == "__main__":
    main()
