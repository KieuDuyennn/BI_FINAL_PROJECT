# Data Profiling & Survey — NYC Yellow Taxi 2024–2025

Scope: assignment section *Data Profiling & Survey* — (1) survey and describe data sources, (2) analyze raw data anomalies.
All numbers come from `profiling/profile_raw.py` run over the full raw data (no sampling). Detailed tables:
[`profiling_results.md`](profiling_results.md) and CSVs in [`tables/`](tables/). Rule codes (T01, M06, …) refer to
`tables/09_anomaly_summary.csv`.

---

## 1. Data source survey

| Source | Format | Size | Records | Grain |
|---|---|---|---|---|
| Yellow Taxi Trip Records (`yellow_tripdata_YYYY-MM.parquet`) | Parquet, 24 monthly files (2024-01 → 2025-12) | ~1.5 GB | **89,892,322** | 1 row = 1 trip (or a fare adjustment / reversal of a trip) |
| Taxi Zone Lookup (`taxi_zone_lookup.csv`) | CSV, UTF-8 | 12 KB | 265 | 1 row = 1 TLC taxi zone |
| Taxi Zone Boundaries (`taxi_zones.shp/.shx/.dbf/.prj/.cpg`) | ESRI Shapefile | 1.6 MB | 263 polygons | 1 row = 1 zone polygon |

### 1.1 Trip records

- **Volume:** 41.17 M trips in 2024 files, 48.72 M in 2025 files (**+18.3 %**). Monthly volume ranges from 2.96 M (2024-01) to 4.59 M (2025-05).
- **Schema:** 19 columns in 2024; **20 columns from 2025-01** — `cbd_congestion_fee` was added when the Manhattan Congestion Relief Zone toll started (2025-01-05). When files are read together, 2024 rows have NULL in this column (45.8 % of all rows) — this is schema drift, not missing data.
- **Column groups:**

| Group | Columns | Notes |
|---|---|---|
| Who / how | `VendorID`, `RatecodeID`, `payment_type`, `store_and_fwd_flag` | Coded values, decoded with the TLC data dictionary |
| When | `tpep_pickup_datetime`, `tpep_dropoff_datetime` | `timestamp[us]`, local NYC time, no timezone |
| Where | `PULocationID`, `DOLocationID` | FK → `taxi_zone_lookup.LocationID` |
| Trip measures | `passenger_count`, `trip_distance` (miles) | |
| Money measures | `fare_amount`, `extra`, `mta_tax`, `tip_amount`, `tolls_amount`, `improvement_surcharge`, `congestion_surcharge`, `Airport_fee`, `cbd_congestion_fee`, `total_amount` | USD |

- **Code domains observed** (all values are inside the TLC dictionary — rules C01/C04/C06 = 0 rows):

| Column | Values (share of trips) |
|---|---|
| `VendorID` | 2 Curb/VTS 77.9 %, 1 CMT 21.5 %, **7 Helix 0.6 %**, **6 Myle 0.03 %** |
| `RatecodeID` | 1 Standard 76.7 %, NULL 17.5 %, 2 JFK 3.0 %, 99 Unknown 1.4 %, 5 Negotiated 0.9 %, 3 Newark 0.3 %, 4 Nassau/Westchester 0.2 %, 6 Group 127 trips |
| `payment_type` | 1 Credit card 68.4 %, **0 Flex Fare/missing 17.5 %**, 2 Cash 11.3 %, 4 Dispute 2.1 %, 3 No charge 0.7 %, 5 Unknown 7 trips, 6 Voided 0 |
| `passenger_count` | 1 → 64.6 %, NULL 17.5 %, 2 → 11.7 %, 3–6 → 5.5 %, 0 → 0.7 %, 7–9 → 430 trips |

> The analytical requirement mentions only vendors **CMT** and **VTS**; the data also contains **Helix (7)** and **Myle (6)**, which must exist in the vendor dimension.

### 1.2 Taxi zone lookup

