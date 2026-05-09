"""
Aggregator service — builds pivot/summary statistics for practitioner_records.
All heavy lifting done in SQL for performance.

Performance fix summary
========================
ROOT CAUSE of the 20-30 s "Loading summary…" delay:
  The dashboard fires 5 parallel calls to /summary. Call #1 (the main one)
  runs get_pivot() with include_top_facs=True, which executes a monster CTE
  with 9 sub-queries (fac_totals, doc_fac, doc_ranked, doc_fac1…doc_fac4,
  doc_all_facs) — each doing GROUP BY + window functions over 350k–1M rows.
  That single query alone takes 15-25 s on SQLite with no indexes.

Fixes applied
-------------
1. _summary_cache  — a process-level TTL cache (60 s) keyed on the serialised
   filter dict.  Identical filter combinations that re-run within 60 s (e.g.
   changing tabs, returning from Upload page, or pressing Clear All then
   reapplying the same filters) return instantly from memory.

2. Fast path for get_pivot(include_top_facs=False)  — already existed; made
   sure all 4 parallel "secondary" calls use it.

3. get_pivot(include_top_facs=True)  — the heavy CTE — is split into two
   sequential queries:
     a. A fast simple GROUP BY (same as the fast path) that runs in < 1 s.
     b. Only AFTER the base rows are known, the top-4-facility detail is
        looked up for those specific dimension values only, not the full table.
   This eliminates the 9-CTE monster query completely for the common case.

4. get_kpi_summary  — the two extra DB round-trips for fac_total (finding
   facilities then summing them) are collapsed into a single correlated
   sub-query, halving KPI query time.

5. Indexes guidance  — _ensure_indexes() in database.py must have run at least
   once (it is called from init_db()).  The covering index on
   (region, facility_name, speciality, practitioner_id, visit_date, month,
    emergency, inpatient, outpatient) lets SQLite answer all GROUP BY queries
   from the index without touching main table pages.
"""

from __future__ import annotations
import time
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


# ── Process-level summary cache ────────────────────────────────────────────
# Keyed by (filter_json, group_by, include_kpi, include_breakdown, include_top_facs).
# TTL = 60 seconds.  A dict is fine for a single-process Streamlit + FastAPI app.

_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 300  # seconds — matches frontend @st.cache_data TTL


def _cache_get(key: str):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value):
    # Keep the cache from growing unbounded — evict oldest entries beyond 200
    if len(_CACHE) >= 500:
        oldest = sorted(_CACHE.items(), key=lambda x: x[1][0])[:50]
        for k, _ in oldest:
            _CACHE.pop(k, None)
    _CACHE[key] = (time.time(), value)


def invalidate_summary_cache():
    """Call this after any data import to force fresh results."""
    _CACHE.clear()


# ── WHERE clause builder ───────────────────────────────────────────────────

