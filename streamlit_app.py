"""
Diagnostic Entry point for Streamlit Community Cloud.
Merges raw binary DB chunks, starts the backend, and runs the frontend.
"""
import os
import subprocess
import time
import socket
import sys
import streamlit as st

# --- 1. GLUE RAW BINARY CHUNKS ---
db_file = "PractitionersWorkloadDB.db"

if not os.path.exists(db_file):
    part_num = 1
    parts_found = []
    
    # Dynamically find all parts (db_part_1, db_part_2, etc.)
    while os.path.exists(f"db_part_{part_num}"):
        parts_found.append(f"db_part_{part_num}")
        part_num += 1

    if parts_found:
        try:
            print(f"Merging {len(parts_found)} raw database chunks...")
            with open(db_file, "wb") as outfile:
                for part in parts_found:
                    with open(part, "rb") as infile:
                        outfile.write(infile.read())
            print("Database fully restored!")
        except Exception as e:
            st.error(f"Failed to merge raw chunks: {e}")
            st.stop()
    else:
        st.error("Error: Database file not found, and no db_part_ chunks were found either!")
        st.stop()

# --- 2. BACKEND PORT CHECK ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 3. START FASTAPI BACKEND ---
if not is_port_in_use(8000):
    err_log_path = "backend_crash.log"
    
    with open(err_log_path, "w") as err_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=err_file 
        )
    
    port_opened = False
    for _ in range(15):
        if is_port_in_use(8000):
            port_opened = True
            break
        time.sleep(1)
    
    if not port_opened:
        with open(err_log_path, "r") as err_file:
            crash_reason = err_file.read()
        
        st.error("🚨 THE FASTAPI BACKEND CRASHED 🚨")
        st.error("Here is the real reason it failed to start:")
        st.code(crash_reason, language="python")
        st.stop() 

# --- 4. PREPARE FRONTEND ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- 5. RUN STREAMLIT FRONTEND ---
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    st.error(f"Frontend file not found at {frontend_path}")
