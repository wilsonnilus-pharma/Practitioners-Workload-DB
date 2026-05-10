"""
Pivot module — aggregation logic for matrix views and exports.
"""
import polars as pl

def get_workload_pivot(df: pl.DataFrame):
    """
    Generate a pivot table for export (Practitioner x ServiceTypes).
    """
    return df.pivot(
        values="Count",
        index="PRACTITIONERNAME",
        on="ServiceType",
        aggregate_function="sum"
    ).fill_null(0)

def get_specialty_summary(df: pl.DataFrame):
    """
    Summarize workload by specialty.
    """
    return df.groupby("SPECIALITY").agg([
        pl.col("EMERGENCY").sum().alias("Total_Emergency"),
        pl.col("INPATIENT").sum().alias("Total_Inpatient"),
        pl.col("OUTPATIENT").sum().alias("Total_Outpatient"),
        pl.col("Total_Visits").sum().alias("Total_Overall")
    ]).sort("Total_Overall", descending=True)
