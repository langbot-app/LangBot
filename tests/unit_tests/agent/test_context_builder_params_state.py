"""Tests for agent run context builder params and state."""
from __future__ import annotations

import pytest

from langbot.pkg.agent.runner.context_builder import AgentRunContextBuilder
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.state_store import reset_state_store

# Import shared test fixtures from conftest.py
from .conftest import make_resources


class FakeApplication:
    """Fake Application for testing."""
    def __init__(self):
        class FakeLogger:
            def info(self, msg):
                pass
            def debug(self, msg):
                pass
            def warning(self, msg):
                pass
            def error(self, msg):
                pass

        class FakeVersionManager:
            def get_current_version(self):
                return '1.0.0'

        self.logger = FakeLogger()
        self.ver_mgr = FakeVersionManager()


def make_descriptor() -> AgentRunnerDescriptor:
    """Create a test descriptor."""
    return AgentRunnerDescriptor(
        id='plugin:langbot/local-agent/default',
        source='plugin',
        label={'en_US': 'Local Agent'},
        plugin_author='langbot',
        plugin_name='local-agent',
        runner_name='default',
        protocol_version='1',
        capabilities={'streaming': True},
    )


class FakeSession:
    """Fake session for testing."""
    def __init__(self):
        self.launcher_type = type('LauncherType', (), {'value': 'telegram'})()
        self.launcher_id = 'group_123'
        self.using_conversation = None


class FakeConversation:
    """Fake conversation for testing."""
    def __init__(self, uuid: str = 'conv_abc'):
        self.uuid = uuid


class FakeMessage:
    """Fake message for testing."""
    def __init__(self, content='Hello'):
        self.content = content
        self.role = 'user'

    def model_dump(self, mode='json'):
        return {'role': self.role, 'content': self.content}


class FakePrompt:
    """Fake prompt container."""
    def __init__(self, messages=None):
        self.messages = messages or []


class FakeAdapter:
    """Fake adapter with streaming capability."""
    async def is_stream_output_supported(self):
        return True


