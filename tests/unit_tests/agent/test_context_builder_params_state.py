"""Tests for Pipeline adapter params and prompt packaging."""
from __future__ import annotations

from langbot.pkg.agent.runner.pipeline_adapter import PipelineAdapter


class FakeMessage:
    """Fake prompt/history message."""
    def __init__(self, content='Hello'):
        self.content = content
        self.role = 'user'

    def model_dump(self, mode='json'):
        return {'role': self.role, 'content': self.content}


class FakePrompt:
    """Fake prompt container."""
    def __init__(self, messages=None):
        self.messages = messages or []


class TestBuildParams:
    """Tests for PipelineAdapter.build_params filtering."""

    def test_params_empty_when_no_variables(self):
        query = type('Query', (), {'variables': None})()
        assert PipelineAdapter.build_params(query) == {}

    def test_params_filters_underscore_prefix(self):
        query = type('Query', (), {
            'variables': {
                '_internal_var': 'should_be_excluded',
                '_pipeline_bound_plugins': ['a/b'],
                '_monitoring_bot_name': 'Bot',
                'public_var': 'should_be_included',
            },
        })()

        params = PipelineAdapter.build_params(query)
        assert '_internal_var' not in params
        assert '_pipeline_bound_plugins' not in params
        assert '_monitoring_bot_name' not in params
        assert params['public_var'] == 'should_be_included'

    def test_params_filters_sensitive_naming(self):
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

        params = PipelineAdapter.build_params(query)
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
        assert 'public_name' in params
        assert 'safe_value' in params

    def test_params_keeps_common_public_vars(self):
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

        params = PipelineAdapter.build_params(query)
        assert params['launcher_type'] == 'telegram'
        assert params['launcher_id'] == 'group_123'
        assert params['sender_id'] == 'user_001'
        assert params['session_id'] == 'sess_abc'
        assert params['msg_create_time'] == 1234567890
        assert params['group_name'] == 'Tech Group'
        assert params['sender_name'] == 'John'
        assert params['user_message_text'] == 'Hello world'

    def test_params_filters_non_json_serializable(self):
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
                'custom_object': CustomObject(),
            },
        })()

        params = PipelineAdapter.build_params(query)
        assert 'string_value' in params
        assert 'int_value' in params
        assert 'float_value' in params
        assert 'bool_value' in params
        assert 'null_value' in params
        assert 'list_value' in params
        assert 'dict_value' in params
        assert 'custom_object' not in params

    def test_params_filters_nested_non_serializable(self):
        class CustomObject:
            pass

        query = type('Query', (), {
            'variables': {
                'nested_list_with_bad': ['a', CustomObject(), 'c'],
                'nested_dict_with_bad': {'good': 'value', 'bad': CustomObject()},
                'good_nested_list': ['a', ['b', 'c']],
                'good_nested_dict': {'outer': {'inner': 'value'}},
            },
        })()

        params = PipelineAdapter.build_params(query)
        assert 'nested_list_with_bad' not in params
        assert 'nested_dict_with_bad' not in params
        assert 'good_nested_list' in params
        assert 'good_nested_dict' in params

    def test_is_json_serializable_primitives_and_collections(self):
        assert PipelineAdapter.is_json_serializable(None) is True
        assert PipelineAdapter.is_json_serializable('string') is True
        assert PipelineAdapter.is_json_serializable(42) is True
        assert PipelineAdapter.is_json_serializable(['a', 'b']) is True
        assert PipelineAdapter.is_json_serializable({'key': 'value'}) is True
        assert PipelineAdapter.is_json_serializable((1, 2, 3)) is True

    def test_is_json_serializable_rejects_sets_and_objects(self):
        class CustomObject:
            pass

        assert PipelineAdapter.is_json_serializable(CustomObject()) is False
        assert PipelineAdapter.is_json_serializable({1, 2, 3}) is False
        assert PipelineAdapter.is_json_serializable([1, {2, 3}]) is False
        assert PipelineAdapter.is_json_serializable({'key': {1, 2}}) is False


class TestBuildPrompt:
    """Tests for PipelineAdapter.build_prompt."""

    def test_prompt_empty_when_missing(self):
        query = type('Query', (), {})()
        assert PipelineAdapter.build_prompt(query) == []

    def test_prompt_serializes_messages(self):
        query = type('Query', (), {
            'prompt': FakePrompt([FakeMessage('Effective prompt')]),
        })()

        prompt = PipelineAdapter.build_prompt(query)
        assert prompt == [{'role': 'user', 'content': 'Effective prompt'}]
