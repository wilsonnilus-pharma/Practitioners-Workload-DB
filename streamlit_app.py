"""
Entry point for Streamlit Community Cloud.
Starts the FastAPI backend in the background, then runs the frontend.
"""
import subprocess
import time
import socket
import os
import sys

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # Use 0.0.0.0 to check all interfaces
        return s.connect_ex(('127.0.0.1', port)) == 0

# Start backend if not running
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    # Bind to 0.0.0.0 for better compatibility in containers
    # Redirect logs to files so we can debug if it fails
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=out,
            stderr=err,
            env=os.environ.copy()
        )
    
    # Wait longer for the backend to initialize (especially if DB is large)
    print("Waiting for backend to be ready...")
    for i in range(15): # Wait up to 15 seconds
        if is_port_in_use(8000):
            print(f"Backend ready after {i} seconds.")
            break
        time.sleep(1)
    else:
        print("Warning: Backend did not start within 15 seconds.")

# Add current dir to path so frontend imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run the frontend app
frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
if os.path.exists(frontend_path):
    with open(frontend_path, encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    print(f"Error: Frontend not found at {frontend_path}")
