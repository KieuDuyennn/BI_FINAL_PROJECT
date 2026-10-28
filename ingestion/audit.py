"""Control and audit logging skeleton."""


def log_event(connection, run_id: str, package: str, data_flow: str, event_type: str,
              start_time, end_time, rows_read: int | None, rows_loaded: int | None,
              rows_rejected: int | None, status: str, message: str | None = None) -> None:
    """Write one event to meta.event_log."""
    raise NotImplementedError
