@echo off
title Nexora Build - restore a backup into a NEW empty database
cd /d %~dp0..
if "%~1"=="" (
  echo Usage: scripts\restore_backup.bat "C:\path\nexora_manual_....json.gz"
  echo Put the NEW empty database in .env DATABASE_URL first. See docs\PHASE_7_GUIDE.md
  pause
  exit /b 1
)
backend\.venv\Scripts\python.exe scripts\restore_backup.py %1
pause
