"""
Entry point for Practitioners Workload DB.
1. Merges database chunks into a single SQLite file.
2. Starts the FastAPI backend.
3. Runs the Streamlit frontend.
"""
import subprocess
import time
import socket
import os
import sys
import streamlit as st

# --- 1. إعداد المسارات الأساسية ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "PractitionersWorkloadDB.db")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 2. تجميع قاعدة البيانات (مهم جداً للبيانات) ---
def merge_db_chunks():
    if not os.path.exists(DB_FILE):
        print("Merging database chunks...")
        part_num = 1
        parts_found = []
        
        while True:
            part_path = os.path.join(BASE_DIR, f"db_part_{part_num}")
            if os.path.exists(part_path):
                parts_found.append(part_path)
                part_num += 1
            else:
                break
        
        if parts_found:
            try:
                with open(DB_FILE, "wb") as outfile:
                    for part in parts_found:
                        with open(part, "rb") as infile:
                            outfile.write(infile.read())
                print(f"✅ Database restored successfully from {len(parts_found)} parts.")
            except Exception as e:
                print(f"❌ Error merging chunks: {e}")
        else:
            print("⚠️ No database chunks found! App might show 0 results.")
    else:
        print("✅ Database file already exists.")

# تنفيذ الدمج قبل أي شيء
merge_db_chunks()

# --- 3. تشغيل الـ FastAPI Backend ---
if not is_port_in_use(8000):
    print("Starting FastAPI backend...")
    with open("backend_out.log", "w") as out, open("backend_err.log", "w") as err:
        subprocess.Popen(
            ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=out,
            stderr=err,
            env=os.environ.copy()
        )
    
    # الانتظار حتى يتأكد أن الـ Backend عمل Load للبيانات
    for i in range(15):
        if is_port_in_use(8000):
            print(f"Backend ready after {i} seconds.")
            break
        time.sleep(1)

# --- 4. تشغيل الـ Frontend (Streamlit) ---
# إضافة المسار الحالي لضمان عمل الـ Imports داخل المجلدات
sys.path.insert(0, BASE_DIR)

frontend_path = os.path.join(BASE_DIR, "frontend", "app.py")

if os.path.exists(frontend_path):
    # تشغيل ملف الـ frontend
    with open(frontend_path, encoding="utf-8") as f:
        code = f.read()
        # تنفيذ الكود مع الحفاظ على الـ Context
        exec(code, globals())
else:
    st.error(f"Error: Frontend file not found at {frontend_path}")
