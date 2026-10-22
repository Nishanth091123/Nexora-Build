@echo off
cd /d %~dp0..\backend
call .venv\Scripts\activate
echo Nexora Build API on http://127.0.0.1:8000   (API docs: http://127.0.0.1:8000/docs)
uvicorn app.main:app --reload --port 8000
pause
