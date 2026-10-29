"""Configuration loader for ingestion scripts."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "KAGGLE_DATASET": "duynlphmkiu/bi-group05-nyc-yellow-taxi-2024-2025",
    "RAW_DATA_DIR": "data/raw",
    "EXPORT_DIR": "data/export",
    "DUCKDB_PATH": "data/warehouse.duckdb",
}


def _resolve(path_str: str) -> Path:
    """Resolve a path relative to the project root unless it is absolute."""
    path = Path(path_str)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings() -> dict:
    """Load settings from .env and environment variables."""
    load_dotenv(PROJECT_ROOT / ".env")
    env = {key: os.getenv(key, default) for key, default in DEFAULTS.items()}
    return {
        "kaggle_dataset": env["KAGGLE_DATASET"],
        "raw_dir": _resolve(env["RAW_DATA_DIR"]),
        "export_dir": _resolve(env["EXPORT_DIR"]),
        "duckdb_path": _resolve(env["DUCKDB_PATH"]),
    }
