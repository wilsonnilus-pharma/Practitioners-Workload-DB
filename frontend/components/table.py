"""Paginated data table component."""

from __future__ import annotations
import streamlit as st
import pandas as pd
from frontend.api_client import get_data, export_csv


_ALL_ROWS = 2_000_000  # sentinel for "load all"


def render_table(filters: dict):
    """Render paginated data table with download button."""
    st.markdown("### 📋 Detailed Records")

    col_ps, col_dl = st.columns([3, 1])

    page_size_label = col_ps.selectbox(
        "Rows per page",
        ["50", "100", "250", "500", "1,000", "All"],
        index=1,
        key="page_size",
    )
    page_size = _ALL_ROWS if page_size_label == "All" else int(page_size_label.replace(",", ""))

    # Reset to page 1 when "All" selected
    page = 1 if page_size == _ALL_ROWS else st.session_state.get("table_page", 1)

    with st.spinner("Loading data…"):
        result = get_data(page=page, page_size=page_size, filters=filters)

    total      = result.get("total", 0)
    total_pages = result.get("total_pages", 1)
    data       = result.get("data", [])

    st.caption(f"**{total:,} records** match current filters — Page {page} of {total_pages}")

    if data:
        df = pd.DataFrame(data)
        # Reorder columns for readability
        priority = [
            "region", "facility_name", "practitioner_id", "practitioner_name",
            "speciality", "visit_date", "emergency", "inpatient", "outpatient",
        ]
        ordered = [c for c in priority if c in df.columns] + \
                  [c for c in df.columns if c not in priority]
        df = df[ordered]
        # 1-based row numbering
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

        st.dataframe(style_df(df), use_container_width=True, height=420)

    # ── Pagination controls (hidden when showing all) ────────────────────
    if page_size != _ALL_ROWS:
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

    # ── Direct Download button (no intermediate Export step) ─────────────
    st.markdown("---")
    with col_dl:
        with st.spinner("Preparing download…"):
            csv_bytes = export_csv(filters=filters)
        if csv_bytes:
            st.download_button(
                label="📥 Download",
                data=csv_bytes,
                file_name="PractitionersWorkloadDB_export.csv",
                mime="text/csv",
                key="dl_btn",
                use_container_width=True,
            )
