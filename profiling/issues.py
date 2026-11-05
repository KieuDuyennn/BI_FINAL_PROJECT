"""Bảng 2.5 – Các vấn đề dữ liệu: bằng chứng số liệu cho từng vấn đề (anomaly profiling).

Every number quoted in the "Bằng chứng" column of Bảng 2.5 comes from this script.
Outputs (docs/profiling/output/):
  Bang_2_5_Bang_chung.csv                issue_key, metric, value  (long format, one metric per row)
  2_5a_Tien_am_theo_payment.csv          negative fare/total rows by payment_type
  2_5b_Doi_soat_total_vendor_nam.csv     total_amount vs. sum of components, by vendor × year
  2_5c_Do_lech_total_pho_bien.csv        most frequent (total − Σ components) gaps
  2_5d_Bat_thuong_theo_thang.csv         main anomaly flags by source month
  2_5e_Tip_theo_payment.csv              tip recording by payment_type
  2_5f_Tien_cuc_tri.csv                  the 25 largest total_amount rows
  2_5g_Chi_so_cuoc_vendor_thang.csv      median fare / fare per mile / duration by vendor × month
  2_5h_Phu_phi_gia_tri.csv               value distribution of the fixed surcharges
Run: python profiling/issues.py
"""

from __future__ import annotations

import pandas as pd

from common import (AIRPORT_ZONES, CBD_FEE_START, NATURAL_KEY, PERIOD_END, PERIOD_START, UNKNOWN_ZONES, Timer,
                    connect, q, save)

COMPONENT_SUM = ("fare_amount + extra + mta_tax + tip_amount + tolls_amount + improvement_surcharge"
                 " + coalesce(congestion_surcharge, 0) + coalesce(Airport_fee, 0) + coalesce(cbd_congestion_fee, 0)")
IN_SCOPE = f"tpep_pickup_datetime >= TIMESTAMP '{PERIOD_START}' AND tpep_pickup_datetime < TIMESTAMP '{PERIOD_END}'"
DST_SPRING = ("2024-03-10", "2025-03-09")  # 02:00–02:59 does not exist (clocks jump to 03:00)
DST_FALL = ("2024-11-03", "2025-11-02")  # 01:00–01:59 happens twice

evidence: list[dict] = []


def put(con, key: str, metrics: dict[str, str]) -> None:
    """Run one SELECT with many named aggregates over trip and store each as a metric row."""
    sql = "SELECT " + ",\n".join(f"{expr} AS \"{name}\"" for name, expr in metrics.items()) + " FROM trip"
    row = con.execute(sql).fetchone()
    for name, val in zip(metrics, row):
        evidence.append({"issue_key": key, "metric": name, "value": val})


def put_value(key: str, name: str, val) -> None:
    evidence.append({"issue_key": key, "metric": name, "value": val})


