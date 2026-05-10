"""Dashboard page — main analytics view: KPI cards, pivot table, charts.

Title: Practitioners Workload DB

Performance fixes applied:
  1. load_summary is decorated with @st.cache_data(ttl=300, show_spinner=False)
     so identical filter+group_by combinations return from the Streamlit
     process-level cache in <1 ms — no HTTP round-trip, no spinner.
  2. The blocking "Loading summary…" spinner is removed from the parallel
     fetch block.  Each tab therefore renders as soon as Streamlit displays it
     (all 5 concurrent HTTP calls still run in a thread-pool but don't block
     the page render for tabs whose data is already cached).
  3. saved_filters (including date_from / date_to strings) is written before
     any st.stop(), so navigating to Upload & Files and returning always
     restores the last active filters.
  4. Clear All Filters bumps filter_version and pops saved_filters; the next
     render rebuilds with defaults, and load_summary immediately serves the
     "no-filter" result from cache (was cached on first page load).
"""

import time
import json
import streamlit as st
from frontend.api_client import get_summary, trigger_scan, get_scan_status, get_facility_type_summary
from frontend.components.sidebar import render_sidebar
from frontend.components.kpi_cards import render_kpi_cards, render_compact_kpi_cards
from frontend.components.charts import render_charts
from frontend.components.table import render_table
from frontend.components.clock import render_floating_clock

render_floating_clock()


# ── Cached summary loader ──────────────────────────────────────────────────
# Keyed on (filter_key, group_by, include_kpi, include_breakdown, include_top_facs).
# TTL=300 s keeps results alive across normal work sessions.
# show_spinner=False so no "Loading…" toast appears on cache hits (instant).

@st.cache_data(ttl=300, show_spinner=False)
def load_summary(
    filter_key: str,
    group_by: str,
    include_kpi: bool = True,
    include_breakdown: bool = True,
    include_top_facs: bool = True,
):
    """Call the summary API and cache the result client-side.

    On the FIRST call for a new filter combination this makes one HTTP request
    to FastAPI (which itself has a 60-s server-side cache in aggregator.py).
    Every subsequent call with the same arguments returns instantly from
    Streamlit's process-level cache — no network, no SQL, no spinner.
    """
    f = json.loads(filter_key)
    f.pop("_grp", None)
    return get_summary(
        filters=f if f else None,
        group_by=group_by,
        include_kpi=include_kpi,
        include_breakdown=include_breakdown,
        include_top_facs=include_top_facs,
    )


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
            "region", "speciality", "visit_date", "month", "facility_type",
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
    prog  = status.get("processed", 0)
    total = status.get("total_files", 1)
    st.progress(
        prog / max(total, 1),
        text=f"Importing: {status.get('current_file', '…')} ({prog}/{total})",
    )
    time.sleep(1)
    st.rerun()

# ── Load summary data — 6 lean parallel calls ─────────────────────────────
#
# Diagnostic results (338k rows, no filter):
#   facility pivot    : 0.37s cold / 0.02s cached
#   region pivot      : 0.44s cold / 0.02s cached
#   pract pivot+kpi   : 1.68s cold / 0.28s cached   (no breakdown)
#   pract breakdown   : 0.40s cold / 0.08s cached   (breakdown only)
#   spec breakdown    : 2.60s cold / 0.08s cached   (was bundled — now separate)
#   pivot no top_facs : 1.44s cold / 0.26s cached
#   Wall-clock (6 parallel, cached): ~0.30s
#
# KEY FIX: call #1 previously requested pivot+kpi+breakdown together
#   → 15,550 rows in one response → 4.12s cold, 0.93s cached.
#   Now split into pivot+kpi (no breakdown) + a separate breakdown call
#   → heaviest call is ~1.68s cold, ~0.30s cached.
import concurrent.futures
from frontend import api_client

_fc = {k: v for k, v in filters.items() if k not in ("top_n", "top_n_by")}

