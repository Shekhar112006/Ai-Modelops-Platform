from __future__ import annotations

import secrets
from collections.abc import Sequence

from backend.app.models.deployment import Deployment


class NoRoutableDeploymentError(ValueError):
    """Raised when no deployment can receive traffic."""


def select_weighted_deployment(
    deployments: Sequence[Deployment],
    random_bucket: int | None = None,
) -> Deployment:
    """
    Select one deployment using its configured traffic percentage.

    Traffic percentages must total 100 across deployments that
    participate in routing.
    """

    routable = [
        deployment
        for deployment in deployments
        if deployment.traffic_percentage > 0
    ]

    if not routable:
        raise NoRoutableDeploymentError(
            "No deployment with traffic was found."
        )

    for deployment in routable:
        if not deployment.model_endpoint:
            raise ValueError(
                f"Deployment '{deployment.id}' has traffic "
                "but no model serving endpoint."
            )

    total_traffic = sum(
        deployment.traffic_percentage
        for deployment in routable
    )

    if total_traffic != 100:
        raise ValueError(
            "Routable deployment traffic must total 100%. "
            f"Current total is {total_traffic}%."
        )

    if random_bucket is None:
        random_bucket = secrets.randbelow(100)

    if not 0 <= random_bucket < 100:
        raise ValueError(
            "Random bucket must be between 0 and 99."
        )

    cumulative = 0

    for deployment in routable:
        cumulative += deployment.traffic_percentage

        if random_bucket < cumulative:
            return deployment

    raise RuntimeError(
        "Weighted deployment selection failed unexpectedly."
    )