def main() -> None:
    con = connect()
    nk = ", ".join(NATURAL_KEY)

    with Timer("schema / nulls / period"):
        put(con, "schema_cbd", {
            "rows_2024_files": "count(*) FILTER (WHERE src_month < '2025-01')",
            "cbd_null_2024_files": "count(*) FILTER (WHERE src_month < '2025-01' AND cbd_congestion_fee IS NULL)",
            "cbd_null_2025_files": "count(*) FILTER (WHERE src_month >= '2025-01' AND cbd_congestion_fee IS NULL)",
            "cbd_gt0_before_start": f"count(*) FILTER (WHERE cbd_congestion_fee > 0 AND tpep_pickup_datetime < TIMESTAMP '{CBD_FEE_START}')",
            "cbd_gt0_2025_files": "count(*) FILTER (WHERE src_month >= '2025-01' AND cbd_congestion_fee > 0)",
        })
        put(con, "null_block", {
            "rows_total": "count(*)",
            "null_block_rows": "count(*) FILTER (WHERE passenger_count IS NULL)",
            "payment_type_0_rows": "count(*) FILTER (WHERE payment_type = 0)",
            "null_block_and_pt0": "count(*) FILTER (WHERE passenger_count IS NULL AND payment_type = 0)",
            "null_block_vendor1": "count(*) FILTER (WHERE passenger_count IS NULL AND VendorID = 1)",
            "null_block_vendor2": "count(*) FILTER (WHERE passenger_count IS NULL AND VendorID = 2)",
            "null_block_vendor6": "count(*) FILTER (WHERE passenger_count IS NULL AND VendorID = 6)",
            "vendor6_rows": "count(*) FILTER (WHERE VendorID = 6)",
            "null_block_fare_neg": "count(*) FILTER (WHERE passenger_count IS NULL AND fare_amount < 0)",
            "null_block_fare_neg_total_pos": "count(*) FILTER (WHERE passenger_count IS NULL AND fare_amount < 0 AND total_amount > 0)",
            "null_block_tip_gt0": "count(*) FILTER (WHERE passenger_count IS NULL AND tip_amount > 0)",
            "null_block_total_sum": "round(sum(total_amount) FILTER (WHERE passenger_count IS NULL), 2)",
            "total_sum_all": "round(sum(total_amount), 2)",
            "null_block_pct_2024_01": "round(100.0 * count(*) FILTER (WHERE passenger_count IS NULL AND src_month = '2024-01') / count(*) FILTER (WHERE src_month = '2024-01'), 2)",
            "null_block_pct_2025_06": "round(100.0 * count(*) FILTER (WHERE passenger_count IS NULL AND src_month = '2025-06') / count(*) FILTER (WHERE src_month = '2025-06'), 2)",
        })
        put(con, "out_of_period", {
            "pickup_year_not_2024_2025": f"count(*) FILTER (WHERE NOT ({IN_SCOPE}))",
            "years_found": f"string_agg(DISTINCT year(tpep_pickup_datetime)::VARCHAR, ',') FILTER (WHERE NOT ({IN_SCOPE}))",
            "pickup_month_ne_file_month": "count(*) FILTER (WHERE strftime(tpep_pickup_datetime, '%Y-%m') <> src_month)",
            "in_scope_but_other_file": f"count(*) FILTER (WHERE {IN_SCOPE} AND strftime(tpep_pickup_datetime, '%Y-%m') <> src_month)",
            "of_which_prev_month_late_night": f"count(*) FILTER (WHERE {IN_SCOPE} AND strftime(tpep_pickup_datetime, '%Y-%m') <> src_month AND tpep_dropoff_datetime >= strptime(src_month || '-01', '%Y-%m-%d'))",
            "dropoff_year_gt_2025": "count(*) FILTER (WHERE tpep_dropoff_datetime >= TIMESTAMP '2026-01-01')",
        })

    with Timer("time / duration"):
        put(con, "duration", {
            "dropoff_before_pickup": "count(*) FILTER (WHERE dur_min < 0)",
            "duration_zero": "count(*) FILTER (WHERE dur_min = 0)",
            "duration_lt_1min": "count(*) FILTER (WHERE dur_min >= 0 AND dur_min < 1)",
            "duration_gt_3h": "count(*) FILTER (WHERE dur_min > 180)",
            "duration_gt_24h": "count(*) FILTER (WHERE dur_min > 1440)",
            "duration_max_h": "round(max(dur_min) / 60, 1)",
            "duration_median_min": "round(median(dur_min) FILTER (WHERE dur_min > 0), 2)",
            "duration_p99_min": "round(quantile_cont(dur_min, 0.99) FILTER (WHERE dur_min > 0), 2)",
            "helix_rows": "count(*) FILTER (WHERE VendorID = 7)",
            "helix_duration_zero": "count(*) FILTER (WHERE VendorID = 7 AND dur_min = 0)",
            "helix_duration_zero_dist_gt0": "count(*) FILTER (WHERE VendorID = 7 AND dur_min = 0 AND trip_distance > 0)",
            "non_helix_duration_zero": "count(*) FILTER (WHERE VendorID <> 7 AND dur_min = 0)",
            "whole_minute_pickup": "count(*) FILTER (WHERE microsecond(tpep_pickup_datetime) = 0)",
        })
        spring = " OR ".join(f"(tpep_pickup_datetime >= TIMESTAMP '{d} 02:00:00' AND tpep_pickup_datetime < TIMESTAMP '{d} 03:00:00')" for d in DST_SPRING)
        fall = " OR ".join(f"CAST(tpep_pickup_datetime AS DATE) = DATE '{d}'" for d in DST_FALL)
        put(con, "dst", {
            "pickup_in_nonexistent_hour": f"count(*) FILTER (WHERE {spring})",
            "fall_back_days_dropoff_before_pickup": f"count(*) FILTER (WHERE ({fall}) AND dur_min < 0)",
            "fall_back_days_neg_between_-60_0": f"count(*) FILTER (WHERE ({fall}) AND dur_min < 0 AND dur_min >= -60)",
            "all_dropoff_before_pickup": "count(*) FILTER (WHERE dur_min < 0)",
            "neg_between_-60_0_all": "count(*) FILTER (WHERE dur_min < 0 AND dur_min >= -60)",
        })

    with Timer("refunds / duplicates"):
        put(con, "negative_money", {
            "fare_lt0": "count(*) FILTER (WHERE fare_amount < 0)",
            "total_lt0": "count(*) FILTER (WHERE total_amount < 0)",
            "total_lt0_all_components_le0": f"count(*) FILTER (WHERE total_amount < 0 AND fare_amount <= 0 AND extra <= 0 AND mta_tax <= 0 AND tip_amount <= 0 AND tolls_amount <= 0 AND improvement_surcharge <= 0 AND coalesce(congestion_surcharge, 0) <= 0 AND coalesce(Airport_fee, 0) <= 0 AND coalesce(cbd_congestion_fee, 0) <= 0)",
            "total_lt0_sum": "round(sum(total_amount) FILTER (WHERE total_amount < 0), 2)",
            "total_eq0": "count(*) FILTER (WHERE total_amount = 0)",
            "fare_lt0_total_gt0": "count(*) FILTER (WHERE fare_amount < 0 AND total_amount > 0)",
        })
        save(q(con, """
            SELECT payment_type, count(*) AS n_rows,
                   count(*) FILTER (WHERE fare_amount < 0) AS n_fare_lt0,
                   count(*) FILTER (WHERE total_amount < 0) AS n_total_lt0,
                   round(100.0 * count(*) FILTER (WHERE total_amount < 0) / count(*), 2) AS pct_total_lt0,
                   round(sum(total_amount) FILTER (WHERE total_amount < 0), 2) AS sum_negative_total
            FROM trip GROUP BY 1 ORDER BY 1"""), "2_5a_Tien_am_theo_payment")

        dup = con.execute(f"""
            WITH g AS (
                SELECT count(*) AS c,
                       count(*) FILTER (WHERE total_amount < 0) AS n_neg,
                       count(*) FILTER (WHERE total_amount > 0) AS n_pos,
                       round(sum(total_amount), 2) AS s
                FROM trip GROUP BY {nk} HAVING count(*) > 1)
            SELECT count(*), sum(c),
                   count(*) FILTER (WHERE c = 2 AND n_neg = 1 AND n_pos = 1 AND s = 0),
                   count(*) FILTER (WHERE n_neg > 0),
                   max(c)
            FROM g""").fetchone()
        for name, val in zip(["dup_key_groups", "dup_key_rows", "reversal_pairs_sum0", "groups_with_negative",
                              "max_rows_per_key"], dup):
            put_value("duplicates", name, val)
        all_cols = ", ".join(c for c in q(con, "DESCRIBE SELECT * EXCLUDE (filename, src_month, dur_min) FROM trip").column_name)
        put_value("duplicates", "full_duplicate_extra_rows", con.execute(
            f"SELECT coalesce(sum(c - 1), 0) FROM (SELECT count(*) AS c FROM trip GROUP BY {all_cols} HAVING count(*) > 1)").fetchone()[0])
        neg_unmatched = con.execute(f"""
            WITH n AS (SELECT {nk}, total_amount FROM trip WHERE total_amount < 0),
                 p AS (SELECT {nk}, total_amount FROM trip WHERE total_amount > 0)
            SELECT count(*) FROM n ANTI JOIN p
              ON n.VendorID = p.VendorID AND n.tpep_pickup_datetime = p.tpep_pickup_datetime
             AND n.tpep_dropoff_datetime = p.tpep_dropoff_datetime AND n.PULocationID = p.PULocationID
             AND n.DOLocationID = p.DOLocationID AND n.total_amount = -p.total_amount""").fetchone()[0]
        put_value("duplicates", "negative_rows_without_positive_twin", neg_unmatched)

    with Timer("total reconciliation"):
        put(con, "total_recon", {
            "gap_eq0": f"count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) < 0.005)",
            "gap_ne0": f"count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) >= 0.005)",
            "gap_ne0_pct": f"round(100.0 * count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) >= 0.005) / count(*), 2)",
            "gap_sum": f"round(sum(total_amount - ({COMPONENT_SUM})), 2)",
        })
        save(q(con, f"""
            SELECT VendorID, year(tpep_pickup_datetime) AS year, count(*) AS n_rows,
                   count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) >= 0.005) AS n_gap,
                   round(100.0 * count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) >= 0.005) / count(*), 2) AS pct_gap,
                   round(sum(total_amount - ({COMPONENT_SUM})), 2) AS sum_gap
            FROM trip WHERE {IN_SCOPE} GROUP BY ALL ORDER BY 1, 2"""), "2_5b_Doi_soat_total_vendor_nam")
        save(q(con, f"""
            SELECT round(total_amount - ({COMPONENT_SUM}), 2) AS gap, count(*) AS n_rows,
                   string_agg(DISTINCT VendorID::VARCHAR, ',') AS vendors
            FROM trip GROUP BY 1 ORDER BY 2 DESC LIMIT 15"""), "2_5c_Do_lech_total_pho_bien")

    with Timer("distance / passengers / codes / zones"):
        put(con, "distance", {
            "distance_zero": "count(*) FILTER (WHERE trip_distance = 0)",
            "distance_zero_dur_gt_1min": "count(*) FILTER (WHERE trip_distance = 0 AND dur_min > 1)",
            "distance_gt_100": "count(*) FILTER (WHERE trip_distance > 100)",
            "distance_max": "max(trip_distance)",
            "distance_p99": "round(quantile_cont(trip_distance, 0.99), 2)",
            "distance_p999": "round(quantile_cont(trip_distance, 0.999), 2)",
            "speed_gt_80mph": "count(*) FILTER (WHERE dur_min > 0 AND trip_distance / (dur_min / 60) > 80)",
            "fare_gt0_dist0_dur0": "count(*) FILTER (WHERE fare_amount > 0 AND trip_distance = 0 AND dur_min = 0)",
            "same_zone_dist_gt_20": "count(*) FILTER (WHERE PULocationID = DOLocationID AND PULocationID NOT IN (264, 265) AND trip_distance > 20)",
        })
        put(con, "passenger", {
            "passenger_null": "count(*) FILTER (WHERE passenger_count IS NULL)",
            "passenger_0": "count(*) FILTER (WHERE passenger_count = 0)",
            "passenger_1": "count(*) FILTER (WHERE passenger_count = 1)",
            "passenger_2_4": "count(*) FILTER (WHERE passenger_count BETWEEN 2 AND 4)",
            "passenger_5_6": "count(*) FILTER (WHERE passenger_count BETWEEN 5 AND 6)",
            "passenger_gt6": "count(*) FILTER (WHERE passenger_count > 6)",
            "passenger_0_vendor1": "count(*) FILTER (WHERE passenger_count = 0 AND VendorID = 1)",
        })
        put(con, "ratecode", {
            "ratecode_null": "count(*) FILTER (WHERE RatecodeID IS NULL)",
            "ratecode_99": "count(*) FILTER (WHERE RatecodeID = 99)",
            "ratecode_99_vendor1": "count(*) FILTER (WHERE RatecodeID = 99 AND VendorID = 1)",
            "ratecode_99_payment": "string_agg(DISTINCT payment_type::VARCHAR, ',') FILTER (WHERE RatecodeID = 99)",
            "ratecode_99_fare_median": "round(median(fare_amount) FILTER (WHERE RatecodeID = 99), 2)",
            "jfk_rate_rows": "count(*) FILTER (WHERE RatecodeID = 2)",
            "jfk_rate_no_jfk_zone": "count(*) FILTER (WHERE RatecodeID = 2 AND PULocationID <> 132 AND DOLocationID <> 132)",
            "newark_rate_rows": "count(*) FILTER (WHERE RatecodeID = 3)",
            "newark_rate_not_to_ewr": "count(*) FILTER (WHERE RatecodeID = 3 AND DOLocationID <> 1 AND PULocationID <> 1)",
            "group_ride_rows": "count(*) FILTER (WHERE RatecodeID = 6)",
        })
        put(con, "zones", {
            "pu_unknown_264_265": f"count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES})",
            "do_unknown_264_265": f"count(*) FILTER (WHERE DOLocationID IN {UNKNOWN_ZONES})",
            "pu_or_do_unknown": f"count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES} OR DOLocationID IN {UNKNOWN_ZONES})",
            "pu_and_do_unknown": f"count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES} AND DOLocationID IN {UNKNOWN_ZONES})",
            "total_amount_pu_unknown": f"round(sum(total_amount) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES}), 2)",
        })
        put(con, "vendor", {
            "vendor1_cmt": "count(*) FILTER (WHERE VendorID = 1)",
            "vendor2_vts": "count(*) FILTER (WHERE VendorID = 2)",
            "vendor6_myle": "count(*) FILTER (WHERE VendorID = 6)",
            "vendor7_helix": "count(*) FILTER (WHERE VendorID = 7)",
            "vendor6_first_month": "min(src_month) FILTER (WHERE VendorID = 6)",
            "vendor7_first_month": "min(src_month) FILTER (WHERE VendorID = 7)",
            "vendor6_median_fare": "round(median(fare_amount) FILTER (WHERE VendorID = 6), 2)",
            "vendor6_median_total": "round(median(total_amount) FILTER (WHERE VendorID = 6), 2)",
        })

    with Timer("money rules"):
        put(con, "money_outlier", {
            "fare_gt_500": "count(*) FILTER (WHERE fare_amount > 500)",
            "total_gt_1000": "count(*) FILTER (WHERE total_amount > 1000)",
            "total_gt_1000_sum": "round(sum(total_amount) FILTER (WHERE total_amount > 1000), 2)",
            "total_gt_1000_vendor1": "count(*) FILTER (WHERE total_amount > 1000 AND VendorID = 1)",
            "total_gt_100k": "count(*) FILTER (WHERE total_amount > 100000)",
            "total_gt_100k_sum": "round(sum(total_amount) FILTER (WHERE total_amount > 100000), 2)",
            "fare_max": "max(fare_amount)",
            "mta_tax_max": "max(mta_tax)",
            "tolls_gt_200": "count(*) FILTER (WHERE tolls_amount > 200)",
            "tip_gt_fare": "count(*) FILTER (WHERE tip_amount > fare_amount AND fare_amount > 0)",
            "tip_gt_fare_and_gt_50": "count(*) FILTER (WHERE tip_amount > fare_amount AND fare_amount > 0 AND tip_amount > 50)",
        })
        save(q(con, "SELECT src_month, VendorID, PULocationID, DOLocationID, tpep_pickup_datetime, round(dur_min, 1) AS dur_min, "
                    "trip_distance, RatecodeID, payment_type, fare_amount, mta_tax, tip_amount, tolls_amount, total_amount "
                    "FROM trip ORDER BY total_amount DESC LIMIT 25"), "2_5f_Tien_cuc_tri")
        save(q(con, """
            SELECT payment_type, count(*) AS n_rows,
                   count(*) FILTER (WHERE tip_amount > 0) AS n_tip_gt0,
                   round(100.0 * count(*) FILTER (WHERE tip_amount > 0) / count(*), 2) AS pct_tip_gt0,
                   round(avg(tip_amount), 2) AS avg_tip,
                   round(100 * median(tip_amount / fare_amount) FILTER (WHERE fare_amount > 0), 2) AS median_tip_pct_of_fare
            FROM trip GROUP BY 1 ORDER BY 1"""), "2_5e_Tip_theo_payment")
        put(con, "surcharge_rules", {
            "airport_fee_gt0": "count(*) FILTER (WHERE Airport_fee > 0)",
            "airport_fee_gt0_pu_not_airport": f"count(*) FILTER (WHERE Airport_fee > 0 AND PULocationID NOT IN {AIRPORT_ZONES})",
            "airport_fee_gt0_pu_not_airport_do_airport": f"count(*) FILTER (WHERE Airport_fee > 0 AND PULocationID NOT IN {AIRPORT_ZONES} AND DOLocationID IN {AIRPORT_ZONES})",
            "airport_fee_0_pu_lga_jfk": "count(*) FILTER (WHERE Airport_fee = 0 AND PULocationID IN (132, 138) AND fare_amount > 0)",
            "mta_tax_nonstandard": "count(*) FILTER (WHERE mta_tax NOT IN (0, 0.5, -0.5))",
            "improvement_nonstandard": "count(*) FILTER (WHERE improvement_surcharge NOT IN (0, 1, -1))",
            "congestion_nonstandard": "count(*) FILTER (WHERE congestion_surcharge NOT IN (0, 2.5, -2.5))",
            "cbd_nonstandard": "count(*) FILTER (WHERE cbd_congestion_fee NOT IN (0, 0.75, -0.75))",
            "cash_tip_gt0": "count(*) FILTER (WHERE payment_type = 2 AND tip_amount > 0)",
        })
        parts = []
        for col in ["mta_tax", "improvement_surcharge", "congestion_surcharge", "Airport_fee", "cbd_congestion_fee"]:
            parts.append(q(con, f"""SELECT '{col}' AS cot, {col} AS value, count(*) AS n_rows,
                                           string_agg(DISTINCT VendorID::VARCHAR, ',') AS vendors
                                    FROM trip GROUP BY 2 ORDER BY 3 DESC"""))
        save(pd.concat(parts, ignore_index=True), "2_5h_Phu_phi_gia_tri")

    with Timer("monthly views"):
        save(q(con, f"""
            SELECT src_month, count(*) AS n_rows,
                   count(*) FILTER (WHERE passenger_count IS NULL) AS n_null_block,
                   count(*) FILTER (WHERE total_amount < 0) AS n_total_lt0,
                   count(*) FILTER (WHERE abs(total_amount - ({COMPONENT_SUM})) >= 0.005) AS n_total_gap,
                   count(*) FILTER (WHERE trip_distance = 0) AS n_distance0,
                   count(*) FILTER (WHERE dur_min <= 0) AS n_duration_le0,
                   count(*) FILTER (WHERE passenger_count = 0) AS n_passenger0,
                   count(*) FILTER (WHERE RatecodeID = 99) AS n_ratecode99,
                   count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES} OR DOLocationID IN {UNKNOWN_ZONES}) AS n_unknown_zone
            FROM trip GROUP BY 1 ORDER BY 1"""), "2_5d_Bat_thuong_theo_thang")
        save(q(con, """
            SELECT src_month, VendorID, count(*) AS n_rows,
                   round(median(fare_amount) FILTER (WHERE fare_amount > 0), 2) AS median_fare,
                   round(median(fare_amount / trip_distance) FILTER (WHERE RatecodeID = 1 AND trip_distance BETWEEN 1 AND 3 AND fare_amount > 0), 2) AS median_fare_per_mile_std_1_3mi,
                   round(median(trip_distance), 2) AS median_distance,
                   round(median(dur_min), 2) AS median_duration_min,
                   round(avg(total_amount) FILTER (WHERE total_amount BETWEEN 0 AND 1000), 2) AS avg_total_0_1000
            FROM trip GROUP BY ALL ORDER BY 2, 1"""), "2_5g_Chi_so_cuoc_vendor_thang")

    save(pd.DataFrame(evidence), "Bang_2_5_Bang_chung")


if __name__ == "__main__":
    main()