- 265 rows, columns `LocationID, Borough, Zone, service_zone`. `LocationID` is unique and contiguous (1–265); every trip location ID matches a lookup row (L01/L02 = 0).
- Boroughs: Manhattan 69, Queens 69, Brooklyn 61, Bronx 43, Staten Island 20, EWR 1, plus two placeholder rows: **264 = Unknown / N/A** and **265 = N/A / Outside of NYC**.
- Duplicate zone names: *Governor's Island/Ellis Island/Liberty Island* (IDs 103, 104, 105) and *Corona* (56, 57) → `Zone` is not a key; always join on `LocationID`.
- `service_zone`: Boro Zone 205, Yellow Zone 55, Airports 2 (JFK 132, LaGuardia 138), EWR 1, N/A 2.

### 1.3 Taxi zone shapefile

- 263 valid polygons/multipolygons (no invalid or empty geometry), `LocationID` unique, names identical to the lookup.
- Missing only IDs **264 and 265** (they are not real places) — expected.
- CRS: **NAD83 / New York Long Island (ftUS), EPSG:2263**, units in feet. Must be re-projected to **WGS84 (EPSG:4326)** for Power BI maps.

---

## 2. Raw data anomalies

Rows hitting at least one rule (excluding the unknown-zone rules): **35.4 M (39.4 %)** — dominated by the reconciliation issue M06 and the NULL block P01/C02/C05/C07. Excluding those structural issues, genuinely invalid rows are a few percent.

### 2.1 Structural NULL block — 15,703,126 rows (17.47 %)

`passenger_count`, `RatecodeID`, `store_and_fwd_flag`, `congestion_surcharge`, `Airport_fee` are **all NULL together**, and always with `payment_type = 0` (`tables/08_null_patterns.csv`). The block grows strongly over time: 140 K rows in 2024-01 vs ~1.2 M per month in mid/late 2025. These are mostly VTS (13.2 M) and CMT (2.4 M) trips; **all Myle (6) trips** are in this block.
2.0 M of these rows have negative `fare_amount` but positive `total_amount` (Flex Fare adjustment records).

*Impact:* passenger-count statistics (requirement 1, 5) and rate-code statistics (requirement 5, advanced 1) cannot use these rows; revenue and trip counts can.

### 2.2 Reversals and negative amounts

| Finding | Rows |
|---|---|
| `fare_amount < 0` (M01) | 3,579,644 (3.98 %) |
| `total_amount < 0` (M04) | 1,583,065 (1.76 %) |
| Natural-key duplicates (vendor, pickup, dropoff, PU, DO) | 1,272,454 (1.42 %) |
| … of which *original trip + negative twin that nets to 0* | **1,245,402 pairs** (~98 %) |
| Exact duplicate rows (all columns) | 5 |

Negative totals are concentrated in payment types Dispute (883 K), Cash (338 K) and No charge (191 K), and in almost all of them every money component is ≤ 0 — i.e. **full reversals** of an earlier trip. Summing raw `total_amount` therefore nets refunds automatically, but **counting rows overstates trip volume by ~1.25 M**.

### 2.3 `total_amount` does not reconcile with its components (M06) — 28.8 M rows (32.1 %)

`total_amount − Σ(components)` is exactly 0 for 61.0 M rows; the remaining gaps are fixed amounts: **+2.50, −2.50, −3.25 (2.50+0.75), −1.75, −4.25 …** — i.e. the congestion surcharge, airport fee or CBD fee is either already included in `extra` or omitted from `total_amount`. It depends on the vendor (`tables/12b_total_reconciliation_vendor.csv`): CMT 87–91 % mismatched, VTS 9 % (2024) → 22 % (2025), Myle 100 %.

*Impact:* use `total_amount` as the revenue measure and do not rebuild it from components; components are fine for tip/fee analysis.

### 2.4 Time anomalies

