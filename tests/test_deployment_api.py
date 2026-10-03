from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete

from backend.app.main import app
from backend.app.db.sync_session import SessionFactory
from backend.app.models.deployment import Deployment
from backend.app.models.project import Project


client = TestClient(app)


def create_test_project() -> str:
    """Create a temporary project and return its ID."""

    response = client.post(
        "/api/v1/projects",
        json={
            "name": f"deployment-test-{uuid4().hex[:8]}",
            "description": "Deployment API test project",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def cleanup_project(project_id: str) -> None:
    """Delete deployment test data from PostgreSQL."""

    with SessionFactory() as session:
        session.execute(
            delete(Deployment).where(
                Deployment.project_id == project_id
            )
        )

        session.execute(
            delete(Project).where(
                Project.id == project_id
            )
        )

        session.commit()


def test_create_deployment() -> None:
    """A validated MLflow model should create a deployment."""

    project_id = create_test_project()

    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/deployments",
            json={
                "model_name": "demo-classifier",
                "model_version": "4",
                "environment": "staging",
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["project_id"] == project_id
        assert data["model_name"] == "demo-classifier"
        assert data["model_version"] == "4"
        assert data["environment"] == "staging"
        assert data["status"] == "created"
        assert data["traffic_percentage"] == 0
        assert data["model_endpoint"] is None

    finally:
        cleanup_project(project_id)


def test_get_deployment() -> None:
    """An existing deployment should be retrievable by ID."""

    project_id = create_test_project()

    try:
        create_response = client.post(
            f"/api/v1/projects/{project_id}/deployments",
            json={
                "model_name": "demo-classifier",
                "model_version": "4",
                "environment": "staging",
            },
        )

        assert create_response.status_code == 201

        deployment_id = create_response.json()["id"]

        response = client.get(
            f"/api/v1/deployments/{deployment_id}"
        )

        assert response.status_code == 200
        assert response.json()["id"] == deployment_id

    finally:
        cleanup_project(project_id)


def test_list_project_deployments() -> None:
    """A project's deployment history should contain its deployments."""

    project_id = create_test_project()

    try:
        create_response = client.post(
            f"/api/v1/projects/{project_id}/deployments",
            json={
                "model_name": "demo-classifier",
                "model_version": "4",
                "environment": "staging",
            },
        )

        assert create_response.status_code == 201

        deployment_id = create_response.json()["id"]

        response = client.get(
            f"/api/v1/projects/{project_id}/deployments"
        )

        assert response.status_code == 200

        deployments = response.json()

        assert any(
            deployment["id"] == deployment_id
            for deployment in deployments
        )

    finally:
        cleanup_project(project_id)


def test_missing_model_returns_404() -> None:
    """A nonexistent MLflow model version should return 404."""

    project_id = create_test_project()

    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/deployments",
            json={
                "model_name": "demo-classifier",
                "model_version": "999999",
                "environment": "staging",
            },
        )

        assert response.status_code == 404

        assert (
            "was not found"
            in response.json()["detail"]
        )

    finally:
        cleanup_project(project_id)


def test_missing_project_returns_404() -> None:
    """A nonexistent project should return 404."""

    project_id = "00000000-0000-0000-0000-000000000000"

    response = client.post(
        f"/api/v1/projects/{project_id}/deployments",
        json={
            "model_name": "demo-classifier",
            "model_version": "4",
            "environment": "staging",
        },
    )

    assert response.status_code == 404


def test_invalid_deployment_request_returns_422() -> None:
    """Invalid deployment input should fail Pydantic validation."""

    project_id = create_test_project()

    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/deployments",
            json={
                "model_name": "",
                "model_version": "4",
                "environment": "staging",
            },
        )

        assert response.status_code == 422

    finally:
        cleanup_project(project_id)
