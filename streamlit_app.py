import subprocess
import time
import socket
import os
import sys
import glob
import re

# ==========================================
# 1. DATABASE REASSEMBLY
# ==========================================
def reassemble_database(base_name="db_part_", output_name="database.db"):
    """Merges split binary files into a single SQLite database."""
    # Find all parts
    parts = glob.glob(f"{base_name}*")
    
    if not parts:
        if os.path.exists(output_name):
            return # Already merged
        print("No database parts found.")
        return

    # Sort numerically (1, 2, ... 10) instead of alphabetically
    parts.sort(key=lambda f: int(re.search(r'\d+', f).group()))

    if os.path.exists(output_name):
        print(f"Database {output_name} exists. Skipping merge.")
        return

    print(f"Merging {len(parts)} parts into {output_name}...")
    with open(output_name, "wb") as output_file:
        for part in parts:
            with open(part, "rb") as f:
                output_file.write(f.read())
    print("Merge complete.")

# Run this FIRST
reassemble_database(base_name="db_part_", output_name="database.db")


# ==========================================
# 2. BACKEND STARTUP (FastAPI)
# ==========================================
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    # Logs are saved to files to help you debug on Streamlit Cloud
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=out,
            stderr=err,
            env=os.environ.copy()
        )
    
    # Wait for the backend to wake up
    for i in range(15):
        if is_port_in_use(8000):
            print(f"Backend ready.")
            break
        time.sleep(1)


# ==========================================
# 3. FRONTEND STARTUP (The Fix)
# ==========================================
# Get absolute paths
root_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(root_dir, "frontend")
frontend_main = os.path.join(frontend_dir, "app.py")

# Add the frontend folder to sys.path so Python can find your modules
sys.path.insert(0, frontend_dir)

# --- THE CRITICAL FIX ---
# We change the current working directory to 'frontend'.
# This allows st.Page("pages/...") to find the files correctly.
os.chdir(frontend_dir)

if os.path.exists(frontend_main):
    with open(frontend_main, encoding="utf-8") as f:
        code = f.read()
        # Execute the frontend code within the frontend directory context
        exec(code, globals())
else:
    print(f"Error: Could not find {frontend_main}")
