"""
End-to-End Server Verification Script
Validates that both FastAPI backend and Vite frontend start and serve requests.
"""

import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

def verify_all():
    print("=== [1/2] Verifying FastAPI Backend ===")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", "8000", "--host", "127.0.0.1"],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        time.sleep(2)
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(f"  GET /health -> HTTP {resp.status}: {data}")
            assert resp.status == 200
            assert data["status"] == "ok"
            
        with urllib.request.urlopen("http://127.0.0.1:8000/api/catalog/variables", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(f"  GET /api/catalog/variables -> HTTP {resp.status}: {data}")
            assert resp.status == 200
            assert data == []
        print("  FastAPI backend verified successfully.")
    finally:
        backend_proc.terminate()
        backend_proc.wait(timeout=5)

    print("\n=== [2/2] Verifying Vite Frontend Server ===")
    frontend_dir = ROOT_DIR / "frontend"
    frontend_proc = subprocess.Popen(
        ["npx.cmd", "vite", "preview", "--host", "127.0.0.1", "--port", "4173"],
        cwd=str(frontend_dir),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        time.sleep(3)
        with urllib.request.urlopen("http://127.0.0.1:4173/", timeout=5) as resp:
            html = resp.read().decode("utf-8")
            print(f"  GET http://127.0.0.1:4173/ -> HTTP {resp.status} (Length: {len(html)} bytes)")
            assert resp.status == 200
            assert '<div id="root">' in html
        print("  Vite frontend server verified successfully.")
    finally:
        # Kill process tree on Windows for shell=True
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], capture_output=True)

    print("\n=======================================================")
    print("SUCCESS: Both Frontend and Backend started and responded!")
    print("=======================================================\n")
    return 0

if __name__ == "__main__":
    sys.exit(verify_all())
