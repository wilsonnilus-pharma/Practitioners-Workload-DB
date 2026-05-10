"""KPI cards component.

Rows:
  Row 1: Total Cases | Emergency | Inpatient | Outpatient | Facilities | Regions
  Row 2: Visits by Facility | % Practitioner | Specialities | Practitioners | Days
  Row 3: PCU | PCC | Hospital | Complex | ICNU  (respond to filters)
"""
from __future__ import annotations
import streamlit as st

_CSS = """
<style>
.kpi-grid       { display:grid; grid-template-columns:repeat(4,1fr); gap:.85rem; margin-bottom:.4rem; }
.kpi-grid-5     { display:grid; grid-template-columns:repeat(5,1fr); gap:.85rem; margin-bottom:.4rem; }
.kpi-grid-2     { display:grid; grid-template-columns:repeat(2,1fr); gap:.85rem; margin-bottom:.4rem; }
.kpi-grid-row1  { display:grid; grid-template-columns:repeat(6,1fr); gap:.85rem; margin-bottom:.4rem; }
.kpi-grid-ftype { display:grid; grid-template-columns:repeat(5,1fr); gap:.85rem; margin-bottom:.4rem; }
@media (max-width:1400px) { .kpi-grid-row1  { grid-template-columns:repeat(3,1fr); } }
@media (max-width:1300px) { .kpi-grid-5, .kpi-grid-ftype { grid-template-columns:repeat(3,1fr); } }
@media (max-width:1100px) { .kpi-grid, .kpi-grid-5, .kpi-grid-ftype { grid-template-columns:repeat(2,1fr); } }
@media (max-width:800px)  { .kpi-grid-row1  { grid-template-columns:repeat(2,1fr); } }
@media (max-width:600px)  { .kpi-grid,.kpi-grid-5,.kpi-grid-row1,.kpi-grid-ftype { grid-template-columns:1fr; } }
.kpi-card {
    background:linear-gradient(145deg,#1e293b 0%,#0f172a 100%);
    border:1px solid #1e3a5f; border-radius:14px; padding:1.1rem 1.3rem .9rem;
    position:relative; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,.35);
    transition:transform .15s ease,box-shadow .15s ease;
}
.kpi-card:hover { transform:translateY(-2px); box-shadow:0 8px 32px rgba(0,0,0,.45); }
.kpi-card::before {
    content:""; position:absolute; top:0; left:0; right:0; height:3px;
    background:var(--kpi-accent,#60a5fa); border-radius:14px 14px 0 0;
}
.kpi-icon  { font-size:1.3rem; line-height:1; margin-bottom:.35rem; text-align:center; }
.kpi-label { font-size:.9rem; color:#ffffff; font-weight:800; letter-spacing:.02em; margin-bottom:.25rem; text-align:center; }
.kpi-value { font-size:2.4rem; font-weight:800; color:var(--kpi-accent,#f1f5f9); line-height:1.1; margin-bottom:.2rem; text-align:left; }
.kpi-sub   { font-size:.65rem; color:#475569; text-align:left; }
.kpi-blue   { --kpi-accent:#60a5fa; }
.kpi-red    { --kpi-accent:#f87171; }
.kpi-green  { --kpi-accent:#34d399; }
.kpi-orange { --kpi-accent:#fb923c; }
.kpi-violet { --kpi-accent:#a78bfa; }
.kpi-cyan   { --kpi-accent:#22d3ee; }
.kpi-pink   { --kpi-accent:#f472b6; }
.kpi-yellow { --kpi-accent:#fbbf24; }
.kpi-amber  { --kpi-accent:#f59e0b; }
.kpi-purple { --kpi-accent:#a855f7; }
.kpi-section-label {
    font-size:.65rem; font-weight:700; color:#475569;
    text-transform:uppercase; letter-spacing:.1em; margin:.6rem 0 .4rem;
}
</style>
"""

def _card(icon: str, label: str, value: str, sub: str, color: str) -> str:
    return (
        f'<div class="kpi-card {color}">'
        f'<div class="kpi-icon">{icon}</div>'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )

def _fmt(n) -> str:
    try:
        return "0" if n is None else f"{int(n):,}"
    except Exception:
        return str(n)

def _fmt_pct(n) -> str:
    try:
        return f"{float(n):.2f}%"
    except Exception:
        return "--"

def render_compact_kpi_cards(card_list: list[dict]):
    st.markdown(_CSS, unsafe_allow_html=True)
    html = '<div class="kpi-grid">'
    for c in card_list:
        html += _card(c["icon"], c["label"], c["value"], c.get("sub", ""), c.get("color", "kpi-blue"))
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# Facility type display config
_FTYPE_ORDER = ["PCU", "PCC", "Hospital", "Complex", "ICNU"]
_FTYPE_ARA   = {"PCU": "وحدة",
                "PCC": "مركز",
                "Hospital": "مستشفى",
                "Complex": "مجمع",
                "ICNU": "مركز الكلى والمسالك"}
