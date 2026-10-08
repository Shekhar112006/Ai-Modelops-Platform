from __future__ import annotations

from types import SimpleNamespace

import pytest

from model_router.selector import (
    select_weighted_deployment,
)


def deployment(
    version: str,
    traffic: int,
    endpoint: str = "http://model-server:8000",
):
    """Create a lightweight deployment test object."""

    return SimpleNamespace(
        id=f"deployment-{version}",
        model_name="demo-classifier",
        model_version=version,
        traffic_percentage=traffic,
        model_endpoint=endpoint,
    )


def test_bucket_selects_stable_deployment() -> None:
    """Buckets inside stable traffic select the stable model."""

    stable = deployment("4", 95)
    canary = deployment(
        "5",
        5,
        endpoint="http://canary-server:8000",
    )

    selected = select_weighted_deployment(
        [stable, canary],
        random_bucket=50,
    )

    assert selected.model_version == "4"


def test_bucket_selects_canary_deployment() -> None:
    """Buckets inside canary traffic select the canary model."""

    stable = deployment("4", 95)
    canary = deployment(
        "5",
        5,
        endpoint="http://canary-server:8000",
    )

    selected = select_weighted_deployment(
        [stable, canary],
        random_bucket=95,
    )

    assert selected.model_version == "5"


def test_last_canary_bucket_selects_canary() -> None:
    """The final canary bucket should still select the canary."""

    stable = deployment("4", 95)
    canary = deployment(
        "5",
        5,
        endpoint="http://canary-server:8000",
    )

    selected = select_weighted_deployment(
        [stable, canary],
        random_bucket=99,
    )

    assert selected.model_version == "5"


def test_traffic_must_total_100() -> None:
    """Invalid total traffic should be rejected."""

    stable = deployment("4", 90)
    canary = deployment("5", 20)

    with pytest.raises(
        ValueError,
        match="must total 100",
    ):
        select_weighted_deployment(
            [stable, canary],
            random_bucket=50,
        )


def test_deployment_with_traffic_requires_endpoint() -> None:
    """A traffic-bearing deployment must have an endpoint."""

    stable = deployment("4", 95)
    canary = deployment(
        "5",
        5,
        endpoint="",
    )

    with pytest.raises(
        ValueError,
        match="no model serving endpoint",
    ):
        select_weighted_deployment(
            [stable, canary],
            random_bucket=95,
        )


def test_empty_routing_set_is_rejected() -> None:
    """There must be at least one traffic-bearing deployment."""

    with pytest.raises(
        ValueError,
        match="No deployment with traffic",
    ):
        select_weighted_deployment(
            [],
            random_bucket=0,
        )
