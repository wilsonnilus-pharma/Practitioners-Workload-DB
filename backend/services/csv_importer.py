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


def _filter_existing_rows(df: pd.DataFrame, db: Session) -> pd.DataFrame:
    """Filter out rows that already exist in practitioner_records to avoid duplicates."""
    if df.empty:
        return df
    
    from sqlalchemy import text
    engine = db.get_bind()

    # 1. Internal deduplication (unique rows within the chunk)
    identity_cols = [
        "region", "facility_name", "practitioner_id", "speciality", 
        "visit_date", "emergency", "inpatient", "outpatient"
    ]
    # Ensure visit_date is string for consistent comparison if needed, 
    # but pandas date objects usually work with to_sql
    df_unique = df.drop_duplicates(subset=identity_cols).copy()
    
    if df_unique.empty:
        return df_unique

    # 2. Check against DB using a temporary table for performance
    import uuid
    temp_table = f"tmp_check_{uuid.uuid4().hex[:8]}"
    
    try:
        # Upload only identity columns to a temporary table
        df_unique[identity_cols].to_sql(temp_table, engine, index=False, if_exists="replace")
        
        # Identify rows that already exist in the main table
        # We use COALESCE for nullable columns to ensure they match correctly
        check_query = text(f"""
            SELECT t.* 
            FROM {temp_table} t
            INNER JOIN practitioner_records p ON 
                COALESCE(t.region, '')          = COALESCE(p.region, '') AND
                COALESCE(t.facility_name, '')   = COALESCE(p.facility_name, '') AND
                COALESCE(t.practitioner_id, '')  = COALESCE(p.practitioner_id, '') AND
                COALESCE(t.speciality, '')       = COALESCE(p.speciality, '') AND
                t.visit_date                    = p.visit_date AND
                t.emergency                     = p.emergency AND
                t.inpatient                     = p.inpatient AND
                t.outpatient                    = p.outpatient
        """)
        existing_rows = pd.read_sql(check_query, engine)
        
        if existing_rows.empty:
            return df_unique

        # Parse dates in existing_rows to match df_unique types (date objects)
        if "visit_date" in existing_rows.columns:
            existing_rows["visit_date"] = pd.to_datetime(existing_rows["visit_date"]).dt.date

        # Remove existing rows from our unique set
        # We do a left merge and keep only rows that didn't find a match
        merged = df_unique.merge(existing_rows, on=identity_cols, how='left', indicator=True)
        new_rows = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
        return new_rows

    finally:
        try:
            db.execute(text(f"DROP TABLE IF EXISTS {temp_table}"))
            db.commit()
        except:
            pass


def import_practitioner_csv(
    file_path: Path,
    file_record: ImportedFile,
    db: Session,
) -> int:
    """
    Import Practitioners Workload.csv in chunks with deduplication.
    Returns number of NEW rows inserted.
    """
    total_csv_rows = 0
    total_inserted = 0
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
            chunk_total = len(chunk)
            total_csv_rows += chunk_total

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

            # Compute Month column
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
            
            for col in ["emergency", "inpatient", "outpatient"]:
                if col in chunk.columns:
                    chunk[col] = chunk[col].fillna(0)

            # ── Deduplication ──────────────────────────────────────────────
            chunk = _filter_existing_rows(chunk, db)
            chunk_inserted = len(chunk)
            
            if chunk_inserted > 0:
                chunk["source_file_id"] = file_id
                from backend.models.practitioner_record import PractitionerRecord
                valid_cols = [c.name for c in PractitionerRecord.__table__.columns]
                chunk_to_save = chunk[[c for c in valid_cols if c in chunk.columns]]
                
                _to_sql_safe(chunk_to_save, "practitioner_records", engine)
                total_inserted += chunk_inserted

            # Log chunk
            log = ImportLog(
                file_id=file_id,
                chunk_number=chunk_num,
                rows_in_chunk=chunk_inserted,
                status="ok",
                message=f"Total in CSV chunk: {chunk_total}, Inserted: {chunk_inserted}"
            )
            db.add(log)
            
            # Update file record progress
            file_record.total_rows = total_csv_rows
            file_record.row_count = total_inserted
            db.commit()

        except Exception as exc:
            db.rollback()
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

    return total_inserted


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

            # Update file record progress
            file_record.total_rows = total_rows
            file_record.row_count = total_rows
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