_FTYPE_ICON  = {"PCU": "\U0001f3ea", "PCC": "\U0001f3e5", "Hospital": "\U0001f3e8",
                "Complex": "\U0001f3d7\ufe0f", "ICNU": "\U0001f48a"}
_FTYPE_COLOR = {"PCU": "kpi-blue", "PCC": "kpi-green", "Hospital": "kpi-amber",
                "Complex": "kpi-purple", "ICNU": "kpi-red"}

def render_kpi_cards(kpi: dict, filters: dict = None, ftype_data: list = None):
    """Render three rows of KPI metric cards."""
    filters    = filters    or {}
    ftype_data = ftype_data or []

    total_cases         = kpi.get("total_cases", 0) or 0
    emergency           = kpi.get("total_emergency", 0) or 0
    inpatient           = kpi.get("total_inpatient", 0) or 0
    outpatient          = kpi.get("total_outpatient", 0) or 0
    visits_by_facility  = kpi.get("total_visits_by_facility", 0) or 0
    unique_specialities = kpi.get("unique_specialities", 0) or 0
    unique_pract        = kpi.get("unique_practitioners", 0) or 0
    total_pract         = kpi.get("total_practitioners", 0) or 0
    pct_facility        = kpi.get("pct_of_facility", 0.0) or 0.0
    total_facilities    = kpi.get("total_facilities", 0) or 0
    total_regions       = kpi.get("total_regions", 0) or 0

    st.markdown(_CSS, unsafe_allow_html=True)

    # Row 1: Case volume & Counts
    st.markdown('<div class="kpi-section-label">\U0001f4ca Case Volume &amp; Counts</div>', unsafe_allow_html=True)
    r1 = [
        _card("\U0001f5c2\ufe0f", "Total Cases",      _fmt(total_cases),      "Emergency + Inpatient + Outpatient", "kpi-blue"),
        _card("\U0001f6a8",         "Total Emergency",  _fmt(emergency),        "Emergency visits",                  "kpi-red"),
        _card("\U0001f3e5",         "Total Inpatient",  _fmt(inpatient),        "Inpatient visits",                  "kpi-green"),
        _card("\U0001fa7a",         "Total Outpatient", _fmt(outpatient),       "Outpatient visits",                 "kpi-orange"),
        _card("\U0001f3e2",         "Facilities Count", _fmt(total_facilities), "DISTINCTCOUNT(FACILITY_NAME)",      "kpi-cyan"),
        _card("\U0001f30d",         "Regions Count",    _fmt(total_regions),    "DISTINCTCOUNT(REGION)",             "kpi-pink"),
    ]
    st.markdown('<div class="kpi-grid-row1">' + "".join(r1) + '</div>', unsafe_allow_html=True)

    # Row 2: Facility & Practitioner metrics
    st.markdown('<div class="kpi-section-label">\U0001f3db\ufe0f Facility &amp; Practitioners</div>', unsafe_allow_html=True)
    r2 = [
        _card("\U0001f3db\ufe0f", "Total Visits by Facility(ies)",    _fmt(visits_by_facility),  "SUM at practitioner facilities",      "kpi-blue"),
        _card("\U0001f4d0",         "% Practitioner per Facility(ies)", _fmt_pct(pct_facility),    "Practitioner share of facility total", "kpi-yellow"),
        _card("\U0001f52c",         "Unique Specialities",               _fmt(unique_specialities), "DISTINCTCOUNT(SPECIALITY)",           "kpi-green"),
        _card("\U0001f464",         "Unique Practitioners",              _fmt(unique_pract),        "DISTINCTCOUNT(PRACTITIONERID)",        "kpi-violet"),
        _card("\U0001f4c5",         "Total Days",                        _fmt(total_pract),         "COUNTA(PRACTITIONERID)",               "kpi-pink"),
    ]
    st.markdown('<div class="kpi-grid-5">' + "".join(r2) + '</div>', unsafe_allow_html=True)

    # Row 3: Facility type counts
    ftype_map = {row.get("facility_type", ""): row for row in ftype_data}
    st.markdown('<div class="kpi-section-label">\U0001f3f7\ufe0f Facility Types</div>', unsafe_allow_html=True)
    r3 = []
    for ft in _FTYPE_ORDER:
        row   = ftype_map.get(ft, {})
        icon  = _FTYPE_ICON.get(ft, "\U0001f3e2")
        color = _FTYPE_COLOR.get(ft, "kpi-blue")
        ara   = _FTYPE_ARA.get(ft, ft)
        # Main value = DISTINCTCOUNT(FACILITY_NAME) per type — matches Excel pivot
        sub   = f"Cases: {_fmt(row.get('total_cases', 0))}  Practs: {_fmt(row.get('unique_practitioners', 0))}"
        r3.append(_card(icon, f"{ft} - {ara}", _fmt(row.get("unique_facilities", 0)), sub, color))
    st.markdown('<div class="kpi-grid-ftype">' + "".join(r3) + '</div>', unsafe_allow_html=True)
