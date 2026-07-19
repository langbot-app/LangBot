"""Unit tests for RuntimeConnectionHandler action handlers."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToLangBotAction
from langbot_plugin.entities.io.context import ActionContext

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.storage.mgr import StorageMgr


TEST_EXECUTION_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
)


def canonical_binary_key(owner_type: str, owner: str, key: str) -> str:
    return StorageMgr.canonical_binary_storage_key(
        TEST_EXECUTION_CONTEXT,
        owner_type=owner_type,
        owner=owner,
        key=key,
    )


def make_handler(app, workspace_context: ActionContext | None = None):
    """Create a RuntimeConnectionHandler with mocked external connection."""
    from langbot.pkg.plugin.handler import RuntimeConnectionHandler

    workspace_context = workspace_context or ActionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    app.workspace_service = SimpleNamespace(
        get_execution_binding=AsyncMock(
            return_value=SimpleNamespace(
                instance_uuid=workspace_context.instance_uuid,
                workspace_uuid=workspace_context.workspace_uuid,
                placement_generation=workspace_context.placement_generation,
            )
        )
    )
    runtime_handler = RuntimeConnectionHandler(
        Mock(),
        AsyncMock(return_value=True),
        app,
        workspace_context,
    )
    installation_uuid = runtime_handler._remember_installation(
        workspace_context,
        'test-author',
        'test-plugin',
    )
    runtime_handler.bind_action_context(workspace_context.for_installation(installation_uuid))
    query_pool = getattr(app, 'query_pool', None)
    if query_pool is not None and hasattr(query_pool, 'cached_queries'):

        def scoped_query(query):
            if query is not None:
                query.instance_uuid = workspace_context.instance_uuid
                query.workspace_uuid = workspace_context.workspace_uuid
                query.placement_generation = workspace_context.placement_generation
            return query

        query_pool.get_query = AsyncMock(
            side_effect=lambda workspace_uuid, query_uuid: scoped_query(query_pool.cached_queries.get(query_uuid))
        )
        query_pool.get_query_by_legacy_id = AsyncMock(
            side_effect=lambda workspace_uuid, query_id: scoped_query(query_pool.cached_queries.get(query_id))
        )
    return runtime_handler


def make_result(first_item=None):
    result = Mock()
    result.first = Mock(return_value=first_item)
    return result


def compiled_params(statement):
    return statement.compile().params


class TestRagRerankAction:
    """Tests for RAG rerank action handler."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.model_mgr = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock(return_value=make_result(SimpleNamespace(uuid='rerank-1')))
        mock_app.logger = Mock()
        return mock_app

    @pytest.mark.asyncio
    async def test_invokes_rerank_model_and_sorts_scores(self, app):
        """Rerank action uses the selected model and returns top scores."""
        provider = Mock()
        provider.invoke_rerank = AsyncMock(
            return_value=[
                {'index': 0, 'relevance_score': 0.2},
                {'index': 1, 'relevance_score': 0.9},
            ]
        )
        rerank_model = SimpleNamespace(provider=provider)
        app.model_mgr.get_rerank_model_by_uuid = AsyncMock(return_value=rerank_model)
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[PluginToRuntimeAction.INVOKE_RERANK.value](
            {
                'rerank_model_uuid': 'rerank-1',
                'query': 'hello',
                'documents': ['a', 'b'],
                'top_k': 1,
                'extra_args': {'return_documents': False},
            }
        )

        assert response.code == 0
        assert response.data['results'] == [{'index': 1, 'relevance_score': 0.9}]
        app.model_mgr.get_rerank_model_by_uuid.assert_awaited_once_with(
            TEST_EXECUTION_CONTEXT,
            'rerank-1',
        )
        provider.invoke_rerank.assert_awaited_once_with(
            model=rerank_model,
            query='hello',
            documents=['a', 'b'],
            extra_args={'return_documents': False},
            execution_context=TEST_EXECUTION_CONTEXT,
        )

    @pytest.mark.asyncio
    async def test_returns_error_when_rerank_model_missing(self, app):
        """Missing rerank model returns an action error."""
        app.model_mgr.get_rerank_model_by_uuid = AsyncMock(side_effect=ValueError('not found'))
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[PluginToRuntimeAction.INVOKE_RERANK.value](
            {
                'rerank_model_uuid': 'missing',
                'query': 'hello',
                'documents': ['a'],
            }
        )

        assert response.code != 0
        assert 'Rerank model with rerank_model_uuid missing not found' in response.message


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

        response = await runtime_handler.actions[RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value](
            {
                'plugin_author': 'test-author',
                'plugin_name': 'test-plugin',
                'install_source': 'local',
                'install_info': {'path': '/test'},
            }
        )

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2
        insert_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert insert_params == {
            'workspace_uuid': 'workspace-a',
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

        response = await runtime_handler.actions[RuntimeToLangBotAction.INITIALIZE_PLUGIN_SETTINGS.value](
            {
                'plugin_author': 'test-author',
                'plugin_name': 'test-plugin',
                'install_source': 'github',
                'install_info': {'repo': 'author/name'},
            }
        )

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
        assert insert_params['workspace_uuid'] == 'workspace-a'
        assert insert_params['unique_key'] == canonical_binary_key(
            'plugin',
            'test-author/test-plugin',
            'test-key',
        )
        assert insert_params['value'] == b'x' * 512

    @pytest.mark.asyncio
    async def test_updates_existing_storage(self, app):
        """An existing binary storage row is updated instead of inserted."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result(SimpleNamespace(value=b'old'))

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](self.payload(b'new'))

        assert response.code == 0
        assert app.persistence_mgr.execute_async.await_count == 2
        select_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[0].args[0])
        update_params = compiled_params(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        expected_key = canonical_binary_key(
            'plugin',
            'test-author/test-plugin',
            'test-key',
        )
        assert expected_key in select_params.values()
        assert expected_key in update_params.values()
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

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](self.payload(b'x'))

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

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value](
            {
                'plugin_author': 'test-author',
                'plugin_name': 'test-plugin',
            }
        )

        assert response.code == 0
        assert response.data == {
            'enabled': True,
            'priority': 0,
            'plugin_config': {},
            'install_source': 'local',
            'install_info': {},
            'installation_uuid': runtime_handler.derive_installation_uuid(
                runtime_handler.require_bound_action_context(),
                'test-author',
                'test-plugin',
            ),
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

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_PLUGIN_SETTINGS.value](
            {
                'plugin_author': 'test-author',
                'plugin_name': 'test-plugin',
            }
        )

        assert response.code == 0
        assert response.data == {
            'enabled': False,
            'priority': 10,
            'plugin_config': {'custom': 'config'},
            'install_source': 'github',
            'install_info': {'repo': 'test/repo'},
            'installation_uuid': runtime_handler.derive_installation_uuid(
                runtime_handler.require_bound_action_context(),
                'test-author',
                'test-plugin',
            ),
        }


class TestGetConfigFile:
    """Plugin config files remain bound to the trusted runtime placement."""

    WORKSPACE_A = '11111111-1111-4111-8111-111111111111'
    WORKSPACE_B = '22222222-2222-4222-8222-222222222222'

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock()
        mock_app.storage_mgr = StorageMgr(mock_app)
        mock_app.storage_mgr.storage_provider = SimpleNamespace(load=AsyncMock(return_value=b'plugin config bytes'))
        mock_app.logger = Mock()
        return mock_app

    @staticmethod
    def object_key(
        *,
        workspace_uuid: str = WORKSPACE_A,
        placement_generation: int = 1,
        owner_type: str = 'plugin_config',
    ) -> str:
        return StorageMgr.scoped_object_key(
            ExecutionContext(
                instance_uuid='instance-a',
                workspace_uuid=workspace_uuid,
                placement_generation=placement_generation,
            ),
            owner_type=owner_type,
            owner=workspace_uuid,
            key='config.json',
        )

    async def invoke(self, app, file_key: str):
        runtime_handler = make_handler(
            app,
            ActionContext(
                instance_uuid='instance-a',
                workspace_uuid=self.WORKSPACE_A,
                placement_generation=1,
            ),
        )
        app.persistence_mgr.execute_async.return_value = make_result(
            SimpleNamespace(config={'uploaded_file': file_key})
        )
        return await runtime_handler.actions[PluginToRuntimeAction.GET_CONFIG_FILE.value]({'file_key': file_key})

    @pytest.mark.asyncio
    async def test_loads_config_file_from_same_workspace_generation(self, app):
        file_key = self.object_key()

        response = await self.invoke(app, file_key)

        assert response.code == 0
        assert base64.b64decode(response.data['file_base64']) == b'plugin config bytes'
        app.storage_mgr.storage_provider.load.assert_awaited_once_with(file_key)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'file_key',
        [
            object_key.__func__(workspace_uuid=WORKSPACE_B),
            object_key.__func__(placement_generation=2),
            object_key.__func__(owner_type='upload_document'),
        ],
        ids=['other-workspace', 'stale-generation', 'wrong-owner-type'],
    )
    async def test_rejects_config_file_outside_trusted_scope(self, app, file_key):
        response = await self.invoke(app, file_key)

        assert response.code != 0
        assert 'Failed to load config file' in response.message
        app.storage_mgr.storage_provider.load.assert_not_awaited()


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

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_BINARY_STORAGE.value](
            {
                'key': 'test-key',
                'owner_type': 'plugin',
                'owner': 'test-owner',
            }
        )

        assert response.code == 0
        assert response.data == {
            'value_base64': base64.b64encode(b'test binary content').decode('utf-8'),
        }
        statement_params = compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert 'workspace-a' in statement_params.values()
        assert (
            canonical_binary_key(
                'plugin',
                'test-author/test-plugin',
                'test-key',
            )
            in statement_params.values()
        )

    @pytest.mark.asyncio
    async def test_returns_error_when_not_found(self, app):
        """Missing binary storage rows return an error response."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result()

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_BINARY_STORAGE.value](
            {
                'key': 'test-key',
                'owner_type': 'plugin',
                'owner': 'test-owner',
            }
        )

        assert response.code != 0
        assert 'Storage with key test-key not found' in response.message


