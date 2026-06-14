"""
15_coherence_reasoning.py
TreasurAI reasoning untuk anomali koherensi internal DIPA.

Target:
  L3 (default ON)  — top-N by pagu, deviasi komposisi akun vs peer
  L1/L2 (default OFF) — top-N by pagu, semantic similarity program/kegiatan/output lemah

Model: oss120b
Kolom ditambahkan ke ddac_coherence_<year> jika belum ada.

Usage:
  python scripts/15_coherence_reasoning.py               # L3 top-30
  python scripts/15_coherence_reasoning.py 50            # L3 top-50
  python scripts/15_coherence_reasoning.py 30 20         # L3 top-30, L1/L2 top-20
"""
import json, requests, time, sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix Windows console encoding untuk karakter Unicode dari TreasurAI
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from common.config import TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS, TABLE_COHERENCE, TABLE_COHERENCE_AKUN
from common.db import get_connection

T_COH      = TABLE_COHERENCE
T_COH_AKUN = TABLE_COHERENCE_AKUN
from common.verdict import parse_verdict
from common.kl_context import get_kl_mandate_context
from common.treasurai_call import call_with_timeout

# === CONFIG ===
MODEL         = "oss120b"
TREASURY_URL  = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
TREASURY_KEY  = TREASURAI_API_KEY
LIMIT_L3      = int(sys.argv[1]) if len(sys.argv) > 1 else 30
LIMIT_L1L2    = int(sys.argv[2]) if len(sys.argv) > 2 else 0   # default off

SYSTEM_PROMPT = """Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. \
Tugasmu menilai apakah pola belanja (komposisi akun, atau koherensi nama struktur) suatu \
output DIPA yang menyimpang dari peer merupakan masalah nyata atau dapat dijustifikasi.

PENTING — menyimpang dari peer BUKAN otomatis berarti salah. Pola berbeda sering JUSTRU \
sesuai sifat program (mis. program Makan Bergizi 100% belanja barang; beasiswa 100% bantuan \
sosial). Bila deviasi DAPAT dijustifikasi oleh mandat/sifat program → itu false_positive.

Tentukan SATU verdict:
- valid          : pola menyimpang signifikan DAN tidak dapat dijustifikasi oleh mandat \
RPJMN/RKP maupun sifat program → perlu ditindaklanjuti.
- false_positive : deviasi nyata tetapi DAPAT dijustifikasi oleh mandat khusus atau sifat \
program → bukan masalah.
- manual_review  : bukti tidak cukup untuk memutuskan.

Format jawaban (Bahasa Indonesia formal, maksimal 4 kalimat):
1. Penjelasan singkat penyebab pola berbeda dan kaitannya dengan mandat/sifat program.
2. Rekomendasi 1 kalimat.
Lalu BARIS TERAKHIR wajib persis: VERDICT: valid | VERDICT: false_positive | VERDICT: manual_review"""

