"""Tests for DifyServiceAPIRunner pure utility methods.

Tests the helper methods that don't require real Dify API calls.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

import langbot_plugin.api.entities.builtin.platform.message as platform_message


class TestDifyWorkflowSubmitClient:
    @pytest.mark.asyncio
    async def test_rejects_empty_error_response_before_iterating_sse(self, monkeypatch):
        from langbot.libs.dify_service_api.v1 import client, errors

        class FakeResponse:
            status_code = 503

            async def aread(self):
                return b''

            async def aiter_lines(self):
                raise AssertionError('error responses must not enter the SSE loop')
                yield

        class FakeStreamContext:
            async def __aenter__(self):
                return FakeResponse()

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        class FakeClient:
            def __init__(self, **kwargs):
                del kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, *args, **kwargs):
                del args, kwargs
                response = MagicMock()
                response.status_code = 200
                return response

            def stream(self, *args, **kwargs):
                del args, kwargs
                return FakeStreamContext()

        monkeypatch.setattr(client.httpx, 'AsyncClient', FakeClient)
        dify_client = client.AsyncDifyServiceClient('test-key', 'https://dify.example/v1')

        with pytest.raises(errors.DifyAPIError, match='503'):
            await anext(
                dify_client.workflow_submit(
                    form_token='token-1',
                    workflow_run_id='run-1',
                    inputs={},
                    user='person_user-1',
                )
            )


class TestDifyExtractTextOutput:
    """Tests for _extract_dify_text_output method."""

    def _create_runner(self):
        """Create runner instance."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'chat',
                    'api-key': 'test-key',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}},
        }

        runner = DifyServiceAPIRunner(mock_app, pipeline_config)
        runner.dify_client = MagicMock()

        return runner

    def test_extract_none_value(self):
        """None returns empty string."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output(None)

        assert result == ''

    def test_extract_string_value(self):
        """Plain string is returned."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('plain text')

        assert result == 'plain text'

    def test_extract_dict_with_content(self):
        """Dict with 'content' key extracts content."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output({'content': 'extracted content'})

        assert result == 'extracted content'

    def test_extract_dict_without_content(self):
        """Dict without 'content' key is JSON dumped."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output({'key': 'value'})

        assert 'key' in result
        assert 'value' in result

    def test_extract_json_string_with_content(self):
        """JSON string with 'content' key extracts content."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('{"content": "json content"}')

        assert result == 'json content'

    def test_extract_json_string_without_content(self):
        """JSON string without 'content' key returns original."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('{"other": "value"}')

        assert '{"other": "value"}' in result

    def test_extract_whitespace_string(self):
        """Whitespace string returns empty."""
        runner = self._create_runner()

        result = runner._extract_dify_text_output('   ')

        assert result == ''


class TestDifyRunnerConfigValidation:
    """Tests for runner config validation."""

    def test_invalid_app_type_raises(self):
        """Invalid app-type raises DifyAPIError."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner
        from langbot.libs.dify_service_api.v1.errors import DifyAPIError

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'invalid-type',
                    'api-key': 'test',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}},
        }

        with pytest.raises(DifyAPIError, match='不支持'):
            DifyServiceAPIRunner(mock_app, pipeline_config)

    def test_valid_app_types(self):
        """Valid app-types don't raise."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()

        for app_type in ['chat', 'agent', 'workflow', 'chatflow']:
            pipeline_config = {
                'ai': {
                    'dify-service-api': {
                        'app-type': app_type,
                        'api-key': 'test',
                        'base-url': 'https://api.dify.ai',
                    }
                },
                'output': {'misc': {}},
            }

            runner = DifyServiceAPIRunner(mock_app, pipeline_config)
            # Should not raise
            assert runner is not None


class TestDifyRunnerInit:
    """Tests for runner initialization."""

    def test_runner_stores_config(self):
        """Runner stores pipeline_config."""
        from unittest.mock import MagicMock

        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'chat',
                    'api-key': 'test-key',
                    'base-url': 'https://api.dify.ai',
                }
            },
            'output': {'misc': {}},
        }

        runner = DifyServiceAPIRunner(mock_app, pipeline_config)

        assert runner.pipeline_config == pipeline_config
        assert runner.ap == mock_app


