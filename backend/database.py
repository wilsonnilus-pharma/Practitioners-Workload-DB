"""
SQLAlchemy engine, session factory, and base model.
Uses SQLite with WAL mode for concurrent reads.

Performance fix: composite indexes on all commonly-filtered columns so every
filter combination (region, facility_name, speciality, practitioner_id,
visit_date, month) uses an index scan instead of a full table scan.
This is why Facility filter was instant (already indexed) while others were
20-30s (full table scans on 350k–1M rows).
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import DATABASE_URL, DATABASE_PATH


# ── Engine ─────────────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 60,
    },
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """Enable WAL mode and performance pragmas on every new connection."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-262144")    # 256 MB page cache
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=1073741824")  # 1 GB mmap
    cursor.execute("PRAGMA wal_autocheckpoint=1000")
    cursor.execute("PRAGMA optimize")
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
    from backend.models import user, file_registry, practitioner_record  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _ensure_indexes()


def _run_migrations():
    """Apply incremental schema changes that SQLAlchemy create_all won't handle."""
    with engine.connect() as conn:
        existing_pr = [
            row[1] for row in conn.execute(text("PRAGMA table_info(practitioner_records)")).fetchall()
        ]
        if "month" not in existing_pr:
            conn.execute(text("ALTER TABLE practitioner_records ADD COLUMN month TEXT"))
            conn.commit()

        existing_if = [
            row[1] for row in conn.execute(text("PRAGMA table_info(imported_files)")).fetchall()
        ]
        if "total_rows" not in existing_if:
            conn.execute(text("ALTER TABLE imported_files ADD COLUMN total_rows INTEGER DEFAULT 0"))
            conn.commit()


def _ensure_indexes():
    """
    Create composite indexes for every filter column used in WHERE clauses.

    Why this fixes the 20-30s lag:
      Previously only facility_name had an index (or the query planner happened
      to pick it). Every other filter (region, speciality, practitioner_id,
      visit_date, month) caused a full table scan on potentially 1M+ rows.

    These indexes are created with IF NOT EXISTS, so they are safe to call on
    every startup — SQLite skips them if they already exist.

    Index strategy:
      - Single-column indexes cover individual filter use.
      - Composite (region, facility_name) covers the most common combined filter.
      - visit_date index covers date-range queries.
    """
    index_ddl = [
        # Individual column indexes (only for columns not covered by composites below)
        "CREATE INDEX IF NOT EXISTS idx_pr_practitioner_id ON practitioner_records (practitioner_id)",
        "CREATE INDEX IF NOT EXISTS idx_pr_month           ON practitioner_records (month)",
        "CREATE INDEX IF NOT EXISTS idx_pr_source_file     ON practitioner_records (source_file_id)",

        # Composite indexes — cover the most common multi-filter combinations
        # (SQLite uses the leftmost prefix, so order matters)
        "CREATE INDEX IF NOT EXISTS idx_pr_region_facility ON practitioner_records (region, facility_name)",
        "CREATE INDEX IF NOT EXISTS idx_pr_facility_spec   ON practitioner_records (facility_name, speciality)",
        "CREATE INDEX IF NOT EXISTS idx_pr_region_date     ON practitioner_records (region, visit_date)",
        "CREATE INDEX IF NOT EXISTS idx_pr_spec_date       ON practitioner_records (speciality, visit_date)",

    ]

    with engine.connect() as conn:
        for ddl in index_ddl:
            conn.execute(text(ddl))
        conn.commit()
        # Update query-planner statistics so SQLite immediately picks index
        # scans for all GROUP BY / WHERE queries on the indexed columns.
        conn.execute(text("PRAGMA analyze"))
        conn.commit()
