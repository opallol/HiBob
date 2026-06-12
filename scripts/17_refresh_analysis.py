"""
17_refresh_analysis.py
Orchestrator refresh pipeline analisis — jalankan SETELAH data DIPA diperbarui di DB.

Skenario penggunaan:
  1. APBN-P (revisi tengah tahun) — data ddac_pagu_akun_<year> berubah
  2. Tahun baru (APBN 2027) — set BUDGET_YEAR=2027 di .env, jalankan skrip ini

Urutan eksekusi:
  10 → anomaly detect + embed ulang pagu vs KP
  11 → reasoning alignment (idempotent, isi yang kosong saja)
  12 → rebuild tabel coherence dari nol
  13 → hitung L1/L2/L3 coherence + peer comparison
  15b → reasoning L3 coherence (idempotent, isi yang kosong saja)
  16 → ekspor JSON statis ke web/public/data/
  [web rebuild] → npm run build di folder web/

Catatan:
  - Script 10 menghapus & rebuild ddac_anomaly_<year> (tetapi preserve reasoning lama)
  - Script 12 DROP+CREATE ddac_coherence_<year> (reasoning akan hilang setelah step ini)
  - Oleh karena itu reasoning (step 11, 15b) dijalankan SETELAH rebuild coherence
  - Script 11 dan 15b butuh koneksi jaringan Kemenkeu (TreasurAI)
  - Proses ini bisa berjam-jam tergantung ukuran data dan kecepatan TreasurAI

Usage:
  python scripts/17_refresh_analysis.py              # full refresh
  python scripts/17_refresh_analysis.py --skip-reasoning  # tanpa reasoning (cepat, for testing)
  python scripts/17_refresh_analysis.py --from-step 12    # mulai dari step tertentu
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPTS_DIR.parent

STEPS = [
    ("10", "Anomaly Detection (embed + classify)",          "10_anomaly_detect.py"),
    ("11", "TreasurAI Reasoning — Policy Alignment",       "11_treasurai_reasoning.py"),
    ("12", "Rebuild Coherence Table",                      "12_coherence.py"),
    ("13", "Coherence Levels L1/L2/L3 + Peer Comparison", "13_coherence_levels.py"),
    ("15b","TreasurAI Reasoning — Coherence L3",          "15b_coherence_template.py"),
    ("16", "Export JSON statis → web/public/data/",        "16_export_web.py"),
]


def run_step(script_name, step_label):
    script_path = SCRIPTS_DIR / script_name
    print("\n" + "=" * 70)
    print(f">>> STEP {step_label}: {script_path.name}")
    print("=" * 70)
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(PROJECT_ROOT),
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n[!] STEP {step_label} GAGAL (exit code {result.returncode}) setelah {elapsed:.0f}s")
        return False
    print(f"\n[OK] STEP {step_label} selesai dalam {elapsed:.0f}s")
    return True


def main():
    parser = argparse.ArgumentParser(description="Refresh pipeline analisis DIPA")
    parser.add_argument("--skip-reasoning", action="store_true",
                        help="Lewati step 11 dan 15b (TreasurAI — butuh jaringan Kemenkeu)")
    parser.add_argument("--from-step", default=None, metavar="STEP_ID",
                        choices=[s[0] for s in STEPS],
                        help="Mulai dari step tertentu (mis. --from-step 12)")
    parser.add_argument("--skip-web-build", action="store_true",
                        help="Lewati npm run build setelah step 16")
    args = parser.parse_args()

    from common.config import BUDGET_YEAR, TABLE_PAGU_AKUN, TABLE_ANOMALY, TABLE_COHERENCE, TABLE_COHERENCE_AKUN
    print("=" * 70)
    print("DDAC — REFRESH PIPELINE ANALISIS")
    print("=" * 70)
    print(f"  BUDGET_YEAR      : {BUDGET_YEAR}")
    print(f"  Tabel pagu       : {TABLE_PAGU_AKUN}")
    print(f"  Tabel anomaly    : {TABLE_ANOMALY}")
    print(f"  Tabel coherence  : {TABLE_COHERENCE}")
    print(f"  skip-reasoning   : {args.skip_reasoning}")
    print(f"  from-step        : {args.from_step or 'awal'}")
    print()

    REASONING_STEPS = {"11", "15b"}
    skip_until = args.from_step
    skipping = skip_until is not None

    total_start = time.time()
    for step_id, label, script in STEPS:
        # Handle --from-step
        if skipping:
            if step_id == skip_until:
                skipping = False
            else:
                print(f"  [skip] Step {step_id}: {label}")
                continue

        # Handle --skip-reasoning
        if args.skip_reasoning and step_id in REASONING_STEPS:
            print(f"  [skip-reasoning] Step {step_id}: {label}")
            continue

        ok = run_step(script, f"{step_id} — {label}")
        if not ok:
            print("\n[!] Pipeline berhenti karena ada error. Perbaiki masalah di atas dan jalankan ulang dengan --from-step", step_id)
            sys.exit(1)

    # Web rebuild
    if not args.skip_web_build:
        web_dir = PROJECT_ROOT / "web"
        if web_dir.exists() and (web_dir / "package.json").exists():
            print("\n" + "=" * 70)
            print(">>> WEB BUILD: npm run build")
            print("=" * 70)
            t0 = time.time()
            result = subprocess.run(["npm", "run", "build"], cwd=str(web_dir), shell=True)
            if result.returncode == 0:
                print(f"[OK] Web build selesai dalam {time.time()-t0:.0f}s")
                print(f"     Deploy folder: {web_dir / 'dist'}")
            else:
                print("[!] Web build gagal — periksa output npm di atas")

    elapsed = time.time() - total_start
    print("\n" + "=" * 70)
    print(f"REFRESH SELESAI — total waktu: {elapsed/60:.1f} menit")
    print("=" * 70)
    print("\nLangkah selanjutnya setelah refresh:")
    print("  1. Verifikasi data: python scripts/00_status_check.py")
    print("  2. Deploy folder web/dist/ ke server hosting")
    print(f"  3. Untuk tahun baru: set BUDGET_YEAR=<tahun> di .env dan jalankan ulang")


if __name__ == "__main__":
    main()
