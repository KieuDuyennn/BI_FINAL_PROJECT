CREATE TABLE IF NOT EXISTS meta.event_type (event_type_key INTEGER, event_type_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.event_log (
    event_log_key BIGINT, run_id VARCHAR, package VARCHAR, data_flow VARCHAR, event_type VARCHAR,
    start_time TIMESTAMP, end_time TIMESTAMP, rows_read BIGINT, rows_loaded BIGINT,
    rows_rejected BIGINT, status VARCHAR, message VARCHAR
);