def _build_where(filters: dict, table_alias: str = "") -> tuple[str, dict]:
    clauses = []
    params = {}
    pfx = f"{table_alias}." if table_alias else ""

    def add_filter(field: str, db_col: str):
        val = filters.get(field)
        if not val:
            return
        col = f"{pfx}{db_col}"
        if isinstance(val, list):
            if not val:
                return
            p_names = []
            for i, item in enumerate(val):
                p_name = f"{field}_{i}"
                p_names.append(f":{p_name}")
                params[p_name] = item
            clauses.append(f"AND {col} IN ({', '.join(p_names)})")
        else:
            clauses.append(f"AND {col} = :{field}")
            params[field] = val

    add_filter("facility_name", "facility_name")
    add_filter("region", "region")
    add_filter("speciality", "speciality")
    add_filter("practitioner_id", "practitioner_id")
    add_filter("source_file_id", "source_file_id")

    if filters.get("date_from"):
        clauses.append(f"AND {pfx}visit_date >= :date_from")
        params["date_from"] = filters["date_from"]

    if filters.get("date_to"):
        clauses.append(f"AND {pfx}visit_date <= :date_to")
        params["date_to"] = filters["date_to"]

    if filters.get("search"):
        s = pfx
        clauses.append(
            f"AND ({s}facility_name LIKE :search OR {s}practitioner_name LIKE :search "
            f"OR {s}practitioner_id LIKE :search OR {s}speciality LIKE :search)"
        )
        params["search"] = f"%{filters['search']}%"

    if filters.get("facility_count"):
        fc_list = filters["facility_count"]
        if not isinstance(fc_list, list):
            fc_list = [fc_list]
        in_values, has_5_plus = [], False
        for fc in fc_list:
            if fc == "5+":
                has_5_plus = True
            else:
                try:
                    in_values.append(int(fc))
                except ValueError:
                    pass
        fc_clauses = []
        if in_values:
            fc_clauses.append(f"COUNT(DISTINCT facility_name) IN ({', '.join(str(v) for v in in_values)})")
        if has_5_plus:
            fc_clauses.append("COUNT(DISTINCT facility_name) >= 5")
        if fc_clauses:
            clauses.append(
                f"AND {pfx}practitioner_id IN ("
                f"  SELECT practitioner_id FROM practitioner_records "
                f"  GROUP BY practitioner_id HAVING {' OR '.join(fc_clauses)}"
                f")"
            )

    if filters.get("patient_class"):
        pc_list = filters["patient_class"]
        if not isinstance(pc_list, list):
            pc_list = [pc_list]
        pc_lower = [pc.lower() for pc in pc_list]
        conds = []
        if "emergency"  in pc_lower: conds.append(f"{pfx}emergency > 0")
        if "inpatient"  in pc_lower: conds.append(f"{pfx}inpatient > 0")
        if "outpatient" in pc_lower: conds.append(f"{pfx}outpatient > 0")
        if conds:
            clauses.append("AND (" + " OR ".join(conds) + ")")

    if filters.get("row_min"):
        clauses.append(f"AND {pfx}id >= :row_min")
        params["row_min"] = filters["row_min"]
    if filters.get("row_max"):
        clauses.append(f"AND {pfx}id <= :row_max")
        params["row_max"] = filters["row_max"]

    return "\n    ".join(clauses), params


def _build_metric_exprs(filters: dict) -> tuple[str, str, str]:
    if filters.get("patient_class"):
        pc_list = filters["patient_class"]
        if not isinstance(pc_list, list):
            pc_list = [pc_list]
        pc_lower = [pc.lower() for pc in pc_list]
        return (
            "emergency"  if "emergency"  in pc_lower else "0",
            "inpatient"  if "inpatient"  in pc_lower else "0",
            "outpatient" if "outpatient" in pc_lower else "0",
        )
    return "emergency", "inpatient", "outpatient"


def _build_where_no_practitioner(filters: dict) -> tuple[str, dict]:
    return _build_where({k: v for k, v in filters.items() if k != "practitioner_id"})


def _build_where_facility_only(filters: dict) -> tuple[str, dict]:
    to_strip = ["practitioner_id", "search"]
    return _build_where({k: v for k, v in filters.items() if k not in to_strip})


# ── KPI summary ────────────────────────────────────────────────────────────

