CREATE TABLE IF NOT EXISTS meta.package (package_key INTEGER, package_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.data_flow (data_flow_key INTEGER, flow_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.status (status_key INTEGER, status_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.extract_control (
    source_name VARCHAR PRIMARY KEY, lset_month VARCHAR, updated_at TIMESTAMP, etl_run_id VARCHAR
);
