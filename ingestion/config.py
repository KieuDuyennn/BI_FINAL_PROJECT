"""Configuration skeleton for local ELT ingestion."""

from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

KAGGLE_DATASET = os.getenv("KAGGLE_DATASET", "<TODO>")
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "data/export"))
DUCKDB_PATH = Path(os.getenv("DUCKDB_PATH", "data/warehouse.duckdb"))


def load_settings() -> dict[str, str]:
    """Return normalized settings for scripts. TODO: add validation."""
    return {
        "kaggle_dataset": KAGGLE_DATASET,
        "raw_data_dir": str(RAW_DATA_DIR),
        "export_dir": str(EXPORT_DIR),
        "duckdb_path": str(DUCKDB_PATH),
    }
