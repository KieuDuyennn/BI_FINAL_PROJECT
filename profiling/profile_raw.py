"""Profile raw source data (trips parquet, zone lookup CSV, zone shapefile).

Outputs a Markdown report plus CSV tables under docs/profiling/.
Run: python profiling/profile_raw.py
"""

import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingestion"))
from config import load_settings  # noqa: E402

OUT_DIR = PROJECT_ROOT / "docs" / "profiling"
TABLE_DIR = OUT_DIR / "tables"

# Official TLC data dictionary codes (Yellow Taxi, 2025 revision).
VENDORS = {1: "Creative Mobile Technologies (CMT)", 2: "Curb Mobility (VTS)", 6: "Myle Technologies", 7: "Helix"}
RATECODES = {1: "Standard rate", 2: "JFK", 3: "Newark", 4: "Nassau or Westchester", 5: "Negotiated fare",
             6: "Group ride", 99: "Null/unknown"}
PAYMENTS = {0: "Flex Fare trip", 1: "Credit card", 2: "Cash", 3: "No charge", 4: "Dispute", 5: "Unknown",
            6: "Voided trip"}
AIRPORT_ZONES = (1, 132, 138)  # Newark, JFK, LaGuardia

MONEY_COLS = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
              "congestion_surcharge", "Airport_fee", "cbd_congestion_fee"]

report: list[str] = []


def md_table(df: pd.DataFrame, floatfmt: str = "{:,.2f}") -> str:
    """Render a DataFrame as a GitHub Markdown table (no tabulate dependency)."""
    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{int(v):,}" if v.is_integer() and abs(v) >= 1000 else floatfmt.format(v)
        if isinstance(v, int) and not isinstance(v, bool):
            return f"{v:,}"
        return str(v).replace("|", "\\|")

    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def emit(title: str, df: pd.DataFrame, name: str, level: int = 3, note: str = "") -> pd.DataFrame:
    """Save a table to CSV and append it to the report."""
    df.to_csv(TABLE_DIR / f"{name}.csv", index=False)
    report.append(f"{'#' * level} {title}\n")
    if note:
        report.append(note + "\n")
    report.append(md_table(df) + "\n")
    return df


def pct(part, whole) -> float:
    return round(100.0 * part / whole, 4) if whole else 0.0


# ---------------------------------------------------------------------------
# 1. Source survey
# ---------------------------------------------------------------------------
def survey_files(raw_dir: Path) -> pd.DataFrame:
    rows, prev_cols = [], None
    for f in sorted(raw_dir.glob("yellow_tripdata_*.parquet")):
        meta, schema = pq.read_metadata(f), pq.read_schema(f)
        cols = list(schema.names)
        drift = ""
        if prev_cols is not None and cols != prev_cols:
            added = [c for c in cols if c not in prev_cols]
            removed = [c for c in prev_cols if c not in cols]
            drift = "; ".join(filter(None, [f"+{added}" if added else "", f"-{removed}" if removed else ""]))
        prev_cols = cols
        rows.append({"file": f.name, "size_mb": round(f.stat().st_size / 2**20, 1), "rows": meta.num_rows,
                     "row_groups": meta.num_row_groups, "columns": len(cols), "schema_change": drift})
    for f in sorted(raw_dir.iterdir()):
        if not f.name.startswith("yellow_tripdata_"):
            rows.append({"file": f.name, "size_mb": round(f.stat().st_size / 2**20, 3), "rows": None,
                         "row_groups": None, "columns": None, "schema_change": ""})
    return pd.DataFrame(rows)


def schema_table(raw_dir: Path) -> pd.DataFrame:
    latest = sorted(raw_dir.glob("yellow_tripdata_*.parquet"))[-1]
    first = sorted(raw_dir.glob("yellow_tripdata_*.parquet"))[0]
    s_first, s_last = pq.read_schema(first), pq.read_schema(latest)
    return pd.DataFrame([{"column": n, "parquet_type": str(t),
                          "present_in_first_file": n in s_first.names} for n, t in zip(s_last.names, s_last.types)])


