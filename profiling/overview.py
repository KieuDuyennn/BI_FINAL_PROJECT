"""Bảng 2.1 – Tổng quan các bảng nguồn (structure profiling).

Outputs (docs/profiling/output/):
  Bang_2_1_Tong_quan_bang.csv       one row per source table
  2_1a_File_nguon.csv               one row per trip parquet file (size, rows, schema, out-of-month rows)
  2_1b_So_chuyen_theo_thang.csv     trips by pickup month (in-scope only) vs. file month
  2_1c_Do_phu_theo_ngay.csv         daily coverage summary (days without trips, min/max per day)
Run: python profiling/overview.py
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq

from common import (NATURAL_KEY, PERIOD_END, PERIOD_START, RAW_DIR, ZONE_CSV, ZONE_SHP, Timer, connect, q,
                    save, scalar)


BOM = bytes([0xEF, 0xBB, 0xBF])


def file_table(con) -> pd.DataFrame:
    rows = []
    per_file = q(con, f"""
        SELECT src_month,
               count(*) AS n_rows,
               min(tpep_pickup_datetime) AS min_pickup,
               max(tpep_pickup_datetime) AS max_pickup,
               count(*) FILTER (WHERE strftime(tpep_pickup_datetime, '%Y-%m') <> src_month) AS n_pickup_outside_file_month
        FROM trip GROUP BY src_month ORDER BY src_month""").set_index("src_month")
    for f in sorted(RAW_DIR.glob("yellow_tripdata_*.parquet")):
        month = f.stem.split("_")[-1]
        meta = pq.read_metadata(f)
        names = meta.schema.to_arrow_schema().names
        r = per_file.loc[month]
        rows.append({
            "file": f.name, "src_month": month, "size_mb": round(f.stat().st_size / 1e6, 1),
            "n_rows": meta.num_rows, "n_cols": len(names), "row_groups": meta.num_row_groups,
            "has_cbd_congestion_fee": "cbd_congestion_fee" in names,
            "min_pickup": r.min_pickup, "max_pickup": r.max_pickup,
            "n_pickup_outside_file_month": int(r.n_pickup_outside_file_month),
            "pct_outside": round(100 * r.n_pickup_outside_file_month / meta.num_rows, 4),
        })
    return pd.DataFrame(rows)


def main() -> None:
    con = connect()

    with Timer("file level"):
        files = save(file_table(con), "2_1a_File_nguon")

    with Timer("monthly / daily coverage"):
        monthly = q(con, f"""
            SELECT strftime(tpep_pickup_datetime, '%Y-%m') AS pickup_month,
                   count(*) AS n_trips,
                   count(*) FILTER (WHERE src_month = strftime(tpep_pickup_datetime, '%Y-%m')) AS n_from_own_file,
                   sum(passenger_count) AS sum_passengers,
                   round(sum(total_amount), 2) AS sum_total_amount
            FROM trip
            WHERE tpep_pickup_datetime >= TIMESTAMP '{PERIOD_START}' AND tpep_pickup_datetime < TIMESTAMP '{PERIOD_END}'
            GROUP BY 1 ORDER BY 1""")
        monthly["pct_change_vs_prev_month"] = (monthly["n_trips"].pct_change() * 100).round(2)
        save(monthly, "2_1b_So_chuyen_theo_thang")

        daily = q(con, f"""
            WITH d AS (
                SELECT CAST(tpep_pickup_datetime AS DATE) AS day, count(*) AS n
                FROM trip
                WHERE tpep_pickup_datetime >= TIMESTAMP '{PERIOD_START}' AND tpep_pickup_datetime < TIMESTAMP '{PERIOD_END}'
                GROUP BY 1),
            cal AS (SELECT CAST(range AS DATE) AS day FROM range(DATE '{PERIOD_START}', DATE '{PERIOD_END}', INTERVAL 1 DAY))
            SELECT cal.day, coalesce(d.n, 0) AS n_trips FROM cal LEFT JOIN d USING (day) ORDER BY cal.day""")
        med = daily["n_trips"].median()
        low = daily[daily["n_trips"] < 0.5 * med]
        coverage = pd.DataFrame([
            {"metric": "calendar_days", "value": len(daily)},
            {"metric": "days_with_zero_trips", "value": int((daily["n_trips"] == 0).sum())},
            {"metric": "median_trips_per_day", "value": med},
            {"metric": "min_trips_per_day", "value": int(daily["n_trips"].min())},
            {"metric": "min_day", "value": str(daily.loc[daily["n_trips"].idxmin(), "day"])},
            {"metric": "max_trips_per_day", "value": int(daily["n_trips"].max())},
            {"metric": "max_day", "value": str(daily.loc[daily["n_trips"].idxmax(), "day"])},
            {"metric": "days_below_50pct_median", "value": len(low)},
            {"metric": "days_below_50pct_median_list",
             "value": "; ".join(f"{r.day} ({r.n_trips:,})" for r in low.itertuples())},
        ])
        save(coverage, "2_1c_Do_phu_theo_ngay")
        save(daily, "2_1d_So_chuyen_theo_ngay")

    with Timer("table summary"):
        n_trip = int(files["n_rows"].sum())
        nk = ", ".join(NATURAL_KEY)
        dup_nk_rows = scalar(con, f"""
            SELECT coalesce(sum(c), 0) FROM (SELECT count(*) AS c FROM trip GROUP BY {nk} HAVING count(*) > 1)""")
        t_min, t_max = con.execute("SELECT min(tpep_pickup_datetime), max(tpep_pickup_datetime) FROM trip").fetchone()
        in_scope = scalar(con, f"""SELECT count(*) FROM trip WHERE tpep_pickup_datetime >= TIMESTAMP '{PERIOD_START}'
                                   AND tpep_pickup_datetime < TIMESTAMP '{PERIOD_END}'""")

        zone = q(con, "SELECT * FROM zone")
        shp = gpd.read_file(ZONE_SHP)
        has_bom = ZONE_CSV.read_bytes().startswith(BOM)

        summary = pd.DataFrame([
            {"bang": "yellow_tripdata (24 file parquet)", "dinh_dang": "Parquet, 1 file/tháng",
             "moi_dong_la": "1 bản ghi chuyến đi do thiết bị đồng hồ (TPEP) gửi lên; có cả dòng điều chỉnh/hoàn tiền",
             "so_dong": n_trip, "so_cot": f"{files.n_cols.min()}–{files.n_cols.max()}",
             "khoa_du_kien": f"Không có cột ID; khóa tự nhiên {nk}",
             "khoa_duy_nhat": f"Không ({dup_nk_rows:,} dòng thuộc nhóm trùng khóa)",
             "pham_vi_thoi_gian": f"{t_min} → {t_max} (tpep_pickup_datetime); trong kỳ 2024–2025: {in_scope:,} dòng",
             "dung_luong_mb": round(files.size_mb.sum(), 1)},
            {"bang": "taxi_zone_lookup.csv", "dinh_dang": f"CSV có dấu nháy, CRLF, BOM={has_bom}",
             "moi_dong_la": "1 taxi zone của TLC", "so_dong": len(zone), "so_cot": zone.shape[1],
             "khoa_du_kien": "LocationID", "khoa_duy_nhat": "Có" if zone.LocationID.is_unique else "Không",
             "pham_vi_thoi_gian": "Không có", "dung_luong_mb": round(ZONE_CSV.stat().st_size / 1e6, 3)},
            {"bang": "taxi_zones.shp (+.dbf/.shx/.prj/.cpg)", "dinh_dang": f"ESRI Shapefile, CRS {shp.crs.to_epsg()}",
             "moi_dong_la": "1 polygon/multipolygon ranh giới của 1 zone", "so_dong": len(shp),
             "so_cot": shp.shape[1], "khoa_du_kien": "LocationID",
             "khoa_duy_nhat": "Có" if shp.LocationID.is_unique else
                 f"Không ({int(shp.LocationID.duplicated(keep=False).sum())} dòng trùng LocationID)",
             "pham_vi_thoi_gian": "Không có",
             "dung_luong_mb": round(sum(p.stat().st_size for p in RAW_DIR.glob("taxi_zones.*")) / 1e6, 2)},
        ])
        save(summary, "Bang_2_1_Tong_quan_bang")


if __name__ == "__main__":
    main()
