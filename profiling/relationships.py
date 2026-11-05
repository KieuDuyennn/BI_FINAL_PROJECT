"""Bảng 2.4 – Quan hệ giữa các bảng nguồn (relationship profiling).

Checks every foreign key of the trip data against the zone lookup and the TLC code lists
(dbt seeds), and the 1-1 match between the zone lookup and the zone shapefile.

Outputs (docs/profiling/output/):
  Bang_2_4_Quan_he.csv          one row per relationship: unmatched rows/values, cardinality, facts
  2_4a_Zone_su_dung.csv         pickups / drop-offs per LocationID joined to lookup + shapefile presence
  2_4b_Lookup_vs_shapefile.csv  LocationIDs whose name / borough differ between lookup and shapefile
  2_4c_Tuyen_pho_bien.csv       top 20 PU→DO routes (in-scope trips)
Run: python profiling/relationships.py
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from common import PERIOD_END, PERIOD_START, UNKNOWN_ZONES, ZONE_SHP, Timer, connect, q, save, scalar


def fk_check(con, child_col: str, parent: str, parent_col: str) -> dict:
    r = con.execute(f"""
        SELECT count(*) FILTER (WHERE t.{child_col} IS NOT NULL AND p.{parent_col} IS NULL),
               count(DISTINCT t.{child_col}) FILTER (WHERE t.{child_col} IS NOT NULL AND p.{parent_col} IS NULL),
               count(*) FILTER (WHERE t.{child_col} IS NULL),
               count(DISTINCT t.{child_col})
        FROM trip t LEFT JOIN {parent} p ON t.{child_col} = p.{parent_col}""").fetchone()
    n_parent = scalar(con, f"SELECT count(*) FROM {parent}")
    unused = q(con, f"""SELECT p.{parent_col} AS v FROM {parent} p
                        WHERE p.{parent_col} NOT IN (SELECT DISTINCT {child_col} FROM trip WHERE {child_col} IS NOT NULL)
                        ORDER BY 1""")["v"].tolist()
    return {"n_unmatched_rows": r[0], "n_unmatched_values": r[1], "n_child_null": r[2],
            "n_distinct_child_values": r[3], "n_parent_rows": n_parent,
            "parent_values_unused": ", ".join(map(str, unused))}


def main() -> None:
    con = connect()
    rows = []
    with Timer("trip foreign keys"):
        for child, parent, pcol, label in [
            ("PULocationID", "zone", "LocationID", "trip.PULocationID → taxi_zone_lookup"),
            ("DOLocationID", "zone", "LocationID", "trip.DOLocationID → taxi_zone_lookup"),
            ("VendorID", "vendor_code", "vendor_code", "trip.VendorID → vendor_code (seed TLC)"),
            ("RatecodeID", "rate_code", "rate_code", "trip.RatecodeID → rate_code (seed TLC)"),
            ("payment_type", "payment_type_code", "payment_type_code", "trip.payment_type → payment_type_code (seed TLC)"),
        ]:
            r = fk_check(con, child, parent, pcol)
            mx = con.execute(f"""SELECT {child}, count(*) FROM trip GROUP BY 1 ORDER BY 2 DESC LIMIT 1""").fetchone()
            r.update({"quan_he": label, "khoa_noi": f"{child} = {pcol}", "kieu_quan_he": "n – 1",
                      "max_rows_per_parent": f"{mx[0]}: {mx[1]:,}"})
            rows.append(r)

        unk = con.execute(f"""SELECT count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES}),
                                     count(*) FILTER (WHERE DOLocationID IN {UNKNOWN_ZONES}),
                                     count(*) FILTER (WHERE PULocationID IN {UNKNOWN_ZONES} OR DOLocationID IN {UNKNOWN_ZONES})
                              FROM trip""").fetchone()

    with Timer("lookup vs shapefile"):
        zone = q(con, "SELECT * FROM zone")
        shp = gpd.read_file(ZONE_SHP)[["LocationID", "zone", "borough", "OBJECTID"]]
        m = zone.merge(shp, on="LocationID", how="outer", indicator=True)
        only_lookup = m[m._merge == "left_only"].LocationID.tolist()
        only_shp = m[m._merge == "right_only"].LocationID.tolist()
        both = m[m._merge == "both"]
        diff = both[(both.Zone != both.zone) | (both.Borough != both.borough)]
        save(diff[["LocationID", "Zone", "zone", "Borough", "borough", "OBJECTID"]], "2_4b_Lookup_vs_shapefile")
        objid_diff = int((both.OBJECTID != both.LocationID).sum())
        rows.append({"quan_he": "taxi_zone_lookup ↔ taxi_zones.shp", "khoa_noi": "LocationID = LocationID",
                     "kieu_quan_he": "1 – 0..1", "n_unmatched_rows": len(only_lookup) + len(only_shp),
                     "n_unmatched_values": len(only_lookup) + len(only_shp), "n_child_null": 0,
                     "n_distinct_child_values": len(shp), "n_parent_rows": len(zone),
                     "parent_values_unused": f"chỉ có ở lookup: {only_lookup}; chỉ có ở shapefile: {only_shp}",
                     "max_rows_per_parent": f"{len(diff)} LocationID khác tên/borough; OBJECTID ≠ LocationID: {objid_diff}"})
        rows.append({"quan_he": "trip (PU/DO) → zone có polygon", "khoa_noi": "PU/DOLocationID ∈ shapefile",
                     "kieu_quan_he": "n – 0..1", "n_unmatched_rows": unk[2], "n_unmatched_values": len(only_lookup),
                     "n_child_null": 0, "n_distinct_child_values": None, "n_parent_rows": len(shp),
                     "parent_values_unused": f"PU ∈ {UNKNOWN_ZONES}: {unk[0]:,}; DO ∈ {UNKNOWN_ZONES}: {unk[1]:,}",
                     "max_rows_per_parent": "không vẽ được trên bản đồ"})

    cols = ["quan_he", "khoa_noi", "kieu_quan_he", "n_unmatched_rows", "n_unmatched_values", "n_child_null",
            "n_distinct_child_values", "n_parent_rows", "parent_values_unused", "max_rows_per_parent"]
    save(pd.DataFrame(rows)[cols], "Bang_2_4_Quan_he")

    with Timer("zone usage + routes"):
        usage = q(con, """
            WITH pu AS (SELECT PULocationID AS LocationID, count(*) AS n_pickup FROM trip GROUP BY 1),
                 do_ AS (SELECT DOLocationID AS LocationID, count(*) AS n_dropoff FROM trip GROUP BY 1)
            SELECT z.LocationID, z.Borough, z.Zone, z.service_zone,
                   coalesce(pu.n_pickup, 0) AS n_pickup, coalesce(do_.n_dropoff, 0) AS n_dropoff
            FROM zone z LEFT JOIN pu USING (LocationID) LEFT JOIN do_ USING (LocationID)
            ORDER BY n_pickup DESC""")
        usage["in_shapefile"] = usage.LocationID.isin(shp.LocationID)
        save(usage, "2_4a_Zone_su_dung")

        routes = q(con, f"""
            SELECT t.PULocationID, pz.Zone AS pickup_zone, t.DOLocationID, dz.Zone AS dropoff_zone,
                   count(*) AS n_trips, round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct_trips
            FROM trip t JOIN zone pz ON t.PULocationID = pz.LocationID JOIN zone dz ON t.DOLocationID = dz.LocationID
            WHERE t.tpep_pickup_datetime >= TIMESTAMP '{PERIOD_START}' AND t.tpep_pickup_datetime < TIMESTAMP '{PERIOD_END}'
            GROUP BY ALL ORDER BY n_trips DESC""")
        n_routes = len(routes)
        top = routes.head(20).copy()
        top.attrs["n_routes"] = n_routes
        top.insert(0, "rank", range(1, len(top) + 1))
        top["n_distinct_routes_total"] = n_routes
        top["n_same_zone_trips_total"] = int(routes.loc[routes.PULocationID == routes.DOLocationID, "n_trips"].sum())
        save(top, "2_4c_Tuyen_pho_bien")


if __name__ == "__main__":
    main()
