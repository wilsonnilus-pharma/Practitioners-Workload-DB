"""
Entry point for Streamlit Community Cloud.
Merges database chunks, starts the FastAPI backend, then runs the frontend.
"""
import subprocess
import time
import socket
import os
import sys
import streamlit as st

# --- 1. GLUE RAW BINARY DB CHUNKS (CRITICAL FOR CLOUD) ---
db_file = "PractitionersWorkloadDB.db"

# If the full DB doesn't exist yet, build it from the parts
if not os.path.exists(db_file):
    part_num = 1
    parts_found = []
    
    while os.path.exists(f"db_part_{part_num}"):
        parts_found.append(f"db_part_{part_num}")
        part_num += 1

    if parts_found:
        print(f"Merging {len(parts_found)} raw database chunks...")
        with open(db_file, "wb") as outfile:
            for part in parts_found:
                with open(part, "rb") as infile:
                    outfile.write(infile.read())
        print("Database fully restored!")
    else:
        st.error("Error: Database file not found, and no db_part_ chunks were found either!")
        st.stop()

# --- 2. BACKEND PORT CHECK ---
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # 127.0.0.1 is the safest internal routing for Streamlit Cloud
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 3. START FASTAPI BACKEND ---
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    
    # We use sys.executable on Cloud to ensure it uses the correct Python environment
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=out,
            stderr=err,
            env=os.environ.copy()
        )
    
    print("Waiting for backend to be ready...")
    for i in range(15): # Wait up to 15 seconds
        if is_port_in_use(8000):
            print(f"Backend ready after {i} seconds.")
            break
        time.sleep(1)
    else:
        print("Warning: Backend did not start within 15 seconds. Check backend_err.log!")

# --- 4. PREPARE & RUN FRONTEND ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    print(f"Error: Frontend not found at {frontend_path}")
