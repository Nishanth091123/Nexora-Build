@echo off
title Nexora Build - prepare to go online
cd /d %~dp0..
echo ==== Nexora Build - prepare the online backend (Render.com, free) ====
echo [1/2] Moving files kept on this PC into the online database (safe to run again)...
backend\.venv\Scripts\python.exe scripts\move_files_to_db.py || goto :fail
echo [2/2] Settings for Render (opens in Notepad)...
backend\.venv\Scripts\python.exe scripts\render_env.py || goto :fail
echo.
echo ==== READY ====  Next: docs\PHASE_7_GUIDE.md  Step 3 (Render) and Step 4 (Vercel)
pause
exit /b 0
:fail
echo.
echo [FAILED] Read the message above. Send it to Claude if unclear (never send your keys).
pause
exit /b 1
