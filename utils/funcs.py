"""Utility functions for the project."""

logger = logging.getLogger(__name__)


def str_to_bool(s: str) -> bool:
    """Convert a string to a boolean value."""
    if s.lower() in ("true", "1", "t", "y", "yes"):
        return True
    if s.lower() in ("false", "0", "f", "n", "no"):
        return False
    logger.warning("unknown value defaulting to false")
    return False
