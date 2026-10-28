# Mage Pipeline (Planned)

Pipeline blocks in order:
1. `download_from_kaggle`
2. `load_raw`
3. `dbt_run`
4. `dbt_test`
5. `export_dds`
6. `write_etl_log`

## Block Responsibility
- `download_from_kaggle`: calls matching function in `ingestion/download_from_kaggle.py`
- `load_raw`: calls matching functions in `ingestion/load_raw.py`
- `dbt_run`: runs dbt command in `dbt_project/`
- `dbt_test`: runs dbt tests in `dbt_project/`
- `export_dds`: calls matching function in `ingestion/export_dds.py`
- `write_etl_log`: calls matching function in `ingestion/etl_log.py`
