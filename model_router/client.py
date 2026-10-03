from __future__ import annotations

import httpx


class ModelServerClient:
    """HTTP client used by the router to communicate with a model server."""

    def __init__(
        self,
        base_url: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")

    async def health(self) -> dict[str, object]:
        """Check whether the model server is healthy."""

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:
            response = await client.get(
                f"{self.base_url}/health"
            )

            response.raise_for_status()

            return response.json()

    async def predict(
        self,
        features: list[float],
    ) -> dict[str, object]:
        """Forward a prediction request to the model server."""

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:
            response = await client.post(
                f"{self.base_url}/predict",
                json={
                    "features": features,
                },
            )

            response.raise_for_status()

            return response.json()
