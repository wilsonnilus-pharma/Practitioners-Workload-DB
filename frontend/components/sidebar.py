"""Sidebar filter component — renders all filter widgets and returns active filters dict.

Cascading logic (bidirectional):
  Every dropdown is scoped by ALL other currently active filters.
  Clear All Filters uses a version counter so widgets are fully re-initialised.
"""

from __future__ import annotations
import json
import datetime
import streamlit as st
from frontend.api_client import get_filter_options, get_filter_options_cascaded, get_date_range


@st.cache_data(ttl=120, show_spinner=False)
def _all_regions():
    return get_filter_options("region")

@st.cache_data(ttl=60, show_spinner=False)
def _facilities(ctx_key: str):
    ctx = json.loads(ctx_key)
    return get_filter_options_cascaded("facility_name", ctx)

@st.cache_data(ttl=60, show_spinner=False)
def _specialities(ctx_key: str):
    ctx = json.loads(ctx_key)
    return get_filter_options_cascaded("speciality", ctx)

@st.cache_data(ttl=300, show_spinner=False)
def _get_min_max_dates():
    res = get_date_range()
    mn_str, mx_str = res.get("min"), res.get("max")
    if not mn_str or not mx_str:
        return datetime.date.today() - datetime.timedelta(days=365), datetime.date.today()
    try:
        return datetime.date.fromisoformat(mn_str[:10]), datetime.date.fromisoformat(mx_str[:10])
    except:
        return datetime.date.today() - datetime.timedelta(days=365), datetime.date.today()


