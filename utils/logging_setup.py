"""Shared logger configuration for command entrypoints."""

from __future__ import annotations

import logging
import os

from utils.customformatter import CustomFormatter


def configure_logger(name: str) -> logging.Logger:
    """Return a module logger with the repo's console formatter attached."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)
    logger.setLevel(int(os.getenv("LOG_LEVEL", str(logging.INFO))))
    return logger