class TestDifyHumanInputForms:
    """Tests for Dify human-input form helpers."""

    def _create_runner(self):
        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        mock_app.logger = MagicMock()
        pipeline_config = {
            'ai': {
                'dify-service-api': {
                    'app-type': 'workflow',
                    'api-key': 'test-key',
                    'base-url': 'https://api.dify.ai',
                    'base-prompt': '',
                }
            },
            'output': {'misc': {}},
        }
        runner = DifyServiceAPIRunner(mock_app, pipeline_config)
        runner.dify_client = MagicMock()
        runner.dify_client.upload_file = AsyncMock(return_value={'id': 'upload-1'})
        return runner

    def test_pending_forms_are_isolated_by_bot_and_pipeline(self):
        from langbot.pkg.provider.runners import difysvapi

        query_a = MagicMock()
        query_a.bot_uuid = 'bot-a'
        query_a.pipeline_uuid = 'pipeline-a'
        query_a.session.launcher_type.value = 'person'
        query_a.session.launcher_id = 'shared-user'

        query_b = MagicMock()
        query_b.bot_uuid = 'bot-b'
        query_b.pipeline_uuid = 'pipeline-a'
        query_b.session.launcher_type.value = 'person'
        query_b.session.launcher_id = 'shared-user'

        query_c = MagicMock()
        query_c.bot_uuid = 'bot-a'
        query_c.pipeline_uuid = 'pipeline-b'
        query_c.session.launcher_type.value = 'person'
        query_c.session.launcher_id = 'shared-user'

        key_a = difysvapi._session_key_from_query(query_a)
        key_b = difysvapi._session_key_from_query(query_b)
        key_c = difysvapi._session_key_from_query(query_c)
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(key_a, {'form_token': 'token-a', 'workflow_run_id': 'run-a'})
        difysvapi._set_pending_form(key_b, {'form_token': 'token-b', 'workflow_run_id': 'run-b'})
        difysvapi._set_pending_form(key_c, {'form_token': 'token-c', 'workflow_run_id': 'run-c'})

        assert key_a != key_b
        assert key_a != key_c
        assert difysvapi._get_pending_form_by_token(key_a, 'token-a') is not None
        assert difysvapi._get_pending_form_by_token(key_a, 'token-b') is None
        assert difysvapi._get_pending_form_by_token(key_a, 'token-c') is None
        assert difysvapi._get_pending_form_by_token(key_b, 'token-b') is not None
        assert difysvapi._get_pending_form_by_token(key_c, 'token-c') is not None
        assert difysvapi._get_latest_pending_form(key_a)['workflow_run_id'] == 'run-a'
        assert difysvapi._get_latest_pending_form(key_b)['workflow_run_id'] == 'run-b'
        assert difysvapi._get_latest_pending_form(key_c)['workflow_run_id'] == 'run-c'
        assert difysvapi._dify_user_from_query(query_a) == difysvapi._dify_user_from_query(query_b)
        assert difysvapi._dify_user_from_query(query_a) == difysvapi._dify_user_from_query(query_c)
        difysvapi._PENDING_FORMS.clear()

    def test_format_human_input_text_includes_field_help(self):
        from langbot.pkg.provider.runners.difysvapi import _format_human_input_text

        text = _format_human_input_text(
            'Manual Review',
            'Please fill fields.',
            [{'id': 'yes', 'title': 'Yes'}],
            [
                {'output_variable_name': 'comment', 'type': 'paragraph'},
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                },
                {'output_variable_name': 'attachment', 'type': 'file-list', 'number_limits': 2},
            ],
        )

        assert 'comment: <value>' in text
        assert 'choice (select): 1. A, 2. B' in text
        assert 'attachment (file-list' in text
        assert 'action: <number or title>' in text

    def test_form_snapshot_for_platform_omits_action_text_and_placeholders(self):
        from langbot.pkg.provider.runners.difysvapi import _extract_form_snapshot

        snapshot, _, _, display_form_content = _extract_form_snapshot(
            'run-1',
            {
                'form_token': 'token-1',
                'node_title': 'Manual Review',
                'form_content': 'Hello\n\n{{#$output.comment#}}\n\n{{#$output.choice#}}\n',
                'inputs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    },
                ],
                'actions': [{'id': 'yes', 'title': 'Yes'}],
            },
            'person_user-1',
        )

        assert '{{#$output.comment#}}' not in display_form_content
        assert 'Actions:' not in display_form_content
        assert 'comment (paragraph)' in display_form_content
        assert snapshot['form_content'] == display_form_content

    def test_interactive_form_content_is_split_by_field_placeholders(self):
        from langbot.pkg.provider.runners.difysvapi import (
            _action_select_form_data,
            _field_input_form_data,
        )

        input_defs = [
            {'output_variable_name': 'us_input', 'type': 'paragraph'},
            {
                'output_variable_name': 'xiala',
                'type': 'select',
                'option_source': {'type': 'constant', 'value': ['1', '2']},
            },
        ]
        pending_form = {
            'raw_form_content': (
                '1\n请输入你的问题\n{{#$output.us_input#}}\n请选择你的答案\n{{#$output.xiala#}}\n提交前请确认'
            ),
            'input_defs': input_defs,
            'actions': [{'id': 'yes', 'title': 'yes'}],
            'inputs': {},
        }

        first_step = _field_input_form_data(pending_form, input_defs[0])
        second_step = _field_input_form_data(pending_form, input_defs[1])
        action_step = _action_select_form_data(pending_form)

        assert first_step['form_content'] == '1\n请输入你的问题'
        assert second_step['form_content'] == '请选择你的答案'
        assert action_step['form_content'] == '提交前请确认'

    def test_interactive_form_content_without_placeholder_uses_compatibility_fallback(self):
        from langbot.pkg.provider.runners.difysvapi import _field_input_form_data

        field = {'output_variable_name': 'comment', 'type': 'paragraph'}

        form_data = _field_input_form_data({'raw_form_content': 'Please review', 'input_defs': [field]}, field)

        assert form_data['form_content'] == 'comment (paragraph): reply "comment: <value>"'

    @pytest.mark.asyncio
    async def test_match_pending_form_collects_select_and_text_inputs(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    },
                ],
                'inputs': {},
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        action = await runner._match_pending_form_action(
            query,
            session_key,
            'action: yes\ncomment: looks good\nchoice: 2',
        )

        assert action['action_id'] == 'yes'
        assert action['inputs'] == {'comment': 'looks good', 'choice': 'B'}

    @pytest.mark.asyncio
    async def test_collect_form_inputs_uploads_files(self):
        runner = self._create_runner()
        image = platform_message.Image(base64='data:image/png;base64,aGVsbG8=')
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([image])

        inputs = await runner._collect_form_inputs_from_query(
            query,
            {
                'input_defs': [{'output_variable_name': 'photo', 'type': 'file'}],
                'inputs': {},
                'user': 'person_user-1',
            },
            '',
        )

        assert inputs['photo'] == {
            'type': 'image',
            'transfer_method': 'local_file',
            'upload_file_id': 'upload-1',
        }

    @pytest.mark.asyncio
    async def test_partial_input_with_multiple_actions_waits_for_missing_fields(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'actions': [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    },
                ],
                'inputs': {},
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        action = await runner._match_pending_form_action(query, session_key, 'comment: ready')

        assert action['_partial'] is True
        assert action['inputs'] == {'comment': 'ready'}
        assert action['_form_data']['_current_input_field'] == 'choice'
        assert 'choice (select)' in action['notice']
        assert difysvapi._get_latest_pending_form(session_key)['inputs'] == {'comment': 'ready'}

    @pytest.mark.asyncio
    async def test_complete_partial_input_with_multiple_actions_renders_action_form(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'raw_form_content': 'Please review\n\n{{#$output.comment#}}\n',
                'form_content': 'Please review\n\nFields:\n  - comment (paragraph): reply "comment: <value>"',
                'actions': [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}],
                'input_defs': [{'output_variable_name': 'comment', 'type': 'paragraph'}],
                'inputs': {},
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        action = await runner._match_pending_form_action(query, session_key, 'comment: ready')

        assert action['_partial'] is True
        assert action['inputs'] == {'comment': 'ready'}
        assert 'action: <number or title>' in action['notice']
        assert action['_form_data']['_action_select_only'] is True
        assert action['_form_data']['input_defs'] == []
        assert action['_form_data']['actions'] == [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}]
        assert '{{#$output.comment#}}' not in action['_form_data']['form_content']
        assert difysvapi._get_latest_pending_form(session_key)['inputs'] == {'comment': 'ready'}

    @pytest.mark.asyncio
    async def test_sequential_field_collection_advances_one_field_at_a_time(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'actions': [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    },
                ],
                'inputs': {},
                'current_input_field': 'comment',
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        first = await runner._match_pending_form_action(query, session_key, 'looks good')

        assert first['_partial'] is True
        assert first['inputs'] == {'comment': 'looks good'}
        assert first['_form_data']['_current_input_field'] == 'choice'
        assert first['_form_data']['input_defs'][0]['output_variable_name'] == 'comment'
        assert 'choice (select)' in first['_form_data']['form_content']

        second = await runner._match_pending_form_action(query, session_key, '2')

        assert second['_partial'] is True
        assert second['inputs'] == {'comment': 'looks good', 'choice': 'B'}
        assert second['_form_data']['_action_select_only'] is True

    @pytest.mark.asyncio
    async def test_digit_reply_fills_missing_select_before_matching_action_number(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'actions': [
                    {'id': 'yes', 'title': 'yes'},
                    {'id': 'no', 'title': 'no'},
                    {'id': 'or', 'title': 'or'},
                    {'id': 'but', 'title': 'but'},
                ],
                'input_defs': [
                    {'output_variable_name': 'us_input', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'xiala',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['1', '2']},
                    },
                ],
                'inputs': {'us_input': 'hello'},
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        action = await runner._match_pending_form_action(query, session_key, '2')

        assert action['_partial'] is True
        assert action['inputs'] == {'us_input': 'hello', 'xiala': '2'}
        assert action['_form_data']['_action_select_only'] is True

    @pytest.mark.asyncio
    async def test_invalid_select_reply_keeps_the_current_form_field(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'input_defs': [
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    }
                ],
                'inputs': {},
                'current_input_field': 'choice',
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        action = await runner._match_pending_form_action(query, session_key, 'C')

        assert action['_partial'] is True
        assert action['inputs'] == {}
        assert action['_form_data']['_current_input_field'] == 'choice'
        assert 'choice: 1. A, 2. B' in action['notice']
        assert difysvapi._get_latest_pending_form(session_key)['inputs'] == {}

    @pytest.mark.asyncio
    async def test_workflow_pause_without_text_yields_form_chunk(self):
        from langbot.pkg.provider.runners import difysvapi

        async def workflow_run(**kwargs):
            del kwargs
            yield {
                'event': 'workflow_started',
                'data': {'workflow_run_id': 'run-1'},
            }
            yield {
                'event': 'workflow_paused',
                'data': {
                    'workflow_run_id': 'run-1',
                    'reasons': [
                        {
                            'TYPE': 'human_input_required',
                            'form_token': 'token-1',
                            'node_title': 'Manual Review',
                            'form_content': 'Please review\n\n{{#$output.comment#}}\n',
                            'inputs': [{'output_variable_name': 'comment', 'type': 'paragraph'}],
                            'actions': [{'id': 'yes', 'title': 'Yes'}],
                        }
                    ],
                },
            }

        runner = self._create_runner()
        runner.dify_client.workflow_run = workflow_run
        query = MagicMock()
        query.session.launcher_type.value = 'person'
        query.session.launcher_id = 'user-1'
        query.session.using_conversation.uuid = 'conversation-1'
        query.variables = {
            'session_id': 'session-1',
            'conversation_id': 'conversation-1',
            'msg_create_time': '0',
        }
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='hello')])

        difysvapi._PENDING_FORMS.clear()
        chunks = [chunk async for chunk in runner._workflow_messages_chunk(query)]

        assert chunks[-1].is_final is True
        assert chunks[-1].content == difysvapi._STREAM_FORM_PLACEHOLDER
        assert chunks[-1]._form_data['form_token'] == 'token-1'
        assert chunks[-1]._form_data['_current_input_field'] == 'comment'

    @pytest.mark.asyncio
    async def test_action_after_partial_input_reuses_saved_inputs(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'node_title': 'Manual Review',
                'actions': [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}],
                'input_defs': [{'output_variable_name': 'comment', 'type': 'paragraph'}],
                'inputs': {},
                'user': session_key,
            },
        )
        query = MagicMock()
        query.message_chain = platform_message.MessageChain([platform_message.Plain(text='')])

        await runner._match_pending_form_action(query, session_key, 'comment: ready')
        action = await runner._match_pending_form_action(query, session_key, 'action: yes')

        assert action.get('_partial') is not True
        assert action['action_id'] == 'yes'
        assert action['inputs'] == {'comment': 'ready'}

    def test_form_action_merges_card_inputs_with_saved_inputs(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {'output_variable_name': 'photo', 'type': 'file'},
                ],
                'inputs': {'photo': {'type': 'image', 'transfer_method': 'local_file', 'upload_file_id': 'upload-1'}},
                'user': session_key,
            },
        )

        action = runner._merge_pending_form_action(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'action_id': 'yes',
                'inputs': {'comment': 'ready'},
            },
        )

        assert action['inputs'] == {
            'comment': 'ready',
            'photo': {'type': 'image', 'transfer_method': 'local_file', 'upload_file_id': 'upload-1'},
        }

    def test_form_action_with_missing_required_file_fields_stays_partial(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {'output_variable_name': 'file', 'type': 'file'},
                    {'output_variable_name': 'files', 'type': 'file-list', 'number_limits': 5},
                ],
                'inputs': {},
                'user': session_key,
            },
        )

        action = runner._merge_pending_form_action(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'action_id': 'yes',
                'inputs': {'comment': 'ready'},
            },
        )

        assert action['_partial'] is True
        assert action['inputs'] == {'comment': 'ready'}
        assert 'file, files' in action['notice']
        assert action['_form_data']['_current_input_field'] == 'file'
        assert action['_form_data']['input_defs'][1]['output_variable_name'] == 'file'

    def test_card_component_input_progress_maps_to_current_field(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}, {'id': 'no', 'title': 'No'}],
                'input_defs': [
                    {'output_variable_name': 'comment', 'type': 'paragraph'},
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['A', 'B']},
                    },
                ],
                'inputs': {},
                'current_input_field': 'comment',
                'user': session_key,
            },
        )

        first = runner._merge_pending_form_action(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'inputs': {'input': 'looks good'},
                '_current_input_field': 'comment',
                '_input_progress': True,
            },
        )

        assert first['_partial'] is True
        assert first['inputs'] == {'comment': 'looks good'}
        assert first['_form_data']['_current_input_field'] == 'choice'

        second = runner._merge_pending_form_action(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'inputs': {'select': '{"index": 1, "value": "B"}'},
                '_current_input_field': 'choice',
                '_input_progress': True,
            },
        )

        assert second['_partial'] is True
        assert second['inputs'] == {'comment': 'looks good', 'choice': 'B'}
        assert second['_form_data']['_action_select_only'] is True

    def test_card_select_preserves_numeric_option_values(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        session_key = 'person_user-1'
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'input_defs': [
                    {
                        'output_variable_name': 'choice',
                        'type': 'select',
                        'option_source': {'type': 'constant', 'value': ['1', '2']},
                    }
                ],
                'inputs': {},
                'current_input_field': 'choice',
                'user': session_key,
            },
        )

        action = runner._merge_pending_form_action(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'inputs': {'select': '1'},
                '_current_input_field': 'choice',
                '_input_progress': True,
            },
        )

        assert action['_partial'] is True
        assert action['inputs'] == {'choice': '1'}

    def test_invalid_card_select_value_is_not_saved(self):
        from langbot.pkg.provider.runners import difysvapi

        form = {
            'input_defs': [
                {
                    'output_variable_name': 'choice',
                    'type': 'select',
                    'option_source': {'type': 'constant', 'value': ['A', 'B']},
                }
            ]
        }

        assert difysvapi._normalize_form_action_inputs(form, {'choice': 'C'}) == {}

    @pytest.mark.asyncio
    async def test_blocking_resume_uses_chatflow_answer_node_output(self):
        runner = self._create_runner()

        async def workflow_submit(**kwargs):
            del kwargs
            yield {'event': 'message', 'answer': 'partial'}
            yield {
                'event': 'node_finished',
                'data': {
                    'node_type': 'answer',
                    'outputs': {'answer': {'content': 'Final chatflow answer'}},
                },
            }
            yield {'event': 'workflow_finished', 'data': {'error': None, 'outputs': {}}}

        runner.dify_client.workflow_submit = workflow_submit

        messages = [
            message
            async for message in runner._submit_workflow_form_blocking(
                {
                    'form_token': 'token-1',
                    'workflow_run_id': 'run-1',
                    'user': 'person_user-1',
                    'action_id': 'yes',
                    'inputs': {},
                },
                ('bot-1', 'pipeline-1', 'adapter.Type', 'person', 'user-1'),
            )
        ]

        assert [message.content for message in messages] == ['Final chatflow answer']

    @pytest.mark.asyncio
    async def test_successful_blocking_resume_clears_pending_form(self):
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        difysvapi._PENDING_FORMS.clear()

        async def workflow_submit(**kwargs):
            del kwargs
            yield {
                'event': 'workflow_finished',
                'data': {'error': None, 'outputs': {'summary': 'Completed'}},
            }

        runner.dify_client.workflow_submit = workflow_submit
        query = MagicMock()
        query.session.launcher_type.value = 'person'
        query.session.launcher_id = 'user-1'
        query.bot_uuid = 'bot-1'
        query.pipeline_uuid = 'pipeline-1'
        session_key = difysvapi._session_key_from_query(query)
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'inputs': {},
                'user': 'person_user-1',
            },
        )
        query.variables = {
            '_dify_form_action': {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'action_id': 'yes',
                'user': 'person_user-1',
                'inputs': {},
            }
        }

        messages = [message async for message in runner._workflow_messages(query)]

        assert [message.content for message in messages] == ['Completed']
        assert difysvapi._get_pending_form_by_token(session_key, 'token-1') is None

    @pytest.mark.asyncio
    async def test_incomplete_blocking_resume_keeps_pending_form_for_retry(self):
        from langbot.libs.dify_service_api.v1.errors import DifyAPIError
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        difysvapi._PENDING_FORMS.clear()

        async def workflow_submit(**kwargs):
            del kwargs
            yield {'event': 'message', 'answer': 'partial answer'}

        runner.dify_client.workflow_submit = workflow_submit
        query = MagicMock()
        query.session.launcher_type.value = 'person'
        query.session.launcher_id = 'user-1'
        query.bot_uuid = 'bot-1'
        query.pipeline_uuid = 'pipeline-1'
        session_key = difysvapi._session_key_from_query(query)
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'inputs': {},
                'user': 'person_user-1',
            },
        )
        query.variables = {
            '_dify_form_action': {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'action_id': 'yes',
                'user': 'person_user-1',
                'inputs': {},
            }
        }

        with pytest.raises(DifyAPIError, match='before a terminal event'):
            _ = [message async for message in runner._workflow_messages(query)]

        assert difysvapi._get_pending_form_by_token(session_key, 'token-1') is not None
        difysvapi._PENDING_FORMS.clear()

    @pytest.mark.asyncio
    async def test_incomplete_streaming_resume_keeps_pending_form_for_retry(self):
        from langbot.libs.dify_service_api.v1.errors import DifyAPIError
        from langbot.pkg.provider.runners import difysvapi

        runner = self._create_runner()
        query = MagicMock()
        query.session.launcher_type.value = 'person'
        query.session.launcher_id = 'user-1'
        query.bot_uuid = 'bot-1'
        query.pipeline_uuid = 'pipeline-1'
        query.variables = {
            '_dify_form_action': {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'action_id': 'yes',
                'user': 'person_user-1',
                'inputs': {},
            }
        }
        session_key = difysvapi._session_key_from_query(query)
        difysvapi._PENDING_FORMS.clear()
        difysvapi._set_pending_form(
            session_key,
            {
                'form_token': 'token-1',
                'workflow_run_id': 'run-1',
                'actions': [{'id': 'yes', 'title': 'Yes'}],
                'inputs': {},
                'user': 'person_user-1',
            },
        )

        async def workflow_submit(**kwargs):
            del kwargs
            yield {'event': 'text_chunk', 'data': {'text': 'partial answer'}}

        runner.dify_client.workflow_submit = workflow_submit

        with pytest.raises(DifyAPIError, match='before a terminal event'):
            _ = [message async for message in runner._workflow_messages_chunk(query)]

        assert difysvapi._get_pending_form_by_token(session_key, 'token-1') is not None
        difysvapi._PENDING_FORMS.clear()