CAT_LABELS = {
    "51": "Belanja Pegawai",
    "52": "Belanja Barang",
    "53": "Belanja Modal",
    "54": "Belanja Bunga Utang",
    "55": "Belanja Subsidi",
    "57": "Belanja Bantuan Sosial",
    "58": "Belanja Lain-lain",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def ensure_columns(cur, conn):
    """Tambah kolom reasoning ke coherence table bila belum ada."""
    additions = [
        ("llm_reasoning",          "TEXT"),
        ("llm_model",              "VARCHAR(50)"),
        ("treasurai_verdict",      "VARCHAR(30)"),
        ("review_status_coherence","VARCHAR(30) DEFAULT 'pending'"),
    ]
    added = []
    for col, defn in additions:
        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME   = '{T_COH}'
              AND COLUMN_NAME  = %s
        """, (col,))
        if cur.fetchone()[0] == 0:
            cur.execute((f"ALTER TABLE {T_COH} ADD COLUMN %s %s") % (col, defn))
            added.append(col)
    if added:
        conn.commit()
        print("Kolom ditambahkan: %s" % ", ".join(added))
    else:
        print("Semua kolom reasoning sudah ada.")


def fmt_akun(detail_json):
    """Format akun_detail JSON → teks singkat untuk prompt."""
    try:
        d   = json.loads(detail_json) if isinstance(detail_json, str) else detail_json
        own = d.get("own",  {})
        peer = d.get("peer", {})
        dev  = d.get("deviation", 0)
        pc   = d.get("peer_count", 0)
        top  = d.get("top_unexpected", [])

        lines = ["Deviasi total: %.1f%% vs %d K/L peer" % (dev * 100, pc)]
        # Tampilkan semua akun dengan selisih > 5%
        for akun in sorted(set(list(own.keys()) + list(peer.keys()))):
            o = float(own.get(akun, 0)) * 100
            p = float(peer.get(akun, 0)) * 100
            if abs(o - p) > 5:
                label = CAT_LABELS.get(akun, "Akun %s" % akun)
                lines.append("  %-25s (%s): K/L ini=%3.0f%% | rata-rata peer=%3.0f%%" % (
                    label, akun, o, p))
        return "\n".join(lines)
    except Exception as e:
        return "(parse error: %s)" % str(e)


def call_treasurai(prompt):
    """Panggil TreasurAI, return (reasoning, verdict, review_status) atau None jika error.
    Resilient: read-timeout pendek + retry ringan; item gagal di-skip & diulang next run."""
    r, err = call_with_timeout(
        TREASURY_URL,
        {"prompt": prompt, "session_id": None,
         "system_prompt": SYSTEM_PROMPT, "temperature": 0.1, "max_tokens": 700},
        {"Content-Type": "application/json", "X-API-Key": TREASURY_KEY},
    )
    if r is None:
        print("  SKIP (%s)" % err)
        return None
    if r.status_code == 200:
        data      = r.json()
        reasoning = (data.get("response") or data.get("text")
                     or data.get("content") or str(data))[:2000]
        verdict   = parse_verdict(reasoning)
        status    = {"false_positive": "dismissed",
                     "valid":          "confirmed",
                     "manual_review":  "needs_review"}.get(verdict, "pending")
        return reasoning, verdict, status
    print("  HTTP %d: %s" % (r.status_code, r.text[:200]))
    return None


# ── L3 — Komposisi Akun vs Peer ──────────────────────────────────────────────

def process_l3(conn, cur, limit):
    if limit <= 0:
        return
    print("\n=== L3 (Komposisi Akun vs Peer) — top %d by pagu ===" % limit)

    # coherence_akun deduplicated per (kl, prog, keg, out).
    # Join ke coherence untuk uraian teks + filter llm_reasoning IS NULL.
    cur.execute(f"""
        SELECT
            ca.kementerian_kode,
            MAX(c.kementerian_uraian)   AS kl_name,
            ca.program_kode,
            MAX(c.program_uraian)       AS prog_name,
            ca.kegiatan_kode,
            MAX(c.kegiatan_uraian)      AS keg_name,
            ca.outputkro_kode,
            MAX(c.outputkro_uraian)     AS out_name,
            ca.akun_komposisi_score,
            ca.peer_count,
            ca.akun_detail,
            SUM(c.total_pagu)           AS total_pagu
        FROM {T_COH_AKUN} ca
        JOIN {T_COH} c
          ON  c.kementerian_kode = ca.kementerian_kode
          AND c.program_kode     = ca.program_kode
          AND c.kegiatan_kode    = ca.kegiatan_kode
          AND c.outputkro_kode   = ca.outputkro_kode
        WHERE ca.akun_komposisi_score >= 40
          AND c.llm_reasoning IS NULL
        GROUP BY ca.kementerian_kode, ca.program_kode, ca.kegiatan_kode,
                 ca.outputkro_kode, ca.akun_komposisi_score,
                 ca.peer_count, ca.akun_detail
        ORDER BY total_pagu DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    print("  %d kasus ditemukan\n" % len(rows))

    for i, (kl, kl_name, prog, prog_name, keg, keg_name,
            out, out_name, dev_score, peer_cnt, akun_detail, pagu) in enumerate(rows):

        akun_text    = fmt_akun(akun_detail)
        mandate_ctx  = get_kl_mandate_context(cur, kl)
        mandate_section = ("\n%s\n" % mandate_ctx) if mandate_ctx else ""

        prompt = (
            "Anomali Koherensi Level 3 — Komposisi Akun vs Peer:\n"
            "K/L     : %s - %s\n"
            "Program : %s - %s\n"
            "Kegiatan: %s - %s\n"
            "Output  : %s - %s\n\n"
            "%s\n"
            "Total pagu K/L ini: Rp %.2f T\n"
            "%s\n"
            "Pertanyaan: Apakah pola belanja yang berbeda dari %d K/L peer ini dapat "
            "dijustifikasi oleh mandat RPJMN/RKP K/L tersebut atau oleh sifat programnya?"
        ) % (
            kl, (kl_name  or "")[:60],
            prog, (prog_name or "")[:80],
            keg,  (keg_name  or "")[:80],
            out,  (out_name  or "")[:80],
            akun_text,
            float(pagu) / 1e12,
            mandate_section,
            peer_cnt,
        )

        print("[%d/%d] %s %s dev=%.1f pagu=Rp%.2fT..." % (
            i + 1, len(rows), kl, out, float(dev_score), float(pagu) / 1e12))

        result = call_treasurai(prompt)
        if result:
            reasoning, verdict, status = result
            # Update SEMUA baris coherence_2026 untuk (kl, prog, keg, out) ini
            cur.execute(f"""
                UPDATE {T_COH}
                SET llm_reasoning=%s, llm_model=%s,
                    treasurai_verdict=%s, review_status_coherence=%s
                WHERE kementerian_kode=%s AND program_kode=%s
                  AND kegiatan_kode=%s AND outputkro_kode=%s
                  AND llm_reasoning IS NULL
            """, (reasoning, MODEL, verdict, status, kl, prog, keg, out))
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:500]))

        time.sleep(0.3)


