"""
Filters module — defines Panel widgets and reactive filtering logic.
"""
import panel as pn
import polars as pl
from dashboard.data_loader import MONTH_ORDER

def create_filters(lf: pl.LazyFrame):
    """
    Initialize all filter widgets based on distinct values in the LazyFrame.
    """
    # Fetch distinct values for initial lists
    # Note: We collect small subsets for filters
    data_sample = lf.select([
        "REGION", "FACILITYNAME", "SPECIALITY", "PRACTITIONERNAME"
    ]).unique().collect()

    regions = sorted(data_sample["REGION"].unique().to_list())
    specialities = sorted(data_sample["SPECIALITY"].unique().to_list())
    practitioners = sorted(data_sample["PRACTITIONERNAME"].unique().to_list())

    # 1. Region Filter (Source for cascading)
    region_filter = pn.widgets.MultiChoice(
        name="🌍 Region",
        options=regions,
        placeholder="Select Regions..."
    )

    # 2. Facility Filter (Cascading)
    facility_filter = pn.widgets.MultiChoice(
        name="🏥 Facility",
        options=[], # Populated dynamically
        placeholder="Select Facilities..."
    )

    # 3. Speciality Filter
    spec_filter = pn.widgets.MultiChoice(
        name="⚕️ Speciality",
        options=specialities,
        placeholder="Select Specialities..."
    )

    # 4. Month Filter (Ordered)
    month_filter = pn.widgets.MultiSelect(
        name="📅 Months",
        options=MONTH_ORDER,
        size=6
    )

    # 5. Practitioner Filter (Searchable)
    pract_filter = pn.widgets.MultiChoice(
        name="👨‍⚕️ Practitioner",
        options=practitioners,
        placeholder="Search Practitioner..."
    )

    # 6. Service Type Checkbox
    service_type = pn.widgets.CheckBoxGroup(
        name="🚑 Service Type",
        options=["EMERGENCY", "INPATIENT", "OUTPATIENT"],
        value=["EMERGENCY", "INPATIENT", "OUTPATIENT"],
        inline=False
    )

    # 7. Date Range
    date_range = pn.widgets.DateRangePicker(
        name="🗓 Visit Date Range"
    )

    # 8. Reset Button
    reset_button = pn.widgets.Button(name="🗑 Reset Filters", button_type="danger")

    def reset_all(event):
        region_filter.value = []
        facility_filter.value = []
        spec_filter.value = []
        month_filter.value = []
        pract_filter.value = []
        service_type.value = ["EMERGENCY", "INPATIENT", "OUTPATIENT"]
        date_range.value = (None, None)

    reset_button.on_click(reset_all)

    # ── Cascading Logic ────────────────────────────────────────────────
    @pn.depends(region_filter.param.value, watch=True)
    def update_facilities(selected_regions):
        if not selected_regions:
            facility_filter.options = sorted(data_sample["FACILITYNAME"].unique().to_list())
        else:
            filtered_facs = data_sample.filter(pl.col("REGION").is_in(selected_regions))["FACILITYNAME"].unique().to_list()
            facility_filter.options = sorted(filtered_facs)
        facility_filter.value = [] # Reset selected facilities when region changes

    # Trigger initial population
    update_facilities([])

    return {
        "region": region_filter,
        "facility": facility_filter,
        "speciality": spec_filter,
        "month": month_filter,
        "practitioner": pract_filter,
        "service_type": service_type,
        "date_range": date_range,
        "reset": reset_button
    }
