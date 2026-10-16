"""Tests for shared structured JSON logging."""

from __future__ import annotations

import json
import logging
import sys
import uuid

import pytest

from backend.app.core.logging_config import (
    JsonFormatter,
    configure_logging,
)


def test_json_formatter_includes_standard_and_custom_fields() -> None:
    """Structured fields should remain searchable after JSON serialization."""

    deployment_id = uuid.uuid4()

    record = logging.LogRecord(
        name="modelops.recovery",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Automated rollback completed.",
        args=(),
        exc_info=None,
    )
    record.event = "rollback_succeeded"
    record.deployment_id = deployment_id
    record.recovery_status = "completed"

    formatted = JsonFormatter("modelops-worker").format(record)
    payload = json.loads(formatted)

    assert payload["level"] == "INFO"
    assert payload["service"] == "modelops-worker"
    assert payload["logger"] == "modelops.recovery"
    assert payload["message"] == "Automated rollback completed."
    assert payload["event"] == "rollback_succeeded"
    assert payload["deployment_id"] == str(deployment_id)
    assert payload["recovery_status"] == "completed"
    assert payload["timestamp"].endswith("Z")


def test_json_formatter_includes_exception_traceback() -> None:
    """Exception details should be preserved in structured logs."""

    formatter = JsonFormatter("modelops-worker")

    try:
        raise ValueError("Example recovery failure")
    except ValueError:
        record = logging.LogRecord(
            name="modelops.recovery",
            level=logging.ERROR,
            pathname=__file__,
            lineno=65,
            msg="Recovery operation failed.",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "ERROR"
    assert "ValueError: Example recovery failure" in payload["exception"]


def test_formatter_does_not_allow_custom_fields_to_override_core_fields() -> None:
    """Custom logging context cannot overwrite core formatter attributes."""

    record = logging.LogRecord(
        name="modelops.health",
        level=logging.INFO,
        pathname=__file__,
        lineno=85,
        msg="Health check completed.",
        args=(),
        exc_info=None,
    )
    record.service = "unexpected-service"
    record.level = "FAKE"

    payload = json.loads(JsonFormatter("modelops-worker").format(record))

    assert payload["service"] == "modelops-worker"
    assert payload["level"] == "INFO"


def test_formatter_rejects_empty_service_name() -> None:
    with pytest.raises(ValueError, match="service_name cannot be empty"):
        JsonFormatter(" ")


def test_configure_logging_emits_json_to_the_supplied_stream() -> None:
    """The shared configuration should emit one parseable JSON log line."""

    import io

    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level

    output = io.StringIO()

    try:
        configure_logging(
            "modelops-test",
            level="DEBUG",
            stream=output,
        )

        logger = logging.getLogger("modelops.test")
        logger.info(
            "Health check completed.",
            extra={
                "event": "health_check_succeeded",
                "deployment_id": "deployment-123",
            },
        )

        lines = output.getvalue().splitlines()
        assert len(lines) == 1

        payload = json.loads(lines[0])

        assert payload["service"] == "modelops-test"
        assert payload["level"] == "INFO"
        assert payload["message"] == "Health check completed."
        assert payload["event"] == "health_check_succeeded"
        assert payload["deployment_id"] == "deployment-123"

    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(previous_handlers)
        root_logger.setLevel(previous_level)


def test_configure_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Invalid logging level"):
        configure_logging("modelops-test", level="NOT_A_LEVEL")
