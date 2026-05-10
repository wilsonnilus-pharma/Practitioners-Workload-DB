"""
Entry point for Streamlit Community Cloud.
Downloads split database files from GitHub, assembles them,
starts the FastAPI backend in the background, then runs the frontend.
"""
import subprocess
import time
import socket
import os
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------
# Database Download and Assembly Logic
# ---------------------------------------------------------
def assemble_database_from_github(base_url, output_db_path):
    """
    Downloads split database files from GitHub and concatenates them.
    Expects files to be named with a numeric suffix (e.g., _1, _2).
    """
    # Skip download if the complete database already exists
    if os.path.exists(output_db_path):
        print(f"Database {output_db_path} already exists. Skipping download.")
        return

    print("Starting database assembly from GitHub...")
    part_number = 1
    
    with open(output_db_path, 'wb') as outfile:
        while True:
            # Construct the URL for the current part (e.g., base_url_1)
            part_url = f"{base_url}_{part_number}"
            
            try:
                print(f"Fetching {part_url}...")
                response = urllib.request.urlopen(part_url)
                outfile.write(response.read())
                part_number += 1
            except urllib.error.HTTPError as e:
                # A 404 error means we have reached the end of the parts
                if e.code == 404:
                    print(f"Finished downloading. Assembled {part_number - 1} parts.")
                    break
                else:
                    print(f"HTTP Error encountered: {e.code}")
                    break
            except Exception as e:
                print(f"An error occurred during download: {e}")
                break
                
    print("Database assembly complete.")

# --- CONFIGURATION: Update these variables ---
# Replace with your actual RAW GitHub URL up to "db_part"
# Example: "https://raw.githubusercontent.com/username/repo/main/data/db_part"
GITHUB_RAW_BASE_URL = "YOUR_RAW_GITHUB_URL_HERE" 
FINAL_DB_PATH = "my_database.db" # The name of the database your backend expects

# Run the assembly before starting the backend
assemble_database_from_github(GITHUB_RAW_BASE_URL, FINAL_DB_PATH)

# ---------------------------------------------------------
# Backend and Frontend Startup Logic
# ---------------------------------------------------------
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