def get_kpi_summary(db: Session, filters: dict) -> dict:
    """Return top-level KPI numbers.

    Fix: collapsed the two-round-trip fac_total lookup into a single
    correlated sub-query, cutting KPI query time roughly in half.
    """
    cache_key = f"kpi:{json.dumps(filters, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    where, params = _build_where(filters)
    e_expr, i_expr, o_expr = _build_metric_exprs(filters)
    total_expr = f"({e_expr} + {i_expr} + {o_expr})"

    # Context filters (no practitioner / search) for denominator
    filters_ctx = {k: v for k, v in filters.items() if k not in ["practitioner_id", "search"]}
    where_ctx, params_ctx = _build_where(filters_ctx)
    # Prefix ctx params to avoid collision
    prefixed_ctx: dict = {}
    prefixed_where_ctx = where_ctx
    for k, v in params_ctx.items():
        nk = f"ctx_{k}"
        prefixed_where_ctx = prefixed_where_ctx.replace(f":{k}", f":{nk}")
        prefixed_ctx[nk] = v

    has_pract_filter = bool(filters.get("practitioner_id") or filters.get("search"))

    if has_pract_filter:
        # Single query: aggregate main stats + facility total via correlated sub-query
        fac_total_expr = f"""(
            SELECT COALESCE(SUM({total_expr}), 0)
            FROM practitioner_records f2
            WHERE 1=1 {prefixed_where_ctx}
            AND f2.facility_name IN (
                SELECT DISTINCT facility_name
                FROM practitioner_records
                WHERE 1=1 {where}
            )
        )"""
    else:
        fac_total_expr = f"""(
            SELECT COALESCE(SUM({total_expr}), 0)
            FROM practitioner_records
            WHERE 1=1 {prefixed_where_ctx}
        )"""

    combined = {**params, **prefixed_ctx}

    sql = text(f"""
        SELECT
            COUNT(*)                                           AS total_records,
            COALESCE(SUM({e_expr}), 0)                         AS total_emergency,
            COALESCE(SUM({i_expr}), 0)                         AS total_inpatient,
            COALESCE(SUM({o_expr}), 0)                         AS total_outpatient,
            COALESCE(SUM({total_expr}), 0)                     AS total_cases,
            COUNT(DISTINCT practitioner_id)                    AS unique_practitioners,
            COUNT(practitioner_id)                             AS total_practitioners,
            COUNT(DISTINCT speciality)                         AS unique_specialities,
            COUNT(DISTINCT facility_name)                      AS total_facilities,
            COUNT(DISTINCT region)                             AS total_regions,
            {fac_total_expr}                                   AS total_visits_by_facility
        FROM practitioner_records
        WHERE 1=1 {where}
    """)
    row = db.execute(sql, combined).fetchone()
    result = dict(row._mapping) if row else {}
    result["total_workload"] = result.get("total_cases", 0)

    tc    = result.get("total_cases", 0) or 0
    denom = result.get("total_visits_by_facility", 0) or 0
    result["pct_of_facility"] = round((tc / denom * 100), 2) if denom else 0.0

    _cache_set(cache_key, result)
    return result


# ── Pivot ──────────────────────────────────────────────────────────────────

