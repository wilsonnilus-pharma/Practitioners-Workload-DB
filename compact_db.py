"""Compact the WAL into the main DB and VACUUM to reclaim space."""
import sqlite3

DB = r"w:\01-03-2026\Dr. Heba\Practitioners Workload DB\PractitionersWorkloadDB.db"
conn = sqlite3.connect(DB)
print("Running WAL checkpoint (TRUNCATE)...")
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("Running VACUUM...")
conn.execute("VACUUM")
conn.close()
print("Done. WAL compacted.")
