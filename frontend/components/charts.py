"""Charts component — all Plotly chart types for the dashboard."""

from __future__ import annotations
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


_CHART_THEME = "plotly_dark"
_COLOR_SEQ   = (
    px.colors.qualitative.Bold
    + px.colors.qualitative.Pastel
    + px.colors.qualitative.Dark2
    + px.colors.qualitative.Set3
)


def _df(pivot: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(pivot) if pivot else pd.DataFrame()


def _chart_height(n: int, min_h: int = 480) -> int:
    """
    Return a chart height that keeps legend entries visible, with a safety cap.
    """
    visible_items = max(n, 20)
    calculated_h = visible_items * 20 + 200
    # Cap at 3000px to prevent browser hanging on extremely large charts
    return min(max(min_h, calculated_h), 3000)


def render_charts(pivot: list[dict], group_by: str, kpi: dict, filters: dict = None):
    """Render all chart types based on pivot data."""
    filters = filters or {}

    show_e = True
    show_i = True
    show_o = True

    df = _df(pivot)
    if df.empty:
        st.info("No data to visualize. Apply filters and make sure data is imported.")
        return

    dim        = group_by.lower()
    df.rename(columns={"dimension": dim}, inplace=True)
    total_rows = len(df)

    # ── TOP N control — same checkbox + slider style as sidebar ───────
    st.markdown("**🏆 TOP N**")
    _enabled = st.checkbox(
        "Enable TOP N", value=True,
        key="chart_topn_enabled",
    )
    if _enabled:
        # Keys for sync
        k_sl = "chart_topn_slider"
        k_num = "chart_topn_num"

        if "chart_topn_val" not in st.session_state:
            st.session_state.chart_topn_val = min(filters.get("top_n", 15), total_rows) if total_rows > 0 else 15
        
        # Auto-cap logic
        if st.session_state.chart_topn_val > total_rows and total_rows > 0:
            st.session_state.chart_topn_val = total_rows

        def on_sl_change():
            val = st.session_state[k_sl]
            st.session_state.chart_topn_val = val
            st.session_state[k_num] = val

        def on_num_change():
            val = st.session_state[k_num]
            capped = min(val, total_rows)
            st.session_state.chart_topn_val = capped
            st.session_state[k_sl] = capped
            st.session_state[k_num] = capped # Force update input box to capped value

        st.markdown("<span style='font-size:0.85rem;color:#94a3b8'>Show top N rows</span>", unsafe_allow_html=True)
        c1, c2 = st.columns([4, 1])
        
        # Initialize widget values if they don't exist yet to match current state
        if k_sl not in st.session_state: st.session_state[k_sl] = st.session_state.chart_topn_val
        if k_num not in st.session_state: st.session_state[k_num] = st.session_state.chart_topn_val

        with c1:
            st.slider(
                "Slider", min_value=1, max_value=max(total_rows, 2),
                key=k_sl, on_change=on_sl_change, label_visibility="collapsed"
            )
        with c2:
            st.number_input(
                "Number", min_value=1, max_value=1000000,
                key=k_num, on_change=on_num_change, label_visibility="collapsed"
            )
        
        chart_n = st.session_state.chart_topn_val
        st.caption(f"Showing top **{chart_n:,}** of **{total_rows:,}** rows")
    else:
        # Safety: rendering > 500 entries in Plotly will hang the browser
        if total_rows > 500:
            st.warning(f"⚠️ Data is too large ({total_rows:,} rows). Visualizing only the top 500 to prevent browser lag.")
            chart_n = 500
        else:
            chart_n = total_rows

    # ── Chart sub-tabs ─────────────────────────────────────────────────
    tabs = st.tabs(["📊 Bar", "📈 Line", "🍩 Pie", "🔥 Heatmap", "📉 Scatter", "🎯 Gauge"])

    # ── 1. Bar ─────────────────────────────────────────────────────────
    with tabs[0]:
        bar_opts = ["total_cases", "total_records"]
        if show_e: bar_opts.append("total_emergency")
        if show_i: bar_opts.append("total_inpatient")
        if show_o: bar_opts.append("total_outpatient")

        metric  = st.selectbox("Metric", bar_opts, key="bar_metric")
        bar_df  = df.head(chart_n)
        fig = px.bar(
            bar_df, x=dim, y=metric,
            color=metric, color_continuous_scale="Blues",
            title=f"Top {chart_n} — {metric.replace('_',' ').title()} by {group_by.replace('_',' ').title()}",
            template=_CHART_THEME,
            labels={dim: group_by.replace("_", " ").title(),
                    metric: metric.replace("_", " ").title()},
        )
        fig.update_layout(xaxis_tickangle=-40, height=_chart_height(chart_n))
        st.plotly_chart(fig, use_container_width=True)

    # ── 2. Line ────────────────────────────────────────────────────────
    with tabs[1]:
        try:
            df_line = df.copy()
            df_line[dim] = pd.to_datetime(df_line[dim], errors="coerce")
            df_line = df_line.dropna(subset=[dim]).sort_values(dim)
            if df_line.empty:
                st.info("Line chart works best when grouped by 'visit_date'.")
            else:
                fig2 = go.Figure()
                lines = []
                if show_e: lines.append(("total_emergency",  "#f87171"))
                if show_i: lines.append(("total_inpatient",  "#34d399"))
                if show_o: lines.append(("total_outpatient", "#fb923c"))
                lines.append(("total_cases", "#60a5fa"))
                for col, color in lines:
                    fig2.add_trace(go.Scatter(
                        x=df_line[dim], y=df_line[col],
                        mode="lines+markers",
                        name=col.replace("total_", "").title(),
                        line=dict(color=color, width=2),
                    ))
                fig2.update_layout(template=_CHART_THEME, height=480,
                                   title="Trend Over Time", xaxis_title="Date")
                st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.warning(f"Line chart error: {e}")

    # ── 3. Pie ─────────────────────────────────────────────────────────
    with tabs[2]:
        pie_opts = ["total_cases", "total_records"]
        if show_e: pie_opts.append("total_emergency")
        if show_i: pie_opts.append("total_inpatient")
        if show_o: pie_opts.append("total_outpatient")

        pie_metric = st.selectbox("Metric", pie_opts, key="pie_metric")
        pie_df     = df.head(chart_n)
        pie_h      = _chart_height(chart_n, min_h=520)

        fig3 = px.pie(
            pie_df, names=dim, values=pie_metric,
            title=f"Top {chart_n} — {pie_metric.replace('_',' ').title()} Distribution",
            template=_CHART_THEME, hole=0.4,
            color_discrete_sequence=_COLOR_SEQ,
        )
        fig3.update_traces(textposition="outside", textinfo="percent+label")
        fig3.update_layout(
            height=pie_h,
            legend=dict(
                orientation="v",
                x=1.02, y=1,
                xanchor="left",
                yanchor="top",
                font=dict(size=11),
                entrywidthmode="pixels",
                entrywidth=200,
                tracegroupgap=0,
            ),
            margin=dict(l=20, r=260, t=60, b=20),
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── 4. Heatmap ─────────────────────────────────────────────────────
    with tabs[3]:
        base_heat = ["total_cases", "unique_practitioners"]
        if show_e: base_heat.insert(0, "total_emergency")
        if show_i: base_heat.insert(1, "total_inpatient")
        if show_o: base_heat.insert(2, "total_outpatient")

        heat_cols = [c for c in base_heat if c in df.columns]
        if not heat_cols:
            st.info("No numeric columns available for the heatmap.")
        else:
            heat_df = df.set_index(dim)[heat_cols].head(chart_n)
            heat_h  = _chart_height(chart_n, min_h=480)
            fig4 = go.Figure(data=go.Heatmap(
                z=heat_df.values,
                x=[c.replace("_", " ").title() for c in heat_cols],
                y=[str(v)[:35] for v in heat_df.index],
                colorscale="Blues",
            ))
            fig4.update_layout(template=_CHART_THEME, height=heat_h,
                               title=f"Heatmap — by {group_by.replace('_',' ').title()}")
            st.plotly_chart(fig4, use_container_width=True)

    # ── 5. Scatter ─────────────────────────────────────────────────────
    with tabs[4]:
        scat_df = df.head(chart_n)
        fig5 = px.scatter(
            scat_df, x="total_emergency", y="total_outpatient",
            size="total_cases", color="total_inpatient",
            hover_name=dim, template=_CHART_THEME, height=500,
            title=f"Top {chart_n} — Emergency vs Outpatient (bubble = Total Cases)",
            color_continuous_scale="Turbo",
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ── 6. Gauge — overall composition ────────────────────────────────
    with tabs[5]:
        st.markdown("#### 🥧 Overall Workload Composition")
        comp_sources, comp_visits = [], []
        if show_e:
            comp_sources.append("Emergency")
            comp_visits.append(kpi.get("total_emergency", 0))
        if show_i:
            comp_sources.append("Inpatient")
            comp_visits.append(kpi.get("total_inpatient", 0))
        if show_o:
            comp_sources.append("Outpatient")
            comp_visits.append(kpi.get("total_outpatient", 0))

        metrics_df = pd.DataFrame({"Source": comp_sources, "Visits": comp_visits})
        fig_comp = px.pie(
            metrics_df, names="Source", values="Visits",
            color="Source",
            color_discrete_map={
                "Emergency":  "#f87171",
                "Inpatient":  "#34d399",
                "Outpatient": "#fb923c",
            },
            template=_CHART_THEME, hole=0.5,
            title=f"Total Cases: {(kpi.get('total_cases') or 0):,}",
        )
        fig_comp.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_comp, use_container_width=True)
