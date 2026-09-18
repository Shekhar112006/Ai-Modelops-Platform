from unittest.mock import MagicMock, patch

from ml.registry.model_registry import (
    REGISTERED_MODEL_NAME,
    mark_as_candidate,
)


@patch("ml.registry.model_registry.get_registry_client")
def test_mark_as_candidate(mock_get_client: MagicMock) -> None:
    """Candidate alias and lifecycle tag should be assigned correctly."""

    mock_client = mock_get_client.return_value

    mark_as_candidate(
        model_name=REGISTERED_MODEL_NAME,
        model_version="1",
    )

    mock_client.set_registered_model_alias.assert_called_once_with(
        name=REGISTERED_MODEL_NAME,
        alias="candidate",
        version="1",
    )

    mock_client.set_model_version_tag.assert_called_once_with(
        name=REGISTERED_MODEL_NAME,
        version="1",
        key="lifecycle_status",
        value="candidate",
    )