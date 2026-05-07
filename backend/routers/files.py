"""Files router — GET /files: list all imported files and their status."""

import os
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user, require_admin
from backend.models.file_registry import ImportedFile, ImportLog

router = APIRouter(tags=["files"])


@router.get("/files")
def list_files(
    status: str = Query(None, description="Filter by import_status"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """List all imported files with their import status."""
    query = db.query(ImportedFile)
    if status:
        query = query.filter(ImportedFile.import_status == status)
    files = query.order_by(ImportedFile.imported_at.desc()).all()
    return {"total": len(files), "files": [f.to_dict() for f in files]}


@router.delete("/files/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """Delete a file from the database along with its associated records."""
    file_record = db.query(ImportedFile).filter(ImportedFile.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from database 
    from backend.models.practitioner_record import PractitionerRecord
    
    db.query(PractitionerRecord).filter(PractitionerRecord.source_file_id == file_id).delete()
    db.query(ImportLog).filter(ImportLog.file_id == file_id).delete()
    db.delete(file_record)
    db.commit()
    
    # Try to delete the physical file if it exists
    try:
        if os.path.exists(file_record.file_path):
            os.remove(file_record.file_path)
    except Exception:
        pass
        
    return {"message": f"File '{file_record.filename}' deleted successfully"}
