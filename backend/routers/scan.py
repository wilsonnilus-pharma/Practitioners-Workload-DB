"""Scan router — POST /scan-folder and GET /scan-status.

IMPORTANT: The background task creates its own DB session via SessionLocal.
Do NOT pass the request-scoped `db` session to a BackgroundTask — FastAPI
closes that session when the HTTP response is sent, which caused the importer
to silently reconnect and re-run the entire import multiple times (4× rows).
"""

from fastapi import APIRouter, BackgroundTasks, Depends

from backend.database import SessionLocal
from backend.auth import require_admin, get_current_user
from backend.services.scanner import scan_and_import, get_progress

router = APIRouter(tags=["import"])


@router.post("/scan-folder")
def trigger_scan(
    background_tasks: BackgroundTasks,
    _=Depends(require_admin),
):
    """Trigger folder scan in the background. Returns immediately."""
    from backend.services.scanner import _import_progress
    
    if _import_progress.get("running"):
        return {"message": "A scan is already running. Please wait."}
        
    # Set it synchronously before the background task starts to prevent race conditions
    _import_progress["running"] = True
    background_tasks.add_task(_run_scan_bg)
    return {"message": "Folder scan started in background. Poll /scan-status for progress."}


def _run_scan_bg():
    """Background task with its own dedicated DB session (not request-scoped)."""
    db = SessionLocal()
    try:
        scan_and_import(db, source="scan")
    finally:
        db.close()


@router.get("/scan-status")
def scan_status(_=Depends(get_current_user)):
    """Poll current import progress."""
    return get_progress()
