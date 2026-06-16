"""
reason_parallel.py — Re-run reasoning TreasurAI oss120b secara PARALEL.

oss120b butuh ~15-25s/call (generasi token), bukan throttle. Server menerima
banyak koneksi serempak, jadi paralelisasi (default 8 worker) memangkas waktu
total ~8x. Resume-safe: hanya proses llm_reasoning IS NULL.

Reasoning via TreasurAI oss120b.

Usage:
  python scripts/reason_parallel.py align            # alignment (ddac_anomaly)
  python scripts/reason_parallel.py coh              # coherence L3 + L1/L2
  python scripts/reason_parallel.py align 12         # 12 worker
"""
import sys, os, json, time, threading
import concurrent.futures as cf
sys.path.insert(0, "scripts")

from common.config import (TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS,
                           TABLE_ANOMALY, TABLE_PAGU_AKUN, TABLE_COHERENCE, TABLE_COHERENCE_AKUN)
from common.db import get_connection
from common.verdict import parse_verdict
from common.kl_context import get_kl_mandate_context
from common.treasurai_call import call_with_timeout

MODE    = sys.argv[1] if len(sys.argv) > 1 else "align"
WORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
MODEL   = "oss120b"
URL     = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
KEY     = TREASURAI_API_KEY
HDR     = {"Content-Type": "application/json", "X-API-Key": KEY}
MAXTOK  = 750   # cukup untuk 4 kalimat + tag VERDICT (450 sempat memotong tag)

T_ANOMALY, T_PAGU = TABLE_ANOMALY, TABLE_PAGU_AKUN
T_COH, T_COH_AKUN = TABLE_COHERENCE, TABLE_COHERENCE_AKUN

ALIGN_SYS = (
    "Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. "
    "Tugasmu menilai apakah satu item belanja DIPA selaras dengan mandat prioritas "
    "nasional (RPJMN/RKP) yang diberikan kepada K/L tersebut.\n\n"
    "PENTING — skor kemiripan rendah BUKAN otomatis berarti tidak selaras (bisa beda "
    "nomenklatur, atau mekanisme pembiayaan yang melaksanakan KP secara tidak langsung). "
    "Daftar mandat BISA TIDAK LENGKAP akibat reorganisasi kementerian Okt 2024, jadi "
    "pertimbangkan juga domain/tupoksi K/L.\n\n"
    "Tentukan SATU verdict (KONSERVATIF, hindari tuduhan keliru):\n"
    "- false_positive : belanja secara substansi mendukung prioritas nasional di domain "
    "K/L ini (tercantum di mandat atau wajar berdasarkan tupoksi); skor rendah akibat beda "
    "nomenklatur/mekanisme.\n"
    "- valid          : belanja JELAS di luar seluruh prioritas nasional DAN domain inti K/L.\n"
    "- manual_review  : ada indikasi keterkaitan namun bukti tak cukup, atau mandat tampak "
    "tidak lengkap.\n\n"
    "Jawab maksimal 4 kalimat Bahasa Indonesia formal (penjelasan + 1 rekomendasi). "
    "BARIS TERAKHIR wajib persis: VERDICT: valid | VERDICT: false_positive | VERDICT: manual_review")

COH_SYS = (
    "Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. "
    "Tugasmu menilai apakah pola belanja (komposisi akun / koherensi nama struktur) suatu "
    "output DIPA yang menyimpang dari peer merupakan masalah nyata atau dapat dijustifikasi.\n\n"
    "PENTING — menyimpang dari peer BUKAN otomatis salah. Pola berbeda sering sesuai sifat "
    "program (mis. Makan Bergizi 100% barang; beasiswa 100% bantuan sosial). Bila deviasi "
    "DAPAT dijustifikasi oleh mandat/sifat program → false_positive.\n\n"
    "Tentukan SATU verdict:\n"
    "- valid          : menyimpang signifikan DAN tak dapat dijustifikasi mandat/sifat program.\n"
    "- false_positive : deviasi dapat dijustifikasi mandat khusus/sifat program.\n"
    "- manual_review  : bukti tak cukup.\n\n"
    "Jawab maksimal 4 kalimat Bahasa Indonesia formal (penjelasan + 1 rekomendasi). "
    "BARIS TERAKHIR wajib persis: VERDICT: valid | VERDICT: false_positive | VERDICT: manual_review")