| Rule | Rows |
|---|---|
| T02 pickup year outside 2024–2025 (2002, 2007–2009, 2023, 2026) | 59 |
| T01 pickup month ≠ source-file month | 634 |
| T03 dropoff before pickup | 3,810 |
| T04 zero duration | 556,004 (0.62 %) |
| T05 duration < 1 min | 1,033,050 (1.15 %) |
| T06 / T07 duration > 3 h / > 24 h | 43,750 / 582 |

Median trip duration is 13.3 min (p99 = 71 min).

### 2.5 Distance, passenger and location anomalies

| Rule | Rows |
|---|---|
| D01 `trip_distance = 0` | 2,179,263 (2.42 %) |
| D03 `trip_distance > 100 mi` (max 398,608 mi) | 4,483 |
| D04 average speed > 80 mph | 26,945 |
| P02 `passenger_count = 0` | 661,416 (0.74 %) |
| P03 `passenger_count > 6` | 430 |
| C03 `RatecodeID = 99` | 1,271,371 (1.41 %) |
| L03 / L04 pickup / dropoff in zone 264–265 (unknown / outside NYC) | 249,244 / 694,524 |

Distance p99 is 19.8 mi; p99.9 is 30 mi. Zones 103/104 (Governor's/Liberty Island) have no trips at all.

### 2.6 Money outliers & business-rule violations

| Rule | Rows |
|---|---|
| M03 `fare_amount > 500` (max 863,372) | 1,444 |
| M09 tip > fare | 104,889 |
| M08 tip recorded on cash payment (tips are only captured for cards) | 3,359 |
| M10 / M11 negative tolls / negative surcharge columns | 122,166 / 1,416,777 |
| M12 `Airport_fee > 0` but pickup is not an airport zone | 252,040 |
| M13 `cbd_congestion_fee > 0` before the 2025-01-05 start date | 406 |
| M14 positive fare with 0 distance and 0 duration | 25,230 |

Non-standard surcharge values also exist (e.g. `mta_tax` = 10.50, `improvement_surcharge` = 0.30 / 2.50), but in small numbers.

---

## 3. Recommendations for Staging / ETL

| # | Issue | Action in staging | Rationale |
|---|---|---|---|
| 1 | Schema drift (`cbd_congestion_fee`) | Read with `union_by_name`; `coalesce(cbd_congestion_fee, 0)` | Fee did not exist before 2025 |
| 2 | Unify codes | Map NULL `RatecodeID` → 99, NULL `payment_type` / 0 → "Unknown / Flex", NULL `passenger_count` → "Unknown" group | Keep rows for revenue; dimension members cover unknowns |
| 3 | Pickup outside 2024–2025 or outside the file month (T01/T02) | **Drop** | Clock errors; 634 rows |
| 4 | Duration ≤ 0 or > 24 h, speed > 80 mph, distance > 100 mi | **Drop** (or flag `is_valid = false`) | Physically impossible |
| 5 | Reversal pairs (original + negative twin) | Flag `is_reversal`; exclude both rows from trip counts, keep in revenue or drop the pair | Avoid inflating counts by 1.25 M |
| 6 | Other negative amounts | Flag `is_refund`; exclude from average fare/tip metrics | |
| 7 | `passenger_count = 0` or > 6 | Treat as "Unknown" group | Does not invalidate the trip |
| 8 | `total_amount` reconciliation | Use `total_amount` as revenue; do not derive it | Vendor-specific inclusion of fees |
| 9 | Zones 264/265 | Keep, map to borough "Unknown" | Not plottable on the map |
| 10 | Shapefile CRS | Re-project EPSG:2263 → EPSG:4326 | Power BI maps need lat/long |
| 11 | Zone name duplicates | Join only on `LocationID` | `Zone` is not unique |
| 12 | Data quality tests (dbt) | `accepted_values` for code columns, `not_null` on keys, range tests on duration/distance, `relationships` PU/DO → zone | Repeatable checks per load |

Each dropped / flagged row should be counted per rule in the ETL log so the warehouse totals can be reconciled with the raw totals above.
