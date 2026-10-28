CREATE TABLE IF NOT EXISTS meta.source_system (source_system_key INTEGER, source_name VARCHAR, owner_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.source_file (
    source_file_key INTEGER, source_system_key INTEGER, file_name VARCHAR, load_month VARCHAR,
    row_count BIGINT, file_size_bytes BIGINT, extracted_at TIMESTAMP
);
