"""
Fix script:
1. Delete ALL rows from practitioner_records
2. Delete all imported_files entries for Practitioners Workload.csv (ids 2,3,4)
3. Leave Doctor.csv (id=1) and doctor_records untouched
4. Reset the DB so the CSV can be re-imported cleanly (once)
"""
import sqlite3

DB = r"w:\01-03-2026\Dr. Heba\Practitioners Workload DB\PractitionersWorkloadDB.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

print("BEFORE cleanup:")
cur.execute("SELECT COUNT(*) FROM practitioner_records")
print(f"  practitioner_records rows: {cur.fetchone()[0]:,}")
cur.execute("SELECT id, filename, import_status, row_count FROM imported_files")
for r in cur.fetchall():
    print(f"  imported_files: id={r[0]}, file={r[1]}, status={r[2]}, rows={r[3]}")

print("\nCleaning up...")

# 1. Delete all practitioner_records
cur.execute("DELETE FROM practitioner_records")
deleted = cur.rowcount
print(f"  Deleted {deleted:,} rows from practitioner_records")

# 2. Delete imported_files entries for Practitioners Workload.csv (file_ids 2,3,4)
cur.execute("DELETE FROM imported_files WHERE id IN (2, 3, 4)")
print(f"  Deleted {cur.rowcount} entries from imported_files (Practitioners Workload.csv)")

# 3. Also clean import_log entries for those files
cur.execute("DELETE FROM import_log WHERE file_id IN (2, 3, 4)")
print(f"  Deleted {cur.rowcount} entries from import_log")

conn.commit()

print("\nAFTER cleanup:")
cur.execute("SELECT COUNT(*) FROM practitioner_records")
print(f"  practitioner_records rows: {cur.fetchone()[0]:,}")
cur.execute("SELECT id, filename, import_status, row_count FROM imported_files")
for r in cur.fetchall():
    print(f"  imported_files: id={r[0]}, file={r[1]}, status={r[2]}, rows={r[3]}")

conn.close()
print("\nDone. Now re-import via Scan & Import in the dashboard.")
print("The CSV will be imported ONCE cleanly, giving correct totals.")
