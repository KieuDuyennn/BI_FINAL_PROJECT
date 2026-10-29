"""Download the private Kaggle source dataset without committing it."""

from pathlib import Path

from .config import KAGGLE_DATASET, RAW_DATA_DIR


def download_dataset(dataset: str = KAGGLE_DATASET, output_dir: Path = RAW_DATA_DIR) -> None:
    """Download and extract the configured Kaggle dataset. TODO: implement."""
    raise NotImplementedError


if __name__ == "__main__":
    download_dataset()
