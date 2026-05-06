"""
FastAPI application entry point.
Registers all routers, initializes DB, creates default admin on first run.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db, SessionLocal
from backend.auth import create_default_admin
from backend.routers import auth, scan, upload, data, export, files

app = FastAPI(
    title="Practitioners Workload DB API",
    description="Medical appointment dashboard backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Streamlit dev server) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()


# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(scan.router)
app.include_router(upload.router)
app.include_router(data.router)
app.include_router(export.router)
app.include_router(files.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": "Practitioners Workload DB"}
