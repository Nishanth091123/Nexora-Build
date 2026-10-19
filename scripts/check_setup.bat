@echo off
echo ==== Nexora Build - setup check ====
for %%T in (git node npm python pip) do (
  where %%T >nul 2>nul && (echo [OK] %%T & call %%T --version) || echo [NOT FOUND] %%T
)
echo.
if exist .env (echo [OK] .env file found) else (echo [MISSING] .env - run: copy .env.example .env)
if exist frontend\public\images\sidebar_main.jpg (echo [OK] images found) else (echo [MISSING] images)
pause
