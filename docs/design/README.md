# Design

## DDS design
- **Grain:** `fact_trip` has one row per valid taxi trip.
- **Dimensions:** date, time, zone, vendor, payment type, and rate code.
- **Hierarchies:** date -> month -> quarter -> year; date includes day of week and weekend; time -> time of day; zone -> borough/service zone.
- **SCD:** `dim_zone` is SCD type 1.
- **Unknown member:** every dimension has integer surrogate key `0`; facts do not contain NULL foreign keys.

## Data firewall rules
Rules are maintained in `dbt_project/seeds/dq_rule.csv`, applied in `int_trip_validated`,
and rejected rows are stored in `dq.trip_rejected`.

## Metadata model
The seven textbook metadata kinds are defined one DDL file per kind in `sql/meta/`.

## ETL design
- **Extraction:** fixed range by month; read LSET, load following months, then update LSET.
- **Recoverability:** delete the selected month before reloading it.
- **Zones:** extract `taxi_zone_lookup` as a whole table every time.
- **Architecture:** Source > Stage > data firewall + DQ database > DDS.

<TODO> Add confirmed mappings, rules, and implementation details.
