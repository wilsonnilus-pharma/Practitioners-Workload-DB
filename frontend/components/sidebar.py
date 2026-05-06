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
    # Incrementing this forces every widget to get a new key → fresh value.
    v = st.session_state.get("filter_version", 0)

    # Load saved filters to persist across pages
    saved = st.session_state.get("saved_filters", {})

    filters: dict = {}

    # ── Date range ─────────────────────────────────────────────────────
    st.sidebar.markdown("<div class='custom-label' style='margin-top: 0.5rem; margin-bottom: 0.8rem;'><strong>📅 Visit Date</strong></div>", unsafe_allow_html=True)
    
    min_date, max_date = _get_min_max_dates()
    
    # Keys for syncing
    key_from = f"date_from_{v}"
    key_to   = f"date_to_{v}"
    key_slider = f"date_slider_{v}"

    # Initialize session state for dates if not set
    # We set them to None by default as requested ("باقي الافتراضي بتاعها يبقي فاضي")
    if key_from not in st.session_state:
        saved_from = saved.get("date_from")
        st.session_state[key_from] = datetime.date.fromisoformat(saved_from) if saved_from else None
    if key_to not in st.session_state:
        saved_to = saved.get("date_to")
        st.session_state[key_to] = datetime.date.fromisoformat(saved_to) if saved_to else None
    if key_slider not in st.session_state:
        sf = st.session_state[key_from]
        st_to = st.session_state[key_to]
        if sf and st_to:
             st.session_state[key_slider] = (sf, st_to)
        else:
             st.session_state[key_slider] = (min_date, max_date)

    # Callbacks for sync
    def on_date_input_change():
        # Only update slider if both dates are selected
        f = st.session_state[key_from]
        t = st.session_state[key_to]
        if f and t:
            # Ensure slider range is within min/max bounds
            f_clamped = max(min(f, max_date), min_date)
            t_clamped = max(min(t, max_date), min_date)
            st.session_state[key_slider] = (f_clamped, t_clamped)

    def on_slider_change():
        # When slider moves, populate the "From" and "To" boxes
        st.session_state[key_from] = st.session_state[key_slider][0]
        st.session_state[key_to]   = st.session_state[key_slider][1]

    col1, col2 = st.sidebar.columns(2)
    # Do NOT pass value= here — session_state[key] already holds the value
    # Passing both causes: "widget created with default value but also set via Session State API"
    date_from = col1.date_input("From", key=key_from, on_change=on_date_input_change)
    date_to   = col2.date_input("To",   key=key_to,   on_change=on_date_input_change)

    # Date Range Slider
    st.sidebar.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    st.sidebar.slider(
        "Date Range",
        min_value=min_date,
        max_value=max_date,
        key=key_slider,
        on_change=on_slider_change,
        label_visibility="collapsed"
    )

    if date_from:
        filters["date_from"] = str(date_from)
    if date_to:
        filters["date_to"] = str(date_to)

    # ── Practitioner ID (text, no cascade dependency) ──────────────────
    st.sidebar.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)
    pract_id = st.sidebar.text_input("🆔 Practitioner ID", value=saved.get("practitioner_id", ""), key=f"txt_practitioner_id_{v}")
    if pract_id.strip():
        filters["practitioner_id"] = pract_id.strip()

    # ── Build cascade context (everything selected so far) ─────────────
    def _ctx() -> str:
        """Snapshot of filters collected so far — used as cache key."""
        return json.dumps(filters, sort_keys=True)

    # ── Region ────────────────────────────────────────────────────────
    region_opts = _all_regions()
    # Filter out invalid defaults
    r_def = [x for x in saved.get("region", []) if x in region_opts]
    region = st.sidebar.multiselect("🌍 Region", region_opts, default=r_def, key=f"sel_region_{v}")
    if region:
        filters["region"] = region

    # ── Facility (cascades from Practitioner + Region + Date) ──────────
    facility_opts = _facilities(_ctx())
    f_def = [x for x in saved.get("facility_name", []) if x in facility_opts]
    facility = st.sidebar.multiselect("🏥 Facility", facility_opts, default=f_def, key=f"sel_facility_{v}")
    if facility:
        filters["facility_name"] = facility

    # ── Speciality (cascades from everything above) ────────────────────
    speciality_opts = _specialities(_ctx())
    s_def = [x for x in saved.get("speciality", []) if x in speciality_opts]
    speciality = st.sidebar.multiselect("⚕️ Speciality", speciality_opts, default=s_def, key=f"sel_speciality_{v}")
    if speciality:
        filters["speciality"] = speciality

    # ── Text search ────────────────────────────────────────────────────
    search = st.sidebar.text_input("🔍 Search (name / speciality)", value=saved.get("search", ""), key=f"txt_search_{v}")
    if search.strip():
        filters["search"] = search.strip()

    # ── Practitioner at more than N facilities ─────────────────────────
    fc_opts = ["1", "2", "3", "4", "5+"]
    fc_def = [x for x in saved.get("facility_count", []) if x in fc_opts]
    facility_count = st.sidebar.multiselect(
        "🏢 Practitioner at more than facility",
        options=fc_opts,
        default=fc_def,
        key=f"sel_facility_count_{v}",
    )
    if facility_count:
        filters["facility_count"] = facility_count

    # ── Patient Class ──────────────────────────────────────────────────
    pc_opts = ["Emergency", "Inpatient", "Outpatient"]
    pc_def = [x for x in saved.get("patient_class", []) if x in pc_opts]
    patient_class = st.sidebar.multiselect(
        "🏥 Patient Class",
        options=pc_opts,
        default=pc_def,
        key=f"sel_patient_class_{v}",
    )
    if patient_class:
        filters["patient_class"] = patient_class

    # ── TOP N ──────────────────────────────────────────────────────────
    st.sidebar.markdown("**🏆 TOP N**")
    top_n_enabled = st.sidebar.checkbox("Enable TOP N filter", value=saved.get("top_n_enabled", False), key=f"top_n_enabled_{v}")
    if top_n_enabled:
        filters["top_n_enabled"] = True
        st.sidebar.markdown("<span style='font-size:0.85rem'>Show top N rows</span>", unsafe_allow_html=True)
        # Using a slider and number input synced via session_state is tricky without callbacks,
        # so we display them side by side. The number input dictates the final value.
        c1, c2 = st.sidebar.columns([3, 1])
        with c1:
            # We don't provide a 'value' so it takes it from session_state key if set
            top_n_sl = st.slider(
                "Slider", min_value=1, max_value=5000, step=1,
                value=saved.get("top_n", 15),
                key=f"top_n_sl_{v}", label_visibility="collapsed"
            )
        with c2:
            top_n = st.number_input(
                "Number", min_value=1, max_value=50000, step=1,
                value=top_n_sl, # Defaults to whatever the slider is at
                key=f"top_n_num_{v}", label_visibility="collapsed"
            )
        options = [
            ("total_cases",          "📊 Total Cases"),
            ("total_emergency",      "🚨 Emergency"),
            ("total_inpatient",      "🏥 Inpatient"),
            ("total_outpatient",     "🩺 Outpatient"),
            ("unique_practitioners", "👤 Unique Practitioners"),
        ]
        
        saved_by = saved.get("top_n_by", "total_cases")
        idx = 0
        for i, opt in enumerate(options):
            if opt[0] == saved_by:
                idx = i
                break

        top_n_by = st.sidebar.selectbox(
            "Rank by",
            options=options,
            index=idx,
            format_func=lambda x: x[1],
            key=f"top_n_by_{v}",
        )
        filters["top_n"]    = top_n
        filters["top_n_by"] = top_n_by[0]

    st.sidebar.markdown("---")

    # Save filters for persistence across pages
    st.session_state["saved_filters"] = filters

    # ── Clear All Filters ──────────────────────────────────────────────
    if st.sidebar.button("🗑 Clear All Filters", use_container_width=True):
        st.session_state["filter_version"] = v + 1
        st.session_state.pop("saved_filters", None)
        st.rerun()

    return filters
