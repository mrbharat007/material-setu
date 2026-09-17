@echo off
title Material Setu - Launch All
echo ==============================================
echo   Launching Material Setu (Backend + Frontend)
echo ==============================================
start "Material Setu Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul
start "Material Setu Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo Both Backend and Frontend have been started in separate windows!
echo Backend:  http://127.0.0.1:8000/docs
echo Frontend: http://localhost:5173
echo ==============================================
pause
