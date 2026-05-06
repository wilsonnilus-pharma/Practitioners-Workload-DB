"""Export router — GET /export: streaming CSV of filtered results."""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
from backend.auth import get_current_user
from backend.services.aggregator import _build_where

router = APIRouter(tags=["data"])


@router.get("/export")
def export_csv(
    region: Optional[str] = None,
    facility_name: Optional[str] = None,
    practitioner_id: Optional[str] = None,
    speciality: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Stream filtered records as a downloadable CSV."""
    filters = {k: v for k, v in {
        "region": region,
        "facility_name": facility_name,
        "practitioner_id": practitioner_id,
        "speciality": speciality,
        "date_from": date_from,
        "date_to": date_to,
        "search": search,
    }.items() if v}

    where, params = _build_where(filters)

    def iterrows():
        """Generator: fetch from DB in batches and yield CSV lines."""
        COLUMNS = [
            "region", "facility_name", "practitioner_id", "practitioner_name",
            "speciality", "visit_date", "emergency", "inpatient", "outpatient",
        ]

        # Write header
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(COLUMNS)
        yield buf.getvalue()

        # Stream data in blocks
        BATCH = 5000
        offset = 0
        while True:
            sql = text(f"""
                SELECT {', '.join(COLUMNS)}
                FROM practitioner_records
                WHERE 1=1 {where}
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """)
            p = {**params, "limit": BATCH, "offset": offset}
            rows = db.execute(sql, p).fetchall()
            if not rows:
                break
            buf = io.StringIO()
            writer = csv.writer(buf)
            for row in rows:
                writer.writerow([str(v) if v is not None else "" for v in row])
            yield buf.getvalue()
            offset += BATCH
            if len(rows) < BATCH:
                break

    return StreamingResponse(
        iterrows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )
