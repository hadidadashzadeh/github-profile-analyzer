"""
Centralized configuration and logging setup for the application.

All tunable values (API base URL, timeouts, file paths, etc.) live
here so the rest of the codebase never hard-codes "magic" values.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass


BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
REPORTS_DIR: Path = BASE_DIR / "reports"
CHARTS_DIR: Path = BASE_DIR / "charts_output"
LOGS_DIR: Path = BASE_DIR / "logs"

for directory in (DATA_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    """Immutable application settings, loaded once at import time."""

    github_api_base_url: str = "https://api.github.com"
    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    request_timeout_seconds: int = 15
    max_repos_per_page: int = 100
    max_pages: int = 5  # safety cap => up to 500 repos analyzed
    database_path: Path = DATA_DIR / "history.db"
    reports_dir: Path = REPORTS_DIR
    charts_dir: Path = CHARTS_DIR
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()


def configure_logging(name: str = "github_analyzer") -> logging.Logger:
    """
    Configure and return a module-level logger that writes to both
    the console and a rotating log file.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Avoid attaching duplicate handlers if called multiple times
        # (e.g. Streamlit reruns the script on every interaction).
        return logger

    logger.setLevel(settings.log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        file_handler = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # If the filesystem is read-only (e.g. some container setups),
        # fall back silently to console-only logging.
        pass

    logger.propagate = False
    return logger
