"""
Aggregator service — builds pivot/summary statistics for practitioner_records.
All heavy lifting done in SQL for performance.

Measures match Power BI DAX definitions:
  Total Cases              = SUM(EMERGENCY) + SUM(INPATIENT) + SUM(OUTPATIENT)
  Total Emergency          = SUM(EMERGENCY)
  Total Inpatient          = SUM(INPATIENT)
  Total Outpatient         = SUM(OUTPATIENT)
  Total Visits by Facility = SUM(cases) removing only practitioner_id filter
                             (keeps region, facility, date, speciality, patient_class)
  Total PractitionerID Unique = DISTINCTCOUNT(PRACTITIONERID)
  Total PractitionerID     = COUNTA(PRACTITIONERID)

  % Doctor Visits to Total (DAX-exact):
    VAR SelectedFacilities = VALUES(FACILITYNAME)           -- from active slicer
    VAR FacilityVisits =
        IF(
            ISFILTERED(PRACTITIONERID) || ISFILTERED(FACILITYNAME),
            CALCULATE(SUM(cases), ALL table, FACILITYNAME IN SelectedFacilities),
            SUM(cases)     -- no slicer active → same as numerator → 100%
        )
    RETURN DIVIDE(TotalCases, FacilityVisits, 0)

  SQL translation:
    - Numerator  = SUM(emergency+inpatient+outpatient) WITH full filters
    - Denominator= SUM(emergency+inpatient+outpatient) WHERE facility_name IN
                   (selected facilities) — ALL other filters stripped.
    - If no practitioner/facility filter active → denominator = numerator → 100%
"""

from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text


# ── WHERE clause builder ───────────────────────────────────────────────────

def _build_where(filters: dict, table_alias: str = "") -> tuple[str, dict]:
    """Build SQL WHERE clauses from filter dict. Returns (clauses_str, params).
    Supports single strings or lists of strings for IN clauses.
    Pass table_alias='pr' to qualify column names (avoids ambiguity in JOIN queries)."""
    clauses = []
    params = {}
    pfx = f"{table_alias}." if table_alias else ""

    def add_filter(field: str, db_col: str):
        val = filters.get(field)
        if not val:
            return
        col = f"{pfx}{db_col}"
        if isinstance(val, list):
            if not val: return
            p_names = []
            for i, item in enumerate(val):
                p_name = f"{field}_{i}"
                p_names.append(f":{p_name}")
                params[p_name] = item
            in_list = ", ".join(p_names)
            clauses.append(f"AND {col} IN ({in_list})")
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
        in_values = []
        has_5_plus = False
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
            fc_in_str = ", ".join(str(v) for v in in_values)
            fc_clauses.append(f"COUNT(DISTINCT facility_name) IN ({fc_in_str})")
        if has_5_plus:
            fc_clauses.append("COUNT(DISTINCT facility_name) >= 5")
        if fc_clauses:
            having_str = " OR ".join(fc_clauses)
            clauses.append(
                f"AND {pfx}practitioner_id IN ("
                f"  SELECT practitioner_id FROM practitioner_records "
                f"  GROUP BY practitioner_id HAVING {having_str}"
                f")"
            )

    if filters.get("patient_class"):
        pc_list = filters["patient_class"]
        if not isinstance(pc_list, list):
            pc_list = [pc_list]
        pc_lower = [pc.lower() for pc in pc_list]
        conds = []
        if "emergency" in pc_lower: conds.append(f"{pfx}emergency > 0")
        if "inpatient" in pc_lower: conds.append(f"{pfx}inpatient > 0")
        if "outpatient" in pc_lower: conds.append(f"{pfx}outpatient > 0")
        if conds:
            clauses.append("AND (" + " OR ".join(conds) + ")")

    return "\n    ".join(clauses), params


def _build_metric_exprs(filters: dict) -> tuple[str, str, str]:
    """Return SQL expressions for emergency, inpatient, outpatient based on patient_class filter."""
    if filters.get("patient_class"):
        pc_list = filters["patient_class"]
        if not isinstance(pc_list, list):
            pc_list = [pc_list]
        pc_lower = [pc.lower() for pc in pc_list]
        
        e_expr = "emergency" if "emergency" in pc_lower else "0"
        i_expr = "inpatient" if "inpatient" in pc_lower else "0"
        o_expr = "outpatient" if "outpatient" in pc_lower else "0"
    else:
        e_expr = "emergency"
        i_expr = "inpatient"
        o_expr = "outpatient"
        
    return e_expr, i_expr, o_expr


