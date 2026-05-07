@echo off
cd /d "%~dp0"
python daily_cache_manager.py save-today
pause
