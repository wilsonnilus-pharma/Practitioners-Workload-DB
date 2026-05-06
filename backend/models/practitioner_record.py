"""SQLAlchemy model for practitioner_records — maps Practitioners Workload.csv."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Index
)
from backend.database import Base


class PractitionerRecord(Base):
    __tablename__ = "practitioner_records"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, nullable=False, index=True)

    # ── Raw columns from Practitioners Workload.csv ────────────────────
    region = Column(String, nullable=True)
    facility_name = Column(String, nullable=True)
    practitioner_id = Column(String, nullable=True)
    practitioner_name = Column(String, nullable=True)
    speciality = Column(String, nullable=True)
    visit_date = Column(Date, nullable=True)
    emergency = Column(Integer, default=0, nullable=False)
    inpatient = Column(Integer, default=0, nullable=False)
    outpatient = Column(Integer, default=0, nullable=False)
    month = Column(String, nullable=True)   # e.g. "03-Mar" – computed from visit_date

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Composite indexes for dashboard filters ────────────────────────
    __table_args__ = (
        Index("idx_pr_facility",        "facility_name"),
        Index("idx_pr_practitioner",    "practitioner_id"),
        Index("idx_pr_date",            "visit_date"),
        Index("idx_pr_region",          "region"),
        Index("idx_pr_speciality",      "speciality"),
        Index("idx_pr_date_facility",   "visit_date", "facility_name"),
    )
