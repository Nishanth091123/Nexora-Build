@echo off
title Nexora Build
cd /d %~dp0..
echo ==================================================
echo   Nexora Build - starting backend + frontend
echo   App:  http://localhost:5173
echo   Stop: press Ctrl+C (then Y) in this window
echo ==================================================
echo Closing any old Nexora backend still running on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>nul
start "" /b cmd /c "cd /d %~dp0..\backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --log-level warning"
echo Waiting for backend...
set /a n=0
:wait
set /a n+=1
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8000/api/health >nul 2>nul && goto ready
if %n% lss 40 goto wait
echo [WARN] Backend did not answer in 80 seconds. Check messages above.
:ready
curl -s http://127.0.0.1:8000/api/health | findstr /c:"phase7" >nul || echo [WARN] An OLD backend is answering. Close ALL CMD windows, then run scripts\start.bat again.
echo Backend ready.
start "" http://localhost:5173
cd frontend
if exist dist\index.html (
  echo Using the built app ^(fast^). After code changes run scripts\update.bat again.
  call npm run preview
) else (
  echo No built app yet - starting development mode ^(slower^). Run scripts\update.bat to build.
  call npm run dev
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>nul
