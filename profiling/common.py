"""Shared helpers for the read-only profiling scripts.

All scripts read the raw files in RAW_DATA_DIR (default data/raw) with DuckDB and write
CSV tables to docs/profiling/output/. Nothing is written to the warehouse.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "ingestion"))
from config import RAW_DATA_DIR  # noqa: E402

RAW_DIR = (PROJECT_ROOT / RAW_DATA_DIR).resolve() if not RAW_DATA_DIR.is_absolute() else RAW_DATA_DIR
OUT_DIR = PROJECT_ROOT / "docs" / "profiling" / "output"
SEED_DIR = PROJECT_ROOT / "dbt_project" / "seeds"
TMP_DIR = PROJECT_ROOT / "data" / ".duckdb_tmp"

TRIP_GLOB = (RAW_DIR / "yellow_tripdata_*.parquet").as_posix()
ZONE_CSV = RAW_DIR / "taxi_zone_lookup.csv"
ZONE_SHP = RAW_DIR / "taxi_zones.shp"

PERIOD_START, PERIOD_END = "2024-01-01", "2026-01-01"  # dataset scope: 24 monthly files 2024-01..2025-12
CBD_FEE_START = "2025-01-05"  # Manhattan Congestion Relief Zone toll start date
AIRPORT_ZONES = (1, 132, 138)  # EWR, JFK, LaGuardia
UNKNOWN_ZONES = (264, 265)  # "Unknown / N/A" and "Outside of NYC"

ID_COLS = ["VendorID", "RatecodeID", "payment_type", "PULocationID", "DOLocationID", "store_and_fwd_flag"]
TIME_COLS = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]
MEASURE_COLS = ["passenger_count", "trip_distance"]
COMPONENT_COLS = ["fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
                  "congestion_surcharge", "Airport_fee", "cbd_congestion_fee"]
MONEY_COLS = COMPONENT_COLS + ["total_amount"]
NATURAL_KEY = ["VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID"]


def connect() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with views over the raw files and the code seeds."""
    if not any(RAW_DIR.glob("yellow_tripdata_*.parquet")):
        raise SystemExit(f"No trip parquet files in {RAW_DIR}. Run ingestion/download_from_kaggle.py first.")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET temp_directory = '{TMP_DIR.as_posix()}'")
    con.execute("SET memory_limit = '10GB'")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET enable_progress_bar = false")
    # src_month = month in the source file name; dur_min = trip duration in minutes.
    con.execute(f"""
        CREATE VIEW trip AS
        SELECT *,
               regexp_extract(filename, 'yellow_tripdata_(\\d{{4}}-\\d{{2}})', 1) AS src_month,
               epoch(tpep_dropoff_datetime - tpep_pickup_datetime) / 60.0 AS dur_min
        FROM read_parquet('{TRIP_GLOB}', union_by_name = true, filename = true)
    """)
    con.execute(f"""
        CREATE VIEW zone AS
        SELECT * FROM read_csv('{ZONE_CSV.as_posix()}', header = true,
            columns = {{'LocationID': 'INTEGER', 'Borough': 'VARCHAR', 'Zone': 'VARCHAR', 'service_zone': 'VARCHAR'}})
    """)
    for seed in ("vendor_code", "rate_code", "payment_type_code"):
        con.execute(f"CREATE VIEW {seed} AS SELECT * FROM read_csv('{(SEED_DIR / (seed + '.csv')).as_posix()}', header = true)")
    return con


def q(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def scalar(con: duckdb.DuckDBPyConnection, sql: str):
    return con.execute(sql).fetchone()[0]


def save(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Write a table to docs/profiling/output/<name>.csv (UTF-8 with BOM so Excel shows Vietnamese)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    print(f"  -> output/{name}.csv ({len(df)} rows)")
    return df


class Timer:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        print(f"[{self.label}] ...", flush=True)
        return self

    def __exit__(self, *exc):
        print(f"[{self.label}] done in {time.time() - self.t0:.1f}s", flush=True)
