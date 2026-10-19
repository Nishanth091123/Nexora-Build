@echo off
title Nexora Build - update
cd /d %~dp0..
echo ==== Nexora Build - install updates + test ====
echo Closing any old Nexora backend still running on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>nul
echo [1/4] Backend packages...
call backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || goto :fail
echo [2/4] Frontend packages...
cd frontend
call npm install --no-fund --no-audit || goto :fail
echo [3/4] Building the app (fast start)...
if exist dist rmdir /s /q dist
call npm run build || echo [WARN] Build failed - start.bat will use development mode. Send the error above to Claude.
cd ..
echo [4/4] Automatic API test (database update runs first)...
backend\.venv\Scripts\python.exe scripts\smoke_test.py || goto :fail
echo.
echo ==== UPDATE OK ====  Now run:  scripts\start.bat
pause
exit /b 0
:fail
echo.
echo [FAILED] Copy the error above and send it to Claude.
pause
exit /b 1