class TestBuildParams:
    """Tests for _build_params filtering."""

    def test_params_empty_when_no_variables(self):
        """Empty variables should produce empty params."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        query = type('Query', (), {
            'variables': None,
        })()

        params = builder._build_params(query)
        assert params == {}

    def test_params_filters_underscore_prefix(self):
        """Params should exclude variables starting with underscore."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        query = type('Query', (), {
            'variables': {
                '_internal_var': 'should_be_excluded',
                '_pipeline_bound_plugins': ['a/b'],
                '_monitoring_bot_name': 'Bot',
                'public_var': 'should_be_included',
            },
        })()

        params = builder._build_params(query)
        assert '_internal_var' not in params
        assert '_pipeline_bound_plugins' not in params
        assert '_monitoring_bot_name' not in params
        assert 'public_var' in params
        assert params['public_var'] == 'should_be_included'

    def test_params_filters_sensitive_naming(self):
        """Params should exclude variables with sensitive naming patterns."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        query = type('Query', (), {
            'variables': {
                'api_key': 'secret123',
                'API_KEY': 'secret456',
                'token': 'tok123',
                'secret': 'sec123',
                'password': 'pass123',
                'credential': 'cred123',
                'user_api_key': 'should_be_excluded',
                'user_secret_key': 'should_be_excluded',
                'my_token_value': 'should_be_excluded',
                'user_password_hash': 'should_be_excluded',
                'public_name': 'should_be_included',
                'safe_value': 'should_be_included',
            },
        })()

        params = builder._build_params(query)
        # All sensitive patterns should be excluded
        assert 'api_key' not in params
        assert 'API_KEY' not in params
        assert 'token' not in params
        assert 'secret' not in params
        assert 'password' not in params
        assert 'credential' not in params
        assert 'user_api_key' not in params
        assert 'user_secret_key' not in params
        assert 'my_token_value' not in params
        assert 'user_password_hash' not in params
        # Public vars should be included
        assert 'public_name' in params
        assert 'safe_value' in params

    def test_params_keeps_common_public_vars(self):
        """Params should keep common public business vars."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        query = type('Query', (), {
            'variables': {
                'launcher_type': 'telegram',
                'launcher_id': 'group_123',
                'sender_id': 'user_001',
                'session_id': 'sess_abc',
                'msg_create_time': 1234567890,
                'group_name': 'Tech Group',
                'sender_name': 'John',
                'user_message_text': 'Hello world',
            },
        })()

        params = builder._build_params(query)
        # All these should be included
        assert params['launcher_type'] == 'telegram'
        assert params['launcher_id'] == 'group_123'
        assert params['sender_id'] == 'user_001'
        assert params['session_id'] == 'sess_abc'
        assert params['msg_create_time'] == 1234567890
        assert params['group_name'] == 'Tech Group'
        assert params['sender_name'] == 'John'
        assert params['user_message_text'] == 'Hello world'

    def test_params_filters_non_json_serializable(self):
        """Params should keep only JSON-serializable values."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        class CustomObject:
            pass

        query = type('Query', (), {
            'variables': {
                'string_value': 'hello',
                'int_value': 42,
                'float_value': 3.14,
                'bool_value': True,
                'null_value': None,
                'list_value': ['a', 'b', 'c'],
                'dict_value': {'nested': 'value'},
                'custom_object': CustomObject(),  # Not serializable
            },
        })()

        params = builder._build_params(query)
        assert 'string_value' in params
        assert 'int_value' in params
        assert 'float_value' in params
        assert 'bool_value' in params
        assert 'null_value' in params
        assert 'list_value' in params
        assert 'dict_value' in params
        assert 'custom_object' not in params

    def test_params_filters_nested_non_serializable(self):
        """Params should filter nested non-serializable values."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        class CustomObject:
            pass

        query = type('Query', (), {
            'variables': {
                'nested_list_with_bad': ['a', CustomObject(), 'c'],  # List with non-serializable
                'nested_dict_with_bad': {'good': 'value', 'bad': CustomObject()},  # Dict with non-serializable
                'good_nested_list': ['a', ['b', 'c']],
                'good_nested_dict': {'outer': {'inner': 'value'}},
            },
        })()

        params = builder._build_params(query)
        # Nested with bad should be excluded
        assert 'nested_list_with_bad' not in params
        assert 'nested_dict_with_bad' not in params
        # Good nested should be included
        assert 'good_nested_list' in params
        assert 'good_nested_dict' in params

    def test_is_json_serializable_primitives(self):
        """_is_json_serializable should return True for primitives."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        assert builder._is_json_serializable(None) is True
        assert builder._is_json_serializable('string') is True
        assert builder._is_json_serializable(42) is True
        assert builder._is_json_serializable(3.14) is True
        assert builder._is_json_serializable(True) is True
        assert builder._is_json_serializable(False) is True

    def test_is_json_serializable_collections(self):
        """_is_json_serializable should check nested collections."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        assert builder._is_json_serializable([]) is True
        assert builder._is_json_serializable(['a', 'b']) is True
        assert builder._is_json_serializable({}) is True
        assert builder._is_json_serializable({'key': 'value'}) is True
        assert builder._is_json_serializable([1, 2, [3, 4]]) is True
        assert builder._is_json_serializable({'a': {'b': 'c'}}) is True

    def test_is_json_serializable_custom_objects(self):
        """_is_json_serializable should return False for custom objects."""
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        class CustomObject:
            pass

        assert builder._is_json_serializable(CustomObject()) is False
        assert builder._is_json_serializable([CustomObject()]) is False
        assert builder._is_json_serializable({'key': CustomObject()}) is False

    def test_is_json_serializable_set_not_allowed(self):
        """_is_json_serializable should return False for set (not JSON-serializable).

        json.dumps({"x": {1}}) fails because set is not JSON-serializable.
        Only list and tuple are allowed.
        """
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        # set is NOT JSON-serializable
        assert builder._is_json_serializable({1, 2, 3}) is False
        assert builder._is_json_serializable({'a', 'b'}) is False
        # list and tuple ARE allowed
        assert builder._is_json_serializable([1, 2, 3]) is True
        assert builder._is_json_serializable((1, 2, 3)) is True
        # Nested set should also be rejected
        assert builder._is_json_serializable([1, {2, 3}]) is False
        assert builder._is_json_serializable({'key': {1, 2}}) is False

    def test_params_filters_set_values(self):
        """Params should filter out variables with set values.

        set is not JSON-serializable and would cause json.dumps to fail.
        """
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)

        query = type('Query', (), {
            'variables': {
                'list_value': ['a', 'b', 'c'],
                'tuple_value': ('a', 'b', 'c'),
                'set_value': {'a', 'b', 'c'},  # Should be filtered
                'nested_with_set': ['a', {'b', 'c'}],  # Should be filtered
                'dict_with_set': {'items': {1, 2}},  # Should be filtered
            },
        })()

        params = builder._build_params(query)
        # list and tuple should be included
        assert 'list_value' in params
        assert params['list_value'] == ['a', 'b', 'c']
        assert 'tuple_value' in params
        # set should be filtered
        assert 'set_value' not in params
        assert 'nested_with_set' not in params
        assert 'dict_with_set' not in params


