"""Shared structured JSON logging for the AI ModelOps Platform."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, TextIO


_STANDARD_LOG_RECORD_FIELDS = set(
    logging.makeLogRecord({}).__dict__
) | {"message", "asctime"}

_RESERVED_OUTPUT_FIELDS = {
    "timestamp",
    "level",
    "service",
    "logger",
    "message",
    "exception",
    "stack_info",
}


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        if not service_name.strip():
            raise ValueError("service_name cannot be empty.")

        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record, including context and exception details."""

        timestamp = (
            datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom structured fields supplied through logging's extra=.
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS:
                continue
            if key in _RESERVED_OUTPUT_FIELDS or key.startswith("_"):
                continue

            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


def configure_logging(
    service_name: str,
    *,
    level: str | int | None = None,
    stream: TextIO | None = None,
) -> logging.Handler:
    """Configure the process root logger to emit structured JSON to a stream.

    LOG_LEVEL may override the default INFO level. Calling this function
    replaces existing root handlers, preventing duplicate root output.
    """
    configured_level: str | int = (
        level if level is not None else os.getenv("LOG_LEVEL", "INFO")
    )

    if isinstance(configured_level, str):
        resolved_level = logging.getLevelName(configured_level.upper())
        if not isinstance(resolved_level, int):
            raise ValueError(
                f"Invalid logging level: {configured_level!r}."
            )
        numeric_level = resolved_level
    else:
        numeric_level = configured_level

    output_stream = stream if stream is not None else sys.stdout

    handler = logging.StreamHandler(output_stream)
    handler.setLevel(numeric_level)
    handler.setFormatter(JsonFormatter(service_name))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    return handler
