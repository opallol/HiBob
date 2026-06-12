"""
15b_coherence_template.py
Reasoning L3 coherence untuk item yang belum diproses script 15.
Menggunakan TreasurAI oss120b, prompt identik dengan script 15.
"""
import json, requests, time, sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from common.config import TREASURAI_BASE_URL, TREASURAI_API_KEY, TREASURAI_MODELS
from common.db import get_connection
from common.verdict import parse_verdict
from common.kl_context import get_kl_mandate_context

MODEL        = "oss120b"
TREASURY_URL = TREASURAI_BASE_URL + TREASURAI_MODELS[MODEL]
TREASURY_KEY = TREASURAI_API_KEY

CAT_LABELS = {
    "51": "Belanja Pegawai",
    "52": "Belanja Barang",
    "53": "Belanja Modal",
    "54": "Belanja Bunga Utang",
    "55": "Belanja Subsidi",
    "57": "Belanja Bantuan Sosial",
    "58": "Belanja Lain-lain",
}

SYSTEM_PROMPT = """Kamu adalah TreasurAI, asisten analisis anggaran ahli di Ditjen Perbendaharaan. \
Analisis anomali koherensi internal struktur DIPA.

Untuk setiap item:
1. Jelaskan mengapa pola ini berbeda dari lazimnya
2. Tentukan: anomali valid, false positive, atau perlu review manual
3. Beri rekomendasi 1 kalimat

Jawaban maksimal 4 kalimat, Bahasa Indonesia formal."""


def fmt_akun(detail_json):
    try:
        d    = json.loads(detail_json) if isinstance(detail_json, str) else detail_json
        own  = d.get("own",  {})
        peer = d.get("peer", {})
        dev  = d.get("deviation", 0)
        pc   = d.get("peer_count", 0)
        lines = ["Deviasi total: %.1f%% vs %d K/L peer" % (dev * 100, pc)]
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
    try:
        r = requests.post(
            TREASURY_URL,
            json={
                "prompt": prompt, "session_id": None,
                "system_prompt": SYSTEM_PROMPT,
                "temperature": 0.1, "max_tokens": 1200,
            },
            headers={"Content-Type": "application/json", "X-API-Key": TREASURY_KEY},
            timeout=(15, 90),
            verify=False,
        )
        if r.status_code == 200:
            data      = r.json()
            reasoning = (data.get("response") or data.get("text")
                         or data.get("content") or str(data))[:2000]
            verdict   = parse_verdict(reasoning)
            status    = {"false_positive": "dismissed",
                         "valid":          "confirmed",
                         "manual_review":  "needs_review"}.get(verdict, "pending")
            return reasoning, verdict, status
        else:
            print("  HTTP %d: %s" % (r.status_code, r.text[:200]))
            return None
    except Exception as e:
        print("  ERR: %s" % str(e)[:200])
        return None


def main():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
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
        FROM ddac_coherence_akun_2026 ca
        JOIN ddac_coherence_2026 c
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
    """)
    rows  = cur.fetchall()
    total = len(rows)

    print("=" * 60)
    print("15b_coherence_template.py")
    print("Model   : %s" % MODEL)
    print("Items to process: %d" % total)
    print("=" * 60)

    for i, (kl, kl_name, prog, prog_name, keg, keg_name,
            out, out_name, dev_score, peer_cnt, akun_detail, pagu) in enumerate(rows):

        akun_text       = fmt_akun(akun_detail)
        mandate_ctx     = get_kl_mandate_context(cur, kl)
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
            "Pertanyaan: Apakah pola belanja yang sangat berbeda dari %d K/L peer ini "
            "dapat dijelaskan oleh mandat RPJMN/RKP K/L tersebut? "
            "Anomali valid, false positive karena mandat khusus, atau perlu review manual?"
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
            i + 1, total, kl, out, float(dev_score), float(pagu) / 1e12))

        result = call_treasurai(prompt)
        if result:
            reasoning, verdict, status = result
            cur.execute("""
                UPDATE ddac_coherence_2026
                SET llm_reasoning=%s, llm_model=%s,
                    treasurai_verdict=%s, review_status_coherence=%s
                WHERE kementerian_kode=%s AND program_kode=%s
                  AND kegiatan_kode=%s AND outputkro_kode=%s
                  AND llm_reasoning IS NULL
            """, (reasoning, MODEL, verdict, status, kl, prog, keg, out))
            conn.commit()
            print("  [%s] %s\n" % (verdict, reasoning[:500]))

        time.sleep(0.3)

    print("\n" + "=" * 60)
    print("FINAL STATUS ddac_coherence_2026 — L3")
    print("=" * 60)
    cur.execute("""
        SELECT
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level3_akun_tidak_lazim'))
                     THEN 1 ELSE 0 END),
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level3_akun_tidak_lazim'))
                      AND llm_reasoning IS NOT NULL THEN 1 ELSE 0 END),
            SUM(CASE WHEN JSON_CONTAINS(anomaly_flags, JSON_QUOTE('level3_akun_tidak_lazim'))
                      AND llm_model = %s THEN 1 ELSE 0 END)
        FROM ddac_coherence_2026
    """, (MODEL,))
    r = cur.fetchone()
    print("  L3 total    : %s baris" % format(r[0], ","))
    print("  L3 done     : %s baris (%.1f%%)" % (format(r[1], ","), r[1] / r[0] * 100))
    print("  llm_model=%s: %s baris" % (MODEL, format(r[2], ",")))

    conn.close()


if __name__ == "__main__":
    main()
