"""Logging configuration."""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger for the given name (default: caller module)."""
    return logging.getLogger(name or __name__)
