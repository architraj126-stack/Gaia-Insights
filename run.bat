@echo off
echo ========================================================
echo Starting Earth Science Explorer
echo ========================================================
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "Backend (FastAPI)" cmd /k "python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Vite Frontend on http://localhost:5173 ...
start "Frontend (Vite)" cmd /k "cd frontend && npm run dev"

echo Both servers launched in separate windows!
echo Backend:  http://127.0.0.1:8000/health
echo Frontend: http://localhost:5173
