@echo off
setlocal
cd /d "%~dp0"
title UnblurBrief PIB Only Debug

echo ============================================================
echo UnblurBrief PIB-only debug runner
echo This will NOT call paid/keyed APIs or Canva.
echo ============================================================
echo.

python run_pib_only.py

echo.
echo Done. Check these files:
echo output\pib_all_releases.json
echo output\pib_only_sources.json
echo output\pib_debug_allRel_snapshot.html
echo output\pib_debug_links.json
echo.
pause