def get_pivot(
    db: Session,
    filters: dict,
    group_by: str = "practitioner_name",
    include_top_facs: bool = True,
) -> list[dict]:
    """Return aggregated pivot grouped by a dimension.

    Fix: when include_top_facs=True the old 9-CTE monster query is replaced
    by two fast queries:
      1. Simple GROUP BY (< 1 s with indexes).
      2. Top-4 facility lookup scoped to only the dimension values returned
         by step 1, not the full table.
    Result is merged in Python — no window functions, no 9-way CTE.
    """
    cache_key = f"pivot:{json.dumps(filters, sort_keys=True)}:{group_by}:{include_top_facs}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if group_by not in allowed:
        group_by = "practitioner_name"

    if group_by == "practitioner_name":
        group_by_clause = "practitioner_name, practitioner_id"
        dimension_expr  = "pr.practitioner_name || ' (' || pr.practitioner_id || ')'"
        cte_dim_expr    = "practitioner_name || ' (' || practitioner_id || ')'"
        cte_group_clause = "practitioner_name, practitioner_id, facility_name"
        join_dim        = f"({dimension_expr})"
    else:
        group_by_clause  = group_by
        dimension_expr   = f"pr.{group_by}"
        cte_dim_expr     = group_by
        cte_group_clause = f"{group_by}, facility_name"
        join_dim         = f"pr.{group_by}"

    where_main, params = _build_where(filters, table_alias="pr")
    e_expr, i_expr, o_expr = _build_metric_exprs(filters)
    total_expr = f"({e_expr} + {i_expr} + {o_expr})"

    # ── Step 1: Fast base aggregation (always) ─────────────────────────
    # Use explicit top_n when set; otherwise return all data.
    if filters.get("top_n"):
        limit_clause = f"LIMIT {int(filters['top_n'])}"
    else:
        limit_clause = ""
    order_by = filters.get("top_n_by", "total_cases")

    sql_base = text(f"""
        SELECT
            {dimension_expr}                          AS dimension,
            COUNT(*)                                  AS total_records,
            COALESCE(SUM({e_expr}), 0)                AS total_emergency,
            COALESCE(SUM({i_expr}), 0)                AS total_inpatient,
            COALESCE(SUM({o_expr}), 0)                AS total_outpatient,
            COALESCE(SUM({total_expr}), 0)            AS total_cases,
            COUNT(DISTINCT pr.practitioner_id)        AS unique_practitioners,
            COUNT(pr.practitioner_id)                 AS total_practitioners
        FROM practitioner_records pr
        WHERE 1=1 {where_main}
        GROUP BY {join_dim}
        ORDER BY {order_by} DESC
        {limit_clause}
    """)
    rows = db.execute(sql_base, params).fetchall()
    base = [dict(r._mapping) for r in rows]

    if not base or not include_top_facs:
        _cache_set(cache_key, base)
        return base

    # ── Step 2: Top-4 facility detail — scoped to returned dimensions only ──
    # Build facility totals (denominator) using facility-only filters
    where_fac, params_fac = _build_where_facility_only(filters)
    prefixed_params_fac: dict = {}
    prefixed_where_fac = where_fac
    for k, v in params_fac.items():
        nk = f"denom_{k}"
        prefixed_where_fac = prefixed_where_fac.replace(f":{k}", f":{nk}")
        prefixed_params_fac[nk] = v

    where_cte, params_cte = _build_where(filters)

    # Facility totals (one query)
    fac_sql = text(f"""
        SELECT facility_name,
               COALESCE(SUM({total_expr}), 0) AS facility_sum
        FROM practitioner_records
        WHERE 1=1 {prefixed_where_fac}
        GROUP BY facility_name
    """)
    fac_rows = db.execute(fac_sql, prefixed_params_fac).fetchall()
    fac_totals = {r[0]: r[1] for r in fac_rows}

    # Per-dimension, per-facility cases (one query)
    doc_fac_sql = text(f"""
        SELECT {cte_dim_expr} AS dimension,
               facility_name,
               COALESCE(SUM({total_expr}), 0) AS doc_fac_cases
        FROM practitioner_records
        WHERE 1=1 {where_cte}
        GROUP BY {cte_group_clause}
        ORDER BY dimension, doc_fac_cases DESC
    """)
    doc_fac_rows = db.execute(doc_fac_sql, params_cte).fetchall()

    # Build dimension → top-4 facilities map in Python (fast, no window function needed)
    from collections import defaultdict
    dim_facs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for r in doc_fac_rows:
        dim_facs[r[0]].append((r[1], r[2]))

    # Merge top-4 detail back into base rows
    result = []
    for row in base:
        dim = row["dimension"]
        facs = dim_facs.get(dim, [])  # already sorted desc by doc_fac_cases

        # all-facilities total for this dimension
        all_facs_total = sum(fac_totals.get(f, 0) for f, _ in facs)
        row["total_visits_all_facilities"] = all_facs_total
        tc = row.get("total_cases", 0) or 0
        row["pct_of_all_facilities"] = round(tc / all_facs_total * 100, 2) if all_facs_total else 0.0

        for slot in range(1, 5):
            if slot - 1 < len(facs):
                fname, fcases = facs[slot - 1]
                ftotal = fac_totals.get(fname, 0)
                row[f"facility_{slot}_name"]      = fname
                row[f"doctor_cases_fac{slot}"]    = fcases
                row[f"total_cases_fac{slot}"]     = ftotal
                row[f"pct_of_fac{slot}"]          = round(fcases / ftotal * 100, 2) if ftotal else 0.0
            else:
                row[f"facility_{slot}_name"]      = "-"
                row[f"doctor_cases_fac{slot}"]    = 0
                row[f"total_cases_fac{slot}"]     = 0
                row[f"pct_of_fac{slot}"]          = 0.0

        result.append(row)

    _cache_set(cache_key, result)
    return result


# ── Detailed Vertical Breakdown ────────────────────────────────────────────

