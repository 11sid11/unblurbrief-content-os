@echo off
cd /d "%~dp0"
python workflow_helper.py package-latest-and-send-canva 5
pause
