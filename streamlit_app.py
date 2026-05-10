"""
Main Entry Point for Streamlit Community Cloud.
Location: /streamlit_app.py (Root)
"""
import subprocess
import time
import socket
import os
import sys
import urllib.request
import urllib.error

# --- CONFIGURATION: UPDATE THESE ---
# 1. Change 'username' and 'repo' to your actual GitHub details
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/wilsonnilus-pharma/Practitioners-Workload-DB/main/db_part" 
FINAL_DB_PATH = "PractitionersWorkloadDB.db" # This must match what your backend logic looks for

def assemble_database_from_github(base_url, output_db_path):
    if os.path.exists(output_db_path):
        print(f"Database {output_db_path} exists. Skipping.")
        return

    print("Downloading database parts...")
    part_number = 1
    try:
        with open(output_db_path, 'wb') as outfile:
            while True:
                part_url = f"{base_url}_{part_number}"
                try:
                    response = urllib.request.urlopen(part_url)
                    outfile.write(response.read())
                    print(f"✅ Downloaded part {part_number}")
                    part_number += 1
                except urllib.error.HTTPError as e:
                    if e.code == 404: break
                    raise e
    except Exception as e:
        print(f"❌ Error downloading DB: {e}")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- EXECUTION ---
# 1. Assemble DB
assemble_database_from_github(GITHUB_RAW_BASE_URL, FINAL_DB_PATH)

# 2. Start Backend
if not is_port_in_use(8000):
    print("🚀 Starting FastAPI backend...")
    # Set PYTHONPATH so uvicorn can find the 'backend' folder
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=out, stderr=err, env=env
        )
    
    # Wait for ready
    for i in range(15):
        if is_port_in_use(8000):
            print(f"✅ Backend ready on port 8000.")
            break
        time.sleep(1)

# 3. Launch Frontend
# Adding current directory to sys.path so 'import frontend' works inside app.py
sys.path.insert(0, os.getcwd())

frontend_file = os.path.join("frontend", "app.py")
if os.path.exists(frontend_file):
    with open(frontend_file, encoding="utf-8") as f:
        code = f.read()
    exec(code, globals())
else:
    print(f"❌ Could not find {frontend_file}")
