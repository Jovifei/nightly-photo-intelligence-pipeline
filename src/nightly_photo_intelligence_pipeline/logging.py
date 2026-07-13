"""Structured logging with mandatory path redaction.

Logs are written only under ``<runtime_root>/logs/`` (never under the source
root). A :class:`RedactingFilter` scrubs every record's message and string
args through :func:`redaction.redact_text` so absolute source paths, usernames,
hostnames, and tokens cannot leak into log files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from .redaction import redact_text

_LOGGER_NAME: Final = "npi"


class RedactingFilter(logging.Filter):
    """Filter that redacts every log record's message and string args."""

    def __init__(self, source_root: Path | None = None) -> None:
        super().__init__()
        self._source_root = source_root

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg), source_root=self._source_root)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_text(str(v), source_root=self._source_root)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_text(str(a), source_root=self._source_root) for a in record.args
                )
        return True


def get_logger() -> logging.Logger:
    """Return the shared NPI logger (does not configure handlers)."""
    return logging.getLogger(_LOGGER_NAME)


def setup_logging(
    runtime_root: Path | None = None,
    *,
    source_root: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """Configure the NPI logger to write under ``<runtime_root>/logs``.

    If *runtime_root* is None, logging is console-only (used by dry-run
    commands that have no runtime root yet). The source root is never written
    to, and a RedactingFilter is attached to every handler.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    # Detach previous handlers to keep setup idempotent in tests.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    redacting = RedactingFilter(source_root=source_root)

    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        stream.addFilter(redacting)
        logger.addHandler(stream)

    if runtime_root is not None:
        logs_dir = Path(runtime_root) / "logs"
        # logs_dir is under runtime, never under source. Source/runtime overlap
        # is rejected upstream by source_guard before logging is set up.
        logs_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(logs_dir / "npi.log", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        file_handler.addFilter(redacting)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
