#!/usr/bin/env python3
"""
13_coherence_levels.py
----------------------
Populates the 3-level coherence detection model onto {T_COH}
(built by 12_coherence.py). Runs IN PLACE -- does not rebuild the 1.5M-row table.

  Level 1  Program <-> Kegiatan   : e5-small cosine similarity -> prog_keg_coherence
  Level 2  Kegiatan <-> Output    : e5-small cosine similarity -> keg_out_coherence
  Level 3  Output  <-> Akun       : peer comparison of belanja -> out_komp_coherence,
                                     akun_komposisi_score (+ detail table)

Composite coherence_score = weighted blend of the per-level anomaly subscores and
the existing jenis_komponen score. anomaly_flags lists which levels tripped.

Design notes:
 * Distinct planning texts are tiny (~2.9k), so embeddings are cheap.
 * All heavy math is done in Python over the small distinct/aggregate sets, then
   written back to the 1.5M rows with a SINGLE indexed UPDATE...JOIN against a
   PK'd temp table (the only pattern that is fast at this scale).
 * LazarusNLP/all-indo-e5-small (Indonesian fine-tune, 384-dim) is used.
   Under-estimates similarity for military/technical jargon; PCT_LOW is set
   conservatively (5th percentile) and MILITARY_DOMAIN_KL {"012","060"}
   combos are suppressed to minimize false positives on domain-specific text.

Usage:
  python scripts/13_coherence_levels.py
  python scripts/13_coherence_levels.py --pct-low 3   # even stricter
  python scripts/13_coherence_levels.py --peer-min 10  # require 10+ peers
"""
import argparse
import json
import os
import time
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
from common.db import get_connection            # noqa: E402
from common.config import EMBEDDING_MODEL, TABLE_PAGU_AKUN, TABLE_COHERENCE, TABLE_COHERENCE_AKUN  # noqa: E402

T_PAGU     = TABLE_PAGU_AKUN
T_COH      = TABLE_COHERENCE
T_COH_AKUN = TABLE_COHERENCE_AKUN

# ---- defaults (override via CLI) ----------------------------------------
PCT_LOW = 5             # percentile below which a similarity is "weak"
                        # (was 15, lowered to 5 because bge-m3 underrates
                        #  Indonesian government compound terms like
                        #  "Infrastruktur Konektivitas"+"Pembangunan Jalan")
PEER_MIN = 5            # min peer K/L to trust a peer profile
PEER_MIN_DETAIL = 3     # min peer K/L to include in detail table
DEV_FLAG = 0.40         # total-variation distance above which akun mix is unusual
DEV_FLAG_INTERNAL = 0.65  # looser threshold for internal support codes (EBA/EBB/EBC/EBD)
W_JENIS, W_L1, W_L2, W_L3 = 0.35, 0.20, 0.20, 0.25

# Output names too generic for the model to align against kegiatan —
# suppress L2 flag to avoid false positives on semantically empty codes.
GENERIC_OUTPUT_PATTERNS = [
    'dukungan teknis', 'kerja sama', 'data dan informasi',
    'dukungan manajemen', 'layanan perkantoran', 'layanan dukungan manajemen',
    'administrasi umum', 'tata kelola',
]

# Fix F1 (2026-06-11): "Program Dukungan Manajemen" adalah catch-all resmi DIPA —
# secara regulasi dirancang untuk menampung semua kegiatan administratif K/L,
# sehingga kegiatan apapun di dalamnya sah dan tidak bisa di-flag L1.
# Analog dengan GENERIC_OUTPUT_PATTERNS untuk L2.
GENERIC_PROGRAM_PATTERNS = [
    'dukungan manajemen',
]