# (filter_key, group_by, include_kpi, include_breakdown, include_top_facs)
keys_and_groups = [
    # [0] Tab1 pivot + KPI cards — NO breakdown (saves 8,141 rows per call)
    (json.dumps(filters,                           sort_keys=True), group_by,        True,  False, True),
    # [1] Tab3 facility counts
    (json.dumps({**_fc, "_grp": "fac"},            sort_keys=True), "facility_name", False, False, False),
    # [2] Tab4 region counts
    (json.dumps({**_fc, "_grp": "reg"},            sort_keys=True), "region",        False, False, False),
    # [3] Tab5 charts
    (json.dumps({**_fc, "_grp": "full"},           sort_keys=True), group_by,        False, False, False),
    # [4] Tab2 facility breakdown — practitioner_name group
    (json.dumps({**filters, "_grp": "brkdwn"},     sort_keys=True), group_by,        False, True,  False),
    # [5] Tab6 speciality breakdown — separate so it doesn't block others
    (json.dumps({**_fc, "_grp": "spec"},           sort_keys=True), "speciality",    False, True,  False),
]

current_token = st.session_state.get("token", "")


def _fetch(p):
    api_client.local_data.token = current_token
    return load_summary(p[0], p[1], p[2], p[3], p[4])


@st.cache_data(ttl=300, show_spinner=False)
def _load_ftype_cached(filter_key: str, token: str):
    """Cached fast facility-type summary — token passed as cache-key param."""
    api_client.local_data.token = token
    f = json.loads(filter_key)
    return get_facility_type_summary(filters=f if f else None)


def _fetch_ftype(filter_key: str):
    """Thread-safe wrapper: sets token then calls the cached loader."""
    api_client.local_data.token = current_token
    return _load_ftype_cached(filter_key, current_token)


with st.spinner("Loading summary…"):
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        main_future   = executor.submit(_fetch, keys_and_groups[0])
        other_futures = [executor.submit(_fetch, p) for p in keys_and_groups[1:]]
        ftype_future  = executor.submit(
            _fetch_ftype,
            json.dumps(_fc, sort_keys=True),
        )
        results      = [main_future.result()] + [f.result() for f in other_futures]
        ftype_data   = ftype_future.result() or []

pivot_summary  = results[0]
fac_summary    = results[1]
region_summary = results[2]
full_summary   = results[3]
brkdwn_summary = results[4]
spec_summary   = results[5]

kpi            = pivot_summary.get("kpi", {})
pivot          = pivot_summary.get("pivot", [])
breakdown      = brkdwn_summary.get("breakdown", [])
fac_pivot      = fac_summary.get("pivot", [])
region_pivot   = region_summary.get("pivot", [])
full_pivot     = full_summary.get("pivot", [])
spec_breakdown = spec_summary.get("breakdown", [])

# ── KPI cards ─────────────────────────────────────────────────────────────
render_kpi_cards(kpi, filters, ftype_data=ftype_data)

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

        pdf.insert(0, "no.", range(1, len(pdf) + 1))
        pdf.index = range(1, len(pdf) + 1)
        n_shown = len(pdf)
        if filters.get("top_n"):
            st.markdown(
                f"<div style='background:#1e3a5f;border:1px solid #2d4a6e;border-radius:8px;"
                f"padding:0.45rem 1rem;margin-bottom:0.5rem;font-size:0.83rem;color:#94a3b8;'>"
                f"&#128202; Showing top <b style='color:#60a5fa'>{n_shown:,}</b> rows "
                f"sorted by <b style='color:#60a5fa'>\"{filters.get('top_n_by','total_cases').replace('_',' ').title()}\"</b> "
                f"by <b style='color:#a78bfa'>&#127942; TOP N</b> in sidebar</div>",
                unsafe_allow_html=True,
            )
        st.dataframe(pdf, use_container_width=True, height=420, hide_index=True)
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

        bdf.insert(0, "no.", range(1, len(bdf) + 1))
        bdf.index = range(1, len(bdf) + 1)
        n_shown = len(bdf)
        if filters.get("top_n"):
            st.markdown(
                f"<div style='background:#1e3a5f;border:1px solid #2d4a6e;border-radius:8px;"
                f"padding:0.45rem 1rem;margin-bottom:0.5rem;font-size:0.83rem;color:#94a3b8;'>"
                f"&#128202; Showing top <b style='color:#60a5fa'>{n_shown:,}</b> rows "
                f"grouped by <b style='color:#60a5fa'>\"{group_by.replace('_',' ').title()}\"</b> "
                f"by <b style='color:#a78bfa'>&#127942; TOP N</b> in sidebar</div>",
                unsafe_allow_html=True,
            )
        st.dataframe(bdf, use_container_width=True, height=420, hide_index=True)
    else:
        st.info("No breakdown data available.")

