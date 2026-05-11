import subprocess
import time
import socket
import os
import sys
import glob
import re
import importlib.util

# ==========================================
# 1. DATABASE REASSEMBLY
# ==========================================
def reassemble_database(base_name="db_part_", output_name="database.db"):
    parts = glob.glob(f"{base_name}*")
    if not parts:
        if os.path.exists(output_name): return
        return

    # Sort numerically (1, 2, 3... 10)
    parts.sort(key=lambda f: int(re.search(r'\d+', f).group()))

    if os.path.exists(output_name):
        return

    print(f"Merging {len(parts)} database parts...")
    with open(output_name, "wb") as output_file:
        for part in parts:
            with open(part, "rb") as f:
                output_file.write(f.read())
    print("Merge complete.")

# Ensure this name matches your FastAPI config
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
# 3. FRONTEND STARTUP (The "Module" Fix)
# ==========================================
root_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(root_dir, "frontend")
frontend_main = os.path.join(frontend_dir, "app.py")

# Add frontend to path so its internal imports work
if frontend_dir not in sys.path:
    sys.path.insert(0, frontend_dir)

# Change working directory so st.Page("pages/...") resolves correctly
os.chdir(frontend_dir)

if os.path.exists(frontend_main):
    # Instead of exec(f.read()), we import the module.
    # This allows Streamlit to correctly identify the file's location.
    spec = importlib.util.spec_from_file_location("frontend_app", frontend_main)
    module = importlib.util.module_from_spec(spec)
    sys.modules["frontend_app"] = module
    
    # This triggers the code inside your frontend/app.py
    spec.loader.exec_module(module)
    
    # If your frontend has a main() function, call it:
    if hasattr(module, 'main'):
        module.main()
else:
    print(f"Error: Could not find {frontend_main}")
