# Mage Pipeline (Planned)

Pipeline blocks in order:
1. `download_from_kaggle`
2. `load_stage`
3. `dbt_build_firewall`
4. `dbt_build_dds`
5. `dbt_test`
6. `reconcile`
7. `export_dds`
8. `write_audit`

## Block Responsibility
- `download_from_kaggle`: calls matching function in `ingestion/download_from_kaggle.py`
- `load_stage`: calls `ingestion/load_stage.py` and updates LSET
- `dbt_build_firewall`: builds `models/firewall/`
- `dbt_build_dds`: builds `models/dds/`
- `dbt_test`: runs dbt tests in `dbt_project/`
- `reconcile`: calls `ingestion/reconcile.py`
- `export_dds`: calls matching function in `ingestion/export_dds.py`
- `write_audit`: calls `ingestion/audit.py`; every block writes start/end/rows/status
