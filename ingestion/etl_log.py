"""ETL run logging utilities."""


def log_run(con, step: str, start_time, end_time, rows_in: int, rows_out: int, status: str, message: str) -> None:
    """Insert ETL run information into metadata.etl_log."""
    # TODO: Insert ETL execution metadata into metadata.etl_log table.
    pass
