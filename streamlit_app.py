import subprocess
import time
import socket
import os
import sys
import glob
import re

# ==========================================
# 1. DATABASE REASSEMBLY (Keep this at the top)
# ==========================================
def reassemble_database(base_name="db_part_", output_name="database.db"):
    parts = glob.glob(f"{base_name}*")
    if not parts:
        if os.path.exists(output_name): return
        return

    # Numerical sort to ensure part_2 comes before part_10
    parts.sort(key=lambda f: int(re.search(r'\d+', f).group()))

    if os.path.exists(output_name):
        return

    print(f"Merging {len(parts)} database parts...")
    with open(output_name, "wb") as output_file:
        for part in parts:
            with open(part, "rb") as f:
                output_file.write(f.read())
    print("Merge complete.")

# Ensure the output_name matches what your FastAPI/SQLAlchemy code uses
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
# 3. FRONTEND STARTUP (The Robust Fix)
# ==========================================
root_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(root_dir, "frontend")
frontend_main = os.path.join(frontend_dir, "app.py")

# 1. Add frontend to sys.path for internal imports
sys.path.insert(0, frontend_dir)

# 2. Change working directory
os.chdir(frontend_dir)

if os.path.exists(frontend_main):
    with open(frontend_main, encoding="utf-8") as f:
        code = f.read()
        
        # 3. THE FIX: Create a custom global context
        # We manually set __file__ so st.Page() knows where it is relative to the pages/ folder
        context = globals().copy()
        context["__file__"] = frontend_main
        
        exec(code, context)
else:
    print(f"Error: Could not find {frontend_main}")
