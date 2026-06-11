@echo off
REM ============================================
REM DeepSeek KMS - Coherence Detection Runner
REM Runs: 12_coherence.py + 13_coherence_levels.py
REM
REM Usage:
REM   RUN_COHERENCE.bat           (default: pct_low=5, peer_min=5)
REM   RUN_COHERENCE.bat strict    (pct_low=3, peer_min=10)
REM   RUN_COHERENCE.bat wide      (pct_low=10, peer_min=3)
REM ============================================

cd /d D:\Project\deepseek-kms

set PCT_LOW=5
set PEER_MIN=5

if /I "%1"=="strict" (
    set PCT_LOW=3
    set PEER_MIN=10
    echo === STRICT MODE: pct_low=3, peer_min=10 ===
) else if /I "%1"=="wide" (
    set PCT_LOW=10
    set PEER_MIN=3
    echo === WIDE MODE: pct_low=10, peer_min=3 ===
) else (
    echo === DEFAULT MODE: pct_low=5, peer_min=5 ===
)

echo.
echo [1/2] Running 12_coherence.py (jenis komponen)...
.venv\Scripts\python.exe scripts\12_coherence.py
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: 12_coherence.py failed!
    pause
    exit /b 1
)

echo.
echo [2/2] Running 13_coherence_levels.py (3-level + peer detail)...
.venv\Scripts\python.exe scripts\13_coherence_levels.py --pct-low %PCT_LOW% --peer-min %PEER_MIN%
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: 13_coherence_levels.py failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo Coherence detection COMPLETE!
echo Results in: ddac_coherence_2026 + ddac_coherence_akun_2026
echo ============================================
pause
