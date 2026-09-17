@echo off
title Material Setu Backend
echo ==============================================
echo   Starting Material Setu Backend (FastAPI)
echo   API URL: http://127.0.0.1:8000
echo   API Docs: http://127.0.0.1:8000/docs
echo ==============================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
