"""
Scanner orchestrator — ties together dedup + CSV/XML importers.
Used by both POST /scan-folder and POST /upload flows.

Fix: calls invalidate_summary_cache() after a successful import so stale
cached aggregations are cleared and the dashboard shows fresh data.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.config import CSV_XML_DIR, ALLOWED_EXTENSIONS
from backend.services.dedup import (
    compute_sha256,
    is_already_imported,
    mark_failed,
    mark_success,
    register_pending,
)
from backend.services.csv_importer import import_practitioner_csv, import_generic_csv
from backend.services.xml_importer import import_xml
from backend.services.aggregator import invalidate_summary_cache


# Shared progress store (single-process use; replace with Redis for multi-worker)
_import_progress: dict[str, Any] = {}


def get_progress() -> dict:
    return dict(_import_progress)


def _reset_progress(filenames: list[str]):
    _import_progress.clear()
    _import_progress.update(
        {
            "total_files": len(filenames),
            "processed": 0,
            "current_file": None,
            "results": [],
            "running": True,
        }
    )


def _is_doctor_file(path: Path) -> bool:
    return "practitioner" in path.stem.lower()


def import_single_file(
    file_path: Path,
    db: Session,
    source: str = "scan",
) -> dict:
    """
    Import one file through the full pipeline.
    Returns a result dict with status and row_count.
    """
    result = {"filename": file_path.name, "status": "skipped", "rows": 0, "error": None}

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        result["error"] = f"Extension {file_path.suffix!r} not supported"
        return result

    try:
        file_hash = compute_sha256(file_path)

        if is_already_imported(db, file_hash):
            result["status"] = "skipped"
            result["error"] = "Already imported (same hash)"
            return result

        file_record = register_pending(db, file_path, file_hash, import_source=source)
        suffix = file_path.suffix.lower()

        try:
            if suffix == ".csv":
                if _is_doctor_file(file_path):
                    rows = import_practitioner_csv(file_path, file_record, db)
                else:
                    rows = import_generic_csv(
                        file_path, file_record, file_record.table_name, db
                    )
            else:  # .xml
                rows = import_xml(
                    file_path, file_record, file_record.table_name, db
                )

            try:
                mark_success(db, file_record, rows)
            except Exception:
                pass

            # Invalidate aggregation cache so dashboard shows fresh data
            invalidate_summary_cache()

            result["status"] = "success"
            result["rows"] = rows

        except Exception as inner_exc:
            try:
                mark_failed(db, file_record, str(inner_exc))
            except Exception:
                pass
            result["status"] = "failed"
            result["error"] = str(inner_exc)

    except Exception as outer_exc:
        result["status"] = "failed"
        result["error"] = str(outer_exc)

    return result


def scan_and_import(db: Session, source: str = "scan") -> dict:
    """
    Scan csv_xml/ folder and import any new files.
    Returns summary of all results.
    """
    CSV_XML_DIR.mkdir(parents=True, exist_ok=True)
    files = [
        p for p in CSV_XML_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS
    ]

    _reset_progress([f.name for f in files])
    results = []

    for i, file_path in enumerate(files):
        _import_progress["current_file"] = file_path.name
        result = import_single_file(file_path, db, source=source)
        results.append(result)
        _import_progress["processed"] = i + 1
        _import_progress["results"] = results

    _import_progress["running"] = False
    _import_progress["current_file"] = None

    return {
        "total": len(files),
        "success": sum(1 for r in results if r["status"] == "success"),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "failed":  sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }
