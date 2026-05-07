@echo off
setlocal
cd /d "%~dp0"
title UnblurBrief PIB Only Debug + Open

echo ============================================================
echo Running PIB-only debug first...
echo ============================================================
python run_pib_only.py

echo.
echo Opening existing UnblurBrief OS...
call OPEN_EXISTING_OS.bat
