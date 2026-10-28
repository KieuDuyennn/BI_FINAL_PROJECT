CREATE TABLE IF NOT EXISTS meta.ds_data_store (data_store_key INTEGER, store_name VARCHAR, store_type VARCHAR);
CREATE TABLE IF NOT EXISTS meta.ds_table (table_key INTEGER, data_store_key INTEGER, table_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.ds_table_type (table_type_key INTEGER, table_type_name VARCHAR);
CREATE TABLE IF NOT EXISTS meta.ds_column (column_key INTEGER, table_key INTEGER, column_name VARCHAR, ordinal_position INTEGER);
CREATE TABLE IF NOT EXISTS meta.ds_column_type (column_type_key INTEGER, column_type_name VARCHAR);
