"""
CSV importer — chunked reading with date parsing and score computation.
Handles Doctor.csv specifically; future CSVs will use generic import.
"""

from __future__ import annotations
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from backend.config import (
    CSV_CHUNK_SIZE,
    PRACTITIONER_CSV_COLUMN_MAP,
    PRACTITIONER_DATE_FORMAT,
)
from backend.models.file_registry import ImportLog, ImportedFile

# SQLite limit for recent versions is 32766 bind parameters per statement
SQLITE_MAX_VARS = 32766


def _safe_sql_chunksize(num_cols: int) -> int:
    """Max rows per INSERT without exceeding SQLite's variable limit."""
    return max(1, SQLITE_MAX_VARS // num_cols)


def _to_sql_safe(df: pd.DataFrame, table_name: str, engine) -> None:
    """
    Insert a DataFrame into SQLite.
    Using default pandas to_sql relies on SQLAlchemy's fast executemany
    which avoids the SQLite bind parameter limit entirely.
    """
    if df.empty:
        return
    df.to_sql(
        table_name,
        con=engine,
        if_exists="append",
        index=False,
    )


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse visit_date column from YYYY-MM-DD to Python date."""
    if "visit_date" in df.columns:
        df["visit_date"] = pd.to_datetime(
            df["visit_date"], format=PRACTITIONER_DATE_FORMAT, errors="coerce"
        ).dt.date
    return df


def _clean_int(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def import_practitioner_csv(
    file_path: Path,
    file_record: ImportedFile,
    db: Session,
) -> int:
    """
    Import Practitioners Workload.csv in chunks.
    Returns total rows inserted.
    """
    total_rows = 0
    chunk_num = 0
    engine = db.get_bind()
    file_id = file_record.id

    for chunk in pd.read_csv(
        file_path,
        chunksize=CSV_CHUNK_SIZE,
        dtype=str,          # read all as string first, then convert
        encoding="utf-8-sig",
        na_values=["", "NA", "N/A", "null", "NULL", "None"],
        keep_default_na=True,
    ):
        try:
            # Rename raw headers → DB column names
            chunk.rename(
                columns={k: v for k, v in PRACTITIONER_CSV_COLUMN_MAP.items() if k in chunk.columns},
                inplace=True,
            )

            # Parse numeric & dates
            chunk = _parse_dates(chunk)
            chunk = _clean_int(chunk, "emergency")
            chunk = _clean_int(chunk, "inpatient")
            chunk = _clean_int(chunk, "outpatient")

            # Compute Month column ─ mirrors Power Query:
            # Text.PadStart(Text.From(Date.Month([VISITDATE])),2,"0") & "-" &
            # Text.Start(Date.MonthName([VISITDATE]),3)
            import calendar
            if "visit_date" in chunk.columns:
                def _month_label(d):
                    if d is None or (hasattr(d, '__class__') and d.__class__.__name__ == 'NaTType'):
                        return None
                    try:
                        return f"{d.month:02d}-{calendar.month_name[d.month][:3]}"
                    except Exception:
                        return None
                chunk["month"] = chunk["visit_date"].apply(_month_label)
            
            # Fill NaN with 0 for metrics just in case
            for col in ["emergency", "inpatient", "outpatient"]:
                if col in chunk.columns:
                    chunk[col] = chunk[col].fillna(0)

            # Add FK
            chunk["source_file_id"] = file_id

            # Keep only columns that exist in DB schema
            from backend.models.practitioner_record import PractitionerRecord
            valid_cols = [c.name for c in PractitionerRecord.__table__.columns]
            chunk = chunk[[c for c in valid_cols if c in chunk.columns]]

            _to_sql_safe(chunk, "practitioner_records", engine)

            rows = len(chunk)
            total_rows += rows

            # Log chunk
            log = ImportLog(
                file_id=file_id,
                chunk_number=chunk_num,
                rows_in_chunk=rows,
                status="ok",
            )
            db.add(log)
            db.commit()

        except Exception as exc:
            log = ImportLog(
                file_id=file_id,
                chunk_number=chunk_num,
                rows_in_chunk=0,
                status="error",
                message=str(exc)[:500],
            )
            db.add(log)
            db.commit()
            raise

        chunk_num += 1

    return total_rows


def import_generic_csv(
    file_path: Path,
    file_record: ImportedFile,
    table_name: str,
    db: Session,
) -> int:
    """
    Generic CSV importer for future files.
    Creates the table dynamically from the CSV headers.
    """
    from sqlalchemy import text

    total_rows = 0
    chunk_num = 0
    engine = db.get_bind()
    file_id = file_record.id

    for chunk in pd.read_csv(
        file_path,
        chunksize=CSV_CHUNK_SIZE,
        dtype=str,
        encoding="utf-8-sig",
        na_values=["", "NA", "N/A", "null", "NULL", "None"],
        keep_default_na=True,
    ):
        try:
            # Sanitize column names
            chunk.columns = [
                c.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
                for c in chunk.columns
            ]
            chunk["source_file_id"] = file_id

            _to_sql_safe(chunk, table_name, engine)

            total_rows += len(chunk)
            log = ImportLog(
                file_id=file_id,
                chunk_number=chunk_num,
                rows_in_chunk=len(chunk),
                status="ok",
            )
            db.add(log)
            db.commit()

        except Exception as exc:
            log = ImportLog(
                file_id=file_id,
                chunk_number=chunk_num,
                rows_in_chunk=0,
                status="error",
                message=str(exc)[:500],
            )
            db.add(log)
            db.commit()
            raise

        chunk_num += 1

    return total_rows
