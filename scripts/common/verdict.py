"""Parse TreasurAI free-text reasoning into a structured verdict label.

Taksonomi:
  - valid          : temuan benar — pola/alignment menyimpang DAN tidak dapat
                     dijustifikasi oleh mandat → perlu ditindaklanjuti.
  - false_positive : deviasi nyata tetapi DAPAT dijustifikasi (mandat khusus,
                     beda nomenklatur) → bukan masalah.
  - manual_review  : tidak cukup bukti untuk memutuskan → perlu cek manusia.
  - unclear        : tidak ada verdict yang dapat dikenali.

Mekanisme:
  1. Utama — tag eksplisit `VERDICT: <label>` yang diminta di prompt. Tidak ambigu.
  2. Fallback — pola KESIMPULAN ("dikategorikan/termasuk/tergolong sebagai X"),
     ambil match PERTAMA (kalimat klasifikasi), bukan kemunculan kata pertama.
     Penting karena teks seperti "perlu review manual ... bukan valid atau sekadar
     false positive" tidak boleh ter-label false_positive hanya karena frasa
     'false positive' muncul lebih dulu.
"""
import re

VERDICTS = ("valid", "false_positive", "manual_review", "unclear")

# 1) Tag eksplisit di akhir jawaban
_TAG = re.compile(
    r"(?:verdict|kesimpulan|status|keputusan|klasifikasi)\s*[:=]\s*\*{0,2}\s*"
    r"(valid|false[_\s-]?positive|manual[_\s-]?review|anomali\s+valid|"
    r"false\s+positive|perlu\s+review\s+manual|review\s+manual)",
    re.IGNORECASE)

# 2) Pola kalimat klasifikasi (fallback)
_CONCL = re.compile(
    r"(?:dikategorikan|dikelompokkan|tergolong|termasuk|merupakan|dinilai|"
    r"diklasifikasikan|sebagai)\W{0,40}?"
    r"(anomali\s+valid|false[_\s-]?positive|false\s+positive|"
    r"perlu\s+review\s+manual|review\s+manual|manual\s+review|valid)",
    re.IGNORECASE)


def _canon(s: str) -> str:
    s = s.lower().replace("-", " ").replace("_", " ")
    if "false" in s:
        return "false_positive"
    if "review" in s:
        return "manual_review"
    if "valid" in s:
        return "valid"
    return "unclear"


# Klausa negasi: "tidak/bukan/belum ... <label>" → bukan verdict, harus diabaikan
_NEG = re.compile(
    r"(?:tidak|bukan|belum|tanpa)\b[^.,;:]{0,40}?"
    r"(?:anomali\s+valid|false[_\s-]?positive|false\s+positive|"
    r"perlu\s+review\s+manual|review\s+manual|manual\s+review|valid)",
    re.IGNORECASE)


def parse_verdict(text: str) -> str:
    if not text:
        return "unclear"

    # 1) Tag eksplisit — ambil yang TERAKHIR (verdict final bila ada beberapa)
    tags = _TAG.findall(text)
    if tags:
        return _canon(tags[-1])

    # Buang klausa negasi sebelum fallback ("tidak dapat dipastikan sebagai
    # false positive" tidak boleh dibaca sebagai verdict false_positive).
    clean = _NEG.sub(" ", text)

    # 2) Kalimat klasifikasi — ambil match PERTAMA (poin klasifikasi)
    m = _CONCL.search(clean)
    if m:
        return _canon(m.group(1))
    text = clean

    # 3) Fallback terakhir: satu-satunya frasa yang muncul
    t = text.lower()
    present = []
    if "false positive" in t or "false-positive" in t:
        present.append("false_positive")
    if any(p in t for p in ("perlu review", "review manual", "manual review", "tinjau manual")):
        present.append("manual_review")
    if "valid" in t:
        present.append("valid")
    if len(present) == 1:
        return present[0]
    return "unclear"
