"""KPI cards component — renders all Power BI measure tiles in a two-row grid.

Measures displayed:
  Row 1: Total Cases | Total Emergency | Total Inpatient | Total Outpatient
  Row 2: Total Visits by Facility | Unique Specialities | Unique Practitioners | Total Days | % of Facility
"""

from __future__ import annotations
import streamlit as st


_CSS = """
<style>
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.85rem;
    margin-bottom: 0.4rem;
}
.kpi-grid-5 {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 0.85rem;
    margin-bottom: 0.4rem;
}
.kpi-grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.85rem;
    margin-bottom: 0.4rem;
}
.kpi-grid-row1 {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 0.85rem;
    margin-bottom: 0.4rem;
}
@media (max-width: 1400px) { .kpi-grid-row1 { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 1300px) { .kpi-grid-5 { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 1100px) { .kpi-grid, .kpi-grid-5 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 800px)  { .kpi-grid-row1 { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 600px)  { .kpi-grid, .kpi-grid-5, .kpi-grid-row1 { grid-template-columns: 1fr; } }

.kpi-card {
    background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #1e3a5f;
    border-radius: 14px;
    padding: 1.1rem 1.3rem 0.9rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.45); }
.kpi-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--kpi-accent, #60a5fa);
    border-radius: 14px 14px 0 0;
}
.kpi-icon  { font-size: 1.3rem; line-height: 1; margin-bottom: 0.35rem; text-align: center; }
.kpi-label {
    font-size: 0.9rem; color: #ffffff;
    font-weight: 800;
    letter-spacing: 0.02em; margin-bottom: 0.25rem;
    text-align: center;
}
.kpi-value {
    font-size: 2.0rem; font-weight: 800;
    color: var(--kpi-accent, #f1f5f9);
    line-height: 1.1; margin-bottom: 0.2rem;
    text-align: left;
}
.kpi-sub { font-size: 0.65rem; color: #475569; text-align: left; }

/* accent colours */
.kpi-blue   { --kpi-accent: #60a5fa; }
.kpi-red    { --kpi-accent: #f87171; }
.kpi-green  { --kpi-accent: #34d399; }
.kpi-orange { --kpi-accent: #fb923c; }
.kpi-violet { --kpi-accent: #a78bfa; }
.kpi-cyan   { --kpi-accent: #22d3ee; }
.kpi-pink   { --kpi-accent: #f472b6; }
.kpi-yellow { --kpi-accent: #fbbf24; }

.kpi-section-label {
    font-size: 0.65rem; font-weight: 700; color: #475569;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 0.6rem 0 0.4rem;
}
</style>
"""


def _card(icon: str, label: str, value: str, sub: str, color: str) -> str:
    return f"""
    <div class="kpi-card {color}">
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""


def _fmt(n) -> str:
    """Format large numbers with commas."""
    try:
        return f"{int(n):,}"
    except Exception:
        return str(n)


def _fmt_pct(n) -> str:
    try:
        return f"{float(n):.2f}%"
    except Exception:
        return "—"


def render_kpi_cards(kpi: dict, filters: dict = None):
    """Render two rows of KPI metric cards."""
    filters = filters or {}
    pc_list = [pc.lower() for pc in filters.get("patient_class", [])]
    
    # User requested to keep all cards visible, even if they are 0.
    show_e = True
    show_i = True
    show_o = True
    # ── Extract values ─────────────────────────────────────────────────
    total_cases        = kpi.get("total_cases", 0) or 0
    emergency          = kpi.get("total_emergency", 0) or 0
    inpatient          = kpi.get("total_inpatient", 0) or 0
    outpatient         = kpi.get("total_outpatient", 0) or 0
    visits_by_facility  = kpi.get("total_visits_by_facility", 0) or 0
    unique_specialities = kpi.get("unique_specialities", 0) or 0
    unique_pract        = kpi.get("unique_practitioners", 0) or 0
    total_pract         = kpi.get("total_practitioners", 0) or 0
    pct_facility        = kpi.get("pct_of_facility", 0.0) or 0.0
    total_facilities    = kpi.get("total_facilities", 0) or 0
    total_regions       = kpi.get("total_regions", 0) or 0

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Row 1: Case volume + Counts ────────────────────────────────────
    st.markdown('<div class="kpi-section-label">📊 Case Volume & Counts</div>', unsafe_allow_html=True)
    cards = []
    cards.append(_card("🗂️", "Total Cases", _fmt(total_cases), "Emergency + Inpatient + Outpatient", "kpi-blue"))
    if show_e: cards.append(_card("🚨", "Total Emergency", _fmt(emergency), "Emergency visits", "kpi-red"))
    if show_i: cards.append(_card("🏥", "Total Inpatient", _fmt(inpatient), "Inpatient visits", "kpi-green"))
    if show_o: cards.append(_card("🩺", "Total Outpatient", _fmt(outpatient), "Outpatient visits", "kpi-orange"))
    
    # Add the requested counts next to Outpatient
    cards.append(_card("🏢", "Facilities Count", _fmt(total_facilities), "DISTINCTCOUNT(FACILITY_NAME)", "kpi-cyan"))
    cards.append(_card("🌍", "Regions Count", _fmt(total_regions), "DISTINCTCOUNT(REGION)", "kpi-pink"))

    st.markdown(
        '<div class="kpi-grid-row1">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    # ── Row 2: Facility & Practitioner metrics ─────────────────────────
    st.markdown('<div class="kpi-section-label">🏛️ Facility & Practitioners</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="kpi-grid-5">'
        + _card("🏛️", "Total Visits by Facility(ies)",
                _fmt(visits_by_facility), "SUM at practitioner's facilities", "kpi-blue")
        + _card("📐", "% Practitioner per Facility(ies)",
                _fmt_pct(pct_facility), "Practitioner share of facility total", "kpi-yellow")
        + _card("🔬", "Unique Specialities",
                _fmt(unique_specialities), "DISTINCTCOUNT(SPECIALITY)", "kpi-green")
        + _card("👤", "Unique Practitioners",
                _fmt(unique_pract), "DISTINCTCOUNT(PRACTITIONERID)", "kpi-violet")
        + _card("📅", "Total Days",
                _fmt(total_pract), "COUNTA(PRACTITIONERID)", "kpi-pink")
        + "</div>",
        unsafe_allow_html=True,
    )