def _build_where_no_practitioner(filters: dict) -> tuple[str, dict]:
    """Same as _build_where but excludes practitioner_id filter.
    Used to compute facility totals (ALLEXCEPT practitioner) for % metric."""
    return _build_where({k: v for k, v in filters.items() if k != "practitioner_id"})


def _build_where_facility_only(filters: dict) -> tuple[str, dict]:
    """Build WHERE clause for 'Total Visits by Facility'.

    Strips ONLY practitioner_id so the denominator reflects all practitioners
    at the selected region / facility / speciality / date range — matching the
    DAX pattern CALCULATE(SUM(cases), ALLEXCEPT(table, FACILITYNAME)) where
    only the practitioner slicer is removed, not region/date/speciality.
    """
    return _build_where({k: v for k, v in filters.items() if k != "practitioner_id"})


# ── KPI summary ────────────────────────────────────────────────────────────

def get_kpi_summary(db: Session, filters: dict) -> dict:
    """Return top-level KPI numbers matching all Power BI measures."""
    where, params = _build_where(filters)

    e_expr, i_expr, o_expr = _build_metric_exprs(filters)
    total_expr = f"({e_expr} + {i_expr} + {o_expr})"

    # Main aggregates
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
            COUNT(DISTINCT region)                             AS total_regions
        FROM practitioner_records
        WHERE 1=1 {where}
    """)
    row = db.execute(sql, params).fetchone()
    result = dict(row._mapping) if row else {}

    # Alias for backward compatibility
    result["total_workload"] = result.get("total_cases", 0)

    # ── Total Visits by one or more Facility ─────────────────────────────
    # If a practitioner filter is active, find all facilities that practitioner
    # works in, then sum ALL visits in those facilities (remove practitioner
    # filter so you get the facility total, not just this practitioner's visits).
    # Without a practitioner filter, sum cases for the selected
    # region/facility/date/speciality without the practitioner scope.
    filters_no_pract = {k: v for k, v in filters.items() if k != "practitioner_id"}
    where_np, params_np = _build_where(filters_no_pract)

    pract_val = filters.get("practitioner_id")
    if pract_val:
        # Build the IN clause for the practitioner subquery
        if isinstance(pract_val, list):
            p_placeholders = ", ".join(f":_pf_{i}" for i in range(len(pract_val)))
            pract_params   = {f"_pf_{i}": v for i, v in enumerate(pract_val)}
        else:
            p_placeholders = ":_pf_0"
            pract_params   = {"_pf_0": pract_val}

        fac_sql = text(f"""
            SELECT COALESCE(SUM({total_expr}), 0)
            FROM practitioner_records
            WHERE 1=1 {where_np}
            AND facility_name IN (
                SELECT DISTINCT facility_name
                FROM practitioner_records
                WHERE practitioner_id IN ({p_placeholders})
            )
        """)
        combined_np = {**params_np, **pract_params}
        fac_total = db.execute(fac_sql, combined_np).scalar() or 0
    else:
        fac_sql = text(f"""
            SELECT COALESCE(SUM({total_expr}), 0)
            FROM practitioner_records
            WHERE 1=1 {where_np}
        """)
        fac_total = db.execute(fac_sql, params_np).scalar() or 0

    result["total_visits_by_facility"] = fac_total

    # ── % Doctor Visits to Total (DAX-exact) ─────────────────────────────
    # DAX logic:
    #   IF(
    #     ISFILTERED(PRACTITIONERID) || ISFILTERED(FACILITYNAME),
    #     CALCULATE(SUM(cases), ALL(table), FACILITYNAME IN SelectedFacilities),
    #     SUM(cases)   ← no slicer → denominator = numerator → 100%
    #   )
    #
    # SQL translation:
    #   - practitioner_id or facility_name filter is active?
    #       YES → denominator = SUM(cases) WHERE facility_name = selected (all other filters removed)
    #       NO  → denominator = numerator (result is 100%)
    tc = result.get("total_cases", 0) or 0
    practitioner_filtered = bool(filters.get("practitioner_id"))
    facility_filtered     = bool(filters.get("facility_name"))

    if practitioner_filtered or facility_filtered:
        # Denominator: full facility total — only facility_name filter kept
        where_fac, params_fac = _build_where_facility_only(filters)
        denom_sql = text(f"""
            SELECT COALESCE(SUM({total_expr}), 0)
            FROM practitioner_records
            WHERE 1=1 {where_fac}
        """)
        denom = db.execute(denom_sql, params_fac).scalar() or 0
    else:
        # No slicer active → denominator = numerator → 100%
        denom = tc

    result["pct_of_facility"] = round((tc / denom * 100), 2) if denom else 0.0

    return result


# ── Pivot  ─────────────────────────────────────────────────────────────────

def get_pivot(db: Session, filters: dict, group_by: str = "practitioner_name", include_top_facs: bool = True) -> list[dict]:
    """Return aggregated pivot grouped by a dimension.
    If include_top_facs is True, includes top 4 facility details per row (heavy CTEs).
    
    When group_by='practitioner_name' we also include practitioner_id in the GROUP BY
    so that practitioners who share the same name but have different IDs each get their
    own row — matching COUNT(DISTINCT practitioner_id) in the KPI cards.
    """
    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if group_by not in allowed:
        group_by = "practitioner_name"

    # When grouping by practitioner_name, also include practitioner_id in GROUP BY
    # so that same-name / different-ID practitioners each appear as a separate row.
    # This ensures the pivot row count equals COUNT(DISTINCT practitioner_id).
    if group_by == "practitioner_name":
        group_by_clause  = "practitioner_name, practitioner_id"
        # dimension shown in the table: "Name (ID)"
        dimension_expr   = "pr.practitioner_name || ' (' || pr.practitioner_id || ')'"
        cte_dim_expr     = "practitioner_name || ' (' || practitioner_id || ')'"
        cte_group_clause = "practitioner_name, practitioner_id, facility_name"
        join_dim         = f"({dimension_expr})"
    else:
        group_by_clause  = group_by
        dimension_expr   = f"pr.{group_by}"
        cte_dim_expr     = group_by
        cte_group_clause = f"{group_by}, facility_name"
        join_dim         = f"pr.{group_by}"

    # where_cte   → unaliased, used in inner CTEs (FROM practitioner_records, no alias)
    # where_main  → qualified with "pr.", used in the final SELECT that JOINs CTEs
    # Both calls produce identical param dicts (same keys, same values), so we reuse params.
    where_cte, params = _build_where(filters)
    where_main, _    = _build_where(filters, table_alias="pr")
    where_nop, params_nop = _build_where_no_practitioner(filters)

    e_expr, i_expr, o_expr = _build_metric_exprs(filters)
    total_expr = f"({e_expr} + {i_expr} + {o_expr})"

    if not include_top_facs:
        # FAST PATH: simple aggregation without the heavy doc_fac CTEs
        sql_fast = text(f"""
            SELECT
                {dimension_expr}                                          AS dimension,
                COUNT(*)                                                  AS total_records,
                COALESCE(SUM({e_expr}), 0)                                AS total_emergency,
                COALESCE(SUM({i_expr}), 0)                                AS total_inpatient,
                COALESCE(SUM({o_expr}), 0)                                AS total_outpatient,
                COALESCE(SUM({total_expr}), 0)                            AS total_cases,
                COUNT(DISTINCT pr.practitioner_id)                        AS unique_practitioners,
                COUNT(pr.practitioner_id)                                 AS total_practitioners
            FROM practitioner_records pr
            WHERE 1=1 {where_main}
            GROUP BY {join_dim}
            ORDER BY {filters.get("top_n_by", "total_cases")} DESC
            {f"LIMIT {int(filters['top_n'])}" if filters.get("top_n") else ""}
        """)
        rows = db.execute(sql_fast, params).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Facility sub-query (ALLEXCEPT facility_name) ─────────────────────
    where_fac, params_fac = _build_where_facility_only(filters)
    prefixed_where_fac = where_fac
    prefixed_params_fac: dict = {}
    for k, v in params_fac.items():
        new_key = f"denom_{k}"
        prefixed_where_fac = prefixed_where_fac.replace(f":{k}", f":{new_key}")
        prefixed_params_fac[new_key] = v

    fac_join = f"""
        WITH fac_totals AS (
            SELECT facility_name,
                   COALESCE(SUM({total_expr}), 0) AS facility_sum
            FROM practitioner_records
            WHERE 1=1 {prefixed_where_fac}
            GROUP BY facility_name
        ),
        doc_fac AS (
            SELECT {cte_dim_expr} AS dimension,
                   facility_name,
                   COALESCE(SUM({total_expr}), 0) AS doc_fac_cases
            FROM practitioner_records
            WHERE 1=1 {where_cte}
            GROUP BY {cte_group_clause}
        ),
        doc_ranked AS (
            SELECT dimension,
                   facility_name,
                   doc_fac_cases,
                   ROW_NUMBER() OVER(PARTITION BY dimension ORDER BY doc_fac_cases DESC) as rn
            FROM doc_fac
        ),
        doc_fac1 AS (
            SELECT dimension,
                   facility_name AS fac1_name,
                   doc_fac_cases AS doc_fac1_cases
            FROM doc_ranked
            WHERE rn = 1
        ),
        doc_fac2 AS (
            SELECT dimension, facility_name AS fac2_name, doc_fac_cases AS doc_fac2_cases
            FROM doc_ranked WHERE rn = 2
        ),
        doc_fac3 AS (
            SELECT dimension, facility_name AS fac3_name, doc_fac_cases AS doc_fac3_cases
            FROM doc_ranked WHERE rn = 3
        ),
        doc_fac4 AS (
            SELECT dimension, facility_name AS fac4_name, doc_fac_cases AS doc_fac4_cases
            FROM doc_ranked WHERE rn = 4
        ),
        doc_all_facs AS (
            SELECT df.dimension,
                   SUM(ft.facility_sum) AS all_facs_total
            FROM doc_fac df
            JOIN fac_totals ft ON df.facility_name = ft.facility_name
            GROUP BY df.dimension
        )
    """

    combined = dict(params)
    combined.update(prefixed_params_fac)

    sql2 = text(f"""
        {fac_join}
        SELECT
            {dimension_expr}                                          AS dimension,
            COUNT(*)                                                  AS total_records,
            COALESCE(SUM({e_expr}), 0)                                AS total_emergency,
            COALESCE(SUM({i_expr}), 0)                                AS total_inpatient,
            COALESCE(SUM({o_expr}), 0)                                AS total_outpatient,
            COALESCE(SUM({total_expr}), 0)                            AS total_cases,
            COUNT(DISTINCT pr.practitioner_id)                        AS unique_practitioners,
            COUNT(pr.practitioner_id)                                 AS total_practitioners,

            COALESCE(MAX(daf.all_facs_total), 0)                      AS total_visits_all_facilities,

            CASE
                WHEN COALESCE(MAX(daf.all_facs_total), 0) = 0 THEN 0.0
                ELSE ROUND(
                    CAST(SUM({total_expr}) AS FLOAT)
                    / MAX(daf.all_facs_total) * 100, 2
                )
            END                                                       AS pct_of_all_facilities,

            COALESCE(MAX(df1.fac1_name), 'Unknown')                   AS facility_1_name,
            COALESCE(MAX(df1.doc_fac1_cases), 0)                      AS doctor_cases_fac1,
            COALESCE(MAX(ft1.facility_sum), 0)                        AS total_cases_fac1,

            CASE
                WHEN COALESCE(MAX(ft1.facility_sum), 0) = 0 THEN 0.0
                ELSE ROUND(
                    CAST(MAX(df1.doc_fac1_cases) AS FLOAT)
                    / MAX(ft1.facility_sum) * 100, 2
                )
            END                                                       AS pct_of_fac1,

            COALESCE(MAX(df2.fac2_name), '-')                         AS facility_2_name,
            COALESCE(MAX(df2.doc_fac2_cases), 0)                      AS doctor_cases_fac2,
            COALESCE(MAX(ft2.facility_sum), 0)                        AS total_cases_fac2,
            CASE WHEN COALESCE(MAX(ft2.facility_sum), 0) = 0 THEN 0.0 ELSE ROUND(CAST(MAX(df2.doc_fac2_cases) AS FLOAT) / MAX(ft2.facility_sum) * 100, 2) END AS pct_of_fac2,

            COALESCE(MAX(df3.fac3_name), '-')                         AS facility_3_name,
            COALESCE(MAX(df3.doc_fac3_cases), 0)                      AS doctor_cases_fac3,
            COALESCE(MAX(ft3.facility_sum), 0)                        AS total_cases_fac3,
            CASE WHEN COALESCE(MAX(ft3.facility_sum), 0) = 0 THEN 0.0 ELSE ROUND(CAST(MAX(df3.doc_fac3_cases) AS FLOAT) / MAX(ft3.facility_sum) * 100, 2) END AS pct_of_fac3,

            COALESCE(MAX(df4.fac4_name), '-')                         AS facility_4_name,
            COALESCE(MAX(df4.doc_fac4_cases), 0)                      AS doctor_cases_fac4,
            COALESCE(MAX(ft4.facility_sum), 0)                        AS total_cases_fac4,
            CASE WHEN COALESCE(MAX(ft4.facility_sum), 0) = 0 THEN 0.0 ELSE ROUND(CAST(MAX(df4.doc_fac4_cases) AS FLOAT) / MAX(ft4.facility_sum) * 100, 2) END AS pct_of_fac4

        FROM practitioner_records pr
        LEFT JOIN doc_all_facs daf ON {join_dim} = daf.dimension
        LEFT JOIN doc_fac1 df1 ON {join_dim} = df1.dimension
        LEFT JOIN fac_totals ft1 ON df1.fac1_name = ft1.facility_name
        LEFT JOIN doc_fac2 df2 ON {join_dim} = df2.dimension
        LEFT JOIN fac_totals ft2 ON df2.fac2_name = ft2.facility_name
        LEFT JOIN doc_fac3 df3 ON {join_dim} = df3.dimension
        LEFT JOIN fac_totals ft3 ON df3.fac3_name = ft3.facility_name
        LEFT JOIN doc_fac4 df4 ON {join_dim} = df4.dimension
        LEFT JOIN fac_totals ft4 ON df4.fac4_name = ft4.facility_name
        WHERE 1=1 {where_main}
        GROUP BY {join_dim}
        ORDER BY {filters.get("top_n_by", "total_cases")} DESC
        {f"LIMIT {int(filters['top_n'])}" if filters.get("top_n") else ""}
    """)

    rows = db.execute(sql2, combined).fetchall()
    return [dict(r._mapping) for r in rows]


# ── Detailed Vertical Breakdown ─────────────────────────────────────────────

def get_facility_breakdown_table(db: Session, filters: dict, group_by: str = "practitioner_name") -> list[dict]:
    """Return vertical facility breakdown per grouped dimension (handles unlimited facilities)."""
    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if group_by not in allowed:
        group_by = "practitioner_name"

    where, params = _build_where(filters, table_alias="pr")
    
    where_fac, params_fac = _build_where_facility_only(filters)
    prefixed_where_fac = where_fac
    prefixed_params_fac: dict = {}
    for k, v in params_fac.items():
        new_key = f"brk_{k}"
        prefixed_where_fac = prefixed_where_fac.replace(f":{k}", f":{new_key}")
        prefixed_params_fac[new_key] = v

    combined = dict(params)
    combined.update(prefixed_params_fac)

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
    """)
    rows = db.execute(sql, combined).fetchall()
    return [dict(r._mapping) for r in rows]


# ── Distinct values (with cascading filter support) ────────────────────────

def get_distinct_values(db: Session, column: str) -> list[str]:
    """Return distinct non-null values for a column (no cascading)."""
    return get_distinct_values_filtered(db, column, {})


def get_distinct_values_filtered(db: Session, column: str, filters: dict) -> list[str]:
    """Return distinct values for a column, respecting any active filters.
    This enables cascading: Region → Facility → Speciality chain.
    """
    allowed = {
        "region", "facility_name", "practitioner_id",
        "practitioner_name", "speciality", "visit_date", "month"
    }
    if column not in allowed:
        return []

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
    return [r[0] for r in rows]


def get_date_range(db: Session) -> tuple[Optional[str], Optional[str]]:
    """Return the minimum and maximum visit_date found in the database."""
    sql = text("SELECT MIN(visit_date), MAX(visit_date) FROM practitioner_records")
    row = db.execute(sql).fetchone()
    if row and row[0] and row[1]:
        return str(row[0]), str(row[1])
    return None, None