CAT = {"51": "Belanja Pegawai", "52": "Belanja Barang", "53": "Belanja Modal",
       "54": "Belanja Bunga Utang", "55": "Belanja Subsidi", "57": "Belanja Bantuan Sosial",
       "58": "Belanja Lain-lain"}

REVMAP = {"false_positive": "dismissed", "valid": "confirmed", "manual_review": "needs_review"}

write_lock = threading.Lock()


def call(prompt, sysp):
    r, err = call_with_timeout(
        URL, {"prompt": prompt, "session_id": None, "system_prompt": sysp,
              "temperature": 0.1, "max_tokens": MAXTOK}, HDR,
        connect_to=10, read_to=80, hard_to=90, retries=1, cooldown=5)
    if r is None or r.status_code != 200:
        return None
    data = r.json()
    return (data.get("response") or data.get("text") or data.get("content") or str(data))[:2000]


# ── ALIGNMENT ────────────────────────────────────────────────────────────────

def run_align():
    conn = get_connection(); cur = conn.cursor()
    # cache mandat per K/L
    cur.execute(f"SELECT DISTINCT kementerian_kode FROM {T_ANOMALY} "
                "WHERE anomaly_type IN ('policy_orphan','weak_alignment')")
    mandate = {}
    for (kl,) in cur.fetchall():
        mandate[kl] = get_kl_mandate_context(cur, kl)
    cur.execute(f"""
        SELECT a.id, a.anomaly_type, a.kementerian_kode, a.kementerian_uraian,
               a.alignment_score,
               (SELECT p.alignment_text FROM {T_PAGU} p WHERE p.id=a.pagu_id),
               a.top3_matches, a.mandate_match_code, a.mandate_match_name, a.mandate_match_score
        FROM {T_ANOMALY} a
        WHERE a.anomaly_type IN ('policy_orphan','weak_alignment') AND a.llm_reasoning IS NULL
        ORDER BY a.review_priority DESC""")
    items = cur.fetchall()
    conn.close()
    print("[align] %d item pending, %d worker" % (len(items), WORKERS), flush=True)

    def build(it):
        aid, atype, kl, kln, score, txt, top3j, mc, mn, ms = it
        top3 = json.loads(top3j) if top3j else []
        t3 = "".join("- %s: %s (skor %s)\n" % (t.get("code", ""), (t.get("name", "") or "")[:100],
                     t.get("score", "")) for t in top3[:3])
        msec = (mandate.get(kl) + "\n") if mandate.get(kl) else \
            "Mandat K/L %s: TIDAK ADA penugasan KP eksplisit di Lampiran III.\n" % kl
        mline = ("KP mandat terdekat: %s — %s (skor %.0f/100)\n" % (mc, (mn or "")[:120], float(ms or 0))) if mc else ""
        label = "Policy Orphan" if atype == "policy_orphan" else "Weak Alignment"
        q = ("Nilai: apakah belanja ini termasuk mandat/domain K/L? Jika ada KP yang secara "
             "substansi mencakupnya (meski beda nomenklatur/mekanisme) → false_positive; jika "
             "jelas di luar semua prioritas & domain → valid; jika ragu → manual_review.")
        return ("[%s] Item belanja DIPA:\nK/L: %s - %s\nProg/Keg/Out: %s\n"
                "Skor kemiripan tertinggi: %.0f/100\n\n=== MANDAT RPJMN/RKP (acuan utama) ===\n%s%s\n"
                "=== Tetangga semantik lintas K/L (info tambahan) ===\n%s\n%s") % (
                label, kl, kln or "", (txt or "")[:300], float(score or 0), msec, mline, t3, q)

    def work(it):
        reasoning = call(build(it), ALIGN_SYS)
        if not reasoning:
            return (it[0], None, None, None)
        v = parse_verdict(reasoning)
        return (it[0], reasoning, v, REVMAP.get(v, "pending"))

    process(items, work, write_align)


