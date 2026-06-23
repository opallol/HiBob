"""
18_reconcile_kl_assignments.py — Perbaiki kode K/L (kddept) di
deepseek_policy_kl_assignments terhadap referensi kanonik DIPA.

LATAR: RPJMN Lampiran III memakai penomoran K/L internal RPJMN yang BERBEDA
dari kddept DIPA. Ekstraksi (script 08) menormalisasi kode dengan tidak konsisten,
sehingga 28% assignment memiliki kddept salah (mis. BNPT→129, Kejaksaan→129,
Kemenperin→059). Akibatnya konteks mandat yang di-inject ke reasoning sering
salah-atribut ke K/L yang keliru.

PENDEKATAN (deterministik, auditable): nama K/L pada field `evidence`
(teks mentah RPJMN) dicocokkan ke referensi kanonik DIPA (ddac_pagu_akun) via
token-overlap distinctive + alias map. Hanya remap bila confident. Tidak memakai
LLM — pencocokan murni terhadap ground-truth kode DIPA.

Usage:
  python scripts/18_reconcile_kl_assignments.py            # dry-run (default)
  python scripts/18_reconcile_kl_assignments.py --apply    # tulis perubahan
"""
import sys, re
sys.path.insert(0, "scripts")
from common.config import DB_CONFIG
import pymysql

APPLY = "--apply" in sys.argv

# Alias: nama/akronim RPJMN yang tidak punya token distinctive cukup → kode DIPA.
# Hanya fakta K/L yang sudah mapan (akronim resmi / hasil reorganisasi 2024).
ALIAS = {
    "POLRI": "060",
    "BKKBN": "068",
    "BNPT": "113",
    "BNN": "066",
    "BNPB": "103",
    "BNPP": "111",
    "BPIP": "122",
    "BRIN": "124",
    "LKPP": "106",
    "PPATK": "078",
    "KPPU": "108",
    "BSSN": "051",
    "BIG": "083",
    "BSN": "084",
    "BPKP": "089",
    "BMKG": "075",
    "LAN": "086",
    "ANRI": "087",
    "BKN": "088",
    "BAPETEN": "085",
    "BASARNAS": "107",
    "LEMHANNAS": "064",
}

# Stopword umum K/L → diabaikan saat token-overlap (terlalu generik)
STOP = {"KEMENTERIAN", "BADAN", "NASIONAL", "REPUBLIK", "INDONESIA", "DAN",
        "LEMBAGA", "NEGARA", "KOMISI", "PUSAT", "BIDANG", "DEWAN", "RI",
        "KOORDINATOR", "PENGELOLA", "OTORITA", "PERWAKILAN"}


def norm(s):
    s = (s or "").upper()
    s = re.sub(r"[^A-Z0-9/ ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s):
    return {t for t in norm(s).replace("/", " ").split() if t and t not in STOP}


def build_dipa(cur):
    cur.execute("SELECT DISTINCT kementerian_kode, kementerian_uraian FROM ddac_pagu_akun_2026")
    ref = {}                    # code -> name
    for code, name in cur.fetchall():
        ref[code] = name.strip()
    return ref


def match(raw_name, dipa_ref):
    """Kembalikan (code, score, how) atau (None, 0, reason)."""
    n = norm(raw_name)
    if not n:
        return None, 0, "empty"

    # 1) alias akronim
    for alias, code in ALIAS.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", n):
            if code in dipa_ref:
                return code, 1.0, f"alias:{alias}"

    # 2) exact full-name match (sebelum '/', tanpa parenthetical "(...)")
    def head_of(s):
        s = re.sub(r"\(.*?\)", " ", s)          # buang "(BNN)", "(DPD)", dst.
        return norm(s).split("/")[0].strip()
    head = head_of(raw_name)
    for code, name in dipa_ref.items():
        if head_of(name) == head:
            return code, 1.0, "exact-head"

    # 3) token-overlap distinctive — butuh >=2 token distinctive yang sama
    #    (1 token generik seperti "USAHA" pada evidence sampah "Badan usaha"
    #     tidak boleh memicu remap; kasus 1-token yang sah ditangkap exact-head).
    ev = tokens(raw_name)
    if len(ev) < 2:
        return None, 0, "too-few-tokens"
    best = (None, 0.0)
    for code, name in dipa_ref.items():
        dt = tokens(name)
        if not dt:
            continue
        inter = ev & dt
        if len(inter) < 2:
            continue
        score = len(inter) / len(ev | dt)
        cover = len(inter) / len(ev)
        if cover >= 0.6 and score > best[1]:
            best = (code, score)
    if best[0]:
        return best[0], best[1], "token"
    return None, 0, "no-match"


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    dipa_ref = build_dipa(cur)
    print(f"DIPA reference: {len(dipa_ref)} K/L | mode={'APPLY' if APPLY else 'DRY-RUN'}\n")

    cur.execute("SELECT id, kddept, nmdept_normalized, evidence FROM deepseek_policy_kl_assignments")
    rows = cur.fetchall()

    remaps = {}     # (old,new) -> count
    unmatched = {}  # name -> count
    updates = []    # (id, newcode, newname)
    same = 0

    for aid, kddept, nm, ev in rows:
        m = re.search(r"->\s*\d+\s+(.+)$", ev or "")
        raw_name = m.group(1).strip() if m else (nm or "")
        code, score, how = match(raw_name, dipa_ref)
        if code is None:
            unmatched[raw_name] = unmatched.get(raw_name, 0) + 1
            continue
        if code != kddept:
            remaps[(kddept, code)] = remaps.get((kddept, code), 0) + 1
            updates.append((aid, code, dipa_ref[code]))
        else:
            same += 1

    print(f"Already correct : {same}")
    print(f"Will remap      : {len(updates)}  ({len(remaps)} distinct code pairs)")
    print(f"Unmatched       : {sum(unmatched.values())}  ({len(unmatched)} distinct names)\n")

    print("=== REMAP PAIRS (old -> new : DIPA name) ===")
    for (old, new), cnt in sorted(remaps.items(), key=lambda x: -x[1]):
        print(f"  {old} -> {new}  x{cnt:3d}  : {dipa_ref[new][:50]}")

    print("\n=== UNMATCHED names (left as-is) ===")
    for nm, cnt in sorted(unmatched.items(), key=lambda x: -x[1]):
        print(f"  x{cnt:2d}  {nm[:60]}")

    if APPLY and updates:
        cur.executemany(
            "UPDATE deepseek_policy_kl_assignments SET kddept=%s, nmdept_normalized=%s WHERE id=%s",
            [(c, n, aid) for aid, c, n in updates])
        conn.commit()
        print(f"\nAPPLIED {len(updates)} updates.")
    elif not APPLY:
        print("\n(dry-run — no changes written. Re-run with --apply)")

    conn.close()


if __name__ == "__main__":
    main()
