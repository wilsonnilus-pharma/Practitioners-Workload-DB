"""
FastAPI application entry point.
Registers all routers, initializes DB, creates default admin on first run.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from backend.database import init_db, SessionLocal
from backend.auth import create_default_admin
from backend.routers import auth, scan, upload, data, export, files

# ── Startup & Shutdown (Modern Lifespan Method) ───────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing Database...")
    init_db()
    db = SessionLocal()
    try:
        create_default_admin(db)
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        db.close()
    
    yield 

app = FastAPI(
    title="Practitioners Workload DB API",
    description="Medical dashboard backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS (Updated for Cloud Deployment) ───────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