# ── L1/L2 — Semantic Coherence ───────────────────────────────────────────────

def process_l1l2(conn, cur, limit):
    if limit <= 0:
        return
    print("\n=== L1/L2 (Semantic Coherence) — top %d by pagu ===" % limit)

    cur.execute(f"""
        SELECT
            kementerian_kode,
            MAX(kementerian_uraian)  AS kl_name,
            program_kode,
            MAX(program_uraian)      AS prog_name,
            kegiatan_kode,
            MAX(kegiatan_uraian)     AS keg_name,
            MIN(prog_keg_coherence)  AS l1_score,
            MIN(keg_out_coherence)   AS l2_score,
            anomaly_flags,
            SUM(total_pagu)          AS total_pagu
        FROM {T_COH}
        WHERE (
            JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level1_program_kegiatan_lemah'))
            OR
            JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level2_kegiatan_output_lemah'))
        )
        AND llm_reasoning IS NULL
        GROUP BY kementerian_kode, program_kode, kegiatan_kode, anomaly_flags
        ORDER BY total_pagu DESC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    print("  %d kasus ditemukan\n" % len(rows))

    for i, (kl, kl_name, prog, prog_name, keg, keg_name,
            l1, l2, flags_json, pagu) in enumerate(rows):

        flags      = json.loads(flags_json) if flags_json else []
        level_info = []
        if "level1_program_kegiatan_lemah" in flags:
            level_info.append("L1 Program ↔ Kegiatan similarity : %.1f/100" % float(l1 or 0))
        if "level2_kegiatan_output_lemah" in flags:
            level_info.append("L2 Kegiatan ↔ Output similarity  : %.1f/100" % float(l2 or 0))

        mandate_ctx     = get_kl_mandate_context(cur, kl)
        mandate_section = ("\n%s\n" % mandate_ctx) if mandate_ctx else ""

        prompt = (
            "Anomali Koherensi Semantik (Level 1/2):\n"
            "K/L     : %s - %s\n"
            "Program : %s - %s\n"
            "Kegiatan: %s - %s\n\n"
            "%s\n"
            "Pagu    : Rp %.3f T\n"
            "%s\n"
            "Pertanyaan: Mengapa similarity rendah? "
            "Gunakan mandat K/L dari RPJMN/RKP di atas untuk menilai apakah "
            "ini perbedaan nomenklatur (false positive) atau incoherence struktural yang genuine."
        ) % (
            kl, (kl_name  or "")[:60],
            prog, (prog_name or "")[:80],
            keg,  (keg_name  or "")[:80],
            "\n".join(level_info),
            float(pagu) / 1e12,
            mandate_section,
        )

        print("[%d/%d] %s L1=%.1f L2=%.1f pagu=Rp%.3fT..." % (
            i + 1, len(rows), kl,
            float(l1 or 0), float(l2 or 0),
            float(pagu) / 1e12))

        result = call_treasurai(prompt)
        if result:
            reasoning, verdict, status = result
            cur.execute(f"""
                UPDATE {T_COH}
                SET llm_reasoning=%s, llm_model=%s,
                    treasurai_verdict=%s, review_status_coherence=%s
                WHERE kementerian_kode=%s AND program_kode=%s AND kegiatan_kode=%s
                  AND llm_reasoning IS NULL
            """, (reasoning, MODEL, verdict, status, kl, prog, keg))
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:500]))

        time.sleep(0.3)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    conn = get_connection()
    cur  = conn.cursor()

    print("=" * 60)
    print("15_coherence_reasoning.py")
    print("Model   : %s" % MODEL)
    print("Limit L3: %d | Limit L1/L2: %d" % (LIMIT_L3, LIMIT_L1L2))
    print("=" * 60)

    ensure_columns(cur, conn)
    process_l3(conn, cur, LIMIT_L3)
    process_l1l2(conn, cur, LIMIT_L1L2)

    # Summary
    print("\n" + "=" * 60)
    print(f"FINAL STATUS {T_COH}")
    print("=" * 60)
    cur.execute(f"""
        SELECT
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level3_akun_tidak_lazim'))   THEN 1 ELSE 0 END) AS l3_total,
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level3_akun_tidak_lazim'))
                      AND llm_reasoning IS NOT NULL THEN 1 ELSE 0 END)                          AS l3_done,
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level1_program_kegiatan_lemah'))
                      OR  JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level2_kegiatan_output_lemah')) THEN 1 ELSE 0 END) AS l12_total,
            SUM(CASE WHEN (JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level1_program_kegiatan_lemah'))
                      OR  JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level2_kegiatan_output_lemah')))
                      AND llm_reasoning IS NOT NULL THEN 1 ELSE 0 END)                          AS l12_done
        FROM {T_COH}
    """)
    r = cur.fetchone()
    print("  L3 anomali : %s baris | %s punya reasoning" % (
        format(r[0], ","), format(r[1], ",")))
    print("  L1/L2 anomali: %s baris | %s punya reasoning" % (
        format(r[2], ","), format(r[3], ",")))

    conn.close()


if __name__ == "__main__":
    main()
