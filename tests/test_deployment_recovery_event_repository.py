from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.models.deployment_recovery_event import (
    DeploymentRecoveryEvent,
)
from backend.app.repositories.deployment_recovery_event_repository import (
    DeploymentRecoveryEventRepository,
)


def make_session(
    events: list[DeploymentRecoveryEvent] | None = None,
) -> MagicMock:
    """Create a mocked SQLAlchemy session for repository tests."""

    session = MagicMock(spec=Session)
    session.scalars.return_value.all.return_value = events or []
    return session


def test_create_persists_event_in_current_transaction() -> None:
    """Creating an event should add it and flush the session."""

    repository = DeploymentRecoveryEventRepository()
    session = make_session()
    deployment_id = uuid4()
    details = {"status_code": 503, "endpoint": "/health"}

    event = repository.create(
        session,
        deployment_id=deployment_id,
        event_type="failure_threshold_reached",
        severity="error",
        message="Deployment reached the configured failure threshold.",
        consecutive_failures=3,
        details=details,
    )

    assert isinstance(event, DeploymentRecoveryEvent)
    assert event.deployment_id == deployment_id
    assert event.event_type == "failure_threshold_reached"
    assert event.severity == "error"
    assert event.consecutive_failures == 3
    assert event.details == details

    session.add.assert_called_once_with(event)
    session.flush.assert_called_once()


def test_list_events_filters_and_orders_results() -> None:
    """Listing events should filter correctly and return newest-first SQL."""

    repository = DeploymentRecoveryEventRepository()
    deployment_id = uuid4()

    events = [
        DeploymentRecoveryEvent(
            deployment_id=deployment_id,
            event_type="failure_threshold_reached",
            severity="error",
            message="Failure threshold reached.",
        )
    ]

    session = make_session(events)

    result = repository.list_by_deployment(
        session,
        deployment_id,
        limit=25,
        event_type="failure_threshold_reached",
    )

    assert result == events

    statement = session.scalars.call_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)

    assert "deployment_recovery_events.deployment_id =" in sql
    assert "deployment_recovery_events.event_type =" in sql
    assert "deployment_recovery_events.created_at DESC" in sql
    assert "deployment_recovery_events.id DESC" in sql
    assert "LIMIT" in sql
    assert 25 in compiled.params.values()


def test_list_events_without_type_filter() -> None:
    """Omitting the event type should return all event types for a deployment."""

    repository = DeploymentRecoveryEventRepository()
    deployment_id = uuid4()
    events = [
        DeploymentRecoveryEvent(
            deployment_id=deployment_id,
            event_type="health_check_failed",
            severity="warning",
            message="Health check failed.",
        ),
        DeploymentRecoveryEvent(
            deployment_id=deployment_id,
            event_type="rollback_succeeded",
            severity="info",
            message="Rollback succeeded.",
        ),
    ]

    session = make_session(events)

    result = repository.list_by_deployment(
        session,
        deployment_id,
        limit=100,
    )

    assert result == events

    statement = session.scalars.call_args.args[0]
    sql = str(statement)

    assert "deployment_recovery_events.deployment_id =" in sql
    assert "deployment_recovery_events.event_type =" not in sql


def test_list_events_rejects_invalid_limit() -> None:
    """A zero or negative limit should be rejected before querying."""

    repository = DeploymentRecoveryEventRepository()
    session = make_session()

    with pytest.raises(ValueError, match="limit must be at least 1"):
        repository.list_by_deployment(
            session,
            uuid4(),
            limit=0,
        )

    session.scalars.assert_not_called()
