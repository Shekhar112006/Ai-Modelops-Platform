from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.session import get_session
from backend.app.main import app


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "AI ModelOps Platform"
    assert data["status"] == "running"


def test_liveness() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_create_and_list_project() -> None:
    project_name = f"test-project-{uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/projects",
        json={
            "name": project_name,
            "description": "Automated API test project",
        },
    )

    assert response.status_code == 201

    created = response.json()

    assert created["name"] == project_name
    assert created["status"] == "active"

    list_response = client.get("/api/v1/projects")

    assert list_response.status_code == 200

    projects = list_response.json()

    assert any(
        project["name"] == project_name
        for project in projects
    )


def test_duplicate_project() -> None:
    project_name = f"duplicate-test-{uuid4().hex[:8]}"

    first_response = client.post(
        "/api/v1/projects",
        json={
            "name": project_name,
            "description": "Duplicate test",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/projects",
        json={
            "name": project_name,
            "description": "Duplicate test",
        },
    )

    assert second_response.status_code == 409


def test_invalid_project_request() -> None:
    response = client.post(
        "/api/v1/projects",
        json={},
    )

    assert response.status_code == 422

class FailingReadinessSession:
    """Simulate a PostgreSQL connection failure."""

    async def execute(self, statement):
        raise SQLAlchemyError("Simulated database outage")


async def failing_readiness_session():
    """Provide a session that fails its database query."""

    yield FailingReadinessSession()


def request_with_unavailable_database(path: str):
    """Issue a request while the database dependency is unavailable."""

    previous_override = app.dependency_overrides.get(get_session)
    app.dependency_overrides[get_session] = failing_readiness_session

    try:
        return client.get(path)
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_session, None)
        else:
            app.dependency_overrides[get_session] = previous_override


def test_readiness_returns_503_when_database_is_unavailable() -> None:
    """Readiness must fail when PostgreSQL cannot execute a query."""

    response = request_with_unavailable_database("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable."}


def test_liveness_remains_healthy_when_database_is_unavailable() -> None:
    """Liveness must not depend on PostgreSQL availability."""

    response = request_with_unavailable_database("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
