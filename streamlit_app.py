"""
Entry point for Streamlit Community Cloud.
Starts the FastAPI backend in the background, then runs the frontend.
"""
import subprocess
import time
import socket
import os

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# Start backend if not running
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    subprocess.Popen(
        ["uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3) # Wait for backend to be ready

# Add current dir to path so frontend imports work
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run the frontend app
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
with open(frontend_path, encoding="utf-8") as f:
    exec(f.read(), globals())