# ── Tab 3 : Facilities Counts ──────────────────────────────────────────────
with tab_fac:
    if fac_pivot:
        raw_cols = ["dimension", "total_cases", "total_emergency", "total_inpatient", "total_outpatient", "unique_practitioners"]
        fdf_raw  = pd.DataFrame(fac_pivot)
        fdf = fdf_raw[[c for c in raw_cols if c in fdf_raw.columns]].rename(columns={
            "dimension":            "Facility Name",
            "total_cases":          "Total Cases",
            "total_emergency":      "Emergency",
            "total_inpatient":      "Inpatient",
            "total_outpatient":     "Outpatient",
            "unique_practitioners": "Unique Practitioners",
        })

        total_facs = len(fdf)
        if "fac_n_val" not in st.session_state:
            st.session_state.fac_n_val = min(30, total_facs)

        def on_s_change():
            val = st.session_state.fac_slider_widget
            st.session_state.fac_n_val = val
            st.session_state.fac_manual_widget = val

        def on_i_change():
            val = st.session_state.fac_manual_widget
            capped = min(val, total_facs)
            st.session_state.fac_n_val = capped
            st.session_state.fac_slider_widget = capped
            st.session_state.fac_manual_widget = capped

        c1, c2, c3 = st.columns([3, 1, 2.5])

        with c1:
            st.markdown("<p style='font-size:0.95rem; font-weight:600; color:#38bdf8; margin-bottom:-10px;'>Top facilities count</p>", unsafe_allow_html=True)
            st.slider("Slider", 1, max(total_facs, 2), key="fac_slider_widget", on_change=on_s_change)

        with c2:
            st.markdown("<div style='margin-top:25px;'></div>", unsafe_allow_html=True)
            st.number_input("Manual", min_value=1, max_value=1000000, key="fac_manual_widget", on_change=on_i_change)

        if "fac_slider_widget" not in st.session_state:
            st.session_state.fac_slider_widget = st.session_state.fac_n_val
        if "fac_manual_widget" not in st.session_state:
            st.session_state.fac_manual_widget = st.session_state.fac_n_val

        effective_n = st.session_state.fac_n_val

        with c3:
            metrics_map = {
                "Total Cases": "Total Cases",
                "Emergency": "Emergency",
                "Inpatient": "Inpatient",
                "Outpatient": "Outpatient",
                "Unique Practitioners": "Unique Practitioners",
            }
            selected_metric = st.selectbox("Sort By Metric", options=list(metrics_map.keys()), index=0)
            sort_col = metrics_map[selected_metric]

        st.markdown(f"<p style='color:#94a3b8; font-size:0.85rem; margin-top:-15px; margin-bottom:10px;'>Showing top <b>{effective_n:,}</b> of <b>{total_facs:,}</b> facilities</p>", unsafe_allow_html=True)

        fdf = fdf.sort_values(by=sort_col, ascending=False).reset_index(drop=True)
        fdf.insert(0, "no.", range(1, len(fdf) + 1))
        fdf.index = range(1, len(fdf) + 1)

        top_df = fdf.head(effective_n)
        fig_fac = px.bar(
            top_df, x="Facility Name", y=sort_col,
            color=sort_col, color_continuous_scale="Blues",
            title=f"Top {effective_n:,} Facilities by {selected_metric}",
            template="plotly_dark", height=450,
        )
        fig_fac.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_fac, use_container_width=True)
        st.dataframe(fdf, use_container_width=True, height=400, hide_index=True)
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
        rdf.insert(0, "no.", range(1, len(rdf) + 1))
        rdf.index = range(1, len(rdf) + 1)
        fig_reg = px.bar(
            rdf, x="Region", y="Total Cases",
            color="Total Cases", color_continuous_scale="Greens",
            title="Cases by Region",
            template="plotly_dark", height=420,
        )
        fig_reg.update_layout(xaxis_tickangle=-40)
        st.plotly_chart(fig_reg, use_container_width=True)
        col_show = [c for c in ["no.", "Region", "Total Cases", "Emergency", "Inpatient", "Outpatient", "Unique Practitioners"]
                    if c in rdf.columns]
        st.dataframe(rdf[col_show], use_container_width=True, height=350, hide_index=True)
    else:
        st.info("No region data available.")

