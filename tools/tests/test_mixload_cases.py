"""Configuration and fixture oracles for actual mixload cases."""

from copy import deepcopy
import json
from pathlib import Path

import unittest

from tools.entrypoints.mock_llm import select_message, validate_scenarios
from tools.regression.mixload_cases import (
    CASE_MODELS,
    CASE_WIRE_STREAMS,
    MEDIA_DATA_URL,
    configure_mock_scenarios,
    extend_mixload_profile,
)


TOOLS = Path(__file__).resolve().parents[1]


def read(rel):
    return json.loads((TOOLS / rel).read_text())


class MixloadCaseTests(unittest.TestCase):
    def test_mixload_uses_distinct_vision_runner_and_preserves_stock_profile_host(self):
        self._test_mixload_uses_distinct_vision_runner_and_preserves_stock_profile('host')

    def test_mixload_uses_distinct_vision_runner_and_preserves_stock_profile_docker(self):
        self._test_mixload_uses_distinct_vision_runner_and_preserves_stock_profile('docker')

    def _test_mixload_uses_distinct_vision_runner_and_preserves_stock_profile(self, backend):
        profile = read('profiles/endurance.json')
        original = deepcopy(profile)
        result = extend_mixload_profile(profile, box_backend=backend)

        assert profile == original
        resources = {row['id']: row['body'] for row in result['resources']}
        cases = {row['name']: row for row in result['cases']}
        assert set(cases) == (set(CASE_MODELS) - {'memory_chat'}) == {'chat', 'box', 'rag_chat', 'media_chat'}
        assert cases['box']['box_exec']['backend'] == backend
        assert cases['media_chat']['http_group']['components'] == [{'type': 'Image', 'base64': MEDIA_DATA_URL}]
        assert '/bots/${media_bot}/sync' in cases['media_chat']['http_group']['url']
        assert resources['media_bot']['event_bindings'][0]['target_uuid'] == '${media_pipeline}'
        pipeline = resources['media_pipeline']['config']['ai']
        runner_id = pipeline['runner']['id']
        assert runner_id == 'plugin:langbot-team/LocalAgent/default'
        assert pipeline['runner_config'][runner_id]['model']['primary'] == '${media_model}'
        assert 'vision' in resources['media_model']['abilities']
        assert resources['media_model']['name'] == CASE_MODELS['media_chat']
        assert CASE_WIRE_STREAMS['media_chat'] == CASE_WIRE_STREAMS['chat'] == 'mock'
        assert resources['media_model']['provider_uuid'] == resources['chat_model']['provider_uuid']

    def test_mock_preserves_real_tool_feedback_and_backend_identity_host(self):
        self._test_mock_preserves_real_tool_feedback_and_backend_identity('host')

    def test_mock_preserves_real_tool_feedback_and_backend_identity_docker(self):
        self._test_mock_preserves_real_tool_feedback_and_backend_identity('docker')

    def _test_mock_preserves_real_tool_feedback_and_backend_identity(self, backend):
        scenarios = read('fixtures/mock_llm_scenarios.json')
        original = deepcopy(scenarios)
        configured = configure_mock_scenarios(scenarios, box_backend=backend)

        validate_scenarios(configured)
        steps = configured['mock-smoke-box']['steps']
        assert scenarios == original
        assert steps[-1]['content'] == 'LANGBOT_BOX_OK'
        assert all(step['expect_tool_output'] == 'LANGBOT_BOX_SENTINEL' for step in steps[1:])
        calls = [step['tool_calls'][0]['arguments']['command'] for step in steps[:-1]]
        assert all(('$(hostname)' in command) == (backend == 'docker') for command in calls)
        assert all('/tmp/' not in command and 'mixload-box-probe.txt' in command for command in calls)
        assert ' > ' in calls[0] and ' > ' not in calls[1]

    def test_media_oracle_requires_exact_image_from_current_attachment_tool_none(self):
        self._test_media_oracle_requires_exact_image_from_current_attachment_tool('none')

    def test_media_oracle_requires_exact_image_from_current_attachment_tool_previous_only(self):
        self._test_media_oracle_requires_exact_image_from_current_attachment_tool('previous_only')

    def test_media_oracle_requires_exact_image_from_current_attachment_tool_duplicate(self):
        self._test_media_oracle_requires_exact_image_from_current_attachment_tool('duplicate')

    def test_media_oracle_requires_exact_image_from_current_attachment_tool_wrong(self):
        self._test_media_oracle_requires_exact_image_from_current_attachment_tool('wrong')

    def test_media_oracle_requires_exact_image_from_current_attachment_tool_text_only(self):
        self._test_media_oracle_requires_exact_image_from_current_attachment_tool('text_only')

    def _test_media_oracle_requires_exact_image_from_current_attachment_tool(self, problem):
        image = {'type': 'image_url', 'image_url': {'url': MEDIA_DATA_URL}}
        tools = [{'type': 'function', 'function': {'name': 'langbot_read_input_attachment'}}]
        scenario = configure_mock_scenarios(read('fixtures/mock_llm_scenarios.json'), box_backend='host')['mock-media']

        def input_turn(turn, token, previous, ref):
            marker = f'Look at this. LB_GROUP=qa-one LB_TURN={turn} LB_TOKEN={token} LB_PREVIOUS={previous}'
            metadata = json.dumps(
                {
                    'type': 'langbot_input_attachments',
                    'attachments': [
                        {
                            'ref': ref,
                            'type': 'image',
                            'mime_type': 'image/png',
                            'source': 'message',
                        }
                    ],
                }
            )
            return {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': marker + '[attachment ' + ref + ': image]'},
                    {'type': 'text', 'text': marker},
                    {'type': 'text', 'text': metadata},
                ],
            }

        def model(messages):
            return select_message({'messages': messages, 'tools': tools}, scenario)

        def result(user_messages, ref):
            call = model(user_messages)
            function = call['tool_calls'][0]['function']
            assert function['name'] == 'langbot_read_input_attachment'
            assert json.loads(function['arguments']) == {'ref': ref, 'mode': 'native'}
            return call, {
                'role': 'tool',
                'tool_call_id': call['tool_calls'][0]['id'],
                'content': '[image attached for inspection]',
            }

        first = input_turn(1, 'aabb', 'none', 'att-1')
        tool_call, tool_result = result([first], 'att-1')
        first_image = {'role': 'user', 'content': [image]}
        first_messages = [first, tool_call, tool_result, first_image]
        first_reply = model(first_messages)
        assert first_reply['content'] == 'LANGBOT_MEDIA_OK GROUP_ACK=aabb'
        prior = [*first_messages, first_reply]

        next_user = input_turn(2, 'ccdd', 'aabb', 'art_fixture2')
        next_call, next_result = result([*prior, next_user], 'art_fixture2')
        current_media = {'role': 'user', 'content': [image]}
        messages = [*prior, next_user, next_call, next_result, current_media]
        assert model(messages)['content'] == 'LANGBOT_MEDIA_OK GROUP_ACK=ccdd'

        if problem == 'none':
            first_image['content'].clear()
            current_media['content'].clear()
        elif problem == 'previous_only':
            current_media['content'].clear()
        elif problem == 'duplicate':
            current_media['content'].append(image)
        elif problem == 'wrong':
            current_media['content'][0] = {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}
        elif problem == 'text_only':
            current_media['content'][0] = {'type': 'text', 'text': MEDIA_DATA_URL}

        with self.assertRaisesRegex(ValueError, 'current attachment tool result must carry'):
            model(messages)

    def test_rag_oracle_needs_retrieved_context_in_the_current_turn_not_only_history_or_text(self):
        scenarios = configure_mock_scenarios(read('fixtures/mock_llm_scenarios.json'), box_backend='host')
        scenario = scenarios['mock-rag']
        sentinel = scenario['steps'][0]['expect_current_retrieved']
        retrieval = json.dumps(
            {'type': 'langbot_retrieved_context', 'data': {'chunks': [{'index': 1, 'content': 'A fact: ' + sentinel}]}}
        )
        first = {
            'role': 'user',
            'content': retrieval + '\n\nQuestion LB_GROUP=qa-one LB_TURN=1 LB_TOKEN=aabb LB_PREVIOUS=none',
        }
        reply = select_message({'messages': [first]}, scenario)
        assert reply['content'] == 'LANGBOT_RAG_OK GROUP_ACK=aabb'
        second = {
            'role': 'user',
            'content': sentinel + ' LB_GROUP=qa-one LB_TURN=2 LB_TOKEN=ccdd LB_PREVIOUS=aabb',
        }
        with self.assertRaisesRegex(ValueError, 'current model user message lacks'):
            select_message({'messages': [first, reply, second]}, scenario)
        second['content'] = [{'type': 'text', 'text': retrieval}, {'type': 'text', 'text': second['content']}]
        assert (
            select_message({'messages': [first, reply, second]}, scenario)['content'] == 'LANGBOT_RAG_OK GROUP_ACK=ccdd'
        )

    def test_memory_is_opt_in_and_only_its_pipeline_binds_the_memory_kb(self):
        result = extend_mixload_profile(read('profiles/endurance.json'), box_backend='host', enable_memory=True)
        resources = {row['id']: row['body'] for row in result['resources']}
        ai = resources['memory_pipeline']['config']['ai']
        cfg = ai['runner_config'][ai['runner']['id']]
        assert cfg['knowledge-bases'] == ['${memory_kb}']
        assert cfg['tools'] == ['remember', 'recall_memory']
        assert resources['memory_kb']['creation_settings']['isolation'] == 'session'
        assert resources['memory_bot']['event_bindings'][0]['target_uuid'] == '${memory_pipeline}'

    def test_memory_model_checks_tool_receipt_not_transcript_current(self):
        self._test_memory_model_checks_tool_receipt_not_transcript(['QA session memory qa-one'])

    def test_memory_model_checks_tool_receipt_not_transcript_foreign(self):
        self._test_memory_model_checks_tool_receipt_not_transcript(['QA session memory other'])

    def test_memory_model_checks_tool_receipt_not_transcript_empty(self):
        self._test_memory_model_checks_tool_receipt_not_transcript([])

    def test_memory_model_checks_tool_receipt_not_transcript_malformed(self):
        self._test_memory_model_checks_tool_receipt_not_transcript(None)

    def _test_memory_model_checks_tool_receipt_not_transcript(self, contents):
        from tools.regression.mixload_cases import memory_scenario

        session = 'QA session memory qa-one'
        user = {'role': 'user', 'content': 'LB_GROUP=qa-one LB_TURN=1 LB_TOKEN=abc LB_PREVIOUS=none'}
        tools = [{'type': 'function', 'function': {'name': n}} for n in ('remember', 'recall_memory')]
        body = {'messages': [user], 'tools': tools}
        scenario = memory_scenario()
        remember = select_message(body, scenario)
        assert json.loads(remember['tool_calls'][0]['function']['arguments']) == {'content': session}
        body['messages'].extend(
            [
                remember,
                {'role': 'tool', 'tool_call_id': remember['tool_calls'][0]['id'], 'content': f'Remembered: {session}'},
            ]
        )
        recall = select_message(body, scenario)
        body['messages'].extend(
            [
                recall,
                {
                    'role': 'tool',
                    'tool_call_id': recall['tool_calls'][0]['id'],
                    'content': json.dumps({'episodes': [{'content': x} for x in contents]})
                    if contents is not None
                    else 'bad JSON',
                },
            ]
        )
        if contents == [session]:
            first = select_message(body, scenario)
            assert first['content'] == 'LANGBOT_MEMORY_OK GROUP_ACK=abc'
            body['messages'].extend(
                [first, {'role': 'user', 'content': 'LB_GROUP=qa-one LB_TURN=2 LB_TOKEN=def LB_PREVIOUS=abc'}]
            )
            later = select_message(body, scenario)
            assert later['tool_calls'][0]['function']['name'] == 'recall_memory'
        else:
            with self.assertRaisesRegex(ValueError, 'recall'):
                select_message(body, scenario)