# Fix E1 (2026-06-11): Kemhan (012) dan Polri (060) menggunakan jargon militer teknis
# yang secara konsisten under-scored oleh model embedding:
#   "Penggunaan Kekuatan" <-> "Operasi Bidang Pertahanan" → skor 4.20 (false positive).
# Verifikasi: 17 distinct keg-out combos flagged di L2 untuk K/L 012+060;
# combos dengan output domain pertahanan/keamanan operasional di bawah adalah FP.
# Combos dengan output manajemen/koordinasi generik tetap di-flag (genuine anomali).
MILITARY_DOMAIN_KL = {"012", "060"}
MILITARY_DOMAIN_OUTPUT_PATTERNS = [
    'operasi bidang pertahanan',
    'operasi bidang keamanan',
    'pemenuhan prioritas direktif presiden',
    'om prasarana bidang pertahanan',
    'sarana bidang pertahanan dan keamanan',
    'sarana bidang pertahanan',
]

CAT_LABELS = {
    "51": "Belanja Pegawai", "52": "Belanja Barang", "53": "Belanja Modal",
    "54": "Belanja Bunga Utang", "55": "Belanja Subsidi", "56": "Belanja Hibah",
    "57": "Belanja Bantuan Sosial", "58": "Belanja Lain-lain",
    "61": "Pembiayaan", "62": "Pembiayaan", "63": "Pembiayaan",
    "64": "Pembiayaan", "65": "Pembiayaan", "66": "Pembiayaan", "67": "Pembiayaan",
}


def robust_anom(sim, lo, hi):
    """Map a similarity to a 0..100 anomaly subscore (low sim -> high score)."""
    if hi <= lo:
        return 0.0
    v = (hi - sim) / (hi - lo)
    return float(max(0.0, min(1.0, v)) * 100.0)


