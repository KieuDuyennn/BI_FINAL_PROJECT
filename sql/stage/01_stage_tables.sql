-- no PK/FK/NOT NULL on purpose, so bad data is captured by the data firewall.
CREATE TABLE IF NOT EXISTS stage.trip (
    VendorID INTEGER,
    tpep_pickup_datetime TIMESTAMP,
    tpep_dropoff_datetime TIMESTAMP,
    passenger_count BIGINT,
    trip_distance DOUBLE,
    RatecodeID BIGINT,
    store_and_fwd_flag VARCHAR,
    PULocationID INTEGER,
    DOLocationID INTEGER,
    payment_type BIGINT,
    fare_amount DOUBLE,
    extra DOUBLE,
    mta_tax DOUBLE,
    tip_amount DOUBLE,
    tolls_amount DOUBLE,
    improvement_surcharge DOUBLE,
    total_amount DOUBLE,
    congestion_surcharge DOUBLE,
    Airport_fee DOUBLE,
    cbd_congestion_fee DOUBLE,
    source_file VARCHAR,
    load_month VARCHAR,
    loaded_at TIMESTAMP,
    etl_run_id VARCHAR
);

CREATE TABLE IF NOT EXISTS stage.taxi_zone_lookup (
    LocationID INTEGER,
    Borough VARCHAR,
    Zone VARCHAR,
    service_zone VARCHAR,
    source_file VARCHAR,
    load_month VARCHAR,
    loaded_at TIMESTAMP,
    etl_run_id VARCHAR
);
