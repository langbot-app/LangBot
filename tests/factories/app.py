"""
Fake application factory for tests.

Provides a mock Application object with all dependencies needed by pipeline stages.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock


class FakeApp:
    """Mock Application object providing all basic dependencies needed by stages."""

    def __init__(
        self,
        *,
        command_prefix: list[str] = ["/", "!"],
        command_enable: bool = True,
        pipeline_concurrency: int = 10,
        admins: list[str] | None = None,
        **extra_attrs,
    ):
        self.logger = self._create_mock_logger()
        self.sess_mgr = self._create_mock_session_manager()
        self.model_mgr = self._create_mock_model_manager()
        self.tool_mgr = self._create_mock_tool_manager()
        self.plugin_connector = self._create_mock_plugin_connector()
        self.persistence_mgr = self._create_mock_persistence_manager()
        self.query_pool = self._create_mock_query_pool()
        self.instance_config = self._create_mock_instance_config(
            command_prefix=command_prefix,
            command_enable=command_enable,
            pipeline_concurrency=pipeline_concurrency,
            admins=admins or [],
        )
        self.task_mgr = self._create_mock_task_manager()

        # Handler-specific optional attributes
        self.telemetry = self._create_mock_telemetry()
        self.survey = None
        self.cmd_mgr = self._create_mock_cmd_mgr()

        # Apply any extra attributes for specific test scenarios
        for name, value in extra_attrs.items():
            setattr(self, name, value)

        # Captured outbound messages (for assertions)
        self._outbound_messages: list = []

    def _create_mock_logger(self):
        logger = Mock()
        logger.debug = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        return logger

    def _create_mock_session_manager(self):
        sess_mgr = AsyncMock()
        sess_mgr.get_session = AsyncMock()
        sess_mgr.get_conversation = AsyncMock()
        return sess_mgr

    def _create_mock_model_manager(self):
        model_mgr = AsyncMock()
        model_mgr.get_model_by_uuid = AsyncMock()
        return model_mgr

    def _create_mock_tool_manager(self):
        tool_mgr = AsyncMock()
        tool_mgr.get_all_tools = AsyncMock(return_value=[])
        return tool_mgr

    def _create_mock_plugin_connector(self):
        plugin_connector = AsyncMock()
        plugin_connector.emit_event = AsyncMock()
        return plugin_connector

    def _create_mock_persistence_manager(self):
        persistence_mgr = AsyncMock()
        persistence_mgr.execute_async = AsyncMock()
        return persistence_mgr

    def _create_mock_query_pool(self):
        query_pool = Mock()
        query_pool.cached_queries = {}
        query_pool.queries = []
        query_pool.condition = AsyncMock()
        return query_pool

    def _create_mock_instance_config(
        self,
        command_prefix: list[str],
        command_enable: bool,
        pipeline_concurrency: int,
        admins: list[str],
    ):
        instance_config = Mock()
        instance_config.data = {
            "command": {"prefix": command_prefix, "enable": command_enable},
            "concurrency": {"pipeline": pipeline_concurrency},
            "admins": admins,
        }
        return instance_config

    def _create_mock_task_manager(self):
        task_mgr = Mock()
        task_mgr.create_task = Mock()
        return task_mgr

    def _create_mock_telemetry(self):
        telemetry = AsyncMock()
        telemetry.start_send_task = AsyncMock()
        return telemetry

    def _create_mock_cmd_mgr(self):
        cmd_mgr = AsyncMock()
        cmd_mgr.execute = AsyncMock()
        return cmd_mgr

    def capture_message(self, message):
        """Capture an outbound message for test assertions."""
        self._outbound_messages.append(message)

    def get_outbound_messages(self) -> list:
        """Get all captured outbound messages."""
        return self._outbound_messages.copy()

    def clear_outbound_messages(self):
        """Clear captured outbound messages."""
        self._outbound_messages.clear()


def fake_app(**kwargs) -> FakeApp:
    """Create a FakeApp instance with optional overrides."""
    return FakeApp(**kwargs)