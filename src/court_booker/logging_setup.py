"""Console logging with per-step elapsed time."""

from __future__ import annotations

import logging
import sys
import time

LOGGER_NAME = "court_booker"


class _ElapsedFilter(logging.Filter):
    """Attach ``elapsed``: seconds since the previous log record."""

    def __init__(self) -> None:
        super().__init__()
        self._last = time.perf_counter()

    def filter(self, record: logging.LogRecord) -> bool:
        now = time.perf_counter()
        record.elapsed = now - self._last
        self._last = now
        return True


def configure_logging(verbose: bool = False) -> None:
    """Send package logs to stdout as ``HH:MM:SS.mmm +0.00s LEVEL message``."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ElapsedFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d +%(elapsed)5.2fs %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers[:] = [handler]
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False
