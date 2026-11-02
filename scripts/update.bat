@echo off
title Nexora Build - update
cd /d %~dp0..
set PY=backend\.venv\Scripts\python.exe
echo ==== Nexora Build - install updates + test ====
echo Start: %time%
echo Closing any old Nexora backend still running on port 8000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>nul

echo [1/4] Backend packages...  (%time%)
%PY% scripts\changed.py check pip backend\requirements.txt
if errorlevel 1 (
  echo       no change - skipped
) else (
  call %PY% -m pip install -q --disable-pip-version-check -r backend\requirements.txt || goto :fail
  %PY% scripts\changed.py save pip backend\requirements.txt
)

echo [2/4] Frontend packages...  (%time%)
%PY% scripts\changed.py check npm frontend\package.json frontend\package-lock.json
if errorlevel 1 if exist frontend\node_modules (
  echo       no change - skipped
  goto :build
)
cd frontend
call npm install --no-fund --no-audit --prefer-offline || goto :fail
cd ..
%PY% scripts\changed.py save npm frontend\package.json frontend\package-lock.json

:build
echo [3/4] Building the app (fast start)...  (%time%)
%PY% scripts\changed.py check build frontend\src frontend\public frontend\index.html frontend\package.json frontend\vite.config.ts
if errorlevel 1 if exist frontend\dist\index.html (
  echo       screens not changed - skipped
  goto :test
)
cd frontend
if exist dist rmdir /s /q dist
call npm run build
if errorlevel 1 (
  cd ..
  echo [WARN] Build failed - start.bat will use development mode. Send the error above to Claude.
  goto :test
)
cd ..
%PY% scripts\changed.py save build frontend\src frontend\public frontend\index.html frontend\package.json frontend\vite.config.ts

:test
echo [4/4] Automatic API test (database update runs first)...  (%time%)
%PY% scripts\smoke_test.py %* || goto :fail
echo.
echo ==== UPDATE OK ====  (%time%)  Now run:  scripts\start.bat
pause
exit /b 0
:fail
echo.
echo [FAILED] (%time%) Copy the error above and send it to Claude.
pause
exit /b 1
