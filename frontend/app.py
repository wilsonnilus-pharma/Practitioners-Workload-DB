"""
Streamlit Frontend — Login & Navigation.
Location: /frontend/app.py
"""
import os
import json
import time
import streamlit as st

# Import the login function from your existing client
try:
    from frontend.api_client import login
except ImportError:
    # Fallback for different pathing structures
    from api_client import login

SESSION_FILE = ".session.json"

def _token_is_valid(token: str) -> bool:
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3: return False
        padded = parts[1] + "==" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return time.time() < payload.get("exp", 0) - 60
    except:
        return False

st.set_page_config(page_title="Practitioners Workload", page_icon="📊", layout="wide")

# Custom CSS (Keeping your design)
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); }
    div[data-testid="stForm"] { background: #1e293b !important; border-radius: 16px !important; border: 1px solid #2d4a6e !important; }
</style>
""", unsafe_allow_html=True)

def show_login():
    st.markdown('<h1 style="text-align:center; color:#60a5fa;">📊 Login</h1>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("🔐 Sign In", use_container_width=True):
            if username and password:
                with st.spinner("Logging in..."):
                    result = login(username, password)
                    if result:
                        st.session_state["token"] = result["access_token"]
                        st.session_state["username"] = result["username"]
                        st.success("Success!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

def main():
    if "token" not in st.session_state:
        show_login()
    else:
        # Navigation
        pg = st.navigation([
            st.Page("pages/1_dashboard.py", title="Dashboard", icon="📊"),
            st.Page("pages/2_upload.py", title="Upload Data", icon="📤")
        ])
        pg.run()

if __name__ == "__main__":
    main()