class TestDeleteAndListBinaryStorage:
    """Delete/list remain fenced to the trusted canonical owner scope."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.persistence_mgr = Mock()
        mock_app.persistence_mgr.execute_async = AsyncMock()
        return mock_app

    @pytest.mark.asyncio
    async def test_delete_uses_workspace_and_canonical_unique_key(self, app):
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[RuntimeToLangBotAction.DELETE_BINARY_STORAGE.value](
            {
                'key': 'test-key',
                'owner_type': 'plugin',
                'owner': 'forged-owner',
            }
        )

        assert response.code == 0
        statement_params = compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert 'workspace-a' in statement_params.values()
        assert (
            canonical_binary_key(
                'plugin',
                'test-author/test-plugin',
                'test-key',
            )
            in statement_params.values()
        )
        assert 'forged-owner' not in statement_params.values()

    @pytest.mark.asyncio
    async def test_list_keys_uses_trusted_plugin_owner(self, app):
        result = Mock()
        result.scalars.return_value.all.return_value = ['first', 'second']
        app.persistence_mgr.execute_async.return_value = result
        runtime_handler = make_handler(app)

        response = await runtime_handler.actions[RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS.value](
            {
                'owner_type': 'plugin',
                'owner': 'forged-owner',
            }
        )

        assert response.code == 0
        assert response.data == {'keys': ['first', 'second']}
        statement_params = compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert 'workspace-a' in statement_params.values()
        assert 'test-author/test-plugin' in statement_params.values()
        assert 'forged-owner' not in statement_params.values()


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

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_BOT_UUID.value](
            {
                'query_id': 'nonexistent-query',
            }
        )

        assert response.code != 0
        assert 'nonexistent-query' in response.message

    @pytest.mark.asyncio
    async def test_query_found_returns_success(self, app):
        """Query-bound actions read data from the cached query object."""
        runtime_handler = make_handler(app)
        query = SimpleNamespace(variables={}, bot_uuid='test-bot-uuid')
        app.query_pool.cached_queries['existing-query'] = query

        response = await runtime_handler.actions[PluginToRuntimeAction.GET_BOT_UUID.value](
            {
                'query_id': 'existing-query',
            }
        )

        assert response.code == 0
        assert response.data == {'bot_uuid': 'test-bot-uuid'}
