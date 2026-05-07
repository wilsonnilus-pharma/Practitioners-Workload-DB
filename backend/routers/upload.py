"""Upload router — POST /upload: receive file, save to csv_xml/, import immediately."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.database import get_db, SessionLocal
from backend.auth import require_admin
from backend.config import CSV_XML_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_MB
from backend.services.scanner import import_single_file, get_progress

router = APIRouter(tags=["import"])


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _=Depends(require_admin),
):
    """Upload a CSV or XML file, save it to csv_xml/, and trigger import."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Stream to disk — do NOT load full file into RAM
    CSV_XML_DIR.mkdir(parents=True, exist_ok=True)
    dest = CSV_XML_DIR / file.filename

    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    total = 0

    with open(dest, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)  # 1 MB at a time
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {MAX_UPLOAD_SIZE_MB} MB limit",
                )
            out.write(chunk)

    # Background task creates its OWN session — do NOT pass the request-scoped
    # session which FastAPI closes when the response is sent.
    background_tasks.add_task(_import_uploaded_bg, dest)

    return {
        "message": f"File '{file.filename}' uploaded ({total / 1024:.1f} KB). Import started.",
        "filename": file.filename,
        "size_bytes": total,
    }


def _import_uploaded_bg(file_path: Path):
    """Background import with its own dedicated DB session."""
    db = SessionLocal()
    try:
        import_single_file(file_path, db, source="upload")
    finally:
        db.close()
