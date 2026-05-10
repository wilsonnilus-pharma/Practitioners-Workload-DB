"""Data router — GET /data (paginated filtered records) + GET /summary."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.auth import get_current_user
from backend.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.services.aggregator import (
    get_kpi_summary, get_pivot, get_distinct_values_filtered, get_facility_breakdown_table
)

router = APIRouter(tags=["data"])


def _parse_filters(
    region: Optional[list[str]] = None,
    facility_name: Optional[list[str]] = None,
    practitioner_id: Optional[list[str]] = None,
    speciality: Optional[list[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    source_file_id: int | None = None,
    facility_count: list[str] | None = None,
    patient_class: list[str] | None = None,
    facility_type: list[str] | None = None,
    top_n: int | None = None,
    top_n_by: str | None = None,
    row_min: int | None = None,
    row_max: int | None = None,
) -> dict:
    return {k: v for k, v in locals().items() if v}


@router.get("/data")
def get_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    region: Optional[list[str]] = Query(None),
    facility_name: Optional[list[str]] = Query(None),
    practitioner_id: Optional[list[str]] = Query(None),
    speciality: Optional[list[str]] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    source_file_id: int = Query(None),
    facility_count: list[str] = Query(None),
    patient_class: list[str] = Query(None),
    facility_type: list[str] = Query(None),
    row_min: Optional[int] = Query(None),
    row_max: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Paginated, filtered data from practitioner_records."""
    filters = _parse_filters(
        region=region, facility_name=facility_name, practitioner_id=practitioner_id, 
        speciality=speciality, date_from=date_from, date_to=date_to, search=search,
        source_file_id=source_file_id, facility_count=facility_count,
        patient_class=patient_class, facility_type=facility_type,
        row_min=row_min, row_max=row_max,
    )

    from backend.services.aggregator import _build_where
    where, params = _build_where(filters)

    # Count total matching rows
    count_sql = text(f"SELECT COUNT(*) FROM practitioner_records WHERE 1=1 {where}")
    total = db.execute(count_sql, params).scalar()

    # Fetch page
    offset = (page - 1) * page_size
    data_sql = text(f"""
        SELECT
            id, region, facility_name, practitioner_id,
            practitioner_name, speciality, visit_date, month,
            emergency, inpatient, outpatient,
            (emergency + inpatient + outpatient) AS total_cases
        FROM practitioner_records
        WHERE 1=1 {where}
        ORDER BY id
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = page_size
    params["offset"] = offset

    rows = db.execute(data_sql, params).fetchall()
    data = [dict(r._mapping) for r in rows]

    # Convert date objects to strings for JSON
    for row in data:
        if row.get("visit_date") and not isinstance(row["visit_date"], str):
            row["visit_date"] = str(row["visit_date"])

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),  # ceiling div
        "data": data,
    }


@router.get("/summary")
def get_summary(
    region: Optional[list[str]] = Query(None),
    facility_name: Optional[list[str]] = Query(None),
    practitioner_id: Optional[list[str]] = Query(None),
    speciality: Optional[list[str]] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    source_file_id: int = Query(None),
    facility_count: list[str] = Query(None),
    patient_class: list[str] = Query(None),
    facility_type: list[str] = Query(None),
    top_n: int = Query(None),
    top_n_by: str = Query(None),
    group_by: str = Query("practitioner_name"),
    include_kpi: bool = Query(True),
    include_breakdown: bool = Query(True),
    include_top_facs: bool = Query(True),
    row_min: Optional[int] = Query(None),
    row_max: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """KPI summary + pivot aggregation."""
    filters = _parse_filters(
        region=region, facility_name=facility_name, practitioner_id=practitioner_id,
        speciality=speciality, date_from=date_from, date_to=date_to, search=search,
        source_file_id=source_file_id, facility_count=facility_count,
        patient_class=patient_class, facility_type=facility_type,
        top_n=top_n, top_n_by=top_n_by,
        row_min=row_min, row_max=row_max,
    )
    kpi = get_kpi_summary(db, filters) if include_kpi else {}
    pivot = get_pivot(db, filters, group_by=group_by, include_top_facs=include_top_facs)
    breakdown = get_facility_breakdown_table(db, filters, group_by=group_by) if include_breakdown else []
    return {"kpi": kpi, "pivot": pivot, "breakdown": breakdown}


@router.get("/filters/options")
def filter_options(
    column: str = Query(...),
    # Cascading filter context — all active filters scope every dropdown
    region: Optional[list[str]] = Query(None),
    facility_name: Optional[list[str]] = Query(None),
    speciality: Optional[list[str]] = Query(None),
    practitioner_id: Optional[list[str]] = Query(None),
    facility_type: Optional[list[str]] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Return distinct values for a given column, respecting ALL active filters (cascading)."""
    cascade_filters = _parse_filters(
        region=region,
        facility_name=facility_name,
        speciality=speciality,
        practitioner_id=practitioner_id,
        facility_type=facility_type,
        date_from=date_from,
        date_to=date_to,
    )
    return {"column": column, "values": get_distinct_values_filtered(db, column, cascade_filters)}


@router.get("/filters/date-range")
def get_date_range_route(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Return the min and max dates found in the database."""
    from backend.services.aggregator import get_date_range
    mn, mx = get_date_range(db)
    return {"min": mn, "max": mx}


@router.get("/filters/row-range")
def get_row_range_route(db: Session = Depends(get_db), _=Depends(get_current_user)):
    """Return the total record count for the row range filter."""
    from backend.services.aggregator import get_record_count
    return {"total": get_record_count(db)}


@router.get("/facility-type-summary")
def facility_type_summary_route(
    region: Optional[list[str]] = Query(None),
    facility_name: Optional[list[str]] = Query(None),
    practitioner_id: Optional[list[str]] = Query(None),
    speciality: Optional[list[str]] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    source_file_id: int = Query(None),
    facility_count: list[str] = Query(None),
    patient_class: list[str] = Query(None),
    facility_type: list[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Fast facility-type breakdown — single GROUP BY, no heavy CTEs."""
    from backend.services.aggregator import get_facility_type_summary
    filters = _parse_filters(
        region=region, facility_name=facility_name, practitioner_id=practitioner_id,
        speciality=speciality, date_from=date_from, date_to=date_to, search=search,
        source_file_id=source_file_id, facility_count=facility_count,
        patient_class=patient_class, facility_type=facility_type,
    )
    return {"data": get_facility_type_summary(db, filters)}
