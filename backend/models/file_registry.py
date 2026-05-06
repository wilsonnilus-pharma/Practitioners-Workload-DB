"""SQLAlchemy model for the imported_files registry and import_log tables."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, BigInteger
from backend.database import Base


class ImportedFile(Base):
    __tablename__ = "imported_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False, index=True)
    file_size_bytes = Column(BigInteger, default=0)
    row_count = Column(Integer, default=0)
    table_name = Column(String, nullable=True)        # target DB table
    import_source = Column(String, default="scan")    # "scan" | "upload"
    import_status = Column(String, default="pending") # "pending"|"success"|"failed"
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error_message = Column(String, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_size_bytes": self.file_size_bytes,
            "row_count": self.row_count,
            "table_name": self.table_name,
            "import_source": self.import_source,
            "import_status": self.import_status,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
            "error_message": self.error_message,
        }


class ImportLog(Base):
    __tablename__ = "import_log"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, nullable=False, index=True)
    chunk_number = Column(Integer, default=0)
    rows_in_chunk = Column(Integer, default=0)
    status = Column(String, default="ok")    # "ok" | "error"
    message = Column(String, nullable=True)
    logged_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
