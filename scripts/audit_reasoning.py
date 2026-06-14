"""
Audit helper — sampel reasoning + verdict dari DB untuk review kualitas.
Tidak menulis apa pun. Read-only.
Usage: python scripts/audit_reasoning.py <mode>
  modes: align_valid, align_fp, align_review, coh_valid, coh_fp, coh_review, align_lowscore
"""
import sys, json, textwrap, io
sys.path.insert(0, "scripts")
from common.config import DB_CONFIG
import pymysql

# Windows console = cp1252; force utf-8 so reasoning text (em-dash, etc.) prints
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def fill(s, w=112):
    return textwrap.fill(s or "", width=w, initial_indent="  ", subsequent_indent="  ")


def top3(raw):
    try:
        t3 = json.loads(raw) if raw else []
        lines = []
        for m in t3[:3]:
            kode = m.get("code", m.get("kode", "?"))
            nama = (m.get("name", m.get("nama", "")) or "")[:55]
            skor = m.get("score", m.get("skor", "?"))
            src = m.get("source", "")
            lines.append(f"      - {kode} [{src}] {nama} ({skor})")
        return "\n".join(lines)
    except Exception as e:
        return f"(parse err: {e})"


def align(where, order, limit, label):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    cur.execute(f"""SELECT a.kementerian_kode, a.kementerian_uraian, a.total_pagu,
           a.alignment_score, a.anomaly_type, a.spending_nature, a.treasurai_verdict,
           a.best_match_code, a.best_match_name, a.best_match_score, a.top3_matches,
           a.llm_reasoning, p.alignment_text
    FROM ddac_anomaly_2026 a
    JOIN ddac_pagu_akun_2026 p ON a.pagu_id = p.id
    WHERE a.llm_reasoning IS NOT NULL AND {where}
    ORDER BY {order} LIMIT {limit}""")
    for i, r in enumerate(cur.fetchall(), 1):
        print(f"--- {label} #{i} | pagu Rp {float(r['total_pagu'])/1e12:.3f}T | score {r['alignment_score']} | {r['anomaly_type']} | nature={r['spending_nature']} | verdict={r['treasurai_verdict']} ---")
        print(f"K/L      : {r['kementerian_kode']} {r['kementerian_uraian']}")
        print(f"DIPA text: {r['alignment_text']}")
        print(f"Best     : {r['best_match_code']} {r['best_match_name']} ({r['best_match_score']})")
        print(f"Top3:\n{top3(r['top3_matches'])}")
        print("Reasoning:")
        print(fill(r["llm_reasoning"]))
        print()
    conn.close()


def coh(verdict, limit, label):
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    # ambil 1 baris perwakilan per kombinasi output unik
    cur.execute(f"""SELECT kementerian_kode, MAX(kementerian_uraian) kl, MAX(program_uraian) prog,
           MAX(kegiatan_uraian) keg, MAX(outputkro_uraian) outp, SUM(total_pagu) pagu,
           MAX(akun_komposisi_score) akun_score, MAX(anomaly_flags) flags,
           MAX(treasurai_verdict) verdict, MAX(llm_reasoning) reasoning
    FROM ddac_coherence_2026
    WHERE llm_reasoning IS NOT NULL AND treasurai_verdict='{verdict}'
    GROUP BY kementerian_kode, program_kode, kegiatan_kode, outputkro_kode
    ORDER BY pagu DESC LIMIT {limit}""")
    for i, r in enumerate(cur.fetchall(), 1):
        print(f"--- {label} #{i} | pagu Rp {float(r['pagu'])/1e12:.3f}T | akun_score {r['akun_score']} | verdict={r['verdict']} ---")
        print(f"K/L   : {r['kementerian_kode']} {r['kl']}")
        print(f"Prog  : {r['prog']}")
        print(f"Keg   : {r['keg']}")
        print(f"Output: {r['outp']}")
        print(f"Flags : {r['flags']}")
        print("Reasoning:")
        print(fill(r["reasoning"]))
        print()
    conn.close()


MODE = sys.argv[1] if len(sys.argv) > 1 else "align_valid"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6

if MODE == "align_valid":
    align("treasurai_verdict='valid'", "total_pagu DESC", N, "VALID")
elif MODE == "align_fp":
    align("treasurai_verdict='false_positive'", "total_pagu DESC", N, "FALSE_POS")
elif MODE == "align_review":
    align("treasurai_verdict='manual_review'", "total_pagu DESC", N, "REVIEW")
elif MODE == "align_lowscore":
    align("treasurai_verdict='valid'", "alignment_score ASC", N, "VALID_LOWSCORE")
elif MODE == "align_highscore_valid":
    align("treasurai_verdict='valid'", "alignment_score DESC", N, "VALID_HIGHSCORE")
elif MODE == "coh_valid":
    coh("valid", N, "COH_VALID")
elif MODE == "coh_fp":
    coh("false_positive", N, "COH_FP")
elif MODE == "coh_review":
    coh("manual_review", N, "COH_REVIEW")
