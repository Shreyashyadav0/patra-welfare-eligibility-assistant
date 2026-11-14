"""Logging configuration.

One place to set the level, so that a deployment can turn on debug output with
PATRA_LOG_LEVEL=DEBUG without touching code. Library modules only ever call
`logging.getLogger(__name__)`; the handler is configured once, here, by whatever
starts the process (the API, the CLI, or a test harness).
"""

from __future__ import annotations

import logging
import os

DEFAULT_FORMAT = "%(asctime)s  %(levelname)-7s %(name)s  %(message)s"


def configure_logging(level: str | None = None) -> None:
    """Configure the root handler once. Safe to call more than once."""
    resolved = (level or os.environ.get("PATRA_LOG_LEVEL", "INFO")).upper()
    root = logging.getLogger()
    if root.handlers:  # already configured by the host application
        root.setLevel(resolved)
        return
    logging.basicConfig(level=resolved, format=DEFAULT_FORMAT, datefmt="%H:%M:%S")
    # Third-party access logs are noisy at INFO during tests.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
