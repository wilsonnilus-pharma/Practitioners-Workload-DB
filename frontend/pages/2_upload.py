"""Upload and Import History page — drag-and-drop file upload and file management."""

import time
import pandas as pd
import streamlit as st
from frontend.api_client import upload_file, get_scan_status, get_files, delete_api_file

st.set_page_config(
    page_title="Practitioners Workload DB — Upload & Files",
    page_icon="📤",
    layout="wide",
)

# ── Auth gate ──────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.warning("⚠️ Please log in first.")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("🔒 Admin access required to upload files.")
    st.stop()

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%); color: #f1f5f9; }
.upload-header { font-size: 1.8rem; font-weight: 800; color: #f1f5f9; margin-bottom: 0.5rem; }
.upload-sub { color: #64748b; margin-bottom: 2rem; }
.stTabs [data-baseweb="tab-list"] { gap: 2rem; }
.stTabs [data-baseweb="tab"] { font-weight: 600; color: #94a3b8; }
.stTabs [aria-selected="true"] { color: #60a5fa !important; }
/* Tighten the history rows */
div[data-testid="stHorizontalBlock"] { align-items: center; }
div.stButton > button { padding: 0.2rem 0.5rem !important; min-height: 30px !important; }
div[data-testid="stVerticalBlock"] > div > div > div > div > p { margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="upload-header">📤 Upload & Files</div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📤 Upload New File", "📁 Import History"])

# ── TAB 1: Upload ─────────────────────────────────────────────────────────
with tab1:
    st.markdown(
        '<div class="upload-sub">Upload a CSV or XML file to import into the database. '
        'Duplicate files (same content) will be skipped automatically.</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Choose a CSV or XML file",
        type=["csv", "xml"],
        accept_multiple_files=False,
        key="file_uploader",
    )

    st.markdown("---")
    st.markdown("### 📄 Practitioners Workload")

    if not uploaded:
        st.info("💡 Please upload your `Practitioners Workload` file above. A preview will appear here.")
    else:
        try:
            uploaded.seek(0)
            total_lines = sum(1 for _ in uploaded)
            total_rows = max(0, total_lines - 1)
            uploaded.seek(0)
        except Exception:
            total_rows = "Unknown"

        st.success(f"📁 **File Selected:** `{uploaded.name}`  |  **Size:** `{uploaded.size / 1024:.1f} KB`  |  **Total Rows:** `{total_rows:,}`")
        
        st.markdown(f"#### 👀 Preview: {uploaded.name} (First 20 rows)")
        try:
            uploaded.seek(0)
            preview_df = pd.read_csv(uploaded, nrows=20)
            st.dataframe(preview_df, use_container_width=True)
            uploaded.seek(0)
        except Exception as e:
            st.warning(f"Could not preview file: {e}")

        st.markdown("---")
        if st.button("🚀 Confirm Upload & Import", type="primary"):
            with st.spinner(f"Uploading `{uploaded.name}`…"):
                result = upload_file(uploaded.name, uploaded.getvalue())

            if "error" in result and result.get("error"):
                st.error(f"❌ Upload failed: {result['error']}")
            else:
                st.success(f"✅ {result.get('message', 'Uploaded successfully!')}")

                st.markdown("#### Import Progress")
                progress_bar = st.progress(0)
                status_text = st.empty()

                for _ in range(60):   # poll up to 60 times (60s)
                    status = get_scan_status()
                    if not status:
                        break
                    running = status.get("running", False)
                    processed = status.get("processed", 0)
                    total = max(status.get("total_files", 1), 1)
                    current = status.get("current_file", "")

                    progress_bar.progress(processed / total)
                    status_text.markdown(f"**{processed}/{total}** files processed" + (f" — `{current}`" if current else ""))

                    if not running:
                        break
                    time.sleep(1)

                final_status = get_scan_status()
                results = final_status.get("results", [])
                if results:
                    st.markdown("#### Results")
                    for r in results:
                        icon = "✅" if r["status"] == "success" else "⏭" if r["status"] == "skipped" else "❌"
                        st.markdown(
                            f"{icon} **{r['filename']}** — {r['status']}"
                            + (f" ({r['rows']:,} rows)" if r.get("rows") else "")
                            + (f" — _{r['error']}_" if r.get("error") else "")
                        )

# ── TAB 2: Files History & Delete ─────────────────────────────────────────
with tab2:
    st.markdown("### 📁 Import History")
    col1, col2 = st.columns([2, 6])
    status_filter = col1.selectbox("Filter by status", ["All", "success", "failed", "pending"], key="file_status_filter")
    
    # State for trigger rerender after delete
    if "delete_trigger" not in st.session_state:
        st.session_state["delete_trigger"] = 0

    with st.spinner("Loading file history…"):
        data = get_files(status=status_filter if status_filter != "All" else None)

    files = data.get("files", [])
    if files:
        df = pd.DataFrame(files)
        # Custom render with delete buttons
        st.markdown("---")
        
        # Header row
        hcol1, hcol2, hcol3, hcol4, hcol5, hcol6 = st.columns([3, 2, 2, 2, 2, 1])
        hcol1.markdown("**Filename**")
        hcol2.markdown("**Status**")
        hcol3.markdown("**Rows**")
        hcol4.markdown("**Size**")
        hcol5.markdown("**Imported At**")
        hcol6.markdown("**Action**")
        
        st.markdown("---")
        
        for idx, row in df.iterrows():
            with st.container():
                c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 1])
                c1.markdown(f"`{row['filename']}`")
                
                # Status badge
                status_color = "green" if row['import_status'] == "success" else "red" if row['import_status'] == "failed" else "orange"
                c2.markdown(f"<span style='color:{status_color}; font-weight:bold'>{row['import_status']}</span>", unsafe_allow_html=True)
                
                if row['import_status'] == 'pending':
                    c3.markdown("⏳ **Importing...**")
                else:
                    c3.markdown(f"{row['row_count']:,}" if row['row_count'] else "0")
                
                size_mb = f"{row['file_size_bytes'] / (1024**2):.2f} MB" if pd.notnull(row.get('file_size_bytes')) else "—"
                c4.markdown(size_mb)
                
                date_str = pd.to_datetime(row['imported_at']).strftime("%Y-%m-%d %H:%M") if pd.notnull(row.get('imported_at')) else "—"
                c5.markdown(date_str)
                
                # Delete button
                if c6.button("🗑️", key=f"del_{row['id']}", help="Delete file and its records"):
                    with st.spinner("Deleting..."):
                        res = delete_api_file(row['id'])
                        if "error" in res:
                            st.error(f"Failed to delete: {res['error']}")
                        else:
                            st.success("Deleted!")
                            time.sleep(0.5)
                            st.session_state["delete_trigger"] += 1
                            st.rerun()
                
                if row['import_status'] == 'success':
                    with st.expander(f"👀 View imported data for `{row['filename']}`"):
                        if st.button("Load Preview", key=f"preview_{row['id']}"):
                            with st.spinner("Loading preview..."):
                                from frontend.api_client import get_data
                                res = get_data(page=1, page_size=20, filters={"source_file_id": row['id']})
                                if res and res.get("data"):
                                    # Hide columns like ID to keep it clean
                                    pdf = pd.DataFrame(res["data"])
                                    if "id" in pdf.columns:
                                        pdf.drop(columns=["id"], inplace=True)
                                    st.dataframe(pdf, use_container_width=True)
                                else:
                                    st.info("No data found.")
                st.markdown("<hr style='margin: 0.5em 0; border-color: #334155;'>", unsafe_allow_html=True)
    else:
        st.info("No import records found.")

# ── Sidebar logout ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        for key in ["token", "username", "role"]:
            st.session_state.pop(key, None)
        import os
        if os.path.exists(".session.json"):
            os.remove(".session.json")
        st.rerun()


