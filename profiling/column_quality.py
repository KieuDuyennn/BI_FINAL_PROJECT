"""Bảng 2.2 – Chất lượng dữ liệu theo cột, Bảng 2.3 – Phân loại dữ liệu khuyết (content profiling).

Outputs (docs/profiling/output/):
  Bang_2_2_Chat_luong_cot.csv            short table used in the report
  Bang_Chat_Luong_Cot_DayDu.csv          every metric: nulls, distinct, min/max, mean, std, skew,
                                         exact quantiles, zeros, negatives, IQR outliers
  2_2a_Phan_bo_cot_ma.csv                full value distribution of code / low-cardinality columns
  Bang_2_3_Mau_khuyet.csv                null patterns over the nullable trip columns
  2_3a_Khuyet_theo_nhom.csv              null rate of passenger_count by vendor / payment_type / month
Run: python profiling/column_quality.py
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from common import ZONE_SHP, Timer, connect, q, save

NUMERIC = ["passenger_count", "trip_distance", "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount",
           "improvement_surcharge", "congestion_surcharge", "Airport_fee", "cbd_congestion_fee", "total_amount"]
CODES = ["VendorID", "RatecodeID", "payment_type", "store_and_fwd_flag", "PULocationID", "DOLocationID"]
DISCRETE_DIST = ["VendorID", "RatecodeID", "payment_type", "store_and_fwd_flag", "passenger_count", "mta_tax",
                 "improvement_surcharge", "congestion_surcharge", "Airport_fee", "cbd_congestion_fee", "extra"]
NULLABLE = ["passenger_count", "RatecodeID", "store_and_fwd_flag", "congestion_surcharge", "Airport_fee",
            "cbd_congestion_fee"]
TIME_LIKE = ["tpep_pickup_datetime", "tpep_dropoff_datetime"]
QS = [0.01, 0.25, 0.5, 0.75, 0.99]


def fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def top_values(con, col: str, n: int = 3, total: int | None = None) -> str:
    df = q(con, f"SELECT {col} AS v, count(*) AS c FROM trip GROUP BY 1 ORDER BY 2 DESC LIMIT {n}")
    return "; ".join(f"{'NULL' if pd.isna(r.v) else fmt(r.v)} ({100 * r.c / total:.1f}%)" for r in df.itertuples())


def trip_columns(con) -> pd.DataFrame:
    types = q(con, "DESCRIBE SELECT * EXCLUDE (filename, src_month, dur_min) FROM trip")
    total = int(con.execute("SELECT count(*) FROM trip").fetchone()[0])
    rows = []
    for col, dtype in zip(types.column_name, types.column_type):
        base = con.execute(f"""SELECT count(*) - count({col}), count(DISTINCT {col}), min({col}), max({col})
                               FROM trip""").fetchone()
        r = {"bang": "yellow_tripdata", "cot": col, "kieu": dtype, "n_rows": total, "n_null": base[0],
             "pct_null": round(100 * base[0] / total, 2), "n_distinct": base[1], "min": base[2], "max": base[3]}
        if col in NUMERIC:
            s = con.execute(f"""
                SELECT avg({col}), stddev_samp({col}), skewness({col}),
                       quantile_cont({col}, {QS}),
                       count(*) FILTER (WHERE {col} = 0), count(*) FILTER (WHERE {col} < 0),
                       count(*) FILTER (WHERE {col} <> round({col}, 2))
                FROM trip""").fetchone()
            qv = s[3]
            q1, q3 = qv[1], qv[3]
            lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            n_out = con.execute(f"SELECT count(*) FROM trip WHERE {col} < {lo} OR {col} > {hi}").fetchone()[0]
            r.update({"mean": s[0], "std": s[1], "skew": s[2], "p01": qv[0], "q1": q1, "median": qv[2], "q3": q3,
                      "p99": qv[4], "n_zero": s[4], "n_negative": s[5], "n_more_than_2_decimals": s[6],
                      "iqr_low": lo, "iqr_high": hi, "n_iqr_outlier": n_out})
        if col in TIME_LIKE:
            s = con.execute(f"""SELECT count(*) FILTER (WHERE microsecond({col}) = 0),
                                       count(*) FILTER (WHERE microsecond({col}) % 1000000 <> 0)
                                FROM trip""").fetchone()
            r.update({"n_whole_minute": s[0], "n_fractional_second": s[1]})
        if col in CODES or col in DISCRETE_DIST:
            r["top3"] = top_values(con, col, 3, total)
        rows.append(r)
    return pd.DataFrame(rows)



def lookup_columns(con) -> pd.DataFrame:
    zone = q(con, "SELECT * FROM zone")
    rows = []
    for col in zone.columns:
        s = zone[col]
        vc = s.value_counts(dropna=False)
        rows.append({"bang": "taxi_zone_lookup", "cot": col, "kieu": str(s.dtype), "n_rows": len(s),
                     "n_null": int(s.isna().sum()), "pct_null": round(100 * s.isna().mean(), 2),
                     "n_distinct": int(s.nunique()), "min": s.min() if col == "LocationID" else None,
                     "max": s.max() if col == "LocationID" else None,
                     "top3": "; ".join(f"{k} ({v})" for k, v in vc.head(3).items()),
                     "n_duplicated_values": int(s.duplicated(keep=False).sum())})
    shp = gpd.read_file(ZONE_SHP)
    for col in shp.columns:
        s = shp[col]
        if col == "geometry":
            rows.append({"bang": "taxi_zones.shp", "cot": col, "kieu": ",".join(sorted(s.geom_type.unique())),
                         "n_rows": len(s), "n_null": int(s.isna().sum()), "pct_null": 0,
                         "n_distinct": len(s), "top3": f"invalid={int((~s.is_valid).sum())}; empty={int(s.is_empty.sum())}"})
            continue
        vc = s.value_counts(dropna=False)
        numeric = pd.api.types.is_numeric_dtype(s)
        rows.append({"bang": "taxi_zones.shp", "cot": col, "kieu": str(s.dtype), "n_rows": len(s),
                     "n_null": int(s.isna().sum()), "pct_null": round(100 * s.isna().mean(), 2),
                     "n_distinct": int(s.nunique()), "min": s.min() if numeric else None,
                     "max": s.max() if numeric else None,
                     "top3": "; ".join(f"{k} ({v})" for k, v in vc.head(3).items()),
                     "n_duplicated_values": int(s.duplicated(keep=False).sum())})
    return pd.DataFrame(rows)


def short_table(full: pd.DataFrame) -> pd.DataFrame:
    def domain(r):
        if r.cot in CODES or (isinstance(r.get("top3"), str) and r.cot not in NUMERIC):
            return r.top3
        if r.cot in NUMERIC:
            return f"{fmt(r['min'])} – {fmt(r['max'])} (trung vị {fmt(r['median'])})"
        return f"{r['min']} → {r['max']}"

    out = full.copy()
    out["mien_gia_tri"] = out.apply(domain, axis=1)
    return out[["bang", "cot", "kieu", "pct_null", "n_distinct", "mien_gia_tri"]]


def null_patterns(con) -> tuple[pd.DataFrame, pd.DataFrame]:
    flags = ", ".join(f"({c} IS NULL)::INT AS {c}_null" for c in NULLABLE)
    grp = ", ".join(f"{c}_null" for c in NULLABLE)
    patterns = q(con, f"""
        WITH t AS (SELECT {flags}, payment_type, VendorID, src_month FROM trip)
        SELECT {grp}, count(*) AS n_rows,
               round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_rows,
               string_agg(DISTINCT payment_type::VARCHAR, ',' ORDER BY payment_type::VARCHAR) AS payment_types,
               string_agg(DISTINCT VendorID::VARCHAR, ',' ORDER BY VendorID::VARCHAR) AS vendors,
               min(src_month) AS first_month, max(src_month) AS last_month
        FROM t GROUP BY ALL ORDER BY n_rows DESC""")
    by_group = []
    for dim in ("VendorID", "payment_type", "src_month", "year(tpep_pickup_datetime)"):
        df = q(con, f"""
            SELECT '{dim}' AS group_by, CAST({dim} AS VARCHAR) AS group_value, count(*) AS n_rows,
                   count(*) FILTER (WHERE passenger_count IS NULL) AS n_null_block,
                   round(100.0 * count(*) FILTER (WHERE passenger_count IS NULL) / count(*), 2) AS pct_null_block,
                   count(*) FILTER (WHERE payment_type = 0) AS n_payment_type_0,
                   count(*) FILTER (WHERE cbd_congestion_fee IS NULL) AS n_cbd_null
            FROM trip GROUP BY ALL ORDER BY group_value""")
        by_group.append(df)
    return patterns, pd.concat(by_group, ignore_index=True)


def distributions(con) -> pd.DataFrame:
    parts = []
    for col in DISCRETE_DIST:
        df = q(con, f"""SELECT '{col}' AS cot, CAST({col} AS VARCHAR) AS value, count(*) AS n_rows,
                               round(100.0 * count(*) / sum(count(*)) OVER (), 4) AS pct
                        FROM trip GROUP BY 2 ORDER BY 3 DESC LIMIT 40""")
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    con = connect()
    with Timer("trip columns"):
        trip = trip_columns(con)
    with Timer("lookup + shapefile columns"):
        lk = lookup_columns(con)
    full = pd.concat([trip, lk], ignore_index=True)
    save(full, "Bang_Chat_Luong_Cot_DayDu")
    save(short_table(full), "Bang_2_2_Chat_luong_cot")
    with Timer("distributions"):
        save(distributions(con), "2_2a_Phan_bo_cot_ma")
    with Timer("null patterns"):
        patterns, by_group = null_patterns(con)
        save(patterns, "Bang_2_3_Mau_khuyet")
        save(by_group, "2_3a_Khuyet_theo_nhom")


if __name__ == "__main__":
    main()