# ---------------------------------------------------------------------------
# 2. Trip profiling (DuckDB)
# ---------------------------------------------------------------------------
def connect(raw_dir: Path, tmp_dir: Path) -> duckdb.DuckDBPyConnection:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='6GB'")
    con.execute(f"SET temp_directory='{tmp_dir.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    glob = (raw_dir / "yellow_tripdata_*.parquet").as_posix()
    con.execute(f"""
        CREATE VIEW trips AS
        SELECT *,
               regexp_extract(filename, 'yellow_tripdata_(\\d{{4}}-\\d{{2}})', 1) AS src_month,
               date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime) AS duration_sec
        FROM read_parquet('{glob}', union_by_name = true, filename = true)
    """)
    lookup = (raw_dir / "taxi_zone_lookup.csv").as_posix()
    con.execute(f"CREATE TABLE zones AS SELECT * FROM read_csv('{lookup}', header = true)")
    return con


def numeric_profile(con) -> pd.DataFrame:
    df = con.execute("""
        SUMMARIZE SELECT * EXCLUDE (filename, src_month, duration_sec) FROM trips
    """).df()
    df = df.rename(columns={"column_name": "column", "column_type": "type"})
    for c in ["avg", "std", "q25", "q50", "q75"]:  # SUMMARIZE returns strings; round the numeric ones
        df[c] = df[c].map(lambda v: f"{float(v):,.3f}" if _is_number(v) else v)
    keep = ["column", "type", "count", "null_percentage", "approx_unique", "min", "max", "avg", "std",
            "q25", "q50", "q75"]
    return df[keep]


def _is_number(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def categorical_profile(con, col: str, labels: dict | None, total: int, limit: int = 30) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT {col} AS value, count(*) AS trips FROM trips GROUP BY 1 ORDER BY trips DESC LIMIT {limit}
    """).df()
    if labels is not None:
        df.insert(1, "meaning", df["value"].map(lambda v: labels.get(int(v), "NOT IN DICTIONARY")
                                                 if pd.notna(v) else "NULL"))
    df["pct"] = df["trips"].map(lambda n: pct(n, total))
    return df


def monthly_profile(con) -> pd.DataFrame:
    return con.execute("""
        SELECT src_month,
               count(*)                                                       AS rows,
               count_if(strftime(tpep_pickup_datetime, '%Y-%m') <> src_month) AS pickup_outside_month,
               min(tpep_pickup_datetime)                                      AS min_pickup,
               max(tpep_pickup_datetime)                                      AS max_pickup,
               count_if(passenger_count IS NULL)                              AS null_passenger_count,
               round(sum(total_amount), 0)                                    AS sum_total_amount,
               round(avg(total_amount), 2)                                    AS avg_total_amount,
               round(avg(trip_distance), 2)                                   AS avg_trip_distance,
               round(median(duration_sec) / 60.0, 2)                          AS median_duration_min
        FROM trips GROUP BY 1 ORDER BY 1
    """).df()


def pickup_year_profile(con) -> pd.DataFrame:
    return con.execute("""
        SELECT CAST(year(tpep_pickup_datetime) AS VARCHAR) AS pickup_year, count(*) AS trips
        FROM trips GROUP BY 1 ORDER BY 1
    """).df()


def anomaly_rules(valid_ids: list[int]) -> list[tuple[str, str, str, str]]:
    """(code, category, description, SQL condition) — each counted independently."""
    ids = ",".join(map(str, valid_ids))
    money_sum = " + ".join(f"coalesce({c}, 0)" for c in MONEY_COLS)
    airports = ",".join(map(str, AIRPORT_ZONES))
    return [
        ("T01", "Time", "Pickup month differs from source file month",
         "strftime(tpep_pickup_datetime, '%Y-%m') <> src_month"),
        ("T02", "Time", "Pickup year outside 2024-2025", "year(tpep_pickup_datetime) NOT IN (2024, 2025)"),
        ("T03", "Time", "Dropoff before pickup", "duration_sec < 0"),
        ("T04", "Time", "Dropoff equals pickup (0 s)", "duration_sec = 0"),
        ("T05", "Time", "Duration under 1 minute (>0 s)", "duration_sec > 0 AND duration_sec < 60"),
        ("T06", "Time", "Duration over 3 hours", "duration_sec > 3 * 3600"),
        ("T07", "Time", "Duration over 24 hours", "duration_sec > 24 * 3600"),
        ("D01", "Distance", "trip_distance = 0", "trip_distance = 0"),
        ("D02", "Distance", "trip_distance < 0", "trip_distance < 0"),
        ("D03", "Distance", "trip_distance > 100 miles", "trip_distance > 100"),
        ("D04", "Distance", "Average speed > 80 mph",
         "duration_sec > 0 AND trip_distance / (duration_sec / 3600.0) > 80"),
        ("D05", "Distance", "Distance > 0 but same PU/DO zone and duration 0",
         "trip_distance > 0 AND PULocationID = DOLocationID AND duration_sec = 0"),
        ("P01", "Passenger", "passenger_count is NULL", "passenger_count IS NULL"),
        ("P02", "Passenger", "passenger_count = 0", "passenger_count = 0"),
        ("P03", "Passenger", "passenger_count > 6", "passenger_count > 6"),
        ("C01", "Code", "VendorID not in dictionary {1,2,6,7}", "VendorID NOT IN (1, 2, 6, 7)"),
        ("C02", "Code", "RatecodeID is NULL", "RatecodeID IS NULL"),
        ("C03", "Code", "RatecodeID = 99 (unknown)", "RatecodeID = 99"),
        ("C04", "Code", "RatecodeID not in dictionary {1..6,99}", "RatecodeID NOT IN (1,2,3,4,5,6,99)"),
        ("C05", "Code", "payment_type = 0 (Flex Fare / missing)", "payment_type = 0"),
        ("C06", "Code", "payment_type not in dictionary {0..6}", "payment_type NOT IN (0,1,2,3,4,5,6)"),
        ("C07", "Code", "store_and_fwd_flag is NULL", "store_and_fwd_flag IS NULL"),
        ("L01", "Location", "PULocationID not in zone lookup", f"PULocationID NOT IN ({ids})"),
        ("L02", "Location", "DOLocationID not in zone lookup", f"DOLocationID NOT IN ({ids})"),
        ("L03", "Location", "PULocationID is Unknown/Outside NYC (264, 265)", "PULocationID IN (264, 265)"),
        ("L04", "Location", "DOLocationID is Unknown/Outside NYC (264, 265)", "DOLocationID IN (264, 265)"),
        ("M01", "Money", "fare_amount < 0", "fare_amount < 0"),
        ("M02", "Money", "fare_amount = 0", "fare_amount = 0"),
        ("M03", "Money", "fare_amount > 500", "fare_amount > 500"),
        ("M04", "Money", "total_amount < 0", "total_amount < 0"),
        ("M05", "Money", "total_amount = 0", "total_amount = 0"),
        ("M06", "Money", "total_amount != sum of components (|diff| > 0.01)",
         f"abs(total_amount - ({money_sum})) > 0.01"),
        ("M07", "Money", "tip_amount < 0", "tip_amount < 0"),
        ("M08", "Money", "tip_amount > 0 on cash payment", "tip_amount > 0 AND payment_type = 2"),
        ("M09", "Money", "tip_amount > fare_amount (fare > 0)", "fare_amount > 0 AND tip_amount > fare_amount"),
        ("M10", "Money", "tolls_amount < 0", "tolls_amount < 0"),
        ("M11", "Money", "Any surcharge/tax column < 0",
         "extra < 0 OR mta_tax < 0 OR improvement_surcharge < 0 OR congestion_surcharge < 0 "
         "OR Airport_fee < 0 OR cbd_congestion_fee < 0"),
        ("M12", "Money", "Airport_fee > 0 but pickup not at an airport zone",
         f"Airport_fee > 0 AND PULocationID NOT IN ({airports})"),
        ("M13", "Money", "cbd_congestion_fee > 0 before program start (2025-01-05)",
         "cbd_congestion_fee > 0 AND tpep_pickup_datetime < TIMESTAMP '2025-01-05'"),
        ("M14", "Money", "Positive fare with zero distance and zero duration",
         "fare_amount > 0 AND trip_distance = 0 AND duration_sec = 0"),
    ]


def anomaly_profile(con, rules, total: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    selects = ",\n".join(f"count_if({cond}) AS {code}" for code, _, _, cond in rules)
    by_month = con.execute(f"SELECT src_month, count(*) AS rows, {selects} FROM trips GROUP BY 1 ORDER BY 1").df()
    summary = pd.DataFrame([{"code": code, "category": cat, "rule": desc,
                             "trips": int(by_month[code].sum()), "pct": pct(int(by_month[code].sum()), total)}
                            for code, cat, desc, _ in rules])
    return summary, by_month


def any_anomaly_count(con, rules) -> int:
    cond = " OR ".join(f"coalesce({c}, false)" for code, _, _, c in rules if not code.startswith(("L03", "L04")))
    return con.execute(f"SELECT count_if({cond}) FROM trips").fetchone()[0]


def duplicate_profile(con, total: int) -> pd.DataFrame:
    cols = ("VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, passenger_count, trip_distance, RatecodeID, "
            "store_and_fwd_flag, PULocationID, DOLocationID, payment_type, fare_amount, extra, mta_tax, "
            "tip_amount, tolls_amount, improvement_surcharge, total_amount, congestion_surcharge, Airport_fee, "
            "cbd_congestion_fee")
    distinct_rows = con.execute(f"SELECT count(DISTINCT hash({cols})) FROM trips").fetchone()[0]
    distinct_keys = con.execute("""
        SELECT count(DISTINCT hash(VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, PULocationID,
                                   DOLocationID)) FROM trips
    """).fetchone()[0]
    return pd.DataFrame([
        {"check": "Exact duplicate rows (all columns)", "duplicate_trips": total - distinct_rows,
         "pct": pct(total - distinct_rows, total)},
        {"check": "Duplicate natural key (vendor, pickup, dropoff, PU, DO)", "duplicate_trips": total - distinct_keys,
         "pct": pct(total - distinct_keys, total)},
    ])


def reversal_profile(con) -> pd.DataFrame:
    """Classify natural-key duplicate groups: original trip + negative reversal vs. true duplicates."""
    return con.execute("""
        WITH g AS (
            SELECT count(*) AS n,
                   count_if(total_amount < 0) > 0 AND count_if(total_amount >= 0) > 0 AS has_negative_twin,
                   abs(sum(total_amount)) < 0.01 AS nets_to_zero
            FROM trips
            GROUP BY VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, PULocationID, DOLocationID
            HAVING count(*) > 1)
        SELECT n AS rows_per_key, has_negative_twin, nets_to_zero, count(*) AS key_groups
        FROM g GROUP BY ALL ORDER BY key_groups DESC
    """).df()


def total_reconciliation_profile(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Where total_amount != sum of components: by vendor/year and by the size of the gap."""
    money_sum = " + ".join(f"coalesce({c}, 0)" for c in MONEY_COLS)
    by_vendor = con.execute(f"""
        SELECT substr(src_month, 1, 4) AS file_year, VendorID, count(*) AS n_trips,
               count_if(abs(total_amount - ({money_sum})) > 0.01) AS mismatched,
               round(100.0 * count_if(abs(total_amount - ({money_sum})) > 0.01) / count(*), 2) AS pct
        FROM trips GROUP BY ALL ORDER BY ALL
    """).df()
    gaps = con.execute(f"""
        SELECT round(total_amount - ({money_sum}), 2) AS total_minus_components, count(*) AS trips
        FROM trips GROUP BY 1 ORDER BY trips DESC LIMIT 12
    """).df()
    return by_vendor, gaps


def null_pattern_profile(con, total: int) -> pd.DataFrame:
    df = con.execute("""
        SELECT passenger_count IS NULL      AS passenger_null,
               RatecodeID IS NULL           AS ratecode_null,
               store_and_fwd_flag IS NULL   AS flag_null,
               congestion_surcharge IS NULL AS congestion_null,
               Airport_fee IS NULL          AS airport_fee_null,
               payment_type,
               count(*)                     AS trips
        FROM trips GROUP BY ALL HAVING passenger_null OR ratecode_null OR flag_null
                                     OR congestion_null OR airport_fee_null
        ORDER BY trips DESC LIMIT 15
    """).df()
    df["pct"] = df["trips"].map(lambda n: pct(n, total))
    return df


def refund_profile(con) -> pd.DataFrame:
    """Negative-amount rows: are they full reversals (all money columns <= 0)?"""
    return con.execute("""
        SELECT payment_type,
               count(*) AS trips_with_negative_total,
               count_if(fare_amount <= 0 AND coalesce(extra, 0) <= 0 AND coalesce(mta_tax, 0) <= 0
                        AND coalesce(improvement_surcharge, 0) <= 0) AS all_components_non_positive
        FROM trips WHERE total_amount < 0 GROUP BY 1 ORDER BY 2 DESC
    """).df()


def outlier_quantiles(con) -> pd.DataFrame:
    rows = []
    for col in ["trip_distance", "fare_amount", "tip_amount", "total_amount", "duration_sec"]:
        q = con.execute(f"""
            SELECT quantile_cont({col}, [0.001, 0.01, 0.05, 0.5, 0.95, 0.99, 0.999]) FROM trips
        """).fetchone()[0]
        rows.append({"column": col, **{p: v for p, v in zip(
            ["p0.1", "p1", "p5", "p50", "p95", "p99", "p99.9"], q)}})
    return pd.DataFrame(rows)


def zone_usage_profile(con) -> pd.DataFrame:
    return con.execute("""
        WITH pu AS (SELECT PULocationID AS id, count(*) AS pickups FROM trips GROUP BY 1),
             dr AS (SELECT DOLocationID AS id, count(*) AS dropoffs FROM trips GROUP BY 1)
        SELECT z.LocationID, z.Borough, z.Zone, coalesce(pu.pickups, 0) AS pickups,
               coalesce(dr.dropoffs, 0) AS dropoffs
        FROM zones z LEFT JOIN pu ON pu.id = z.LocationID LEFT JOIN dr ON dr.id = z.LocationID
        ORDER BY pickups
    """).df()


# ---------------------------------------------------------------------------
# 3. Zone lookup + shapefile
# ---------------------------------------------------------------------------
def lookup_profile(raw_dir: Path) -> dict[str, pd.DataFrame]:
    z = pd.read_csv(raw_dir / "taxi_zone_lookup.csv", keep_default_na=False)
    cols = pd.DataFrame([{
        "column": c, "dtype": str(z[c].dtype), "distinct": z[c].nunique(),
        "empty_or_NA": int(z[c].astype(str).str.strip().isin(["", "N/A", "NA", "Unknown"]).sum()),
        "example": z[c].iloc[0],
    } for c in z.columns])
    ids = z["LocationID"]
    expected = set(range(ids.min(), ids.max() + 1))
    checks = pd.DataFrame([
        {"check": "Row count", "result": len(z)},
        {"check": "LocationID unique", "result": ids.is_unique},
        {"check": "LocationID range", "result": f"{ids.min()}..{ids.max()}"},
        {"check": "Missing IDs in range", "result": sorted(expected - set(ids)) or "none"},
        {"check": "Duplicate Zone names", "result": ", ".join(sorted(z.loc[z["Zone"].duplicated(keep=False), "Zone"]
                                                                  .unique())) or "none"},
        {"check": "Rows with Borough Unknown/N/A/empty",
         "result": ", ".join(f"{r.LocationID}={r.Borough!r}/{r.Zone!r}" for r in z.itertuples()
                             if str(r.Borough).strip() in ("", "N/A", "Unknown"))},
    ])
    borough = z.groupby("Borough").size().reset_index(name="zones").sort_values("zones", ascending=False)
    service = z.groupby("service_zone").size().reset_index(name="zones").sort_values("zones", ascending=False)
    return {"columns": cols, "checks": checks, "borough": borough, "service": service, "df": z}


def shapefile_profile(raw_dir: Path, lookup: pd.DataFrame) -> dict[str, pd.DataFrame] | None:
    try:
        import geopandas as gpd
    except ImportError:
        return None
    g = gpd.read_file(raw_dir / "taxi_zones.shp")
    cols = pd.DataFrame([{"column": c, "dtype": str(g[c].dtype),
                          "nulls": int(g[c].isna().sum()), "distinct": int(g[c].astype(str).nunique())}
                         for c in g.columns])
    shp_ids, lk_ids = set(g["LocationID"]), set(lookup["LocationID"])
    dup_ids = g.loc[g["LocationID"].duplicated(keep=False), ["OBJECTID", "LocationID", "zone", "borough"]]
    lk = lookup.set_index("LocationID")
    name_mismatch = [f"{r.LocationID}: shp={r.zone!r} vs csv={lk.at[r.LocationID, 'Zone']!r}"
                     for r in g.drop_duplicates("LocationID").itertuples()
                     if r.LocationID in lk.index and r.zone != lk.at[r.LocationID, "Zone"]]
    checks = pd.DataFrame([
        {"check": "Feature count", "result": len(g)},
        {"check": "CRS", "result": str(g.crs.name if g.crs else None)},
        {"check": "Geometry types", "result": ", ".join(sorted(g.geom_type.unique()))},
        {"check": "Invalid geometries", "result": int((~g.is_valid).sum())},
        {"check": "Empty geometries", "result": int(g.is_empty.sum())},
        {"check": "Distinct LocationID", "result": len(shp_ids)},
        {"check": "Duplicated LocationID (multiple polygons)",
         "result": "; ".join(f"{r.LocationID} (OBJECTID {r.OBJECTID}, {r.zone})" for r in dup_ids.itertuples())
         or "none"},
        {"check": "OBJECTID != LocationID",
         "result": int((g["OBJECTID"] != g["LocationID"]).sum())},
        {"check": "IDs in lookup but not in shapefile", "result": sorted(lk_ids - shp_ids) or "none"},
        {"check": "IDs in shapefile but not in lookup", "result": sorted(shp_ids - lk_ids) or "none"},
        {"check": "Zone names differing from lookup", "result": "; ".join(name_mismatch) or "none"},
        {"check": "Total bounds (CRS units)", "result": ", ".join(f"{v:,.0f}" for v in g.total_bounds)},
    ])
    return {"columns": cols, "checks": checks}


# ---------------------------------------------------------------------------
def main() -> None:
    settings = load_settings()
    raw_dir = Path(settings["raw_dir"])
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    report.append("# Raw Data Profiling Results (auto-generated)\n")
    report.append(f"Generated by `profiling/profile_raw.py` on {time.strftime('%Y-%m-%d %H:%M')}. "
                  "Source: `data/raw/`. CSV copies of every table are in `docs/profiling/tables/`.\n")

    # 1. Survey
    report.append("## 1. Source survey\n")
    files = emit("1.1 Files", survey_files(raw_dir), "01_files")
    emit("1.2 Trip schema (latest file)", schema_table(raw_dir), "02_trip_schema")

    # 2. Trips
    print("Profiling trips with DuckDB ...")
    con = connect(raw_dir, PROJECT_ROOT / "data" / ".duckdb_tmp")
    total = con.execute("SELECT count(*) FROM trips").fetchone()[0]
    print(f"  total rows: {total:,}")
    report.append("## 2. Trip records\n")
    report.append(f"Total trip rows: **{total:,}** across {int(files['rows'].notna().sum())} monthly files.\n")

    print("  numeric summary ...")
    emit("2.1 Column summary (DuckDB SUMMARIZE)", numeric_profile(con), "03_column_summary")
    print("  quantiles ...")
    emit("2.2 Quantiles of key measures", outlier_quantiles(con), "04_quantiles",
         note="`duration_sec` = dropoff - pickup in seconds.")
    print("  monthly ...")
    emit("2.3 Per source file", monthly_profile(con), "05_monthly")
    emit("2.4 Trips by pickup year", pickup_year_profile(con), "06_pickup_year")

    print("  categorical ...")
    report.append("### 2.5 Categorical distributions\n")
    cats = [("VendorID", VENDORS), ("RatecodeID", RATECODES), ("payment_type", PAYMENTS),
            ("store_and_fwd_flag", None), ("passenger_count", None), ("mta_tax", None),
            ("improvement_surcharge", None), ("congestion_surcharge", None), ("Airport_fee", None),
            ("cbd_congestion_fee", None), ("extra", None)]
    for i, (col, labels) in enumerate(cats):
        emit(f"`{col}`", categorical_profile(con, col, labels, total, limit=15), f"07_{i:02d}_cat_{col}",
             level=4)

    print("  null patterns ...")
    emit("2.6 Co-occurring NULL patterns", null_pattern_profile(con, total), "08_null_patterns")

    print("  anomaly rules ...")
    zones = lookup_profile(raw_dir)
    rules = anomaly_rules(sorted(zones["df"]["LocationID"].tolist()))
    summary, by_month = anomaly_profile(con, rules, total)
    report.append("## 3. Anomaly checks\n")
    emit("3.1 Rule results (each rule counted independently)", summary, "09_anomaly_summary")
    flagged = any_anomaly_count(con, rules)
    report.append(f"Rows hitting at least one rule (excluding L03/L04 unknown-zone rules): "
                  f"**{flagged:,}** ({pct(flagged, total)}%).\n")
    by_month.to_csv(TABLE_DIR / "10_anomaly_by_month.csv", index=False)
    report.append("Per-month breakdown: `tables/10_anomaly_by_month.csv`.\n")

    print("  duplicates ...")
    emit("3.2 Duplicates", duplicate_profile(con, total), "11_duplicates")
    emit("3.3 Natural-key duplicate groups", reversal_profile(con), "11b_duplicate_key_groups",
         note="`has_negative_twin` = group contains a negative-total row; `nets_to_zero` = amounts cancel out.")
    emit("3.4 Negative total_amount by payment type", refund_profile(con), "12_negative_totals")
    by_vendor, gaps = total_reconciliation_profile(con)
    emit("3.5 total_amount reconciliation by vendor/year", by_vendor, "12b_total_reconciliation_vendor")
    emit("3.6 Most common gaps (total_amount - sum of components)", gaps, "12c_total_reconciliation_gaps")

    print("  zone usage ...")
    usage = zone_usage_profile(con)
    usage.to_csv(TABLE_DIR / "13_zone_usage.csv", index=False)
    emit("3.7 Least-used zones (pickups)", usage.head(15), "13_zone_usage_least", level=3)

    # 4. Lookup + shapefile
    report.append("## 4. Taxi zone lookup (`taxi_zone_lookup.csv`)\n")
    emit("4.1 Columns", zones["columns"], "14_lookup_columns")
    emit("4.2 Checks", zones["checks"].astype(str), "15_lookup_checks")
    emit("4.3 Zones per borough", zones["borough"], "16_lookup_borough")
    emit("4.4 Zones per service_zone", zones["service"], "17_lookup_service_zone")

    print("Profiling shapefile ...")
    shp = shapefile_profile(raw_dir, zones["df"])
    report.append("## 5. Taxi zone shapefile (`taxi_zones.shp`)\n")
    if shp is None:
        report.append("geopandas is not installed; shapefile profiling skipped.\n")
    else:
        emit("5.1 Attribute columns", shp["columns"], "18_shp_columns")
        emit("5.2 Checks", shp["checks"].astype(str), "19_shp_checks")

    out = OUT_DIR / "profiling_results.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"Done in {time.time() - started:,.0f}s -> {out.relative_to(PROJECT_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