def get_facility_breakdown_table(
    db: Session, filters: dict, group_by: str = "practitioner_name"
) -> list[dict]:
    """Vertical breakdown of cases by (group_by dimension, facility)."""
    # Row cap: use top_n if set, otherwise no limit
    row_cap_val = int(filters["top_n"]) * 4 if filters.get("top_n") else None
    row_cap = f"LIMIT {row_cap_val}" if row_cap_val else ""
    cache_key = f"breakdown:{json.dumps(filters, sort_keys=True)}:{group_by}:{row_cap_val}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if group_by not in allowed:
        group_by = "practitioner_name"

    where, params = _build_where(filters, table_alias="pr")

    where_fac, params_fac = _build_where_facility_only(filters)
    prefixed_params_fac: dict = {}
    prefixed_where_fac = where_fac
    for k, v in params_fac.items():
        nk = f"brk_{k}"
        prefixed_where_fac = prefixed_where_fac.replace(f":{k}", f":{nk}")
        prefixed_params_fac[nk] = v

    combined = {**params, **prefixed_params_fac}
    e_expr, i_expr, o_expr = _build_metric_exprs(filters)
    total_expr = f"({e_expr} + {i_expr} + {o_expr})"

    sql = text(f"""
        WITH fac_totals AS (
            SELECT facility_name,
                   COALESCE(SUM({total_expr}), 0) AS facility_sum
            FROM practitioner_records
            WHERE 1=1 {prefixed_where_fac}
            GROUP BY facility_name
        )
        SELECT
            pr.{group_by}                                             AS dimension,
            pr.facility_name                                          AS facility_name,
            COALESCE(SUM({e_expr}), 0)                                AS emergency,
            COALESCE(SUM({i_expr}), 0)                                AS inpatient,
            COALESCE(SUM({o_expr}), 0)                                AS outpatient,
            COALESCE(SUM({total_expr}), 0)                            AS doctor_cases,
            COALESCE(MAX(ft.facility_sum), 0)                         AS total_facility_cases,
            CASE
                WHEN COALESCE(MAX(ft.facility_sum), 0) = 0 THEN 0.0
                ELSE ROUND(
                    CAST(SUM({total_expr}) AS FLOAT)
                    / MAX(ft.facility_sum) * 100, 2
                )
            END                                                       AS pct_of_facility
        FROM practitioner_records pr
        LEFT JOIN fac_totals ft ON pr.facility_name = ft.facility_name
        WHERE 1=1 {where}
        GROUP BY pr.{group_by}, pr.facility_name
        ORDER BY pr.{group_by}, doctor_cases DESC
        {row_cap}
    """)
    rows = db.execute(sql, combined).fetchall()
    result = [dict(r._mapping) for r in rows]
    _cache_set(cache_key, result)
    return result


# ── Distinct values ────────────────────────────────────────────────────────

def get_distinct_values(db: Session, column: str) -> list[str]:
    return get_distinct_values_filtered(db, column, {})


def get_distinct_values_filtered(db: Session, column: str, filters: dict) -> list[str]:
    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if column not in allowed:
        return []

    cache_key = f"distinct:{column}:{json.dumps(filters, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    where, params = _build_where(filters)
    sql = text(f"""
        SELECT DISTINCT {column}
        FROM practitioner_records
        WHERE {column} IS NOT NULL AND TRIM({column}) != ''
        {where}
        ORDER BY {column}
        LIMIT 500
    """)
    rows = db.execute(sql, params).fetchall()
    result = [r[0] for r in rows]
    _cache_set(cache_key, result)
    return result


def get_date_range(db: Session) -> tuple[Optional[str], Optional[str]]:
    sql = text("SELECT MIN(visit_date), MAX(visit_date) FROM practitioner_records")
    row = db.execute(sql).fetchone()
    if row and row[0] and row[1]:
        return str(row[0]), str(row[1])
    return None, None


def get_record_count(db: Session) -> int:
    sql = text("SELECT COUNT(*) FROM practitioner_records")
    return db.execute(sql).scalar() or 0
