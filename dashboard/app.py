"""
Main Entry Point — ties filters, data, and charts into a Panel template.
"""
import panel as pn
import polars as pl
from dashboard.data_loader import load_workload_data, get_filtered_data
from dashboard.filters import create_filters
from dashboard.charts import (
    get_specialty_treemap, get_workload_distribution, 
    get_emergency_trends, get_practitioner_matrix
)

pn.extension('vega', template='fast', sizing_mode='stretch_width')

# 1. Load Initial Lazy Data
try:
    LF = load_workload_data()
except Exception as e:
    pn.state.notifications.error(f"Error loading data: {e}")
    LF = pl.LazyFrame()

# 2. Initialize Filters
widgets = create_filters(LF)

# 3. Reactive Data Pipeline
def filtered_df_view():
    filters = {
        "regions": widgets["region"].value,
        "facilities": widgets["facility"].value,
        "specialities": widgets["speciality"].value,
        "months": widgets["month"].value,
        "practitioners": widgets["practitioner"].value,
        "date_range": widgets["date_range"].value
    }
    return get_filtered_data(LF, filters)

# Bind the data fetching to the widgets
reactive_df = pn.bind(filtered_df_view)

# 4. Reactive Chart Components
@pn.depends(reactive_df)
def kpi_cards(df):
    if df.empty: return pn.Column("No data available")
    
    metrics = df.select([
        pl.col("EMERGENCY").sum(),
        pl.col("INPATIENT").sum(),
        pl.col("OUTPATIENT").sum(),
        pl.col("Total_Visits").sum()
    ])
    
    return pn.Row(
        pn.indicators.Number(name="🚨 Emergency", value=metrics[0,0], format='{value:,}', font_size='24pt'),
        pn.indicators.Number(name="🏥 Inpatient", value=metrics[0,1], format='{value:,}', font_size='24pt'),
        pn.indicators.Number(name="🩺 Outpatient", value=metrics[0,2], format='{value:,}', font_size='24pt'),
        pn.indicators.Number(name="📊 Total All", value=metrics[0,3], format='{value:,}', font_size='24pt'),
    )

@pn.depends(reactive_df)
def specialty_chart(df):
    if df.empty: return "No data"
    return pn.pane.Vega(get_specialty_treemap(df.to_pandas()))

@pn.depends(reactive_df)
def monthly_trends_pane(df):
    if df.empty: return "No data"
    # Group by Month and Service Type
    monthly = df.groupby(["MonthNum", "Month"]).agg([
        pl.col("EMERGENCY").sum(),
        pl.col("INPATIENT").sum(),
        pl.col("OUTPATIENT").sum()
    ]).sort("MonthNum").to_pandas()
    
    melted = monthly.melt(id_vars=["Month"], value_vars=["EMERGENCY", "INPATIENT", "OUTPATIENT"])
    chart = alt.Chart(melted).mark_line(point=True).encode(
        x=alt.X("Month:N", sort=MONTH_ORDER),
        y=alt.Y("value:Q", title="Total Visits"),
        color="variable:N",
        tooltip=["Month", "variable", "value"]
    ).properties(title="Monthly Workload Trends", height=300)
    return pn.pane.Vega(chart)

@pn.depends(reactive_df)
def dow_chart(df):
    if df.empty: return "No data"
    # Group by DayOfWeek
    dow_data = df.groupby(["DayOfWeekNum", "DayOfWeek"]).agg([
        pl.col("EMERGENCY").sum(),
        pl.col("OUTPATIENT").sum()
    ]).sort("DayOfWeekNum").to_pandas()
    
    melted = dow_data.melt(id_vars=["DayOfWeek"], value_vars=["EMERGENCY", "OUTPATIENT"])
    chart = alt.Chart(melted).mark_bar().encode(
        x=alt.X("DayOfWeek:N", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
        y=alt.Y("value:Q", title="Total Visits"),
        color="variable:N",
        column="variable:N"
    ).properties(title="Day of Week Breakdown", width=200)
    return pn.pane.Vega(chart)

@pn.depends(reactive_df)
def emergency_trends_pane(df):
    if df.empty: return "No data"
    return pn.pane.Vega(get_emergency_trends(df))

@pn.depends(reactive_df)
def workload_distribution_pane(df):
    if df.empty: return "No data"
    # Note: Toggle logic for practitioner vs specialty can be added here
    return pn.pane.Vega(get_workload_distribution(df.to_pandas(), "SPECIALITY"))

@pn.depends(reactive_df)
def practitioner_heatmap(df):
    if df.empty: return "No data"
    return pn.pane.Vega(get_practitioner_matrix(df))

# 4.5 Export Functionality
def export_filtered_csv(event):
    df = filtered_df_view()
    import io
    sio = io.BytesIO()
    df.write_csv(sio)
    sio.seek(0)
    return sio

export_btn = pn.widgets.FileDownload(
    callback=export_filtered_csv,
    filename="filtered_workload.csv",
    label="📥 Export Filtered Data",
    button_type="success"
)

# 5. Layout Setup
sidebar = [
    widgets["region"],
    widgets["facility"],
    widgets["speciality"],
    widgets["month"],
    widgets["practitioner"],
    widgets["service_type"],
    widgets["date_range"],
    export_btn,
    widgets["reset"]
]

main_content = pn.Column(
    kpi_cards,
    pn.Row(specialty_chart, workload_distribution_pane),
    pn.Row(emergency_trends_pane),
    pn.Row(monthly_trends_pane, dow_chart),
    pn.Row(practitioner_heatmap),
    pn.pane.Markdown("*Efficiency analysis (cases per hour) will be enabled when work-hours data is available*", style={'color': 'gray'})
)

# 6. Template Configuration
template = pn.template.FastListTemplate(
    title="Practitioner Workload Analytics",
    sidebar=sidebar,
    main=[main_content],
    accent_base_color="#10b981",
    header_background="#0f172a",
)

template.servable()
if __name__ == "__main__":
    pn.serve(template, port=5006)
