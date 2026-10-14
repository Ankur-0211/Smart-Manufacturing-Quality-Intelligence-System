"""Structured logging (roadmap 9.6 / Plan 16.1).

Every log line carries ``request_id`` (bound per request by the middleware) and,
where relevant, ``run_id`` (bound by the simulation engine).
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import LogFormat, Settings


def configure_logging(settings: Settings) -> None:
    level = logging.getLevelName(settings.log_level.upper())
    if not isinstance(level, int):
        level = logging.INFO

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_format is LogFormat.JSON
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