def write_align(results):
    conn = get_connection(); cur = conn.cursor()
    for aid, reasoning, v, st in results:
        if reasoning is None:
            continue
        cur.execute(f"UPDATE {T_ANOMALY} SET llm_reasoning=%s, llm_model=%s, "
                    "treasurai_verdict=%s, review_status=%s WHERE id=%s",
                    (reasoning, MODEL, v, st, aid))
    conn.commit(); conn.close()


# ── COHERENCE ────────────────────────────────────────────────────────────────

def fmt_akun(dj):
    try:
        d = json.loads(dj) if isinstance(dj, str) else dj
        own, peer = d.get("own", {}), d.get("peer", {})
        lines = ["Deviasi total: %.1f%% vs %d K/L peer" % (d.get("deviation", 0) * 100, d.get("peer_count", 0))]
        for a in sorted(set(list(own) + list(peer))):
            o, p = float(own.get(a, 0)) * 100, float(peer.get(a, 0)) * 100
            if abs(o - p) > 5:
                lines.append("  %-22s (%s): K/L ini=%3.0f%% | peer=%3.0f%%" % (CAT.get(a, "Akun " + a), a, o, p))
        return "\n".join(lines)
    except Exception as e:
        return "(parse err %s)" % e


def run_coh():
    conn = get_connection(); cur = conn.cursor()
    # L3 items
    cur.execute(f"""
        SELECT ca.kementerian_kode, MAX(c.kementerian_uraian), ca.program_kode, MAX(c.program_uraian),
               ca.kegiatan_kode, MAX(c.kegiatan_uraian), ca.outputkro_kode, MAX(c.outputkro_uraian),
               ca.peer_count, ca.akun_detail, SUM(c.total_pagu)
        FROM {T_COH_AKUN} ca JOIN {T_COH} c
          ON c.kementerian_kode=ca.kementerian_kode AND c.program_kode=ca.program_kode
         AND c.kegiatan_kode=ca.kegiatan_kode AND c.outputkro_kode=ca.outputkro_kode
        WHERE ca.akun_komposisi_score>=40 AND c.llm_reasoning IS NULL
        GROUP BY ca.kementerian_kode, ca.program_kode, ca.kegiatan_kode, ca.outputkro_kode,
                 ca.peer_count, ca.akun_detail
        ORDER BY SUM(c.total_pagu) DESC""")
    l3 = [("l3",) + r for r in cur.fetchall()]
    # L1/L2 items
    cur.execute(f"""
        SELECT kementerian_kode, MAX(kementerian_uraian), program_kode, MAX(program_uraian),
               kegiatan_kode, MAX(kegiatan_uraian), MIN(prog_keg_coherence), MIN(keg_out_coherence),
               anomaly_flags, SUM(total_pagu)
        FROM {T_COH}
        WHERE (JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level1_program_kegiatan_lemah'))
            OR JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level2_kegiatan_output_lemah')))
          AND llm_reasoning IS NULL
        GROUP BY kementerian_kode, program_kode, kegiatan_kode, anomaly_flags
        ORDER BY SUM(total_pagu) DESC""")
    l12 = [("l12",) + r for r in cur.fetchall()]
    mandate = {}
    for it in l3 + l12:
        kl = it[1]
        if kl not in mandate:
            mandate[kl] = get_kl_mandate_context(cur, kl)
    conn.close()
    items = l3 + l12
    print("[coh] %d item (L3=%d, L1/L2=%d), %d worker" % (len(items), len(l3), len(l12), WORKERS), flush=True)

    def work(it):
        kind = it[0]
        kl = it[1]
        msec = ("\n" + mandate.get(kl) + "\n") if mandate.get(kl) else ""
        if kind == "l3":
            (_, kl, kln, prog, progn, keg, kegn, out, outn, pc, adetail, pagu) = it
            body = fmt_akun(adetail)
            prompt = ("Anomali Koherensi L3 — Komposisi Akun vs Peer:\nK/L: %s - %s\nProgram: %s - %s\n"
                      "Kegiatan: %s - %s\nOutput: %s - %s\n\n%s\nTotal pagu: Rp %.2f T\n%s\n"
                      "Apakah pola belanja yang berbeda dari %d K/L peer dapat dijustifikasi oleh "
                      "mandat RPJMN/RKP atau sifat program?") % (
                      kl, (kln or "")[:60], prog, (progn or "")[:80], keg, (kegn or "")[:80],
                      out, (outn or "")[:80], body, float(pagu) / 1e12, msec, pc)
            key = ("l3", kl, prog, keg, out)
        else:
            (_, kl, kln, prog, progn, keg, kegn, l1, l2, flagsj, pagu) = it
            flags = json.loads(flagsj) if flagsj else []
            li = []
            if "level1_program_kegiatan_lemah" in flags:
                li.append("L1 Program↔Kegiatan: %.1f/100" % float(l1 or 0))
            if "level2_kegiatan_output_lemah" in flags:
                li.append("L2 Kegiatan↔Output: %.1f/100" % float(l2 or 0))
            prompt = ("Anomali Koherensi Semantik (L1/L2):\nK/L: %s - %s\nProgram: %s - %s\n"
                      "Kegiatan: %s - %s\n\n%s\nPagu: Rp %.3f T\n%s\n"
                      "Mengapa similarity rendah? Perbedaan nomenklatur (false_positive) atau "
                      "incoherence struktural genuine (valid)?") % (
                      kl, (kln or "")[:60], prog, (progn or "")[:80], keg, (kegn or "")[:80],
                      "\n".join(li), float(pagu) / 1e12, msec)
            key = ("l12", kl, prog, keg, None)
        reasoning = call(prompt, COH_SYS)
        if not reasoning:
            return (key, None, None, None)
        v = parse_verdict(reasoning)
        return (key, reasoning, v, REVMAP.get(v, "pending"))

    process(items, work, write_coh)


