"""
SQLAlchemy engine, session factory, and base model.
Uses SQLite with WAL mode for concurrent reads.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import DATABASE_URL, DATABASE_PATH


# ── Engine ─────────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,  # Required for SQLite + FastAPI threads
        "timeout": 60,               # 60s lock timeout for heavy queries
    },
    pool_pre_ping=True,
    pool_size=10,                    # More concurrent readers
    max_overflow=20,
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """Enable WAL mode and performance pragmas on every new connection.
    Tuned for 350k–1M rows of analytical queries.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-262144")   # 256 MB page cache (was 64 MB)
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=1073741824") # 1 GB mmap  (was 256 MB)
    cursor.execute("PRAGMA wal_autocheckpoint=1000")  # checkpoint less often → faster writes
    cursor.execute("PRAGMA optimize")             # let SQLite pick best query plan
    cursor.close()


# ── Session factory ────────────────────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Declarative base ───────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency for FastAPI routes ──────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup and apply lightweight migrations."""
    # Import models so their metadata is registered before create_all
    from backend.models import user, file_registry, practitioner_record  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Apply incremental schema changes that SQLAlchemy create_all won't handle."""
    with engine.connect() as conn:
        # ── Add `month` column if it was added after initial deploy ──────────
        existing = [row[1] for row in conn.execute(text("PRAGMA table_info(practitioner_records)")).fetchall()]
        if "month" not in existing:
            conn.execute(text("ALTER TABLE practitioner_records ADD COLUMN month TEXT"))
            conn.commit()
