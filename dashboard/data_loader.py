"""
Data loader module — handles Polars ingestion and lazy transformations.
"""
import polars as pl
from pathlib import Path

# Constants
CSV_PATH = Path(r"W:\01-03-2026\Dr. Heba\Practitioners Workload.csv")

MONTH_ORDER = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

def load_workload_data() -> pl.LazyFrame:
    """
    Injest CSV using Lazy API and apply calculations.
    """
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Data file not found at {CSV_PATH}")

    lf = pl.scan_csv(CSV_PATH)

    # 1. Parse Date and extract components
    lf = lf.with_columns(
        pl.col("VISITDATE").str.to_date("%Y-%m-%d")
    ).with_columns([
        pl.col("VISITDATE").dt.month().alias("MonthNum"),
        pl.col("VISITDATE").dt.weekday().alias("DayOfWeekNum"),
        pl.col("VISITDATE").dt.strftime("%a").alias("DayOfWeek"),
        pl.col("VISITDATE").dt.week().alias("WeekNumber"),
    ])

    # 2. Add Month Name as ordered categorical
    # We use a mapping for the month numbers to names
    month_map = {i+1: name for i, name in enumerate(MONTH_ORDER)}
    lf = lf.with_columns(
        pl.col("MonthNum").replace_strict(month_map).alias("Month")
    )

    # 3. Add Metric Calculations
    lf = lf.with_columns(
        (pl.col("EMERGENCY").fill_null(0) + 
         pl.col("INPATIENT").fill_null(0) + 
         pl.col("OUTPATIENT").fill_null(0)).alias("Total_Visits")
    )

    return lf

def get_filtered_data(lf: pl.LazyFrame, filters: dict) -> pl.DataFrame:
    """
    Apply filters to the LazyFrame and collect into a DataFrame.
    """
    # Filter by Speciality
    if filters.get("specialities"):
        lf = lf.filter(pl.col("SPECIALITY").is_in(filters["specialities"]))
    
    # Filter by Region
    if filters.get("regions"):
        lf = lf.filter(pl.col("REGION").is_in(filters["regions"]))

    # Filter by Facility (Cascading)
    if filters.get("facilities"):
        lf = lf.filter(pl.col("FACILITYNAME").is_in(filters["facilities"]))

    # Filter by Practitioner
    if filters.get("practitioners"):
        lf = lf.filter(pl.col("PRACTITIONERNAME").is_in(filters["practitioners"]))

    # Filter by Month
    if filters.get("months"):
        lf = lf.filter(pl.col("Month").is_in(filters["months"]))

    # Filter by Date Range
    if filters.get("date_range"):
        start, end = filters["date_range"]
        if start:
            lf = lf.filter(pl.col("VISITDATE") >= start)
        if end:
            lf = lf.filter(pl.col("VISITDATE") <= end)

    return lf.collect()