def write_coh(results):
    conn = get_connection(); cur = conn.cursor()
    for key, reasoning, v, st in results:
        if reasoning is None:
            continue
        kind, kl, prog, keg, out = key
        if kind == "l3":
            cur.execute(f"""UPDATE {T_COH} SET llm_reasoning=%s, llm_model=%s,
                treasurai_verdict=%s, review_status_coherence=%s
                WHERE kementerian_kode=%s AND program_kode=%s AND kegiatan_kode=%s
                  AND outputkro_kode=%s AND llm_reasoning IS NULL""",
                (reasoning, MODEL, v, st, kl, prog, keg, out))
        else:
            cur.execute(f"""UPDATE {T_COH} SET llm_reasoning=%s, llm_model=%s,
                treasurai_verdict=%s, review_status_coherence=%s
                WHERE kementerian_kode=%s AND program_kode=%s AND kegiatan_kode=%s
                  AND llm_reasoning IS NULL""",
                (reasoning, MODEL, v, st, kl, prog, keg))
    conn.commit(); conn.close()


# ── pool driver ──────────────────────────────────────────────────────────────

def process(items, work, writer):
    t0 = time.time(); done = 0; buf = []
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(work, it) for it in items]
        for fut in cf.as_completed(futs):
            res = fut.result()
            buf.append(res)
            done += 1
            if len(buf) >= 10:
                with write_lock:
                    writer(buf)
                buf = []
            if done % 25 == 0:
                el = time.time() - t0
                print("  %d/%d  (%.1f/min, %.0fs)" % (done, len(items), done / el * 60, el), flush=True)
    if buf:
        writer(buf)
    print("SELESAI %d item dalam %.0f menit" % (len(items), (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    if MODE == "align":
        run_align()
    elif MODE == "coh":
        run_coh()
    else:
        print("mode: align | coh")
