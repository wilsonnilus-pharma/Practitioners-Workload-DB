import sqlite3

DB = r"w:\01-03-2026\Dr. Heba\Practitioners Workload DB\PractitionersWorkloadDB.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print("Tables:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT COUNT(*) FROM practitioner_records")
print("Total rows in practitioner_records:", cur.fetchone()[0])

cur.execute("SELECT source_file_id, COUNT(*) FROM practitioner_records GROUP BY source_file_id ORDER BY source_file_id")
print("Rows per source_file_id:")
for r in cur.fetchall():
    print(f"  file_id={r[0]}: {r[1]:,}")

cur.execute("SELECT id, filename, import_status, row_count FROM imported_files ORDER BY id")
print("Imported files:")
for r in cur.fetchall():
    print(f"  id={r[0]}, file={r[1]}, status={r[2]}, rows={r[3]}")

# The CORRECT data should be file_id=2, and the row_count=338454 matches Power BI
# So 1,353,816 rows were inserted but only 338,454 are correct
# 1,353,816 / 338,454 = 4 -> the CSV was imported 4 times in one batch
print()
print("file_id=2 totals (all rows):")
cur.execute("SELECT SUM(emergency), SUM(inpatient), SUM(outpatient), COUNT(*), COUNT(DISTINCT practitioner_id) FROM practitioner_records WHERE source_file_id=2")
r = cur.fetchone()
print(f"  Emergency={r[0]:,} Inpatient={r[1]:,} Outpatient={r[2]:,} Rows={r[3]:,} UniqueID={r[4]:,}")

print()
print("Power BI correct values: Emergency=1,355,830 Inpatient=366 Outpatient=6,553,435 Cases=7,909,631")
print(f"Ratio (rows/correct): {1353816/338454:.2f}x")

conn.close()