def main():
    parser = argparse.ArgumentParser(description="3-Level Coherence Detection")
    parser.add_argument("--pct-low", type=float, default=PCT_LOW,
                        help="Percentile below which similarity is weak")
    parser.add_argument("--peer-min", type=int, default=PEER_MIN,
                        help="Min peer K/L for L3 flag")
    parser.add_argument("--peer-min-detail", type=int, default=PEER_MIN_DETAIL,
                        help="Min peer K/L for detail table")
    parser.add_argument("--dev-flag", type=float, default=DEV_FLAG,
                        help="Total-variation threshold for L3 flag")
    parser.add_argument("--model", type=str, default=EMBEDDING_MODEL,
                        help="SentenceTransformer model name (default: from common.config.EMBEDDING_MODEL)")
    parser.add_argument("--query-prefix", type=str, default="query: ",
                        help="Prefix prepended to each text before encoding (default: 'query: ' for e5)")
    args = parser.parse_args()

    pct_low = args.pct_low
    peer_min = args.peer_min
    peer_min_detail = args.peer_min_detail
    dev_flag = args.dev_flag
    model_name = args.model
    query_prefix = args.query_prefix

    conn = get_connection()
    cur = conn.cursor()
    t0 = time.time()

    # =====================================================================
    # Load embedding model
    # =====================================================================
    print("=== 3-LEVEL COHERENCE DETECTION ===")
    print("  pct_low=%d  peer_min=%d  dev_flag=%.2f" % (pct_low, peer_min, dev_flag))
    print("  model=%s" % model_name)
    print("  query_prefix=%r" % query_prefix)
    print("  weights: jenis=%.2f L1=%.2f L2=%.2f L3=%.2f" % (W_JENIS, W_L1, W_L2, W_L3))
    print()
    print("Loading embedding model %s ..." % model_name)
    import torch
    torch.set_num_threads(os.cpu_count() or 12)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    print("[%.0fs] model ready (threads=%d)" % (time.time() - t0, torch.get_num_threads()))

    def embed(texts):
        prefixed = [query_prefix + t for t in texts] if query_prefix else list(texts)
        # batch_size besar — hanya 2923 distinct texts, muat dalam 1-2 batch di RAM 33GB
        return model.encode(
            prefixed, normalize_embeddings=True, batch_size=2048,
            show_progress_bar=False, convert_to_numpy=True,
        ).astype(np.float32)

    # =====================================================================
    # Embed all distinct planning texts (program / kegiatan / output)
    # =====================================================================
    print("[%.0fs] Collecting distinct planning texts..." % (time.time() - t0))
    texts = set()
    for col in ("program_uraian", "kegiatan_uraian", "outputkro_uraian"):
        cur.execute(
            (f"SELECT DISTINCT %s FROM {T_COH} "
             "WHERE %s IS NOT NULL AND %s <> ''") % (col, col, col)
        )
        for (t,) in cur.fetchall():
            texts.add(t)
    texts = sorted(texts)
    print("[%.0fs] Embedding %s distinct texts..." % (time.time() - t0, format(len(texts), ",")))
    vecs = embed(texts)
    vmap = {t: vecs[i] for i, t in enumerate(texts)}
    print("[%.0fs] Embeddings done" % (time.time() - t0))

    def cos(a, b):
        va, vb = vmap.get(a), vmap.get(b)
        if va is None or vb is None:
            return None
        return float(np.dot(va, vb))

    # =====================================================================
    # LEVEL 1: Program <-> Kegiatan  (grain: kl, prog, keg)
    # =====================================================================
    print("\n[%.0fs] LEVEL 1: program<->kegiatan" % (time.time() - t0))
    cur.execute(
        f"SELECT DISTINCT kementerian_kode, program_kode, kegiatan_kode, "
        f"program_uraian, kegiatan_uraian FROM {T_COH}"
    )
    pk = {}  # (kl,prog,keg) -> sim
    generic_prog_combos = set()
    dm_prog_combos = set()   # HANYA program Dukungan Manajemen — dipakai utk exclusion L3
                             # (generic_prog_combos juga memuat K/L militer yang L3-nya valid)
    for kl, prog, keg, pu, ku in cur.fetchall():
        c = cos(pu, ku)
        if c is not None:
            pk[(kl, prog, keg)] = c
        pu_lower = (pu or '').lower()
        # Fix F1: Program Dukungan Manajemen adalah catch-all DIPA
        if any(p in pu_lower for p in GENERIC_PROGRAM_PATTERNS):
            generic_prog_combos.add((kl, prog, keg))
            dm_prog_combos.add((kl, prog, keg))
        # Fix F2: Military K/L — model under-scores domain-specific terminology
        # (sama dengan MILITARY_DOMAIN_KL yang sudah dipakai di L2 / Fix E1)
        elif kl in MILITARY_DOMAIN_KL:
            generic_prog_combos.add((kl, prog, keg))
    sims1 = np.array(list(pk.values()), dtype=np.float64)
    lo1, hi1 = np.percentile(sims1, 5), np.percentile(sims1, 95)
    thr1 = np.percentile(sims1, pct_low)
    print("[%.0fs]   %s prog-keg pairs | sim p5/p50/p95 = %.3f/%.3f/%.3f | weak<%.3f"
          % (time.time() - t0, format(len(pk), ","), lo1, np.percentile(sims1, 50), hi1, thr1))

    # =====================================================================
    # LEVEL 2: Kegiatan <-> Output  (grain: kl, prog, keg, out)
    # =====================================================================
    print("\n[%.0fs] LEVEL 2: kegiatan<->output" % (time.time() - t0))
    cur.execute(
        f"SELECT DISTINCT kementerian_kode, program_kode, kegiatan_kode, outputkro_kode, "
        f"kegiatan_uraian, outputkro_uraian FROM {T_COH}"
    )
    ko = {}  # (kl,prog,keg,out) -> sim
    generic_out_combos = set()
    for kl, prog, keg, out, ku, ou in cur.fetchall():
        c = cos(ku, ou)
        if c is not None:
            ko[(kl, prog, keg, out)] = c
        ou_lower = (ou or '').lower()
        # Fix F3: EB-series output codes (EBA/EBB/EBC/EBD) adalah output
        # internal/rutin per klasifikasi resmi Kemenkeu — konsisten dengan
        # script 10 yang mengklasifikasikan EB sebagai routine_support.
        # Catatan: L3 tetap bisa mendeteksi anomali komposisi akun pada output EB.
        if out and out.upper().startswith('EB'):
            generic_out_combos.add((kl, prog, keg, out))
        # Generic outputs: model cannot score these against kegiatan
        elif any(p in ou_lower for p in GENERIC_OUTPUT_PATTERNS):
            generic_out_combos.add((kl, prog, keg, out))
        # Fix E1: military/defense K/L with operational defense outputs —
        # model consistently under-scores these due to technical jargon mismatch.
        # Only suppress outputs that are clearly in the defense/security operational
        # domain; generic management outputs under defense kegiatan are kept.
        elif (kl in MILITARY_DOMAIN_KL
              and any(p in ou_lower for p in MILITARY_DOMAIN_OUTPUT_PATTERNS)):
            generic_out_combos.add((kl, prog, keg, out))
    sims2 = np.array(list(ko.values()), dtype=np.float64)
    lo2, hi2 = np.percentile(sims2, 5), np.percentile(sims2, 95)
    thr2 = np.percentile(sims2, pct_low)
    print("[%.0fs]   %s keg-out pairs | sim p5/p50/p95 = %.3f/%.3f/%.3f | weak<%.3f"
          % (time.time() - t0, format(len(ko), ","), lo2, np.percentile(sims2, 50), hi2, thr2))

    # =====================================================================
    # LEVEL 3: Output <-> Akun  (peer comparison of belanja composition)
    # =====================================================================
    print("\n[%.0fs] LEVEL 3: output<->akun peer comparison" % (time.time() - t0))

    # Peer profile via MEAN-OF-SHARES (Fix L3, 2026-06-14): tiap K/L = satu
    # observasi dengan BOBOT SAMA, bukan pooled pagu-weighted. Pooling lama membuat
    # satu K/L ber-pagu raksasa mendefinisikan 'norma' sehingga memunculkan anomali
    # palsu (terbukti ~17% temuan L3 lama: mis. output QMA, satu K/L Rp1,7T modal
    # menutupi 28 K/L lain yang barang). Mean-of-shares sesuai metode terdokumentasi
    # dan benar untuk pertanyaan 'apakah komposisi K/L ini tidak lazim dibanding peer'.
    cur.execute(
        f"SELECT outputkro_kode, kementerian_kode, LEFT(akun_kode,2) cat, "
        "CAST(SUM(total_pagu) AS DOUBLE) "
        f"FROM {T_PAGU} WHERE total_pagu > 0 "
        "GROUP BY outputkro_kode, kementerian_kode, LEFT(akun_kode,2)"
    )
    out_kl_cat = {}  # out -> kl -> {cat: pagu}
    for out, kl, cat, pagu in cur.fetchall():
        out_kl_cat.setdefault(out, {}).setdefault(kl, {})[cat] = pagu
    out_kl_share = {}  # out -> kl -> {cat: share}  (tiap K/L dinormalisasi sendiri)
    for out, klmap in out_kl_cat.items():
        sh = {}
        for kl, cats in klmap.items():
            tot = sum(cats.values())
            if tot > 0:
                sh[kl] = {c: v / tot for c, v in cats.items()}
        out_kl_share[out] = sh
    peer_count = {out: len(sh) for out, sh in out_kl_share.items()}
    print("[%.0fs]   peer profiles (mean-of-shares) for %s output codes"
          % (time.time() - t0, format(len(out_kl_share), ",")))

    # Own profile per (kl,prog,keg,out)
    cur.execute(
        f"SELECT kementerian_kode, program_kode, kegiatan_kode, outputkro_kode, "
        "LEFT(akun_kode,2) cat, CAST(SUM(total_pagu) AS DOUBLE) "
        f"FROM {T_PAGU} WHERE total_pagu > 0 "
        "GROUP BY kementerian_kode, program_kode, kegiatan_kode, outputkro_kode, LEFT(akun_kode,2)"
    )
    own = {}  # combo -> {cat: pagu}
    for kl, prog, keg, out, cat, pagu in cur.fetchall():
        own.setdefault((kl, prog, keg, out), {})[cat] = pagu
    print("[%.0fs]   own profiles for %s combos" % (time.time() - t0, format(len(own), ",")))

    dev_map = {}            # combo -> deviation (0..1)
    adjusted_pc_map = {}    # combo -> peer count excluding self (Fix 3A)
    detail_rows = []
    n_detail_skipped = 0
    for combo, cats in own.items():
        kl, prog, keg, out = combo
        # L3 exclusion (Fix audit, 2026-06-14): program "Dukungan Manajemen"
        # dikecualikan dari L3 — overhead administratif lintas-K/L bervariasi wajar,
        # komposisi akun-nya bukan sinyal kebijakan substantif (sebelumnya ~52%
        # temuan "valid" koherensi berasal dari program manajemen = noise).
        # CATATAN: pakai dm_prog_combos (HANYA Dukungan Manajemen), BUKAN
        # generic_prog_combos/generic_out_combos — keduanya memuat K/L militer &
        # EB-series yang komposisi akun L3-nya tetap valid untuk dibandingkan.
        if (kl, prog, keg) in dm_prog_combos:
            continue
        klshare = out_kl_share.get(out)
        tot = sum(cats.values())
        if not klshare or tot <= 0:
            continue

        # peer = rata-rata share atas K/L LAIN (self-excluded), bobot sama tiap K/L
        peers = [k for k in klshare if k != kl]
        pc = len(peers)
        if pc <= 0:
            continue  # hanya K/L ini yang punya output ini — tak ada peer pembanding
        psh = {}
        for pkl in peers:
            for c, s in klshare[pkl].items():
                psh[c] = psh.get(c, 0.0) + s
        psh = {c: v / pc for c, v in psh.items()}

        osh = {c: v / tot for c, v in cats.items()}
        allcats = set(osh) | set(psh)
        dev = 0.5 * sum(abs(osh.get(c, 0.0) - psh.get(c, 0.0)) for c in allcats)
        dev_map[combo] = dev
        adjusted_pc_map[combo] = pc
        unexpected = sorted(
            ((c, osh.get(c, 0.0) - psh.get(c, 0.0)) for c in allcats),
            key=lambda x: x[1], reverse=True,
        )
        top_unexpected = [
            {"akun": c, "label": CAT_LABELS.get(c, "Lainnya"),
             "own": round(osh.get(c, 0.0), 3), "peer": round(psh.get(c, 0.0), 3)}
            for c, d in unexpected if d > 0.15
        ][:3]
        if pc >= peer_min_detail:
            detail_rows.append((
                combo[0], combo[1], combo[2], combo[3],
                round((1 - dev) * 100, 2), round(dev * 100, 2), pc,
                json.dumps({
                    "own": {c: round(s, 3) for c, s in sorted(osh.items())},
                    "peer": {c: round(s, 3) for c, s in sorted(psh.items())},
                    "deviation": round(dev, 3), "peer_count": pc,
                    "top_unexpected": top_unexpected,
                }, ensure_ascii=False),
            ))
        else:
            n_detail_skipped += 1
    print("[%.0fs]   computed deviation for %s combos" % (time.time() - t0, format(len(dev_map), ",")))
    print("[%.0fs]   detail rows: %s included, %s skipped (peer < %d)"
          % (time.time() - t0, format(len(detail_rows), ","),
             format(n_detail_skipped, ","), peer_min_detail))

    # =====================================================================
    # Build the single PK'd combo table that drives all UPDATEs
    # =====================================================================
    print("\n[%.0fs] Building tmp_combo (output grain)..." % (time.time() - t0))
    combos = set(ko) | set(dev_map)
    rows = []
    n_l1 = n_l2 = n_l3 = 0
    for (kl, prog, keg, out) in combos:
        sim1 = pk.get((kl, prog, keg))
        sim2 = ko.get((kl, prog, keg, out))
        dev = dev_map.get((kl, prog, keg, out))
        # Fix 3A: use adjusted peer count (self-excluded)
        pc = adjusted_pc_map.get((kl, prog, keg, out), peer_count.get(out, 0))

        l1_coh = round(sim1 * 100, 2) if sim1 is not None else None
        l2_coh = round(max(0.0, sim2) * 100, 2) if sim2 is not None else None
        l3_coh = round((1 - dev) * 100, 2) if dev is not None else None
        l3_score = round(dev * 100, 2) if dev is not None else None

        l1_anom = robust_anom(sim1, lo1, hi1) if sim1 is not None else 0.0
        l2_anom = robust_anom(sim2, lo2, hi2) if sim2 is not None else 0.0
        l3_anom = (dev * 100.0) if dev is not None else 0.0

        flags = []
        if (sim1 is not None and sim1 < thr1
                and (kl, prog, keg) not in generic_prog_combos):
            flags.append("level1_program_kegiatan_lemah"); n_l1 += 1
        if (sim2 is not None and sim2 < thr2
                and (kl, prog, keg, out) not in generic_out_combos):
            flags.append("level2_kegiatan_output_lemah"); n_l2 += 1
        # Fix 3B: higher threshold for internal support output codes (EBA/EBB/EBC/EBD)
        l3_thr = DEV_FLAG_INTERNAL if out.startswith("EB") else dev_flag
        if dev is not None and pc >= peer_min and dev >= l3_thr:
            flags.append("level3_akun_tidak_lazim"); n_l3 += 1

        rows.append((
            kl, prog, keg, out, l1_coh, l2_coh, l3_coh, l3_score,
            round(l1_anom, 2), round(l2_anom, 2), round(l3_anom, 2),
            json.dumps(flags, ensure_ascii=False) if flags else None,
        ))
    print("[%.0fs]   %s combos | flags L1=%s L2=%s L3=%s"
          % (time.time() - t0, format(len(rows), ","),
             format(n_l1, ","), format(n_l2, ","), format(n_l3, ",")))

    cur.execute("DROP TABLE IF EXISTS tmp_combo")
    cur.execute(
        "CREATE TABLE tmp_combo ("
        " kementerian_kode CHAR(3), program_kode CHAR(2), kegiatan_kode CHAR(4), outputkro_kode CHAR(3),"
        " l1_coh DECIMAL(5,2), l2_coh DECIMAL(5,2), l3_coh DECIMAL(5,2), l3_score DECIMAL(5,2),"
        " l1_anom DECIMAL(5,2), l2_anom DECIMAL(5,2), l3_anom DECIMAL(5,2), flags JSON,"
        " PRIMARY KEY (kementerian_kode, program_kode, kegiatan_kode, outputkro_kode)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    conn.commit()
    for i in range(0, len(rows), 5000):
        cur.executemany(
            "INSERT INTO tmp_combo VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows[i:i + 5000],
        )
    conn.commit()
    print("[%.0fs]   tmp_combo inserted" % (time.time() - t0))

    # Index on coherence table for the join (kl,prog,keg,out).
    cur.execute(f"SHOW INDEX FROM {T_COH} WHERE Key_name='idx_ko'")
    if not cur.fetchall():
        print("[%.0fs] Adding idx_ko..." % (time.time() - t0))
        cur.execute(
            f"ALTER TABLE {T_COH} "
            "ADD INDEX idx_ko (kementerian_kode, program_kode, kegiatan_kode, outputkro_kode)"
        )
        conn.commit()

    # =====================================================================
    # Single indexed UPDATE: write all level columns + composite + flags
    # =====================================================================
    print("[%.0fs] Applying level columns to 1.5M rows..." % (time.time() - t0))
    cur.execute(
        (f"UPDATE {T_COH} c JOIN tmp_combo t "
         " ON c.kementerian_kode=t.kementerian_kode AND c.program_kode=t.program_kode "
         " AND c.kegiatan_kode=t.kegiatan_kode AND c.outputkro_kode=t.outputkro_kode "
         "SET c.prog_keg_coherence=t.l1_coh, c.keg_out_coherence=t.l2_coh, "
         " c.out_komp_coherence=t.l3_coh, c.akun_komposisi_score=t.l3_score, "
         " c.anomaly_flags=t.flags, "
         " c.coherence_score=ROUND(%s*c.jenis_anomaly_score + %s*t.l1_anom + %s*t.l2_anom + %s*t.l3_anom, 2)")
        % (W_JENIS, W_L1, W_L2, W_L3)
    )
    conn.commit()
    print("[%.0fs]   updated %s rows" % (time.time() - t0, format(cur.rowcount, ",")))
    cur.execute("DROP TABLE IF EXISTS tmp_combo")
    conn.commit()

    # =====================================================================
    # Level-3 detail table (rich per-output peer comparison)
    # =====================================================================
    print(f"[%.0fs] Writing {T_COH_AKUN} (level-3 detail)..." % (time.time() - t0))
    cur.execute(f"DROP TABLE IF EXISTS {T_COH_AKUN}")
    cur.execute(
        f"CREATE TABLE {T_COH_AKUN} ("
        " kementerian_kode CHAR(3), program_kode CHAR(2), kegiatan_kode CHAR(4), outputkro_kode CHAR(3),"
        " out_komp_coherence DECIMAL(5,2), akun_komposisi_score DECIMAL(5,2), peer_count INT,"
        " akun_detail JSON,"
        " PRIMARY KEY (kementerian_kode, program_kode, kegiatan_kode, outputkro_kode),"
        " INDEX idx_score (akun_komposisi_score)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    conn.commit()
    for i in range(0, len(detail_rows), 5000):
        cur.executemany(
            f"INSERT INTO {T_COH_AKUN} VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            detail_rows[i:i + 5000],
        )
    conn.commit()
    print("[%.0fs]   %s detail rows" % (time.time() - t0, format(len(detail_rows), ",")))

    # =====================================================================
    # Summary
    # =====================================================================
    print("\n" + "=" * 60)
    print("MULTI-LEVEL COHERENCE SUMMARY")
    print("=" * 60)
    cur.execute(
        f"SELECT "
        " AVG(prog_keg_coherence), AVG(keg_out_coherence), AVG(out_komp_coherence), "
        f" AVG(akun_komposisi_score), AVG(coherence_score) FROM {T_COH}"
    )
    a = cur.fetchone()
    print("avg L1 prog_keg   : %.2f" % (a[0] or 0))
    print("avg L2 keg_out    : %.2f" % (a[1] or 0))
    print("avg L3 out_komp   : %.2f" % (a[2] or 0))
    print("avg akun_score    : %.2f" % (a[3] or 0))
    print("avg composite     : %.2f" % (a[4] or 0))
    for flag in ("level1_program_kegiatan_lemah", "level2_kegiatan_output_lemah", "level3_akun_tidak_lazim"):
        cur.execute(
            f"SELECT COUNT(*), CAST(SUM(total_pagu) AS DOUBLE) FROM {T_COH} "
            "WHERE JSON_CONTAINS(anomaly_flags, %s)", (json.dumps(flag),)
        )
        cnt, pagu = cur.fetchone()
        cur.execute(
            f"SELECT COUNT(DISTINCT kementerian_kode, program_kode, kegiatan_kode) "
            f"FROM {T_COH} WHERE JSON_CONTAINS(anomaly_flags, %s)",
            (json.dumps(flag),)
        )
        uniq = cur.fetchone()[0] or 0
        print("  %-32s: %10s rows | %6s unik (kl,prog,keg) | Rp %.1f T"
              % (flag, format(cnt or 0, ","), format(uniq, ","), (pagu or 0) / 1e12))

    # embedding model diagnosis
    print("\n--- embedding model diagnosis ---")
    print("  model: %s" % model_name)
    if "e5" in model_name.lower():
        print("  NOTE: e5 model with query_prefix=%r" % query_prefix)
        print("  Indonesian-specific fine-tune, better for birokrasi/militer terms.")
    else:
        print("  NOTE: bge-m3 is a multilingual model (1024-dim). It may under-estimate")
        print("  similarity for Indonesian government/birokrasi/militer compound terms.")
    print("  Current pct_low=%d balances coverage vs false positives." % pct_low)
    print("  For stricter L1/L2, re-run with --pct-low 3")
    print("  For more L1/L2 coverage, re-run with --pct-low 10")

    print(f"\n[%.0fs] Done. Tables: {T_COH}, {T_COH_AKUN}" % (time.time() - t0))
    conn.close()


if __name__ == "__main__":
    main()