class TestBuildState:
    """Tests for state snapshot building."""

    @pytest.mark.asyncio
    async def test_context_has_state_field(self):
        """AgentRunContextV1 should have state field."""
        reset_state_store()
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)
        descriptor = make_descriptor()
        resources = make_resources()

        session = FakeSession()
        query = type('Query', (), {
            'query_id': 1,
            'bot_uuid': 'bot_001',
            'pipeline_uuid': 'pipeline_001',
            'sender_id': 'user_001',
            'session': session,
            'user_message': None,
            'message_chain': None,
            'messages': [],
            'pipeline_config': {},
            'variables': {},
        })()

        context = await builder.build_context(query, descriptor, resources)

        assert 'state' in context
        assert 'conversation' in context['state']
        assert 'actor' in context['state']
        assert 'subject' in context['state']
        assert 'runner' in context['state']

    @pytest.mark.asyncio
    async def test_state_seeds_conversation_id_from_existing(self):
        """State should seed external.conversation_id from existing conversation uuid."""
        reset_state_store()
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)
        descriptor = make_descriptor()
        resources = make_resources()

        conversation = FakeConversation(uuid='conv_existing')
        session = FakeSession()
        session.using_conversation = conversation
        query = type('Query', (), {
            'query_id': 1,
            'bot_uuid': 'bot_001',
            'pipeline_uuid': 'pipeline_001',
            'sender_id': 'user_001',
            'session': session,
            'user_message': None,
            'message_chain': None,
            'messages': [],
            'pipeline_config': {},
            'variables': {},
        })()

        context = await builder.build_context(query, descriptor, resources)

        assert context['state']['conversation']['external.conversation_id'] == 'conv_existing'


class TestBuildParamsInContext:
    """Tests for params in full context."""

    @pytest.mark.asyncio
    async def test_context_has_params_field(self):
        """AgentRunContextV1 should have params field."""
        reset_state_store()
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)
        descriptor = make_descriptor()
        resources = make_resources()

        session = FakeSession()
        query = type('Query', (), {
            'query_id': 1,
            'bot_uuid': 'bot_001',
            'pipeline_uuid': 'pipeline_001',
            'sender_id': 'user_001',
            'session': session,
            'user_message': None,
            'message_chain': None,
            'messages': [],
            'pipeline_config': {},
            'variables': {
                'public_param': 'value',
                '_private': 'excluded',
            },
        })()

        context = await builder.build_context(query, descriptor, resources)

        assert 'params' in context
        assert context['params']['public_param'] == 'value'
        assert '_private' not in context['params']

    @pytest.mark.asyncio
    async def test_params_and_state_both_present(self):
        """Context should have both params and state."""
        reset_state_store()
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)
        descriptor = make_descriptor()
        resources = make_resources()

        conversation = FakeConversation(uuid='conv_abc')
        session = FakeSession()
        session.using_conversation = conversation
        query = type('Query', (), {
            'query_id': 1,
            'bot_uuid': 'bot_001',
            'pipeline_uuid': 'pipeline_001',
            'sender_id': 'user_001',
            'session': session,
            'user_message': None,
            'message_chain': None,
            'messages': [],
            'pipeline_config': {},
            'variables': {
                'workflow_input': 'user_question',
                'sender_name': 'John',
            },
        })()

        context = await builder.build_context(query, descriptor, resources)

        # params should have public vars
        assert 'params' in context
        assert context['params']['workflow_input'] == 'user_question'
        assert context['params']['sender_name'] == 'John'

        # state should have seeded conversation_id
        assert 'state' in context
        assert context['state']['conversation']['external.conversation_id'] == 'conv_abc'

    @pytest.mark.asyncio
    async def test_context_includes_effective_prompt_and_runtime_capabilities(self):
        """Context should expose host-preprocessed prompt and adapter capabilities."""
        reset_state_store()
        ap = FakeApplication()
        builder = AgentRunContextBuilder(ap)
        descriptor = make_descriptor()
        resources = make_resources()

        session = FakeSession()
        query = type('Query', (), {
            'query_id': 1,
            'bot_uuid': 'bot_001',
            'pipeline_uuid': 'pipeline_001',
            'sender_id': 'user_001',
            'session': session,
            'user_message': None,
            'message_chain': None,
            'messages': [],
            'prompt': FakePrompt([FakeMessage('Effective prompt')]),
            'adapter': FakeAdapter(),
            'pipeline_config': {'output': {'misc': {'remove-think': True}}},
            'variables': {},
        })()

        context = await builder.build_context(query, descriptor, resources)

        assert context['prompt'][0]['content'] == 'Effective prompt'
        assert context['runtime']['metadata']['streaming_supported'] is True
        assert context['runtime']['metadata']['remove_think'] is True
