CREATE TABLE IF NOT EXISTS meta.data_mapping (
    mapping_key INTEGER, source_table VARCHAR, source_column VARCHAR,
    target_table VARCHAR, target_column VARCHAR, transformation_rule VARCHAR
);
