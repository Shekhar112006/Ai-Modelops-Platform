from __future__ import annotations

import re

from platform_version import PLATFORM_VERSION


def test_platform_version_uses_semantic_versioning() -> None:
    """The central platform version follows MAJOR.MINOR.PATCH."""

    pattern = r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"

    assert re.fullmatch(pattern, PLATFORM_VERSION), (
        f"Invalid platform version: {PLATFORM_VERSION!r}"
    )


def test_fastapi_services_use_central_platform_version() -> None:
    """All application APIs report the shared platform version."""

    from backend.app.main import app as control_plane_app
    from model_router.main import app as model_router_app
    from model_server.main import app as model_server_app

    service_versions = {
        "control plane": control_plane_app.version,
        "model router": model_router_app.version,
        "model server": model_server_app.version,
    }

    for service_name, version in service_versions.items():
        assert version == PLATFORM_VERSION, (
            f"{service_name} reports {version!r}; "
            f"expected {PLATFORM_VERSION!r}"
        )
