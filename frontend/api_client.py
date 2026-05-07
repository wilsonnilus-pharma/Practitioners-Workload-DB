"""
API client — thin wrapper around FastAPI calls.
Used by all Streamlit pages.
"""

import os
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


import threading
local_data = threading.local()

def _headers() -> dict:
    try:
        token = st.session_state.get("token", "")
    except Exception:
        token = ""
    
    if not token:
        token = getattr(local_data, "token", "")
        
    return {"Authorization": f"Bearer {token}"} if token else {}


def _get(path: str, params: dict = None, stream: bool = False):
    return requests.get(f"{API_BASE}{path}", headers=_headers(), params=params, stream=stream, timeout=60)


def _post(path: str, data: dict = None, files: dict = None, json_data: dict = None):
    return requests.post(
        f"{API_BASE}{path}",
        headers=_headers() if files else {**_headers(), "Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        files=files,
        json=json_data,
        timeout=120,
    )


# ── Auth ───────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> dict | None:
    r = requests.post(
        f"{API_BASE}/login",
        data={"username": username, "password": password},
        timeout=10,
    )
    if r.status_code == 200:
        return r.json()
    return None


def get_me() -> dict | None:
    r = _get("/me")
    return r.json() if r.status_code == 200 else None


# ── Import ─────────────────────────────────────────────────────────────────

def trigger_scan() -> dict:
    r = _post("/scan-folder")
    return r.json() if r.ok else {"error": r.text}


def get_scan_status() -> dict:
    r = _get("/scan-status")
    return r.json() if r.ok else {}


def upload_file(filename: str, file_bytes: bytes) -> dict:
    files = {"file": (filename, file_bytes)}
    r = requests.post(
        f"{API_BASE}/upload",
        headers=_headers(),
        files=files,
        timeout=300,
    )
    return r.json() if r.ok else {"error": r.text}


# ── Data ───────────────────────────────────────────────────────────────────

def get_data(page: int = 1, page_size: int = 100, filters: dict = None) -> dict:
    params = {"page": page, "page_size": page_size, **(filters or {})}
    r = _get("/data", params=params)
    return r.json() if r.ok else {"total": 0, "data": [], "error": r.text}


def get_summary(filters: dict = None, group_by: str = "practitioner_name", include_kpi: bool = True, include_breakdown: bool = True, include_top_facs: bool = True) -> dict:
    params = {"group_by": group_by, "include_kpi": include_kpi, "include_breakdown": include_breakdown, "include_top_facs": include_top_facs, **(filters or {})}
    r = _get("/summary", params=params)
    return r.json() if r.ok else {"kpi": {}, "pivot": []}


def get_filter_options(column: str) -> list[str]:
    """Return all distinct values for a column (no cascading)."""
    r = _get("/filters/options", params={"column": column})
    if r.ok:
        return r.json().get("values", [])
    return []


def get_filter_options_cascaded(column: str, active_filters: dict) -> list[str]:
    """Return distinct values for a column scoped by ALL currently active filters.
    Enables full bidirectional cascading across all filter dimensions.
    """
    params = {"column": column}
    for key in ("region", "facility_name", "speciality", "practitioner_id", "date_from", "date_to"):
        val = active_filters.get(key)
        if val:
            params[key] = val
    r = _get("/filters/options", params=params)
    if r.ok:
        return r.json().get("values", [])
    return []


def get_date_range() -> dict:
    """Return the min and max dates from the backend."""
    r = _get("/filters/date-range")
    if r.ok:
        return r.json()
    return {"min": None, "max": None}


def get_row_range() -> dict:
    """Return the total record count from the backend."""
    r = _get("/filters/row-range")
    if r.ok:
        return r.json()
    return {"total": 0}


@st.cache_data(ttl=600, show_spinner=False)
def export_csv(filters: dict = None) -> bytes | None:
    # Use a separate local_data for threading safety if needed, 
    # but here we are in main thread usually.
    r = _get("/export", params=filters or {}, stream=True)
    if r.ok:
        return b"".join(r.iter_content(chunk_size=8192))
    return None


# ── Files ──────────────────────────────────────────────────────────────────

def get_files(status: str = None) -> dict:
    params = {"status": status} if status else {}
    r = _get("/files", params=params)
    return r.json() if r.ok else {"total": 0, "files": []}

def delete_api_file(file_id: int) -> dict:
    import requests
    from frontend.api_client import API_BASE, _headers
    r = requests.delete(f"{API_BASE}/files/{file_id}", headers=_headers(), timeout=30)
    return r.json() if r.ok else {"error": r.text}
