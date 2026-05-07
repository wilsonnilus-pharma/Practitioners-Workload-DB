"""Dashboard page — main analytics view: KPI cards, pivot table, charts.

Title: Practitioners Workload DB
"""

import time
import streamlit as st
from frontend.api_client import get_summary, trigger_scan, get_scan_status
from frontend.components.sidebar import render_sidebar
from frontend.components.kpi_cards import render_kpi_cards
from frontend.components.charts import render_charts
from frontend.components.table import render_table
import json

@st.cache_data(ttl=120, show_spinner=False)
def load_summary(filter_key: str, group_by: str, include_kpi: bool = True, include_breakdown: bool = True, include_top_facs: bool = True):
    f = json.loads(filter_key)
    # strip sentinel keys before calling API
    f.pop("_grp", None)
    return get_summary(filters=f if f else None, group_by=group_by, include_kpi=include_kpi, include_breakdown=include_breakdown, include_top_facs=include_top_facs)

st.set_page_config(
    page_title="Practitioners Workload DB",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate ──────────────────────────────────────────────────────────────
if "token" not in st.session_state:
    st.warning("⚠️ Please log in first.")
    st.stop()

# ── Global CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: linear-gradient(160deg, #0f172a 0%, #1e293b 100%); color: #f1f5f9; }
.stTabs [data-baseweb="tab"] { font-weight: 600; color: #94a3b8; }
.stTabs [aria-selected="true"] { color: #60a5fa !important; }
div[data-testid="stMetricValue"] { font-size: 2.4rem; font-weight: 800; }
.block-container { padding-top: 3rem; }
.page-header {
    background: linear-gradient(90deg, #1e3a5f 0%, #1e293b 100%);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 1rem 1.5rem;
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.page-header-title {
    font-size: 2.0rem; font-weight: 800;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0; line-height: 1.2;
    white-space: nowrap;
}
.page-header-sub { font-size: 0.8rem; color: #64748b; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ── Header row ─────────────────────────────────────────────────────────────
h1, h2 = st.columns([5, 1])
with h1:
    st.markdown("""
    <div class="page-header">
        <span style="font-size:2rem">📊</span>
        <div>
            <div class="page-header-title">Practitioners Workload DB</div>
            <div class="page-header-sub">Practitioners analytics — Emergency · Inpatient · Outpatient</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption(f"Logged in as **{st.session_state.get('username')}** | Role: {st.session_state.get('role')}")
with h2:
    if st.session_state.get("role") == "admin":
        if st.button("🔄 Scan & Import", use_container_width=True, type="primary", key="scan_btn"):
            with st.spinner("Triggering folder scan…"):
                result = trigger_scan()
            st.success(result.get("message", "Scan started"))

# ── Sidebar filters ────────────────────────────────────────────────────────
filters = render_sidebar()

# ── Group-by selector ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**📐 Pivot Group By**")
    group_by = st.selectbox(
        "Group by dimension",
        [
            "practitioner_name", "practitioner_id", "facility_name",
            "region", "speciality", "visit_date", "month",
        ],
        key="group_by",
        label_visibility="collapsed",
    )

    # ── Logout ────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        for key in ["token", "username", "role"]:
            st.session_state.pop(key, None)
        import os
        if os.path.exists(".session.json"):
            os.remove(".session.json")
        st.rerun()

# ── Scan progress (if running) ─────────────────────────────────────────────
status = get_scan_status()
if status.get("running"):
    prog = status.get("processed", 0)
    total = status.get("total_files", 1)
    st.progress(prog / max(total, 1), text=f"Importing: {status.get('current_file', '…')} ({prog}/{total})")
    time.sleep(1)
    st.rerun()

# ── Load summary data ────────────────────────────────────────────────────────
with st.spinner("Loading summary…"):
    import concurrent.futures
    from frontend import api_client

    # Prepare keys: (filter_json, group_by, include_kpi, include_breakdown, include_top_facs)
    _fc = {k: v for k, v in filters.items() if k not in ("top_n", "top_n_by")}
    keys_and_groups = [
        (json.dumps(filters, sort_keys=True), group_by, True, True, True),                               # summary
        (json.dumps({**_fc, "_grp": "fac"}, sort_keys=True),  "facility_name", False, False, False),      # fac_summary
        (json.dumps({**_fc, "_grp": "reg"}, sort_keys=True),  "region", False, False, False),             # region_summary
        (json.dumps({**_fc, "_grp": "full"}, sort_keys=True), group_by, False, False, False),             # full_summary
        (json.dumps({**_fc, "_grp": "spec"}, sort_keys=True), "speciality", False, True, False)           # spec_summary
    ]

    # Capture token from main thread
    current_token = st.session_state.get("token", "")

    def _fetch(p):
        # Safely pass the token to the background thread
        api_client.local_data.token = current_token
        return load_summary(p[0], p[1], p[2], p[3], p[4])

    # Fetch all 5 queries in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_fetch, keys_and_groups))
        
    summary        = results[0]
    fac_summary    = results[1]
    region_summary = results[2]
    full_summary   = results[3]
    spec_summary   = results[4]

kpi           = summary.get("kpi", {})
pivot         = summary.get("pivot", [])
breakdown     = summary.get("breakdown", [])
fac_pivot     = fac_summary.get("pivot", [])
region_pivot  = region_summary.get("pivot", [])
full_pivot    = full_summary.get("pivot", [])    # unlimited → used by charts slider
spec_breakdown = spec_summary.get("breakdown", [])  # speciality × facility


# ── KPI cards ─────────────────────────────────────────────────────────────
render_kpi_cards(kpi, filters)

st.markdown("<div style='margin-bottom: 0.8rem;'></div>", unsafe_allow_html=True)

# ── Main tabs ──────────────────────────────────────────────────────────────
import pandas as pd
import plotly.express as px

tab_pivot, tab_breakdown, tab_fac, tab_reg, tab_charts, tab_spec, tab_records = st.tabs([
    "🔢 Pivot Summary",
    "🏥 Facility Breakdown",
    "🏢 Facilities Counts",
    "🌍 Regions Counts",
    "📈 Charts",
    "🔬 Speciality Cases",
    "📋 Detailed Records",
])

# ── Tab 1 : Pivot Summary ──────────────────────────────────────────────────
with tab_pivot:
    if pivot:
        pdf = pd.DataFrame(pivot)
        col_rename = {
            "dimension":             group_by.replace("_", " ").title(),
            "total_records":         "Records",
            "total_emergency":       "Emergency",
            "total_inpatient":       "Inpatient",
            "total_outpatient":      "Outpatient",
            "total_cases":           "Total Cases",
            "unique_practitioners":  "Unique Practitioners",
            "total_practitioners":   "Total Practitioners",
            "total_visits_all_facilities": "Total Visits by Facility(ies)",
            "pct_of_all_facilities": "% Practitioner per Facility(ies)",
            "facility_1_name":       "Facility 1",
            "doctor_cases_fac1":     "Dr Cases (Fac 1)",
            "total_cases_fac1":      "Total (Fac 1)",
            "pct_of_fac1":           "% Fac 1",
            "facility_2_name":       "Facility 2",
            "doctor_cases_fac2":     "Dr Cases (Fac 2)",
            "total_cases_fac2":      "Total (Fac 2)",
            "pct_of_fac2":           "% Fac 2",
            "facility_3_name":       "Facility 3",
            "doctor_cases_fac3":     "Dr Cases (Fac 3)",
            "total_cases_fac3":      "Total (Fac 3)",
            "pct_of_fac3":           "% Fac 3",
            "facility_4_name":       "Facility 4",
            "doctor_cases_fac4":     "Dr Cases (Fac 4)",
            "total_cases_fac4":      "Total (Fac 4)",
            "pct_of_fac4":           "% Fac 4",
        }
        pdf.rename(columns=col_rename, inplace=True)
        for pct_col in ["% Practitioner per Facility(ies)", "% Fac 1", "% Fac 2", "% Fac 3", "% Fac 4"]:
            if pct_col in pdf.columns:
                pdf[pct_col] = pdf[pct_col].apply(lambda x: f"{x:.2f}%")
        pdf.index = range(1, len(pdf) + 1)
        st.dataframe(pdf, use_container_width=True, height=420)
    else:
        st.info("No data in pivot table. Import data first or adjust filters.")

# ── Tab 2 : Facility Breakdown ─────────────────────────────────────────────
with tab_breakdown:
    if breakdown:
        bdf = pd.DataFrame(breakdown)
        dim_label = group_by.replace("_", " ").title()
        fac_label = "Facility Name" if dim_label != "Facility Name" else "Facility (Filter)"
        bdf.rename(columns={
            "dimension":            dim_label,
            "facility_name":        fac_label,
            "emergency":            "Emergency",
            "inpatient":            "Inpatient",
            "outpatient":           "Outpatient",
            "doctor_cases":         "Doctor Cases",
            "total_facility_cases": "Total Visits by Facility(ies)",
            "pct_of_facility":      "% Practitioner per Facility(ies)",
        }, inplace=True)
        if "% Practitioner per Facility(ies)" in bdf.columns:
            bdf["% Practitioner per Facility(ies)"] = bdf["% Practitioner per Facility(ies)"].apply(lambda x: f"{x:.2f}%")
        bdf.index = range(1, len(bdf) + 1)
        st.dataframe(bdf, use_container_width=True, height=420)
    else:
        st.info("No breakdown data available.")

# ── Tab 3 : Facilities Counts ──────────────────────────────────────────────
with tab_fac:
    if fac_pivot:
        raw_cols = ["dimension","total_cases","total_emergency","total_inpatient","total_outpatient","unique_practitioners"]
        fdf_raw  = pd.DataFrame(fac_pivot)
        fdf = fdf_raw[[c for c in raw_cols if c in fdf_raw.columns]].rename(columns={
            "dimension":            "Facility Name",
            "total_cases":          "Total Cases",
            "total_emergency":      "Emergency",
            "total_inpatient":      "Inpatient",
            "total_outpatient":     "Outpatient",
            "unique_practitioners": "Unique Practitioners",
        })
        fdf.index = range(1, len(fdf) + 1)
        n = filters.get("top_n", 30)
        fig_fac = px.bar(
            fdf.head(n), x="Facility Name", y="Total Cases",
            color="Total Cases", color_continuous_scale="Blues",
            title=f"Top {n} Facilities by Cases",
            template="plotly_dark", height=420,
        )
        fig_fac.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_fac, use_container_width=True)
        st.dataframe(fdf, use_container_width=True, height=350)
    else:
        st.info("No facility data available.")

# ── Tab 4 : Regions Counts ─────────────────────────────────────────────────
with tab_reg:
    if region_pivot:
        rdf = pd.DataFrame(region_pivot).rename(columns={
            "dimension":            "Region",
            "total_cases":          "Total Cases",
            "total_emergency":      "Emergency",
            "total_inpatient":      "Inpatient",
            "total_outpatient":     "Outpatient",
            "unique_practitioners": "Unique Practitioners",
        })
        rdf.index = range(1, len(rdf) + 1)
        fig_reg = px.bar(
            rdf, x="Region", y="Total Cases",
            color="Total Cases", color_continuous_scale="Greens",
            title="Cases by Region",
            template="plotly_dark", height=420,
        )
        fig_reg.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_reg, use_container_width=True)
        col_show = [c for c in ["Region","Total Cases","Emergency","Inpatient","Outpatient","Unique Practitioners"]
                    if c in rdf.columns]
        st.dataframe(rdf[col_show], use_container_width=True, height=350)
    else:
        st.info("No region data available.")

# ── Tab 5 : Charts ──────────────────────────────────────────────────
with tab_charts:
    render_charts(full_pivot, group_by, kpi, filters)

# ── Tab 6 : Speciality Cases ───────────────────────────────────────────
with tab_spec:
    if spec_breakdown:
        sdf = pd.DataFrame(spec_breakdown)
        sdf.rename(columns={
            "dimension":            "Speciality",
            "facility_name":        "Facility Name",
            "emergency":            "Emergency",
            "inpatient":            "Inpatient",
            "outpatient":           "Outpatient",
            "doctor_cases":         "Total Cases",
            "total_facility_cases": "Total Visits by Facility(ies)",
            "pct_of_facility":      "% Practitioner per Facility(ies)",
        }, inplace=True)
        if "% Practitioner per Facility(ies)" in sdf.columns:
            sdf["% Practitioner per Facility(ies)"] = sdf["% Practitioner per Facility(ies)"].apply(lambda x: f"{x:.2f}%")

        # ── Quick search ──────────────────────────────────────────────
        s_search = st.text_input("🔍 Filter by speciality…", key="spec_search",
                                  placeholder="Type to filter")
        if s_search:
            sdf = sdf[sdf["Speciality"].str.contains(s_search, case=False, na=False)]

        # ── Summary KPIs ──────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("🔬 Unique Specialities", sdf["Speciality"].nunique())
        k2.metric("🏢 Unique Facilities",
                  sdf["Facility Name"].nunique() if "Facility Name" in sdf.columns else "—")
        k3.metric("📋 Total Cases",
                  f"{int(sdf['Total Cases'].sum()):,}" if "Total Cases" in sdf.columns else "—")
        k4.metric("📋 Total Records", f"{len(sdf):,}")

        # ── Table ─────────────────────────────────────────────────────
        show_cols = [c for c in ["Speciality", "Facility Name", "Emergency",
                                  "Inpatient", "Outpatient", "Total Cases",
                                  "Total Visits by Facility(ies)", "% Practitioner per Facility(ies)"]
                     if c in sdf.columns]
        sdf.index = range(1, len(sdf) + 1)
        st.dataframe(sdf[show_cols], use_container_width=True, height=520)
    else:
        st.info("No speciality data available. Make sure data is imported.")

# ── Tab 7 : Detailed Records ──────────────────────────────────────────────
with tab_records:
    if "table_page" not in st.session_state:
        st.session_state["table_page"] = 1
    prev_filters = st.session_state.get("_prev_filters", {})
    if filters != prev_filters:
        st.session_state["table_page"] = 1
        st.session_state["_prev_filters"] = filters
    render_table(filters)
