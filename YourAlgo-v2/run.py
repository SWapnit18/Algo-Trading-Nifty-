#!/usr/bin/env python3
"""
YourAlgo v2 — Unified Platform Launcher
Run with:
    python run.py          (Unified production mode: Serves backend + UI on http://127.0.0.1:8000)
    python run.py --dev    (Full development mode: Backend on :8000 + Vite hot-reload on :5173)
"""

import sys
import os
import subprocess
import time
import webbrowser
import signal
import shutil

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")

def print_banner():
    print("=" * 65)
    print("   🚀 YourAlgo v2 — Indian Equity Algorithmic Platform")
    print("   Authoritative Real Market Data: NSE / UPSTOX API v2")
    print("=" * 65)

def check_env():
    env_file = os.path.join(ROOT_DIR, ".env")
    backend_env = os.path.join(BACKEND_DIR, ".env")
    if not os.path.exists(env_file) and not os.path.exists(backend_env):
        print("⚠️ Warning: .env file not found. Copying .env.example to .env...")
        example = os.path.join(ROOT_DIR, ".env.example")
        if os.path.exists(example):
            shutil.copyfile(example, env_file)
            print("✅ Created .env from .env.example. Please populate your Upstox credentials.")

def ensure_frontend_built():
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.exists(index_html):
        print("📦 Building React Frontend (one-time setup)...")
        res = subprocess.run("npm run build", cwd=FRONTEND_DIR, shell=True)
        if res.returncode != 0:
            print("⚠️ Frontend build encountered warnings, falling back to Vite dev mode.")
            return False
    print("✅ Frontend bundle ready at frontend/dist.")
    return True

def run_unified():
    print_banner()
    check_env()
    built = ensure_frontend_built()

    print("\n🟢 Starting Unified Server on http://127.0.0.1:8000 ...")
    print("   - API Endpoints: http://127.0.0.1:8000/api/v1/*")
    print("   - WebSocket Feed: ws://127.0.0.1:8000/ws/market-feed")
    print("   - Interactive UI: http://127.0.0.1:8000/\n")

    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    
    # Open browser after a brief delay
    def open_browser():
        time.sleep(1.8)
        try:
            webbrowser.open("http://127.0.0.1:8000/")
        except Exception:
            pass

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        proc = subprocess.Popen(cmd, cwd=BACKEND_DIR)
        proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down YourAlgo v2 server...")
        proc.terminate()
        proc.wait()
        print("✅ Shutdown complete.")

def run_dev():
    print_banner()
    check_env()

    print("\n🟢 Starting Development Environment...")
    print("   - Backend (Uvicorn): http://127.0.0.1:8000")
    print("   - Frontend (Vite HMR): http://127.0.0.1:5173")
    print("   - Press Ctrl+C to stop both services.\n")

    backend_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    frontend_cmd = "npm run dev -- --host 127.0.0.1 --port 5173"

    backend_proc = subprocess.Popen(backend_cmd, cwd=BACKEND_DIR)
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=FRONTEND_DIR, shell=True)

    def open_browser():
        time.sleep(2.0)
        try:
            webbrowser.open("http://127.0.0.1:5173/")
        except Exception:
            pass

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        while True:
            time.sleep(0.5)
            if backend_proc.poll() is not None or frontend_proc.poll() is not None:
                break
    except KeyboardInterrupt:
        print("\n🛑 Stopping both services...")
    finally:
        try:
            backend_proc.terminate()
            subprocess.run(f"taskkill /F /T /PID {backend_proc.pid}", shell=True, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            frontend_proc.terminate()
            subprocess.run(f"taskkill /F /T /PID {frontend_proc.pid}", shell=True, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        print("✅ All processes stopped.")

if __name__ == "__main__":
    if "--dev" in sys.argv:
        run_dev()
    else:
        run_unified()
