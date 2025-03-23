"""Custom logging formatter for colored logs."""

import logging
from typing import ClassVar


class CustomFormatter(logging.Formatter):
    """Custom formatter for colored logs."""

    grey = "\\x1b[38;21m"
    yellow = "\\x1b[33;21m"
    red = "\\x1b[31;21m"
    bold_red = "\\x1b[31;1m"
    reset = "\\x1b[0m"
    format = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )
    FORMATS: ClassVar = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with the color based on the log level."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
