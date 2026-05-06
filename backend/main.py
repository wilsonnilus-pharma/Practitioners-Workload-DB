"""
FastAPI application entry point.
Registers all routers, initializes DB, creates default admin on first run.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.database import init_db, SessionLocal
from backend.auth import create_default_admin
from backend.routers import auth, scan, upload, data, export, files

app = FastAPI(
    title="Practitioners Workload DB API",
    description="Medical dashboard backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (Updated for Cloud Deployment) ───────────────────────────────────
# We allow "*" (all) for origins in production to ensure the Streamlit 
# cloud URL can always communicate with the FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ────────────────────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    # Ensure the database is initialized in the current cloud directory
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
