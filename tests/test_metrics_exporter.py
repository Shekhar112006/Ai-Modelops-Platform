from __future__ import annotations

import pytest
from prometheus_client import CollectorRegistry

from worker.metrics_exporter import create_registry


def test_registry_requires_multiprocess_directory(
    monkeypatch,
) -> None:
    """Exporter startup must require an explicit shared directory."""

    monkeypatch.delenv(
        "PROMETHEUS_MULTIPROC_DIR",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="PROMETHEUS_MULTIPROC_DIR",
    ):
        create_registry()


def test_registry_rejects_missing_directory(
    tmp_path,
) -> None:
    """Exporter must reject a nonexistent multiprocess directory."""

    missing_directory = tmp_path / "missing"

    with pytest.raises(
        RuntimeError,
        match="does not exist",
    ):
        create_registry(missing_directory)


def test_registry_accepts_existing_directory(
    tmp_path,
) -> None:
    """Exporter can create a registry backed by a shared directory."""

    registry = create_registry(tmp_path)

    assert isinstance(registry, CollectorRegistry)
    assert list(registry.collect()) == []
