@echo off
cd /d %~dp0..
echo ==== Nexora Build - Phase 1 setup ====
echo.
echo [1/3] Backend packages...
cd backend
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || goto :fail
cd ..
echo.
echo [2/3] .env settings...
python scripts\update_env.py || goto :fail
echo.
echo [3/3] Frontend packages (takes 1-3 minutes)...
cd frontend
call npm install || goto :fail
cd ..
echo.
echo ==== SETUP DONE ====
echo Next: open TWO CMD windows
echo   window 1:  scripts\run_backend.bat
echo   window 2:  scripts\run_frontend.bat
pause
exit /b 0
:fail
echo.
echo [FAILED] Copy the error above and send it to Claude.
pause
exit /b 1
