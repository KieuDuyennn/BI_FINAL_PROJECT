"""Stage ingestion skeleton using fixed-range monthly extraction."""

from datetime import datetime
from pathlib import Path
from typing import Iterable


def get_lset(connection, source_name: str) -> str | None:
    """Read the Last Successfully Extracted month from meta.extract_control."""
    raise NotImplementedError


def set_lset(connection, source_name: str, load_month: str, etl_run_id: str) -> None:
    """Update LSET only after a successful month load."""
    raise NotImplementedError


def load_trips_month(connection, parquet_path: Path, load_month: str, etl_run_id: str, loaded_at: datetime) -> int:
    """Delete the month, then load source-shaped rows plus audit columns."""
    raise NotImplementedError


def load_zones(connection, csv_path: Path, etl_run_id: str, loaded_at: datetime) -> int:
    """Whole-table extraction for taxi_zone_lookup on every run."""
    raise NotImplementedError


def months_after_lset(lset: str | None, available_months: Iterable[str]) -> list[str]:
    """Return fixed-range months after LSET in source order. TODO: implement."""
    raise NotImplementedError
