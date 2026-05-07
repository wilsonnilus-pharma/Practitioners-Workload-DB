"""Paginated data table component."""

from __future__ import annotations
import pandas as pd
import streamlit as st
from frontend.api_client import get_data, export_csv

# Increase styler limit for "Show All" cases
pd.set_option("styler.render.max_elements", 5000000)

_ALL_ROWS = 100000000  # sentinel for "load all"


def render_table(filters: dict):
    """Render paginated data table with column searching and compact controls."""
    st.markdown("### 📋 Detailed Records")

    # Global CSS for checkbox label and font consistency
    st.markdown("""
        <style>
        .stCheckbox label { 
            font-size: 0.95rem !important; 
            color: #38bdf8 !important; 
            font-weight: 600 !important;
            font-family: 'Inter', sans-serif !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # ── Controls Row (Above Columns) ──
    col_labels = st.columns([1.5, 4.5])
    with col_labels[0]:
        # Matching style and color for the label
        st.markdown("<p style='font-size:0.95rem; font-weight:600; color:#38bdf8; font-family:\"Inter\", sans-serif; margin-top:2px; margin-bottom:2px;'>Rows per page</p>", unsafe_allow_html=True)
        show_all = st.checkbox("Show All Rows", key="chk_all_rows")

    # ── Main Controls (Aligned in one line) ──
    c1, c2, c3 = st.columns([1.2, 4, 1.5])
    
    with c1:
        page_size_input_val = st.session_state.get("_total_cache", 100) if show_all else int(st.session_state.get("page_size_val", 100))
        if show_all:
            page_size = 1000000 # Fetch all for the API
            st.number_input("Count", value=page_size_input_val, disabled=True, label_visibility="collapsed", key="ps_disabled")
        else:
            page_size = st.number_input("Count", min_value=1, max_value=1000000, value=page_size_input_val, step=50, key="page_size_val", label_visibility="collapsed")

    # Reset to page 1 when page_size changes
    if "last_ps" not in st.session_state or st.session_state["last_ps"] != page_size:
        st.session_state["table_page"] = 1
        st.session_state["last_ps"] = page_size

    page = st.session_state.get("table_page", 1)

    with st.spinner("Loading data…"):
        result = get_data(page=page, page_size=page_size, filters=filters)

    total      = result.get("total", 0)
    total_pages = result.get("total_pages", 1)
    data       = result.get("data", [])
    
    # Cache total for the "Show All" display in the next rerun
    st.session_state["_total_cache"] = total

    start_idx = ((page - 1) * page_size) + 1 if total > 0 else 0
    end_idx   = min(page * page_size, total)
    
    with c2:
        # Balanced middle alignment with reduced top margin
        st.markdown(f"<div style='margin-top:8px; color:#94a3b8; font-size:0.9rem; line-height:1.2;'>Showing <b>{start_idx:,}-{end_idx:,}</b> of <b>{total:,}</b> rows</div>", unsafe_allow_html=True)

    with c3:
        # Pushed up slightly to match the rest of the row
        st.markdown("<div style='margin-top:0px;'></div>", unsafe_allow_html=True)
        with st.spinner("..."):
            csv_bytes = export_csv(filters=filters)
        if csv_bytes:
            st.download_button(
                label="📥 Download Records",
                data=csv_bytes,
                file_name="PractitionersWorkloadDB_export.csv",
                mime="text/csv",
                key="dl_btn",
                use_container_width=True
            )

    if data:
        df = pd.DataFrame(data)
        
        # Reorder columns
        priority = [
            "region", "facility_name", "practitioner_id", "practitioner_name",
            "speciality", "visit_date", "month", "emergency", "inpatient", "outpatient", "total_cases"
        ]
        ordered = [c for c in priority if c in df.columns] + \
                  [c for c in df.columns if c not in priority]
        df = df[ordered]
        
        # 1-based row numbering
        df.insert(0, "no.", range(1, len(df) + 1))
        df.index = range(1, len(df) + 1)

        def style_df(df):
            styled = df.style
            if "emergency" in df.columns:
                styled = styled.apply(
                    lambda col: ["color: #f87171; font-weight: bold" if v > 0 else "" for v in col]
                    if col.name == "emergency" else [""] * len(col),
                    axis=0,
                )
            return styled

        # ── Table Display ─────────────────────────────────────────────
        # If the dataset is very large, skip styling to prevent browser hang
        if len(df) <= 10000:
            st.dataframe(style_df(df), use_container_width=True, height=480, hide_index=True)
        else:
            st.dataframe(df, use_container_width=True, height=480, hide_index=True)

    # ── Pagination controls ────────────────────
    if total_pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("← Prev", disabled=(page <= 1), key="btn_prev"):
                st.session_state["table_page"] = max(1, page - 1)
                st.rerun()
        with p2:
            st.markdown(
                f"<div style='text-align:center;margin-top:8px'>Page {page} / {total_pages}</div>",
                unsafe_allow_html=True,
            )
        with p3:
            if st.button("Next →", disabled=(page >= total_pages), key="btn_next"):
                st.session_state["table_page"] = min(total_pages, page + 1)
                st.rerun()
