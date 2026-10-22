@echo off
cd /d %~dp0..\frontend
echo Nexora Build app on http://localhost:5173
call npm run dev
pause
