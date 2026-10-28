# Data Warehouse for NYC Yellow Taxi Trips (2024–2025)

## Course Information
- **Course:** CSC12107 – Information Systems for Business Intelligence
- **Instructor:** Tiết Gia Hồng
- **Group:** 05

## Team Members
| Student ID | Full name | Tasks | Evaluation |
|---|---|---|---|
| <TODO> | <TODO> | <TODO> | <TODO> |
| <TODO> | <TODO> | <TODO> | <TODO> |
| <TODO> | <TODO> | <TODO> | <TODO> |
| <TODO> | <TODO> | <TODO> | <TODO> |
| <TODO> | <TODO> | <TODO> | <TODO> |

## Dataset
This project uses the shared private Kaggle dataset:
- **Kaggle dataset:** `duynlphmkiu/bi-group05-nyc-yellow-taxi-2024-2025`
- **Link:** https://www.kaggle.com/datasets/duynlphmkiu/bi-group05-nyc-yellow-taxi-2024-2025
- **Sources included in dataset:**
  - `yellow_tripdata_YYYY-MM.parquet` (24 monthly files)
  - `taxi_zone_lookup.csv`
  - `taxi_zones.zip` (shapefile)

> Data files are **not stored in GitHub**. Each member downloads data locally.

## Architecture
This project follows the **Single DDS** architecture:

`Source > Stage > data firewall + DQ database > DDS`

Supporting components are **Metadata** and **Control + Audit**. The implementation uses
**ELT**: extract and load into Stage inside DuckDB, then transform inside the warehouse
with dbt. Stage preserves source structure with audit columns; dbt applies the firewall,
loads the star-schema DDS, and runs tests.

See diagrams in: [`docs/diagrams/`](docs/diagrams/)

## Folder Structure
- `.github/`: pull request template
- `notebooks/`: Kaggle notebook exports (`.ipynb`)
- `ingestion/`: ingestion/export/logging skeleton scripts
- `dbt_project/`: dbt models, tests, macros, seeds, profile template
- `mage_pipeline/`: Mage pipeline documentation/skeleton
- `docs/diagrams/`: architecture and design diagrams
- `docs/report/`: report assets and notes
- `dashboards/`: Power BI usage notes
- `sql/meta/`: metadata and control DDL
- `sql/stage/`: raw Stage table DDL
- `data/`: local-only data and DuckDB file (ignored by git)

## Setup (One Time)
1. Install Python.
2. Create and activate a virtual environment.
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Set `KAGGLE_API_TOKEN` in your environment (never commit credentials).
5. Ask the dataset owner to add your Kaggle account as a collaborator.
6. Copy `.env.example` to `.env` and adjust values if needed.
7. Copy `dbt_project/profiles.example.yml` to `~/.dbt/profiles.yml`.

## Run order
1. Run `sql/meta/*.sql` to create metadata and control schemas/tables.
2. Run `sql/stage/*.sql` to create raw Stage tables before ingestion.
3. `download_from_kaggle`
4. `load_stage`
5. `dbt_build_firewall`
6. `dbt_build_dds`
7. `dbt_test`
8. `reconcile`
9. `export_dds`
10. `write_audit`

Run these blocks in Mage.ai, or call the corresponding skeleton scripts manually.

## Team Workflow
- Notebooks are developed on Kaggle and exported to `notebooks/`.
- ETL and dbt run on each member's local machine.
- GitHub stores code only.
- Power BI `.pbix` file is shared via Google Drive.

## Grading Weights
- Profiling: 5%
- Requirements & DDS design: 15%
- ETL & loading: 30%
- Report/OLAP/Dashboard: 35%
- Advanced: 15%

## Submission Naming
`05_MSSV1_MSSV2_MSSV3_MSSV4_MSSV5`

Use each member's MSSV in place of placeholders.
