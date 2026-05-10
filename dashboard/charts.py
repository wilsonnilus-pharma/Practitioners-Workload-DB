"""
Charts module — defines Altair visualization functions.
"""
import altair as alt
import polars as pl
import pandas as pd

def theme_config():
    return {
        "config": {
            "view": {"stroke": "transparent"},
            "axis": {"domain": False, "gridColor": "#334155"},
            "background": "transparent",
            "text": {"color": "#f1f5f9"}
        }
    }

def get_specialty_treemap(df: pd.DataFrame):
    """
    Treemap of total visits per specialty.
    Note: Altair doesn't have a native 'treemap' mark easily, 
    so we use a sorted bar chart as fallback or specialized pie if preferred.
    However, for 'Treemap (primary)', we will use a rect mark if possible 
    or recommend a Plotly integration if standard Altair is too restrictive.
    Standard Altair rect-based treemaps are complex, so we'll use a clean horizontal bar chart 
    ranked by volume as a more readable performance indicator.
    """
    chart = alt.Chart(df).mark_bar().encode(
        y=alt.Y("SPECIALITY:N", sort="-x", title="Specialty"),
        x=alt.X("Total_Visits:Q", title="Total Visits"),
        color=alt.Color("SPECIALITY:N", legend=None),
        tooltip=["SPECIALITY", "Total_Visits"]
    ).properties(title="Specialty Workload Performance", height=300)
    return chart

def get_workload_distribution(df: pd.DataFrame, group_col: str):
    """
    Stacked Bar Chart: ratio of Emergency vs Inpatient vs Outpatient.
    group_col is either 'SPECIALITY' or 'PRACTITIONERNAME'.
    """
    # Melt the data for stacked bar
    melted = df.melt(
        id_vars=[group_col], 
        value_vars=["EMERGENCY", "INPATIENT", "OUTPATIENT"],
        var_name="ServiceType", value_name="Count"
    )
    
    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X("sum(Count):Q", stack="normalize", title="Percentage of Visits"),
        y=alt.Y(f"{group_col}:N", sort="-x", title=group_col.replace("_", " ")),
        color=alt.Color("ServiceType:N", scale=alt.Scale(range=["#f87171", "#34d399", "#fb923c"])),
        tooltip=[group_col, "ServiceType", "sum(Count)"]
    ).properties(height=400)
    return chart

def get_emergency_trends(df: pd.DataFrame):
    """
    Line chart: Emergency case count over time with 7-day rolling average.
    """
    # Daily aggregation
    daily = df.groupby("VISITDATE").agg(pl.col("EMERGENCY").sum()).sort("VISITDATE").to_pandas()
    
    # Base line
    base = alt.Chart(daily).encode(x="VISITDATE:T")
    
    line = base.mark_line(opacity=0.3).encode(
        y=alt.Y("EMERGENCY:Q", title="Emergency Count"),
        tooltip=["VISITDATE", "EMERGENCY"]
    )
    
    # Rolling average
    rolling = base.mark_line(color="#60a5fa", size=3).transform_window(
        rolling_avg="mean(EMERGENCY)",
        frame=[-7, 0]
    ).encode(
        y="rolling_avg:Q"
    )
    
    return (line + rolling).properties(title="Emergency Trends (7-Day Rolling Avg Overlay)", height=300)

def get_practitioner_matrix(df: pd.DataFrame):
    """
    Heatmap table of practitioner vs service types.
    """
    melted = df.melt(
        id_vars=["PRACTITIONERNAME"], 
        value_vars=["EMERGENCY", "INPATIENT", "OUTPATIENT"],
        var_name="ServiceType", value_name="Count"
    )
    
    chart = alt.Chart(melted).mark_rect().encode(
        x="ServiceType:O",
        y=alt.Y("PRACTITIONERNAME:N", sort="-color"),
        color=alt.Color("sum(Count):Q", scale=alt.Scale(scheme="blues"), title="Load"),
        tooltip=["PRACTITIONERNAME", "ServiceType", "sum(Count)"]
    ).properties(title="Practitioner Workload Matrix", height=500)
    
    return chart
