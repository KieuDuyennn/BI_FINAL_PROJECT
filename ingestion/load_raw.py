"""Load raw source files into DuckDB raw schema."""


def load_trips(con, raw_dir: str) -> None:
    """Load monthly yellow trip parquet files into raw schema."""
    # TODO: Implement month-by-month trip loading into DuckDB raw schema.
    pass


def load_zones(con, raw_dir: str) -> None:
    """Load taxi zone lookup CSV/shapefile metadata into raw schema."""
    # TODO: Implement zone lookup and zones loading into DuckDB raw schema.
    pass


if __name__ == "__main__":
    # TODO: Open DuckDB connection, call load_trips and load_zones.
    pass
