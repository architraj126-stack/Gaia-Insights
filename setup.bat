@echo off
echo ========================================================
echo Setting up Earth Science Explorer (Phase 0 Monorepo)
echo ========================================================

echo [1/3] Installing backend requirements...
python -m pip install -r backend/requirements.txt
if not exist "backend\.env" (
    echo Copying backend\.env.example to backend\.env...
    copy backend\.env.example backend\.env
)

echo [2/3] Installing frontend dependencies...
cd frontend
call npm install
cd ..

echo [3/3] Creating local cache directory...
if not exist "data\cache" mkdir data\cache

echo ========================================================
echo Setup complete! Run run.bat to start both servers.
echo ========================================================
