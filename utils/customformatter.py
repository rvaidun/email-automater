"""Custom logging formatter for colored logs."""

import logging
from typing import ClassVar


class CustomFormatter(logging.Formatter):
    """Custom formatter for colored logs."""

    grey = "\033[90m"
    cyan = "\033[96m"
    yellow = "\033[33m"
    red = "\033[41m"
    bold_red = "\033[91;1m"
    reset = "\033[0m"
    base_format = " (%(filename)s:%(lineno)d) %(message)s"
    FORMATS: ClassVar = {
        logging.DEBUG: grey + base_format + reset,
        logging.INFO: cyan + base_format + reset,
        logging.WARNING: yellow + base_format + reset,
        logging.ERROR: red + base_format + reset,
        logging.CRITICAL: bold_red + base_format + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with the color based on the log level."""
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
