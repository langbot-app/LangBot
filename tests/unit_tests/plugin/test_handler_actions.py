"""Unit tests for RuntimeConnectionHandler action handlers."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction, RuntimeToLangBotAction

from langbot.pkg.provider.tools.errors import ToolExecutionDeniedError


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


def make_agent_resources(
    models: list[dict] | None = None,
    tools: list[dict] | None = None,
    knowledge_bases: list[dict] | None = None,
):
    """Create a minimal AgentRun resources payload for run-scoped action tests."""
    return {
        'models': models or [],
        'tools': tools or [],
        'knowledge_bases': knowledge_bases or [],
        'files': [],
        'storage': {'plugin_storage': False, 'workspace_storage': False},
        'platform_capabilities': {},
    }


class TestRagRerankAction:
    """Tests for RAG rerank action handler."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.model_mgr = Mock()
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
        app.model_mgr.get_rerank_model_by_uuid.assert_awaited_once_with('rerank-1')
        provider.invoke_rerank.assert_awaited_once_with(
            model=rerank_model,
            query='hello',
            documents=['a', 'b'],
            extra_args={'return_documents': False},
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
        assert insert_params['unique_key'] == 'plugin:test-owner:test-key'
        assert insert_params['value'] == b'x' * 512

    @pytest.mark.asyncio
    async def test_updates_existing_storage(self, app):
        """An existing binary storage row is updated instead of inserted."""
        runtime_handler = make_handler(app)
        app.persistence_mgr.execute_async.return_value = make_result(SimpleNamespace(value=b'old'))

        response = await runtime_handler.actions[RuntimeToLangBotAction.SET_BINARY_STORAGE.value](self.payload(b'new'))

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


class TestAgentRunProxyActions:
    """Tests for AgentRunner proxy actions that need host Query semantics."""

    @pytest.fixture
    def app(self):
        mock_app = Mock()
        mock_app.logger = Mock()
        mock_app.query_pool = Mock()
        mock_app.query_pool.cached_queries = {}
        mock_app.model_mgr = Mock()
        mock_app.model_mgr.get_model_by_uuid = AsyncMock()
        mock_app.model_mgr.get_rerank_model_by_uuid = AsyncMock()
        mock_app.tool_mgr = Mock()
        mock_app.tool_mgr.execute_func_call = AsyncMock(return_value={'ok': True})
        mock_app.tool_mgr.get_tool_detail = AsyncMock(
            return_value={
                'name': 'test/search',
                'description': 'Search test data',
                'human_desc': 'Search',
                'parameters': {'type': 'object'},
            }
        )
        return mock_app

    @staticmethod
    def query(remove_think=True):
        return SimpleNamespace(
            pipeline_config={'output': {'misc': {'remove-think': remove_think}}},
            variables={},
            prompt=SimpleNamespace(messages=[provider_message.Message(role='system', content='effective prompt')]),
        )

    @pytest.mark.asyncio
    async def test_get_prompt_returns_query_effective_prompt(self, app):
        """GET_PROMPT returns the preprocessed Query prompt for the active run."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_get_prompt'
        query = self.query()
        app.query_pool.cached_queries[900] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=900,
            plugin_identity='test/runner',
            resources=make_agent_resources(),
            available_apis={'prompt_get': True},
        )

        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.GET_PROMPT.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert response.data['prompt'][0]['role'] == 'system'
        assert response.data['prompt'][0]['content'] == 'effective prompt'

    @pytest.mark.asyncio
    async def test_invoke_llm_restores_query_and_model_options(self, app):
        """INVOKE_LLM passes Query, model extra_args and remove-think to provider."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_invoke_llm_options'
        query = self.query(remove_think=True)
        app.query_pool.cached_queries[901] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=901,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'llm_001'}]),
        )

        provider = SimpleNamespace(
            invoke_llm=AsyncMock(return_value=provider_message.Message(role='assistant', content='ok')),
        )
        model = SimpleNamespace(
            model_entity=SimpleNamespace(
                abilities=['func_call'],
                extra_args={'temperature': 0.2, 'top_p': 0.8},
            ),
            provider=provider,
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.INVOKE_LLM.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_001',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                    'funcs': [
                        {
                            'name': 'search',
                            'human_desc': 'Search',
                            'description': 'Search',
                            'parameters': {'type': 'object'},
                        }
                    ],
                    'extra_args': {'temperature': 0.7, 'presence_penalty': 0.1},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        provider.invoke_llm.assert_awaited_once()
        kwargs = provider.invoke_llm.await_args.kwargs
        assert kwargs['query'] is query
        assert kwargs['extra_args'] == {
            'temperature': 0.7,
            'top_p': 0.8,
            'presence_penalty': 0.1,
        }
        assert kwargs['remove_think'] is True
        assert [tool.name for tool in kwargs['funcs']] == ['search']

    @pytest.mark.asyncio
    async def test_invoke_llm_returns_provider_usage(self, app):
        """INVOKE_LLM includes optional provider usage in the action response."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        from langbot.pkg.provider.modelmgr import requester as model_requester

        usage = {
            'prompt_tokens': 11,
            'completion_tokens': 7,
            'total_tokens': 18,
            'prompt_tokens_details': {'cached_tokens': 3},
        }

        class UsageProvider:
            async def invoke_llm(self, **kwargs):
                kwargs['query'].variables[model_requester.LLM_USAGE_QUERY_VARIABLE] = usage
                return provider_message.Message(role='assistant', content='ok')

        run_id = 'run_proxy_invoke_llm_usage'
        query = self.query()
        app.query_pool.cached_queries[905] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=905,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'llm_usage_001'}]),
        )

        model = SimpleNamespace(
            model_entity=SimpleNamespace(abilities=[], extra_args={}),
            provider=UsageProvider(),
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.INVOKE_LLM.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_usage_001',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert response.data['message']['content'] == 'ok'
        assert response.data['usage'] == usage
        assert model_requester.LLM_USAGE_QUERY_VARIABLE not in query.variables

    @pytest.mark.asyncio
    async def test_count_tokens_validates_run_authorization_and_calls_provider(self, app):
        """COUNT_TOKENS is run-scoped and forwards messages/tools to the model requester."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_count_tokens'
        query = self.query()
        app.query_pool.cached_queries[906] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=906,
            plugin_identity='test/runner',
            resources=make_agent_resources(
                models=[{'model_id': 'llm_count_001', 'operations': ['count_tokens']}],
            ),
        )

        requester = SimpleNamespace(count_tokens=AsyncMock(return_value=37))
        model = SimpleNamespace(
            model_entity=SimpleNamespace(abilities=[], extra_args={'temperature': 0.2}),
            provider=SimpleNamespace(requester=requester),
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.COUNT_TOKENS.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_count_001',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                    'funcs': [
                        {
                            'name': 'search',
                            'human_desc': 'Search',
                            'description': 'Search',
                            'parameters': {'type': 'object'},
                        }
                    ],
                    'extra_args': {'temperature': 0.7},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert response.data == {'tokens': 37}
        requester.count_tokens.assert_awaited_once()
        kwargs = requester.count_tokens.await_args.kwargs
        assert kwargs['model'] is model
        assert kwargs['messages'][0].content == 'hello'
        assert [tool.name for tool in kwargs['funcs']] == ['search']
        assert kwargs['extra_args'] == {'temperature': 0.7}

    @pytest.mark.asyncio
    async def test_count_tokens_rejects_model_without_operation(self, app):
        """COUNT_TOKENS requires the explicit model operation in the run snapshot."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_count_tokens_denied'
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=make_agent_resources(
                models=[{'model_id': 'llm_count_002', 'operations': ['invoke']}],
            ),
        )

        runtime_handler = make_handler(app)
        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.COUNT_TOKENS.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_count_002',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code != 0
        assert 'operation count_tokens' in response.message
        app.model_mgr.get_model_by_uuid.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_restores_query_and_options(self, app):
        """INVOKE_LLM_STREAM applies the same host context as non-streaming calls."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        class StreamProvider:
            def __init__(self):
                self.kwargs = None

            async def invoke_llm_stream(self, **kwargs):
                self.kwargs = kwargs
                yield provider_message.MessageChunk(role='assistant', content='hi')

        run_id = 'run_proxy_invoke_llm_stream_options'
        query = self.query(remove_think=False)
        app.query_pool.cached_queries[902] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=902,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'llm_stream_001'}]),
        )

        provider = StreamProvider()
        model = SimpleNamespace(
            model_entity=SimpleNamespace(abilities=[], extra_args={'max_tokens': 128}),
            provider=provider,
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        responses = []
        try:
            stream = runtime_handler.actions[PluginToRuntimeAction.INVOKE_LLM_STREAM.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_stream_001',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                    'funcs': [
                        {
                            'name': 'search',
                            'human_desc': 'Search',
                            'description': 'Search',
                            'parameters': {'type': 'object'},
                        }
                    ],
                    'extra_args': {'max_tokens': 256},
                    'remove_think': True,
                }
            )
            async for response in stream:
                responses.append(response)
        finally:
            await registry.unregister(run_id)

        assert [response.code for response in responses] == [0]
        assert provider.kwargs['query'] is query
        assert provider.kwargs['extra_args'] == {'max_tokens': 256}
        assert provider.kwargs['remove_think'] is True
        assert provider.kwargs['funcs'] == []

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_skips_none_chunks(self, app):
        """INVOKE_LLM_STREAM tolerates provider heartbeat/no-op chunks."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        class StreamProvider:
            async def invoke_llm_stream(self, **kwargs):
                yield provider_message.MessageChunk(role='assistant', content='ok')
                yield None
                yield provider_message.MessageChunk(role='assistant', content=' done', is_final=True)

        run_id = 'run_proxy_invoke_llm_stream_none_chunks'
        query = self.query()
        app.query_pool.cached_queries[904] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=904,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'llm_stream_002'}]),
        )

        model = SimpleNamespace(
            model_entity=SimpleNamespace(abilities=[], extra_args={}),
            provider=StreamProvider(),
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        responses = []
        try:
            stream = runtime_handler.actions[PluginToRuntimeAction.INVOKE_LLM_STREAM.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_stream_002',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                }
            )
            async for response in stream:
                responses.append(response)
        finally:
            await registry.unregister(run_id)

        assert [response.code for response in responses] == [0, 0]
        assert [response.data['chunk']['content'] for response in responses] == ['ok', ' done']

    @pytest.mark.asyncio
    async def test_invoke_llm_stream_returns_provider_usage_event(self, app):
        """INVOKE_LLM_STREAM emits a final usage-only action response when available."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        from langbot.pkg.provider.modelmgr import requester as model_requester

        usage = {
            'prompt_tokens': 9,
            'completion_tokens': 4,
            'total_tokens': 13,
            'prompt_tokens_details': {'cached_tokens': 2},
        }

        class StreamProvider:
            async def invoke_llm_stream(self, **kwargs):
                yield provider_message.MessageChunk(role='assistant', content='ok')
                kwargs['query'].variables[model_requester.LLM_USAGE_QUERY_VARIABLE] = usage

        run_id = 'run_proxy_invoke_llm_stream_usage'
        query = self.query()
        app.query_pool.cached_queries[906] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=906,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'llm_stream_usage_001'}]),
        )

        model = SimpleNamespace(
            model_entity=SimpleNamespace(abilities=[], extra_args={}),
            provider=StreamProvider(),
        )
        app.model_mgr.get_model_by_uuid.return_value = model
        runtime_handler = make_handler(app)

        responses = []
        try:
            stream = runtime_handler.actions[PluginToRuntimeAction.INVOKE_LLM_STREAM.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'llm_model_uuid': 'llm_stream_usage_001',
                    'messages': [{'role': 'user', 'content': 'hello'}],
                }
            )
            async for response in stream:
                responses.append(response)
        finally:
            await registry.unregister(run_id)

        assert [response.code for response in responses] == [0, 0]
        assert responses[0].data['chunk']['content'] == 'ok'
        assert responses[1].data == {'usage': usage}
        assert model_requester.LLM_USAGE_QUERY_VARIABLE not in query.variables

    @pytest.mark.asyncio
    async def test_call_tool_passes_current_query(self, app):
        """CALL_TOOL passes the current Query back into tool execution."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_call_tool_query'
        query = self.query()
        app.query_pool.cached_queries[903] = query

        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=903,
            plugin_identity='test/runner',
            resources=make_agent_resources(
                tools=[
                    {
                        'tool_name': 'test/search',
                        'source': 'mcp',
                        'source_id': 'bound-mcp',
                    }
                ]
            ),
        )

        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.CALL_TOOL.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'test/search',
                    'parameters': {'q': 'langbot'},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert getattr(query, '_agent_run_session')['run_id'] == run_id
        app.tool_mgr.execute_func_call.assert_awaited_once_with(
            name='test/search',
            parameters={'q': 'langbot'},
            query=query,
            source_ref={'source': 'mcp', 'source_id': 'bound-mcp'},
        )

    @pytest.mark.asyncio
    async def test_get_tool_detail_passes_frozen_source_ref(self, app):
        """GET_TOOL_DETAIL resolves only the implementation frozen for the run."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_get_tool_detail_source'
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=make_agent_resources(
                tools=[
                    {
                        'tool_name': 'test/search',
                        'source': 'mcp',
                        'source_id': 'bound-mcp',
                    }
                ]
            ),
        )
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.GET_TOOL_DETAIL.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'test/search',
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        app.tool_mgr.get_tool_detail.assert_awaited_once_with(
            'test/search',
            source_ref={'source': 'mcp', 'source_id': 'bound-mcp'},
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ('action', 'action_payload', 'manager_method'),
        [
            pytest.param(
                PluginToRuntimeAction.CALL_TOOL,
                {'parameters': {'q': 'langbot'}},
                'execute_func_call',
                id='call',
            ),
            pytest.param(
                PluginToRuntimeAction.GET_TOOL_DETAIL,
                {},
                'get_tool_detail',
                id='detail',
            ),
        ],
    )
    @pytest.mark.parametrize(
        'tool_resource',
        [
            pytest.param(
                {'tool_name': 'test/search', 'source_id': 'bound-mcp'},
                id='missing-source',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 'mcp'},
                id='missing-source-id',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 7, 'source_id': 'bound-mcp'},
                id='invalid-source-type',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 'mcp', 'source_id': 7},
                id='invalid-source-id-type',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 'mcp', 'source_id': None},
                id='unscoped-mcp-source',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 'plugin', 'source_id': None},
                id='unscoped-plugin-source',
            ),
            pytest.param(
                {'tool_name': 'test/search', 'source': 'builtin', 'source_id': 'unexpected'},
                id='builtin-source-id',
            ),
        ],
    )
    async def test_tool_actions_reject_malformed_frozen_source_identity(
        self,
        app,
        action,
        action_payload,
        manager_method,
        tool_resource,
    ):
        """Run-scoped tool actions never fall back from a malformed authorization snapshot."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = f'run_proxy_malformed_source_{action.value}'
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=make_agent_resources(tools=[tool_resource]),
        )
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[action.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'test/search',
                    **action_payload,
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code != 0
        assert response.message == 'Tool test/search has an invalid frozen source identity for this agent run'
        getattr(app.tool_mgr, manager_method).assert_not_awaited()

    @pytest.mark.asyncio
    async def test_call_tool_returns_error_when_host_denies_execution(self, app):
        """CALL_TOOL preserves the existing error response when a loader denies execution."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_call_tool_denied'
        query = self.query()
        app.query_pool.cached_queries[907] = query
        app.tool_mgr.execute_func_call.side_effect = ToolExecutionDeniedError(
            'langbot_mcp_read_resource',
            'MCP resource agent reads are disabled',
        )
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=907,
            plugin_identity='test/runner',
            resources=make_agent_resources(
                tools=[
                    {
                        'tool_name': 'langbot_mcp_read_resource',
                        'source': 'mcp',
                        'source_id': None,
                    }
                ]
            ),
        )
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.CALL_TOOL.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'langbot_mcp_read_resource',
                    'parameters': {'server_name': 'docs', 'uri': 'file:///README.md'},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code != 0
        assert 'Failed to execute tool langbot_mcp_read_resource' in response.message
        assert 'MCP resource agent reads are disabled' in response.message

    @pytest.mark.asyncio
    async def test_call_tool_falls_back_to_host_execution_query(self, app):
        """Pure EBA runs use their Host-only Query when no cached Query exists."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_call_tool_event_first'
        query = self.query()
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=make_agent_resources(tools=[{'tool_name': 'exec', 'source': 'builtin', 'source_id': None}]),
            execution_query=query,
        )

        runtime_handler = make_handler(app)
        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.CALL_TOOL.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'exec',
                    'parameters': {'command': 'pwd'},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert getattr(query, '_agent_run_session')['run_id'] == run_id
        app.tool_mgr.execute_func_call.assert_awaited_once_with(
            name='exec',
            parameters={'command': 'pwd'},
            query=query,
            source_ref={'source': 'builtin', 'source_id': None},
        )

    @pytest.mark.asyncio
    async def test_pure_event_call_tool_exec_uses_native_host_path(self, app):
        """A pure EBA run can call authorized native exec through CALL_TOOL."""
        from langbot.pkg.agent.runner.execution_context import build_execution_query
        from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
        from langbot.pkg.agent.runner.session_registry import get_session_registry
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.toolmgr import ToolManager
        from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
        from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput

        event = AgentEventEnvelope(
            event_id='event-native-exec',
            event_type='message.received',
            source='platform',
            bot_id='bot-1',
            conversation_id='person_user-1',
            input=AgentInput(text='run pwd'),
            delivery=DeliveryContext(
                surface='platform',
                reply_target={'target_type': 'person', 'target_id': 'user-1'},
                platform_capabilities={'adapter': 'TestAdapter'},
            ),
        )
        query = build_execution_query(event, [])
        app.box_service = SimpleNamespace(
            execute_tool=AsyncMock(
                return_value={
                    'ok': True,
                    'session_id': 'lb-box-test',
                    'stdout': '/workspace\n',
                    'stderr': '',
                }
            ),
        )
        app.monitoring_service = None
        app.skill_mgr = None
        native_loader = NativeToolLoader(app)
        native_loader._backend_available = True
        tool_mgr = ToolManager(app)
        tool_mgr.native_tool_loader = native_loader
        tool_mgr.plugin_tool_loader = Mock()
        tool_mgr.mcp_tool_loader = Mock()
        tool_mgr.skill_tool_loader = Mock()
        app.tool_mgr = tool_mgr

        run_id = 'run_pure_event_native_exec'
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=None,
            plugin_identity='test/runner',
            resources=make_agent_resources(tools=[{'tool_name': 'exec', 'source': 'builtin', 'source_id': None}]),
            execution_query=query,
        )

        runtime_handler = make_handler(app)
        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.CALL_TOOL.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'tool_name': 'exec',
                    'parameters': {'command': 'pwd'},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert response.data['result']['ok'] is True
        assert response.data['result']['stdout'] == '/workspace\n'
        app.box_service.execute_tool.assert_awaited_once_with({'command': 'pwd'}, query)

    @pytest.mark.asyncio
    async def test_invoke_rerank_uses_authorized_model_and_extra_args(self, app):
        """INVOKE_RERANK validates run-scoped model access and merges model extra_args."""
        from langbot.pkg.agent.runner.session_registry import get_session_registry

        run_id = 'run_proxy_rerank_options'
        registry = get_session_registry()
        await registry.unregister(run_id)
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test/runner/default',
            query_id=904,
            plugin_identity='test/runner',
            resources=make_agent_resources(models=[{'model_id': 'rerank_001'}]),
        )

        provider = SimpleNamespace(
            invoke_rerank=AsyncMock(
                return_value=[
                    {'index': 0, 'relevance_score': 0.2},
                    {'index': 1, 'relevance_score': 0.9},
                ]
            ),
        )
        rerank_model = SimpleNamespace(
            model_entity=SimpleNamespace(extra_args={'top_n': 5, 'return_documents': False}),
            provider=provider,
        )
        app.model_mgr.get_rerank_model_by_uuid.return_value = rerank_model
        runtime_handler = make_handler(app)

        try:
            response = await runtime_handler.actions[PluginToRuntimeAction.INVOKE_RERANK.value](
                {
                    'run_id': run_id,
                    'caller_plugin_identity': 'test/runner',
                    'rerank_model_uuid': 'rerank_001',
                    'query': 'hello',
                    'documents': ['a', 'b'],
                    'top_k': 1,
                    'extra_args': {'top_n': 2},
                }
            )
        finally:
            await registry.unregister(run_id)

        assert response.code == 0
        assert response.data['results'] == [{'index': 1, 'relevance_score': 0.9}]
        provider.invoke_rerank.assert_awaited_once()
        kwargs = provider.invoke_rerank.await_args.kwargs
        assert kwargs['extra_args'] == {'top_n': 2, 'return_documents': False}
