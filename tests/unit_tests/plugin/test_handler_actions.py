"""Unit tests for RuntimeConnectionHandler action handlers."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToLangBotAction


def make_handler(app):
    """Create a RuntimeConnectionHandler with mocked external connection."""
    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    return RuntimeConnectionHandler(Mock(), AsyncMock(return_value=True), app)


def make_result(first_item=None):
    result = Mock()
    result.first = Mock(return_value=first_item)
    return result


def compiled_params(statement):
    return statement.compile().params


class TestInitializePluginSettings:
    """Tests for initialize_plugin_settings action handler."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.logger = Mock()
        return mock_app

    @pytest.mark.asyncio
    async def test_creates_new_setting_when_not_exists(self, app):
        """New plugin settings use default enabled, priority and config values."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.side_effect = [
            make_result(),
            Mock(),
        ]

        response = await runtime_handler.actions[RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value]({
            'plugin_author': 'test-author',
            'plugin_name': 'test-plugin',
            'install_source': 'local',
            'install_info': {'path': '/test'},
        })

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2
        insert_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert insert_params == {
            'plugin_author': 'test-author',
            'plugin_name': 'test-plugin',
            'install_source': 'local',
            'install_info': {'path': '/test'},
            'enabled': True,
            'priority': 0,
            'config': {},
        }

    @pytest.mark.asyncio
    async def test_inherits_values_from_existing_setting(self, app):
        """Existing settings are replaced while preserving user-controlled values."""
        runtime_handler = make_handler(app)
        existing_setting = SimpleNamespace(
            enabled=False,
            priority=5,
            config={'key': 'value'},
        )
        app.persistence_mgr.execute_async.side_effect = [
            make_result(existing_setting),
            Mock(),
            Mock(),
        ]

        response = await runtime_handler.actions[RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value]({
            'plugin_author': 'test-author',
            'plugin_name': 'test-plugin',
            'install_source': 'github',
            'install_info': {'repo': 'author/name'},
        })

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 3
        insert_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[2].args[0])
        assert insert_params['enabled'] is False
        assert insert_params['priority'] == 5
        assert insert_params['config'] == {'key': 'value'}
        assert insert_params['install_source'] == 'github'
        assert insert_params['install_info'] == {'repo': 'author/name'}


class TestSetBinaryStorage:
    """Tests for set_binary_storage action handler with size limit validation."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.instance_config = Mock()
        mock_app.instance_config.data = {
            'plugin': {
                'binary_storage': {
                    'max_value_bytes': 1024,
                },
            },
        }
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=make_result())
        mock_app.logger = Mock()
        return mock_app

    @staticmethod
    def payload(value: bytes):
        return {
            'key': 'test-key',
            'owner_type': 'plugin',
            'owner': 'test-owner',
            'value_base64': base64.b64encode(value).decode('utf-8'),
        }

    @pytest.mark.asyncio
    async def test_rejects_value_exceeding_limit(self, app):
        """Values larger than max_value_bytes are rejected before persistence writes."""
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'x' * 2048)
        )

        assert response.code != 0
        assert '2048 > 1024 bytes' in response.message
        app.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_accepts_value_within_limit_and_inserts_storage(self, app):
        """A new small value is inserted into binary storage."""
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'x' * 512)
        )

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2
        insert_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert insert_params['unique_key'] == 'plugin:test-owner:test-key'
        assert insert_params['value'] == b'x' * 512

    @pytest.mark.asyncio
    async def test_updates_existing_storage(self, app):
        """An existing binary storage row is updated instead of inserted."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result(SimpleNamespace(value=b'old'))

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'new')
        )

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2
        update_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_params['value'] == b'new'

    @pytest.mark.asyncio
    async def test_invalid_max_value_bytes_falls_back_to_default_limit(self, app):
        """Invalid max_value_bytes uses the 10MB default limit."""
        runtime_handler = make_handler(app)
        app.instance_config.data['plugin']['binary_storage']['max_value_bytes'] = 'invalid'

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'x' * (10 * 1024 * 1024 + 1))
        )

        assert response.code != 0
        assert '10485761 > 10485760 bytes' in response.message
        app.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_negative_limit_disables_size_check(self, app):
        """Negative max_value_bytes allows values larger than the normal default."""
        runtime_handler = make_handler(app)
        app.instance_config.data['plugin']['binary_storage']['max_value_bytes'] = -1

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'x' * 2048)
        )

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2

    @pytest.mark.asyncio
    async def test_zero_limit_rejects_non_empty_values(self, app):
        """A zero byte limit rejects non-empty values."""
        runtime_handler = make_handler(app)
        app.instance_config.data['plugin']['binary_storage']['max_value_bytes'] = 0

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](
            self.payload(b'x')
        )

        assert response.code != 0
        assert '1 > 0 bytes' in response.message
        app.persistence_mgr.execute_async.assert_not_awaited()


class TestGetPluginSettings:
    """Tests for get_plugin_settings action handler with defaults."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock()
        return mock_app

    @pytest.mark.asyncio
    async def test_returns_defaults_when_setting_not_found(self, app):
        """Default plugin settings are returned when no persisted row exists."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result()

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value]({
            'plugin_author': 'test-author',
            'plugin_name': 'test-plugin',
        })

        assert response.code == 0
        assert response.data == {
            'enabled': True,
            'priority': 0,
            'plugin_config': {},
            'install_source': 'local',
            'install_info': {},
        }

    @pytest.mark.asyncio
    async def test_returns_actual_values_when_setting_exists(self, app):
        """Persisted plugin setting values override defaults."""
        runtime_handler = make_handler(app)
        setting = SimpleNamespace(
            enabled=False,
            priority=10,
            config={'custom': 'config'},
            install_source='github',
            install_info={'repo': 'test/repo'},
        )
        app.persistence_mgr.execute_async.return_value = make_result(setting)

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value]({
            'plugin_author': 'test-author',
            'plugin_name': 'test-plugin',
        })

        assert response.code == 0
        assert response.data == {
            'enabled': False,
            'priority': 10,
            'plugin_config': {'custom': 'config'},
            'install_source': 'github',
            'install_info': {'repo': 'test/repo'},
        }


class TestGetBinaryStorage:
    """Tests for get_binary_storage action handler."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock()
        return mock_app

    @pytest.mark.asyncio
    async def test_returns_base64_encoded_value(self, app):
        """Stored bytes are returned as base64."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result(SimpleNamespace(value=b'test binary content'))

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_BINARY_STORAGE.value]({
            'key': 'test-key',
            'owner_type': 'plugin',
            'owner': 'test-owner',
        })

        assert response.code == 0
        assert response.data == {
            'value_base64': base64.b64encode(b'test binary content').decode('utf-8'),
        }

    @pytest.mark.asyncio
    async def test_returns_error_when_not_found(self, app):
        """Missing binary storage rows return an error response."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result()

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_BINARY_STORAGE.value]({
            'key': 'test-key',
            'owner_type': 'plugin',
            'owner': 'test-owner',
        })

        assert response.code != 0
        assert 'Storage with key test-key not found' in response.message


class TestHandlerQueryLookup:
    """Tests for query lookup in cached_queries."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.query_pool = Mock()
        mock_app.query_pool.cached_queries = {}
        mock_app.logger = Mock()
        return mock_app

    @pytest.mark.asyncio
    async def test_query_not_found_returns_error(self, app):
        """Query-bound actions return error when query_id is not cached."""
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_BOT_UUID.value]({
            'query_id': 'nonexistent-query',
        })

        assert response.code != 0
        assert 'nonexistent-query' in response.message

    @pytest.mark.asyncio
    async def test_query_found_returns_success(self, app):
        """Query-bound actions read data from the cached query object."""
        runtime_handler = make_handler(app)
        query = SimpleNamespace(variables={}, bot_uuid='test-bot-uuid')
        app.query_pool.cached_queries['existing-query'] = query

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_BOT_UUID.value]({
            'query_id': 'existing-query',
        })

        assert response.code == 0
        assert response.data == {'bot_uuid': 'test-bot-uuid'}