class TestDifyCumulativeStreaming:
    def _create_runner(self, *, remove_think: bool = False):
        from langbot.pkg.provider.runners.difysvapi import DifyServiceAPIRunner

        mock_app = MagicMock()
        mock_app.logger = MagicMock()
        runner = DifyServiceAPIRunner(
            mock_app,
            {
                'ai': {
                    'dify-service-api': {
                        'app-type': 'chat',
                        'api-key': 'test-key',
                        'base-url': 'https://api.dify.ai',
                        'base-prompt': '',
                    }
                },
                'output': {'misc': {'remove-think': remove_think}},
            },
        )
        runner.dify_client = MagicMock()
        return runner

    @staticmethod
    def _query():
        query = MagicMock()
        query.session.launcher_type.value = 'person'
        query.session.launcher_id = 'user-1'
        query.session.using_conversation.uuid = 'conversation-1'
        query.variables = {}
        query.user_message.content = 'hello'
        return query

    def test_merge_stream_text_accepts_deltas_and_snapshots(self):
        from langbot.pkg.provider.runners.difysvapi import _merge_stream_text

        assert _merge_stream_text('Hello', ' world') == 'Hello world'
        assert _merge_stream_text('<think>one', '<think>one two') == '<think>one two'
        assert _merge_stream_text('ha', 'ha') == 'haha'

    @pytest.mark.asyncio
    async def test_chat_stream_deduplicates_cumulative_snapshots(self):
        runner = self._create_runner()
        snapshots = [f'<think>Reasoning{"." * idx}' for idx in range(1, 10)]
        snapshots.append(f'{snapshots[-1]}</think>\nHello!')

        async def chat_messages(**kwargs):
            del kwargs
            for snapshot in snapshots:
                yield {'event': 'message', 'answer': snapshot, 'conversation_id': 'conversation-2'}
            yield {'event': 'message_end', 'conversation_id': 'conversation-2'}

        runner.dify_client.chat_messages = chat_messages

        chunks = [chunk async for chunk in runner._chat_messages_chunk(self._query())]

        assert chunks[-1].content == snapshots[-1]
        assert chunks[-1].content.count('<think>') == 1

    @pytest.mark.asyncio
    async def test_chat_stream_removes_think_from_cumulative_snapshots(self):
        runner = self._create_runner(remove_think=True)

        async def chat_messages(**kwargs):
            del kwargs
            yield {'event': 'message', 'answer': '<think>Reasoning', 'conversation_id': 'conversation-2'}
            yield {
                'event': 'message',
                'answer': '<think>Reasoning complete</think>\nHello!',
                'conversation_id': 'conversation-2',
            }
            yield {'event': 'message_end', 'conversation_id': 'conversation-2'}

        runner.dify_client.chat_messages = chat_messages

        chunks = [chunk async for chunk in runner._chat_messages_chunk(self._query())]

        assert chunks[-1].content == 'Hello!'
        assert all('<think>' not in chunk.content for chunk in chunks if isinstance(chunk.content, str))
