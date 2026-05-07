"""
Entry point for Practitioners Workload DB on Hugging Face.
1. Merges database chunks.
2. Starts FastAPI backend safely.
3. Runs the Streamlit frontend.
"""
import subprocess
import time
import socket
import os
import sys
import streamlit as st

# --- 1. إعداد الصفحة (يجب أن يكون أول سطر) ---
st.set_page_config(page_title="Practitioners Workload DB", layout="wide")

# إعداد المسارات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
# تأكد أن هذا هو نفس المسار الذي يبحث عنه FastAPI في backend/config.py
DB_FILE = os.path.join(BASE_DIR, "PractitionersWorkloadDB.db")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(('127.0.0.1', port)) == 0

# --- 2. التهيئة (الكاش يمنع التكرار مع الـ Refresh) ---
@st.cache_resource
def init_system():
    # أ. تجميع قاعدة البيانات (عشان الداتا متقراش أصفار)
    if not os.path.exists(DB_FILE):
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
                print(f"✅ Database merged successfully from {len(parts_found)} chunks.")
            except Exception as e:
                print(f"❌ Error merging database: {e}")
        else:
            print("⚠️ No database chunks found! Backend will create an empty DB (All 0s).")

    # ب. تشغيل محرك البيانات (FastAPI)
    if not is_port_in_use(8000):
        env = os.environ.copy()
        env["PYTHONPATH"] = BASE_DIR
        
        # تشغيل آمن يتجنب الـ Crashes
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-use-colors"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL
        )
        
        # ج. الانتظار حتى يعمل السيرفر
        with st.spinner("جاري تهيئة قاعدة البيانات والسيرفر..."):
            for _ in range(15):
                if is_port_in_use(8000):
                    return True
                time.sleep(1)
        return False
    return True

# --- 3. التنفيذ ---
if not init_system():
    st.error("❌ فشل تشغيل السيرفر الخلفي (FastAPI).")
    st.stop()

# --- 4. تشغيل الواجهة وتصحيح المسارات ---
if FRONTEND_DIR not in sys.path:
    sys.path.insert(0, FRONTEND_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# تغيير مسار العمل عشان Streamlit يلاقي مجلد pages
os.chdir(FRONTEND_DIR)

if os.path.exists("app.py"):
    with open("app.py", encoding="utf-8") as f:
        exec(f.read(), globals())
else:
    st.error(f"ملف الواجهة مفقود في: {FRONTEND_DIR}")
