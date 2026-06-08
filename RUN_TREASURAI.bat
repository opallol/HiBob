@echo off
cd /d D:\Project\deepseek-kms
echo ========================================
echo TreasuryAI Reasoning - OSS 120B
echo ========================================
echo.
echo Mengirim top 15 policy orphans ke TreasuryAI...
echo.
python scripts\11_treasurai_reasoning.py 15
echo.
echo ========================================
echo SELESAI! Cek hasilnya:
echo   SELECT * FROM ddac_anomaly_2026 WHERE llm_reasoning IS NOT NULL
echo ========================================
pause
