"""
Streamlit entry point — Login gate.
Checks session state; shows login form or redirects to dashboard.
"""

import os
import json
import time
import streamlit as st
from frontend.api_client import login

SESSION_FILE = ".session.json"

def _token_is_valid(token: str) -> bool:
    """Return True only if the JWT is well-formed and not yet expired."""
    try:
        import base64
        parts = token.split(".")
        if len(parts) != 3:
            return False
        padded = parts[1] + "==" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        exp = payload.get("exp", 0)
        return time.time() < exp - 60
    except Exception:
        return False

st.set_page_config(
    page_title="Practitioners Workload DB — Login",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global dark theme CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* ── Unified login card — header + form same exact width ── */
.login-header-card {
    background: linear-gradient(160deg, #1e3a5f 0%, #1e293b 100%);
    border: 1px solid #2d4a6e;
    border-bottom: none;
    border-radius: 16px 16px 0 0;
    padding: 2.2rem 2rem 1.8rem;
    text-align: center;
    box-shadow: 0 -2px 20px rgba(0,0,0,0.3);
    width: 440px;
    max-width: 90vw;
    margin: 5rem auto 0;
    box-sizing: border-box;
}
.login-icon  { font-size: 2.8rem; margin-bottom: 0.5rem; display: block; }
.login-title {
    font-size: 1.7rem; font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.login-sub   { color: #64748b; font-size: 0.88rem; }

/* Streamlit form — matches header width exactly */
div[data-testid="stForm"] {
    background: #1e293b !important;
    border: 1px solid #2d4a6e !important;
    border-top: none !important;
    border-radius: 0 0 16px 16px !important;
    padding: 1.8rem 2rem 2rem !important;
    box-shadow: 0 12px 32px rgba(0,0,0,0.45) !important;
    width: 440px !important;
    max-width: 90vw !important;
    margin: 0 auto !important;
    box-sizing: border-box !important;
}
div[data-testid="stForm"] > div:first-child { padding: 0 !important; }
</style>
""", unsafe_allow_html=True)


def load_local_session():
    if "token" not in st.session_state and os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
            token = data.get("token", "")
            if _token_is_valid(token):
                st.session_state["token"] = token
                st.session_state["username"] = data["username"]
                st.session_state["role"] = data["role"]
            else:
                try:
                    os.remove(SESSION_FILE)
                except OSError:
                    pass
        except Exception:
            pass

def show_login():
    st.markdown("""
    <div class="login-header-card">
        <span class="login-icon">📊</span>
        <div class="login-title">Practitioners Workload DB</div>
        <div class="login-sub">Practitioners Analytics Dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", placeholder="admin", key="login_user")
        password = st.text_input("Password", type="password", placeholder="••••••••", key="login_pass")
        submitted = st.form_submit_button("🔐 Sign In", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Please enter username and password.")
        else:
            with st.spinner("Authenticating…"):
                result = login(username, password)
            if result:
                st.session_state["token"] = result["access_token"]
                st.session_state["username"] = result["username"]
                st.session_state["role"] = result["role"]
                
                try:
                    with open(SESSION_FILE, "w") as f:
                        json.dump({
                            "token": result["access_token"],
                            "username": result["username"],
                            "role": result["role"]
                        }, f)
                except Exception:
                    pass
                    
                st.success(f"Welcome, **{result['username']}**!")
                st.rerun()
            else:
                st.error("Invalid username or password.")

def main():
    load_local_session()
    
    if "token" not in st.session_state:
        login_pg = st.Page(show_login, title="Log In", icon="🔐")
        pg = st.navigation([login_pg])
        pg.run()
    else:
        # CRITICAL FIX FOR CLOUD: Paths must start with frontend/pages/
        dash_pg = st.Page("frontend/pages/1_dashboard.py", title="Dashboard", icon="📊")
        upload_pg = st.Page("frontend/pages/2_upload.py", title="Upload & Files", icon="📤")
        
        pg = st.navigation([dash_pg, upload_pg])
        pg.run()

if __name__ == "__main__":
    main()
