import subprocess
import time
import socket
import os
import sys
import glob
import re

# ==========================================
# 1. DATABASE MERGE LOGIC
# ==========================================
def reassemble_database(base_name="db_part_", output_name="database.db"):
    parts = glob.glob(f"{base_name}*")
    if not parts:
        if os.path.exists(output_name): return
        return

    parts.sort(key=lambda f: int(re.search(r'\d+', f).group()))
    if os.path.exists(output_name):
        return

    print(f"Merging database parts into '{output_name}'...")
    with open(output_name, "wb") as output_file:
        for part in parts:
            with open(part, "rb") as f:
                output_file.write(f.read())

# Run merge (make sure output name matches your FastAPI config)
reassemble_database(base_name="db_part_", output_name="database.db")


# ==========================================
# 2. BACKEND STARTUP (FastAPI)
# ==========================================
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=out, stderr=err, env=os.environ.copy()
        )
    
    for i in range(15):
        if is_port_in_use(8000):
            break
        time.sleep(1)


# ==========================================
# 3. FRONTEND STARTUP (Streamlit Fix)
# ==========================================
# Get the absolute path to the frontend directory
root_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(root_dir, "frontend")

# 1. Add frontend to sys.path so imports still work
sys.path.insert(0, frontend_dir)

# 2. CRITICAL FIX: Change the working directory to 'frontend' 
# This allows st.Page() to find the files it's looking for.
os.chdir(frontend_dir)

frontend_file = "app.py"
if os.path.exists(frontend_file):
    print("Launching Streamlit frontend...")
    with open(frontend_file, encoding="utf-8") as f:
        # We execute the file while contextually being 'inside' the frontend folder
        exec(f.read(), globals())
else:
    print(f"Error: Could not find {frontend_file} inside {frontend_dir}")
