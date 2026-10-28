"""Configuration loader for ingestion scripts."""

from dotenv import load_dotenv


def load_settings() -> dict:
    """Load settings from .env and environment variables."""
    # TODO: Load .env variables and return normalized settings dictionary.
    load_dotenv()
    return {}
