"""Tests for deployment recovery-state persistence."""

from uuid import uuid4

from sqlalchemy.dialects import postgresql

from backend.app.repositories.deployment_recovery_state_repository import (
    DeploymentRecoveryStateRepository,
)


class FakeResult:
    """Minimal SQLAlchemy result substitute for repository unit tests."""

    def __init__(self, scalar=None, rowcount=0):
        self.scalar = scalar
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self.scalar


class FakeSession:
    """Capture SQL statements without modifying a database."""

    def __init__(self, result):
        self.result = result
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return self.result


def compiled_statement(session):
    """Compile the captured statement using PostgreSQL SQL syntax."""
    compiled = session.statement.compile(
        dialect=postgresql.dialect()
    )
    return str(compiled), compiled.params


def test_claim_succeeds_when_database_returns_state_id():
    deployment_id = uuid4()
    state_id = uuid4()
    session = FakeSession(FakeResult(scalar=state_id))
    repository = DeploymentRecoveryStateRepository()

    claimed = repository.claim(
        session,
        deployment_id=deployment_id,
        consecutive_failures=3,
    )

    assert claimed is True

    sql, _ = compiled_statement(session)
    assert "ON CONFLICT (deployment_id) DO UPDATE" in sql
    assert "WHERE deployment_recovery_states.status =" in sql
    assert "RETURNING deployment_recovery_states.id" in sql


def test_claim_returns_false_when_another_task_has_claimed():
    session = FakeSession(FakeResult(scalar=None))
    repository = DeploymentRecoveryStateRepository()

    claimed = repository.claim(
        session,
        deployment_id=uuid4(),
        consecutive_failures=3,
    )

    assert claimed is False


def test_claim_only_updates_an_existing_idle_state():
    session = FakeSession(FakeResult(scalar=None))
    repository = DeploymentRecoveryStateRepository()

    repository.claim(
        session,
        deployment_id=uuid4(),
        consecutive_failures=3,
    )

    sql, params = compiled_statement(session)

    assert "ON CONFLICT (deployment_id) DO UPDATE" in sql
    assert "WHERE deployment_recovery_states.status =" in sql
    assert "idle" in params.values()


def test_reset_after_healthy_succeeds_when_one_row_is_updated():
    session = FakeSession(FakeResult(rowcount=1))
    repository = DeploymentRecoveryStateRepository()

    reset = repository.reset_after_healthy(
        session,
        deployment_id=uuid4(),
    )

    assert reset is True

    sql, params = compiled_statement(session)

    assert "UPDATE deployment_recovery_states" in sql
    assert "deployment_recovery_states.status !=" in sql
    assert "in_progress" in params.values()
    assert "idle" in params.values()


def test_reset_after_healthy_returns_false_when_no_row_is_updated():
    session = FakeSession(FakeResult(rowcount=0))
    repository = DeploymentRecoveryStateRepository()

    reset = repository.reset_after_healthy(
        session,
        deployment_id=uuid4(),
    )

    assert reset is False


def test_mark_completed_only_updates_an_in_progress_recovery():
    session = FakeSession(FakeResult(rowcount=1))
    repository = DeploymentRecoveryStateRepository()

    completed = repository.mark_completed(
        session,
        deployment_id=uuid4(),
    )

    assert completed is True

    sql, params = compiled_statement(session)

    assert "UPDATE deployment_recovery_states" in sql
    assert "deployment_recovery_states.status =" in sql
    assert "completed" in params.values()
    assert "in_progress" in params.values()


def test_mark_failed_persists_error_and_requires_in_progress_state():
    session = FakeSession(FakeResult(rowcount=1))
    repository = DeploymentRecoveryStateRepository()

    failed = repository.mark_failed(
        session,
        deployment_id=uuid4(),
        error="Restored deployment failed its health check.",
    )

    assert failed is True

    sql, params = compiled_statement(session)

    assert "UPDATE deployment_recovery_states" in sql
    assert "in_progress" in params.values()
    assert (
        "Restored deployment failed its health check."
        in params.values()
    )


def test_final_state_transition_returns_false_when_state_is_not_in_progress():
    repository = DeploymentRecoveryStateRepository()
    deployment_id = uuid4()

    completed_session = FakeSession(FakeResult(rowcount=0))
    failed_session = FakeSession(FakeResult(rowcount=0))

    assert repository.mark_completed(
        completed_session,
        deployment_id=deployment_id,
    ) is False

    assert repository.mark_failed(
        failed_session,
        deployment_id=deployment_id,
        error="Rollback failed.",
    ) is False
