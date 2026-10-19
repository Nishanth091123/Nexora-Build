@echo off
title Nexora Build - GitHub push
cd /d %~dp0..
echo ==== Push Nexora Build to GitHub (your .env keys are NOT uploaded) ====
backend\.venv\Scripts\python.exe scripts\github_push.py %* || goto :fail
pause
exit /b 0
:fail
echo.
echo [FAILED] Read the message above. Send it to Claude if unclear (never send your keys).
pause
exit /b 1
