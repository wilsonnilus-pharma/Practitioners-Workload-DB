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
    """
    Finds all files starting with base_name, sorts them numerically,
    and merges them into a single file.
    """
    # Find all matching parts
    parts = glob.glob(f"{base_name}*")
    
    if not parts:
        print("No database parts found. Checking if merged database already exists...")
        if os.path.exists(output_name):
            return
        else:
            print("Error: No parts and no existing database found.")
            return

    # Sort parts by the number in the filename (e.g., part_1, part_2, part_10)
    parts.sort(key=lambda f: int(re.search(r'\d+', f).group()))

    # Avoid re-merging if the file is already there (saves time/resources)
    if os.path.exists(output_name):
        print(f"Database '{output_name}' already exists. Skipping merge.")
        return

    print(f"Merging {len(parts)} parts into '{output_name}'...")
    try:
        with open(output_name, "wb") as output_file:
            for part in parts:
                with open(part, "rb") as f:
                    output_file.write(f.read())
        print("Merge complete.")
    except Exception as e:
        print(f"Failed to merge database: {e}")

# IMPORTANT: Set 'output_name' to the exact filename your FastAPI/SQLAlchemy code expects.
reassemble_database(base_name="db_part_", output_name="database.db")


# ==========================================
# 2. BACKEND STARTUP (FastAPI)
# ==========================================
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# Start backend if not running
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    # Redirect logs to files for debugging
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=out,
            stderr=err,
            env=os.environ.copy()
        )
    
    print("Waiting for backend to be ready...")
    for i in range(15):
        if is_port_in_use(8000):
            print(f"Backend ready after {i} seconds.")
            break
        time.sleep(1)
    else:
        print("Warning: Backend did not start within 15 seconds.")


# ==========================================
# 3. FRONTEND STARTUP (Streamlit)
# ==========================================
# Add current dir to path so frontend imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    print("Launching Streamlit frontend...")
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    print(f"Error: Frontend not found at {frontend_path}")
