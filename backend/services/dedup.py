"""Deduplication helper — SHA-256 hash check against imported_files registry."""

import hashlib
from pathlib import Path
from sqlalchemy.orm import Session

from backend.models.file_registry import ImportedFile


def compute_sha256(file_path: Path, chunk_bytes: int = 8 * 1024 * 1024) -> str:
    """Stream-hash a file without loading it fully into memory."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            block = f.read(chunk_bytes)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def is_already_imported(db: Session, file_hash: str) -> bool:
    """Return True if a file with this hash was successfully imported before."""
    record = (
        db.query(ImportedFile)
        .filter(
            ImportedFile.file_hash == file_hash,
            ImportedFile.import_status == "success",
        )
        .first()
    )
    return record is not None


def register_pending(
    db: Session,
    file_path: Path,
    file_hash: str,
    import_source: str = "scan",
) -> ImportedFile:
    """
    Upsert a pending entry into imported_files and return it.

    If a prior attempt (status 'pending' or 'failed') already exists for this
    hash, reset it for a fresh import run instead of inserting a duplicate
    (which would violate the UNIQUE constraint on file_hash).
    """
    stem = file_path.stem.lower().replace(" ", "_").replace("-", "_")
    table_name = f"{stem}_records"

    # Check for an existing non-success record (failed or stuck pending)
    existing = (
        db.query(ImportedFile)
        .filter(ImportedFile.file_hash == file_hash)
        .first()
    )

    if existing is not None:
        from sqlalchemy import text
        # Delete any partially inserted rows from previous failed attempts
        if existing.table_name:
            try:
                db.execute(text(f"DELETE FROM {existing.table_name} WHERE source_file_id = :fid"), {"fid": existing.id})
                db.execute(text("DELETE FROM import_log WHERE file_id = :fid"), {"fid": existing.id})
            except Exception:
                pass

        # Reset the existing record for a fresh attempt
        existing.filename = file_path.name
        existing.file_path = str(file_path)
        existing.file_size_bytes = file_path.stat().st_size
        existing.table_name = table_name
        existing.import_source = import_source
        existing.import_status = "pending"
        existing.row_count = 0
        existing.error_message = None
        db.commit()
        db.refresh(existing)
        return existing

    record = ImportedFile(
        filename=file_path.name,
        file_path=str(file_path),
        file_hash=file_hash,
        file_size_bytes=file_path.stat().st_size,
        table_name=table_name,
        import_source=import_source,
        import_status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def mark_success(db: Session, record: ImportedFile, row_count: int):
    record.import_status = "success"
    record.row_count = row_count
    db.commit()


def mark_failed(db: Session, record: ImportedFile, error: str):
    record.import_status = "failed"
    record.error_message = str(error)[:2000]
    db.commit()
