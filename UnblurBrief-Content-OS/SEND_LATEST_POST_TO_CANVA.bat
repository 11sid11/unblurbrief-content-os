@echo off
cd /d "%~dp0"
python workflow_helper.py send-latest-to-canva
pause
