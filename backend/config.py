"""
Central configuration for Practitioners Workload DB backend.
All paths, constants, and environment-driven settings live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent          # Base Directory
CSV_XML_DIR = BASE_DIR / "csv_xml"
DATABASE_PATH = BASE_DIR / "PractitionersWorkloadDB.db"

# ── Database ───────────────────────────────────────────────────────────────
DATABASE_URL = "sqlite:///./database.db"

# ── Auth / Security ────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_32_CHAR_KEY!!")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))  # 8 hours

# ── Import settings ────────────────────────────────────────────────────────
CSV_CHUNK_SIZE = int(os.getenv("CSV_CHUNK_SIZE", "100000"))
ALLOWED_EXTENSIONS = {".csv", ".xml"}
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

# ── Pagination ─────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 2_000_000  # allow "All rows" from the table UI

# ── Practitioner CSV known column mapping ─────────────────────────────────
# Maps raw CSV header → clean DB column name
PRACTITIONER_CSV_COLUMN_MAP = {
    "REGION": "region",
    "FACILITYNAME": "facility_name",
    "PRACTITIONERID": "practitioner_id",
    "PRACTITIONERNAME": "practitioner_name",
    "SPECIALITY": "speciality",
    "VISITDATE": "visit_date",
    "EMERGENCY": "emergency",
    "INPATIENT": "inpatient",
    "OUTPATIENT": "outpatient",
}

# Date format used in Practitioners Workload.csv
PRACTITIONER_DATE_FORMAT = "%Y-%m-%d"
