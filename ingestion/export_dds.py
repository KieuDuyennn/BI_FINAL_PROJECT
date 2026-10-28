"""Export DDS tables from DuckDB to Parquet for Power BI."""

from pathlib import Path


def export_dds(connection, export_dir: Path) -> None:
    """Export approved DDS tables to Parquet. TODO: implement."""
    raise NotImplementedError


def export_tables(connection, export_dir: str) -> None:
    """Compatibility wrapper for the planned export step."""
    export_dds(connection, Path(export_dir))
