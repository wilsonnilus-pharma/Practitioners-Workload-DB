"""
Entry point for Streamlit Community Cloud.
Extracts the database, starts the FastAPI backend, then runs the frontend.
"""
import os
import patoolib
import subprocess
import time
import socket
import sys

# --- 1. DATABASE EXTRACTION ---
# This looks for your 10MB .rar file and extracts it so the app can see the 98MB .db
rar_file = "PractitionersWorkloadDB.rar"
db_file = "PractitionersWorkloadDB.db"

if not os.path.exists(db_file):
    if os.path.exists(rar_file):
        print(f"Extracting {rar_file}...")
        try:
            patoolib.extract_archive(rar_file, outdir=".")
            print("Extraction complete.")
        except Exception as e:
            print(f"Error extracting database: {e}")
    else:
        print("Error: Database .rar file not found!")

# --- 2. BACKEND PORT CHECK ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 3. START FASTAPI BACKEND ---
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    subprocess.Popen(
        ["uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(5) # Increased wait time for extraction and startup

# --- 4. PREPARE FRONTEND ---
# Add current dir to path so frontend imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 5. RUN STREAMLIT FRONTEND ---
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    print(f"Error: Frontend file not found at {frontend_path}")
