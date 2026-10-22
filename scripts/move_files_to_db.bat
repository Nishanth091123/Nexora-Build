@echo off
title Nexora Build - move files into the database
cd /d %~dp0..
echo ==== Moving drawings / photos / documents / backups into the online database (once) ====
backend\.venv\Scripts\python.exe scripts\move_files_to_db.py || goto :fail
echo.
echo ==== DONE ====
pause
exit /b 0
:fail
echo.
echo [FAILED] Copy the message above and send it to Claude (never send your keys).
pause
exit /b 1
