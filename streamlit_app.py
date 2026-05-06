"""
Diagnostic Entry point for Streamlit Community Cloud.
Captures backend errors and displays them on the screen.
"""
import os
import patoolib
import subprocess
import time
import socket
import sys
import streamlit as st

# --- 1. DATABASE EXTRACTION ---
rar_file = "PractitionersWorkloadDB.rar"
db_file = "PractitionersWorkloadDB.db"

if not os.path.exists(db_file):
    if os.path.exists(rar_file):
        print(f"Extracting {rar_file}...")
        try:
            patoolib.extract_archive(rar_file, outdir=".")
        except Exception as e:
            st.error(f"Failed to extract database: {e}")
            st.stop()
    else:
        st.error("Error: Database .rar file not found!")
        st.stop()

# --- 2. BACKEND PORT CHECK ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 3. START FASTAPI BACKEND WITH ERROR CAPTURE ---
if not is_port_in_use(8000):
    # We will write all backend errors to this text file
    err_log_path = "backend_crash.log"
    
    with open(err_log_path, "w") as err_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=err_file # Capture the crash here!
        )
    
    # Wait for up to 15 seconds for the port to open
    port_opened = False
    for _ in range(15):
        if is_port_in_use(8000):
            port_opened = True
            break
        time.sleep(1)
    
    # If the port NEVER opened, the backend crashed. Let's read the error.
    if not port_opened:
        with open(err_log_path, "r") as err_file:
            crash_reason = err_file.read()
        
        st.error("🚨 THE FASTAPI BACKEND CRASHED 🚨")
        st.error("Here is the real reason it failed to start:")
        st.code(crash_reason, language="python")
        st.stop() # Stop the frontend from loading so we don't get the ConnectionError

# --- 4. PREPARE FRONTEND ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 5. RUN STREAMLIT FRONTEND ---
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    st.error(f"Frontend file not found at {frontend_path}")