def render_sidebar() -> dict:
    """Render all sidebar filters and return a dict of active filter values."""
    st.sidebar.markdown(
        """
        <style>
        .sidebar-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #60a5fa;
            letter-spacing: 0.04em;
            margin-top: 0rem;
            margin-bottom: 0.2rem;
        }
        /* Use the empty space at the top of the sidebar */
        [data-testid="stSidebarUserContent"] {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        /* Reduce gap slightly without causing overlaps */
        [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
            gap: 0.2rem !important;
        }
        /* Push the date slider down away from the date inputs */
        div[data-testid="stSlider"] {
            margin-top: 0.5rem !important;
        }
        /* Aggressively hide slider labels, ticks, min/max, and floating values */
        div[data-testid="stSlider"] [data-testid="stTickBar"],
        div[data-testid="stSlider"] [data-testid="stTickBarMin"],
        div[data-testid="stSlider"] [data-testid="stTickBarMax"],
        div[data-testid="stSlider"] [data-testid="stThumbValue"],
        div[data-testid="stSlider"] [data-baseweb="typography"] {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            font-size: 0 !important;
        }
        /* Fallback for generic text spans inside the slider */
        div[data-testid="stSlider"] span {
            color: transparent !important;
        }
        /* Unified filter labels (Markdown strong and widget labels) */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] p strong,
        .custom-label {
            font-size: 0.85rem !important;
            color: #f8fafc !important;
            font-weight: 600 !important;
        }
        /* Center date input labels */
        [data-testid="stSidebar"] .stDateInput label {
            text-align: center !important;
            display: block !important;
            width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div class='sidebar-title' style='margin-top: -0.5rem;'>🔎 Filters</div>", unsafe_allow_html=True)

    # ── Version counter for reliable "Clear All" ───────────────────────
    v = st.session_state.get("filter_version", 0)

    # Load saved filters to persist across pages
    saved = st.session_state.get("saved_filters", {})
    filters: dict = {}

    # ── Date range ─────────────────────────────────────────────────────
    st.sidebar.markdown("<div class='custom-label' style='margin-top: 0.5rem; margin-bottom: 0.8rem;'><strong>📅 Visit Date</strong></div>", unsafe_allow_html=True)
    
    min_date, max_date = _get_min_max_dates()
    
    # Versioned Keys
    key_from   = f"sb_date_from_{v}"
    key_to     = f"sb_date_to_{v}"
    key_slider = f"sb_date_slider_{v}"

    # Initialize from saved if first render
    if key_from not in st.session_state:
        saved_val = saved.get("date_from")
        st.session_state[key_from] = datetime.date.fromisoformat(saved_val) if saved_val else min_date
    if key_to not in st.session_state:
        saved_val = saved.get("date_to")
        st.session_state[key_to] = datetime.date.fromisoformat(saved_val) if saved_val else max_date
    if key_slider not in st.session_state:
        st.session_state[key_slider] = (st.session_state[key_from], st.session_state[key_to])

    def on_date_input_change():
        f = st.session_state.get(key_from)
        t = st.session_state.get(key_to)
        if not f or not t: return
        f_clamped = max(min(f, max_date), min_date)
        t_clamped = max(min(t, max_date), min_date)
        st.session_state[key_slider] = (f_clamped, t_clamped)

    def on_slider_change():
        val = st.session_state.get(key_slider)
        if not val or len(val) < 2: return
        st.session_state[key_from] = val[0]
        st.session_state[key_to]   = val[1]

    col1, col2 = st.sidebar.columns(2)
    date_from = col1.date_input("From", key=key_from, on_change=on_date_input_change)
    date_to   = col2.date_input("To",   key=key_to,   on_change=on_date_input_change)

    st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    st.sidebar.slider(
        "Date Range", min_value=min_date, max_value=max_date,
        key=key_slider, on_change=on_slider_change, label_visibility="collapsed"
    )

    if date_from: filters["date_from"] = str(date_from)
    if date_to:   filters["date_to"]   = str(date_to)

    # ── Other Filters ──────────────────────────────────────────────────
    st.sidebar.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    
    # Practitioner ID
    pract_id = st.sidebar.text_input("🆔 Practitioner ID", value=saved.get("practitioner_id", ""), key=f"sb_pract_id_{v}")
    if pract_id.strip(): filters["practitioner_id"] = pract_id.strip()

    # Cascade context helper
    def _ctx() -> str: return json.dumps(filters, sort_keys=True)

    # Region
    region_opts = _all_regions()
    r_def = [x for x in saved.get("region", []) if x in region_opts]
    region = st.sidebar.multiselect("🌍 Region", region_opts, default=r_def, key=f"sb_region_{v}")
    if region: filters["region"] = region

    # Facility
    facility_opts = _facilities(_ctx())
    f_def = [x for x in saved.get("facility_name", []) if x in facility_opts]
    facility = st.sidebar.multiselect("🏥 Facility", facility_opts, default=f_def, key=f"sb_facility_{v}")
    if facility: filters["facility_name"] = facility

    # Speciality
    speciality_opts = _specialities(_ctx())
    s_def = [x for x in saved.get("speciality", []) if x in speciality_opts]
    speciality = st.sidebar.multiselect("⚕️ Speciality", speciality_opts, default=s_def, key=f"sb_speciality_{v}")
    if speciality: filters["speciality"] = speciality

    # Search
    search = st.sidebar.text_input("🔍 Search (name / speciality)", value=saved.get("search", ""), key=f"sb_search_{v}")
    if search.strip(): filters["search"] = search.strip()

    # Facility Count
    fc_opts = ["1", "2", "3", "4", "5+"]
    fc_def = [x for x in saved.get("facility_count", []) if x in fc_opts]
    facility_count = st.sidebar.multiselect("🏢 Practitioner at more than facility", options=fc_opts, default=fc_def, key=f"sb_fac_count_{v}")
    if facility_count: filters["facility_count"] = facility_count

    # Patient Class
    pc_opts = ["Emergency", "Inpatient", "Outpatient"]
    pc_def = [x for x in saved.get("patient_class", []) if x in pc_opts]
    patient_class = st.sidebar.multiselect("🏥 Patient Class", options=pc_opts, default=pc_def, key=f"sb_pat_class_{v}")
    if patient_class: filters["patient_class"] = patient_class

    # TOP N
    st.sidebar.markdown("**🏆 TOP N**")
    tn_enabled = st.sidebar.checkbox("Enable TOP N filter", value=saved.get("top_n_enabled", False), key=f"sb_tn_enabled_{v}")
    if tn_enabled:
        filters["top_n_enabled"] = True
        st.sidebar.markdown("<span style='font-size:0.85rem'>Show top N rows</span>", unsafe_allow_html=True)
        
        k_sl, k_num = f"sb_tn_sl_{v}", f"sb_tn_num_{v}"
        if k_sl not in st.session_state: st.session_state[k_sl] = saved.get("top_n", 15)
        if k_num not in st.session_state: st.session_state[k_num] = saved.get("top_n", 15)

        def on_tn_sl(): st.session_state[k_num] = st.session_state[k_sl]
        def on_tn_num(): st.session_state[k_sl] = st.session_state[k_num]

        tc1, tc2 = st.sidebar.columns([3, 1])
        with tc1: st.slider("Slider", 1, 5000, key=k_sl, on_change=on_tn_sl, label_visibility="collapsed")
        with tc2: st.number_input("Num", 1, 50000, key=k_num, on_change=on_tn_num, label_visibility="collapsed")
        
        top_n = st.session_state[k_num]
        filters["top_n"] = top_n
        
        options = [("total_cases", "📊 Total Cases"), ("total_emergency", "🚨 Emergency"), ("total_inpatient", "🏥 Inpatient"), ("total_outpatient", "🩺 Outpatient"), ("unique_practitioners", "👤 Unique Practitioners")]
        saved_by = saved.get("top_n_by", "total_cases")
        idx = next((i for i, o in enumerate(options) if o[0] == saved_by), 0)
        top_n_by = st.sidebar.selectbox("Rank by", options=options, index=idx, format_func=lambda x: x[1], key=f"sb_tn_by_{v}")
        filters["top_n_by"] = top_n_by[0]

    st.sidebar.markdown("---")
    st.session_state["saved_filters"] = filters

    # ── Clear All Filters ──────────────────────────────────────────────
    if st.sidebar.button("🗑 Clear All Filters", use_container_width=True):
        st.session_state["filter_version"] = v + 1
        st.session_state.pop("saved_filters", None)
        # Clear current version keys to free memory
        for key in list(st.session_state.keys()):
            if key.startswith("sb_"):
                st.session_state.pop(key, None)
        st.rerun()

    return filters

    return filters
