@echo off
cd /d "%~dp0"
python rebuild_candidates_from_cache.py latest
pause
