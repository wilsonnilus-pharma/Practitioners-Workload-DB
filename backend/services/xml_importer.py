"""
XML importer — streaming parser using iterparse for memory-efficient processing.
Each XML file has its own schema; columns are discovered dynamically.
"""

from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.config import CSV_CHUNK_SIZE
from backend.models.file_registry import ImportLog, ImportedFile

SQLITE_MAX_VARS = 999


def _safe_sql_chunksize(num_cols: int) -> int:
    return max(1, SQLITE_MAX_VARS // num_cols)


def _sanitize_tag(tag: str) -> str:
    """Strip namespace and sanitize to a valid column name."""
    # Remove namespace like {http://...}TagName
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    return (
        tag.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "_")
    )


def import_xml(
    file_path: Path,
    file_record: ImportedFile,
    table_name: str,
    db: Session,
) -> int:
    """
    Stream-parse an XML file using iterparse.
    Discovers repeating record elements and inserts them in batches.
    Returns total rows inserted.
    """
    engine = db.get_bind()
    total_rows = 0
    chunk_num = 0
    batch: list[dict] = []

    # ── Discover repeating element name (first non-root child tag) ─────
    record_tag: str | None = None
    context = ET.iterparse(str(file_path), events=("start",))
    root_seen = False
    for _event, elem in context:
        if not root_seen:
            root_seen = True
            continue
        record_tag = _sanitize_tag(elem.tag)
        break
    del context

    if record_tag is None:
        raise ValueError("Cannot determine record element from XML structure")

    # ── Stream-parse all record elements ───────────────────────────────
    context = ET.iterparse(str(file_path), events=("end",))
    raw_tag_cache: dict[str, str] = {}

    for _event, elem in context:
        clean = _sanitize_tag(elem.tag)
        if clean != record_tag:
            continue

        # Build row from child elements
        row: dict[str, str | None] = {"source_file_id": file_record.id}
        for child in elem:
            raw = child.tag
            if raw not in raw_tag_cache:
                raw_tag_cache[raw] = _sanitize_tag(raw)
            col = raw_tag_cache[raw]
            row[col] = child.text

        batch.append(row)
        elem.clear()  # Free memory

        if len(batch) >= CSV_CHUNK_SIZE:
            _flush_batch(batch, table_name, engine, file_record, chunk_num, db)
            total_rows += len(batch)
            batch = []
            chunk_num += 1

    # Final batch
    if batch:
        _flush_batch(batch, table_name, engine, file_record, chunk_num, db)
        total_rows += len(batch)

    return total_rows


def _flush_batch(
    batch: list[dict],
    table_name: str,
    engine,
    file_record: ImportedFile,
    chunk_num: int,
    db: Session,
):
    """Insert a batch of rows into the target table, creating it if needed."""
    import pandas as pd

    df = pd.DataFrame(batch)

    try:
        df.to_sql(
            table_name,
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=_safe_sql_chunksize(len(df.columns)),
        )
        log = ImportLog(
            file_id=file_record.id,
            chunk_number=chunk_num,
            rows_in_chunk=len(batch),
            status="ok",
        )
        db.add(log)
        
        # Update file record progress
        # For XML, we don't have a separate total count yet, so we use current total
        current_total = (file_record.row_count or 0) + len(batch)
        file_record.row_count = current_total
        file_record.total_rows = current_total
        
        db.commit()
    except Exception as exc:
        log = ImportLog(
            file_id=file_record.id,
            chunk_number=chunk_num,
            rows_in_chunk=0,
            status="error",
            message=str(exc)[:500],
        )
        db.add(log)
        db.commit()
        raise