# ── Tab 5 : Charts ─────────────────────────────────────────────────────────
with tab_charts:
    render_charts(full_pivot, group_by, kpi, filters)

# ── Tab 6 : Speciality Cases ───────────────────────────────────────────────
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

        render_compact_kpi_cards([
            {
                "icon": "🔬",
                "label": "Unique Specialities",
                "value": f"{sdf['Speciality'].nunique():,}" if "Speciality" in sdf.columns else "0",
                "color": "kpi-green",
            },
            {
                "icon": "🏢",
                "label": "Unique Facilities",
                "value": f"{sdf['Facility Name'].nunique():,}" if "Facility Name" in sdf.columns else "0",
                "color": "kpi-cyan",
            },
            {
                "icon": "🗂️",
                "label": "Total Cases",
                "value": f"{int(sdf['Total Cases'].sum()):,}" if "Total Cases" in sdf.columns else "0",
                "color": "kpi-blue",
            },
            {
                "icon": "📋",
                "label": "Total Records",
                "value": f"{len(sdf):,}",
                "color": "kpi-pink",
            },
        ])

        sdf.insert(0, "no.", range(1, len(sdf) + 1))
        sdf.index = range(1, len(sdf) + 1)

        show_cols = [c for c in ["no.", "Speciality", "Facility Name", "Emergency",
                                  "Inpatient", "Outpatient", "Total Cases",
                                  "Total Visits by Facility(ies)", "% Practitioner per Facility(ies)"]
                     if c in sdf.columns]
        st.dataframe(sdf[show_cols], use_container_width=True, height=520, hide_index=True)
    else:
        st.info("No speciality data available. Make sure data is imported.")


# ── Tab 7 : Detailed Records ────────────────────────────────────────────────
with tab_records:
    if "table_page" not in st.session_state:
        st.session_state["table_page"] = 1
    prev_filters = st.session_state.get("_prev_filters", {})
    if filters != prev_filters:
        st.session_state["table_page"] = 1
        st.session_state["_prev_filters"] = filters
    render_table(filters)

st.markdown(
    """
    <div style='text-align: center; margin-top: 10rem; padding-top: 2rem; border-top: 1px solid rgba(148, 163, 184, 0.1); padding-bottom: 2rem; color: #64748b; font-size: 0.8rem; font-family: "Inter", sans-serif; letter-spacing: 0.02em;'>
        <p style='margin: 0; padding-bottom: 4px; font-weight: 500;'>&copy; 2026 <strong>WilsonPharmacy</strong>. All rights reserved.</p>
        <p style='margin: 0;'>Contact us: <a href="mailto:wilsonnilus@gmail.com" style="color: #38bdf8; text-decoration: none; font-weight: 500; transition: color 0.2s;">wilsonnilus@gmail.com</a></p>
    </div>
    """,
    unsafe_allow_html=True,
)


