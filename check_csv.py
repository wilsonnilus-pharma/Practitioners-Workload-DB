import pandas as pd

CSV = r"w:\01-03-2026\Dr. Heba\Practitioners Workload DB\csv_xml\Practitioners Workload.csv"

# Read just the first few rows to see structure
df_head = pd.read_csv(CSV, nrows=5, dtype=str, encoding="utf-8-sig")
print("Columns:", list(df_head.columns))
print("First 5 rows:")
print(df_head.to_string())

# Count total rows
total = sum(1 for _ in open(CSV, encoding="utf-8-sig")) - 1  # subtract header
print(f"\nTotal rows in CSV: {total:,}")

# Quick scan for duplicate rows - check first 1000 rows
df_sample = pd.read_csv(CSV, nrows=10000, dtype=str, encoding="utf-8-sig")
dups = df_sample.duplicated().sum()
print(f"Duplicates in first 10,000 rows: {dups}")

# Check if row 338454 and row 338455 are the same (wrapping point)
df_wrap = pd.read_csv(CSV, skiprows=range(1, 338450), nrows=10, dtype=str, encoding="utf-8-sig")
print(f"\nRows around the 338454 mark (if 4x duplication):")
print(df_wrap.to_string())
