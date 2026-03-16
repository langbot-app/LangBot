from unittest.mock import AsyncMock, MagicMock


def test_runtime_handler_allows_missing_vector_list_action_for_older_plugin_sdk():
    from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
    from src.langbot.pkg.plugin.handler import RuntimeConnectionHandler

    assert not hasattr(PluginToRuntimeAction, 'VECTOR_LIST')

    mock_connection = MagicMock()
    mock_app = MagicMock()
    mock_app.logger = MagicMock()

    handler = RuntimeConnectionHandler(
        connection=mock_connection,
        disconnect_callback=AsyncMock(return_value=False),
        ap=mock_app,
    )

    assert handler is not None
