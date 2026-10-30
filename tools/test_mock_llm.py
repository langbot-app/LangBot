"""Exercise the real HTTP server without LangBot, credentials or dependencies."""

from concurrent.futures import ThreadPoolExecutor
import base64
from http.client import IncompleteRead
import json
from pathlib import Path
import tempfile
import struct
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import mock_llm
from mock_llm import MockServer, validate_scenarios


class MockLLMTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.record = Path(cls.tmp.name) / 'requests.jsonl'
        cls.record.touch()
        scenarios = json.loads(Path(__file__).with_name('mock_llm_scenarios.json').read_text())
        scenarios['test-stall-recovery'] = {
            **scenarios['mock-stream-stall'],
            'stall_seconds': 0.2,
            'recover_after': 1,
        }
        scenarios['test-delay-recovery'] = {
            'delay_seconds': 0.2,
            'recover_after': 1,
            'steps': [{'content': 'RECOVERED'}],
        }
        cls.server = MockServer(('127.0.0.1', 0), scenarios, cls.record)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def post(self, model='mock-chat', timeout=5, **kwargs):
        body = {
            'model': model,
            'messages': [{'role': 'user', 'content': 'test'}],
            **kwargs,
        }
        request = Request(
            self.url + '/v1/chat/completions',
            data=json.dumps(body).encode(),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer must-not-be-recorded',
            },
        )
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode()

    def embed(self, timeout=5, **patch):
        body = {'model': 'mock-embedding', 'input': ['repeatable fixture', 'another fixture'], **patch}
        request = Request(
            self.url + '/v1/embeddings',
            data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'},
        )
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def records(self, scope, count):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with self.server.record_lock:
                rows = [json.loads(line) for line in self.record.read_text().splitlines()]
            rows = [row for row in rows if row.get('scope') == scope]
            if len(rows) >= count:
                return sorted(rows, key=lambda row: row.get('attempt', 0))
            time.sleep(0.01)
        self.fail(f'missing completed request records for {scope}')

    def release(self, scope):
        with urlopen(Request(self.url + '/_mock/scopes/' + scope, method='DELETE'), timeout=5) as response:
            return json.load(response)

    def test_chat_and_model_discovery(self):
        with urlopen(self.url + '/v1/models') as response:
            models = json.load(response)
        self.assertIn('mock-box', [m['id'] for m in models['data']])
        self.assertEqual(
            json.loads(self.post())['choices'][0]['message']['content'],
            'LANGBOT_CHAT_OK',
        )

    def test_stream_and_usage(self):
        events = self.post(stream=True, stream_options={'include_usage': True}).splitlines()
        self.assertEqual(events[-2], 'data: [DONE]')
        chunks = [json.loads(line[6:]) for line in events if line.startswith('data: {')]
        content = ''.join(c['choices'][0]['delta'].get('content', '') for c in chunks if c['choices'])
        self.assertEqual(content, 'LANGBOT_CHAT_OK')
        self.assertEqual(chunks[-1]['usage']['total_tokens'], 15)

    def test_group_history_requires_previous_user_reply_and_isolation(self):
        first = {'role': 'user', 'content': 'LB_GROUP=group-a LB_TURN=1 LB_TOKEN=aaa LB_PREVIOUS=none'}
        second = {'role': 'user', 'content': 'LB_GROUP=group-a LB_TURN=2 LB_TOKEN=bbb LB_PREVIOUS=aaa'}
        reply = json.loads(self.post(messages=[first]))['choices'][0]['message']
        self.assertIn('GROUP_ACK=aaa', reply['content'])
        result = json.loads(self.post(messages=[first, reply, second]))['choices'][0]['message']
        self.assertIn('GROUP_ACK=bbb', result['content'])
        other = {'role': 'user', 'content': 'LB_GROUP=group-b LB_TURN=1 LB_TOKEN=ccc LB_PREVIOUS=none'}
        for messages in ([second], [first, second], [other, reply, second]):
            with self.subTest(messages=messages), self.assertRaises(HTTPError) as failure:
                self.post(messages=messages)
            self.assertEqual(failure.exception.code, 400)

    def test_embedding_http_float_base64_and_validation(self):
        first = self.embed()['data']
        self.assertEqual(first, self.embed()['data'])
        self.assertEqual([item['index'] for item in first], [0, 1])
        self.assertEqual(len(first[0]['embedding']), 384)
        self.assertAlmostEqual(sum(value * value for value in first[0]['embedding']), 1)
        encoded = self.embed(encoding_format='base64')['data'][0]['embedding']
        decoded = struct.unpack('<384f', base64.b64decode(encoded))
        for actual, expected in zip(decoded, first[0]['embedding']):
            self.assertAlmostEqual(actual, expected, places=6)
        for patch in ({'input': []}, {'dimensions': 0}, {'encoding_format': 'bad'}, {'model': 'unknown'}):
            with self.subTest(patch=patch), self.assertRaises(HTTPError) as caught:
                self.embed(**patch)
            self.assertEqual(caught.exception.code, 400)

    def box_turn(self, streaming=False):
        messages = [{'role': 'user', 'content': 'run box checks'}]
        tools = [
            {
                'type': 'function',
                'function': {'name': 'exec', 'parameters': {'type': 'object'}},
            }
        ]
        commands = []
        for _ in range(2):
            wire = self.post('mock-box', messages=messages, tools=tools, stream=streaming)
            if streaming:
                deltas = [
                    json.loads(line[6:])['choices'][0]['delta']
                    for line in wire.splitlines()
                    if line.startswith('data: {')
                ]
                call = next(d['tool_calls'][0] for d in deltas if d.get('tool_calls') and 'id' in d['tool_calls'][0])
                arguments = ''.join(d['tool_calls'][0]['function']['arguments'] for d in deltas if d.get('tool_calls'))
                call = {
                    **call,
                    'function': {**call['function'], 'arguments': arguments},
                }
                call.pop('index')
                message = {'role': 'assistant', 'content': None, 'tool_calls': [call]}
            else:
                message = json.loads(wire)['choices'][0]['message']
                call = message['tool_calls'][0]
            commands.append(json.loads(call['function']['arguments'])['command'])
            messages.extend(
                [
                    message,
                    {
                        'role': 'tool',
                        'tool_call_id': call['id'],
                        'content': 'LANGBOT_BOX_SENTINEL',
                    },
                ]
            )
        final = json.loads(self.post('mock-box', messages=messages, tools=tools))
        self.assertEqual(final['choices'][0]['message']['content'], 'LANGBOT_BOX_OK')
        self.assertIn('printf LANGBOT_BOX_SENTINEL', commands[0])
        self.assertEqual(commands[1], 'cat /workspace/mock-llm.txt')

    def test_tool_rounds_and_fragmented_stream(self):
        self.box_turn()
        self.box_turn(streaming=True)

    def test_concurrent_turns_do_not_share_progress(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.box_turn(), range(8)))

    def test_rag_requires_expected_model_input(self):
        with self.assertRaises(HTTPError) as caught:
            self.post('mock-rag')
        self.assertEqual(caught.exception.code, 400)
        response = json.loads(
            self.post(
                'mock-rag',
                messages=[
                    {'role': 'system', 'content': 'Retrieved document: aurora-parser-rag-9137'},
                    {'role': 'user', 'content': 'What is the documented sentinel?'},
                ],
            )
        )
        self.assertEqual(response['choices'][0]['message']['content'], 'LANGBOT_RAG_OK')

    def test_empty_rag_rejects_context_from_another_knowledge_base(self):
        self.assertIn('LANGBOT_EMPTY_RAG_CHAT_OK', self.post('mock-daily-empty-rag-chat'))
        for leaked in ('aurora-parser-rag-9137', 'cedar-isolation-4826'):
            with self.subTest(leaked=leaked), self.assertRaises(HTTPError) as caught:
                self.post('mock-daily-empty-rag-chat', messages=[{'role': 'user', 'content': leaked}])
            self.assertEqual(caught.exception.code, 400)

    def test_concurrent_scopes_fail_independently_then_recover(self):
        def conversation(index):
            scope = f'concurrent-{index}'
            body = {'messages': [{'role': 'user', 'content': f'hello LB_MOCK_SCOPE={scope}'}]}
            with self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', **body)
            self.assertEqual(caught.exception.code, 503)
            self.assertIn('LANGBOT_CHAT_OK', self.post())
            self.assertIn('LANGBOT_RECOVERY_OK', self.post('mock-recover-503', **body))
            rows = self.records(scope, 2)
            self.assertEqual([row['attempt'] for row in rows], [1, 2])
            self.assertEqual(rows[0]['faults'], [{'kind': 'http_error', 'status': 503}])
            self.assertEqual(rows[1]['faults'], [])
            self.assertTrue(rows[1]['response_complete'])
            self.assertEqual(self.release(scope)['released'], 1)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(conversation, range(8)))

    def test_concurrent_retries_consume_only_one_failure(self):
        def request(_):
            try:
                self.post('mock-recover-503', mock_scope='same-scope')
                return 200
            except HTTPError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(request, range(8)))
        self.assertEqual(sorted(statuses), [200] * 7 + [503])
        rows = self.records('same-scope', 8)
        self.assertEqual(sorted(row['attempt'] for row in rows), list(range(1, 9)))
        self.assertEqual(self.release('same-scope')['released'], 1)

    def test_stream_disconnect_is_a_transport_failure_and_recovers(self):
        with self.assertRaises(IncompleteRead) as caught:
            self.post('mock-recover-stream-disconnect', stream=True, mock_scope='disconnect')
        self.assertIn(b'LANGBOT_', caught.exception.partial)
        self.assertNotIn(b'[DONE]', caught.exception.partial)
        result = self.post('mock-recover-stream-disconnect', stream=True, mock_scope='disconnect')
        self.assertIn('data: [DONE]', result)
        rows = self.records('disconnect', 2)
        self.assertEqual(rows[0]['faults'], [{'kind': 'stream_disconnect', 'after_chunks': 2}])
        self.assertFalse(rows[0]['response_complete'])
        self.assertTrue(rows[0]['injected_disconnect'])
        self.assertEqual(rows[1]['faults'], [])
        self.assertTrue(rows[1]['response_complete'])
        self.release('disconnect')

    def test_delay_and_midstream_stall_timeout_then_recover(self):
        for model, stream, kind in (
            ('test-delay-recovery', False, 'delay'),
            ('test-stall-recovery', True, 'stream_stall'),
        ):
            with self.subTest(model=model):
                with self.assertRaises(TimeoutError):
                    self.post(model, stream=stream, timeout=0.05, mock_scope=model)
                self.assertIn('LANGBOT_CHAT_OK', self.post())
                result = self.post(model, stream=stream, mock_scope=model)
                self.assertIn('data: [DONE]' if stream else 'RECOVERED', result)
                rows = sorted(self.records(model, 2), key=lambda row: row['attempt'])
                self.assertEqual(rows[0]['faults'][0]['kind'], kind)
                self.assertGreaterEqual(rows[0]['faults'][0]['elapsed_seconds'], 0.2)
                self.assertEqual(rows[1]['faults'], [])
                self.release(model)

    def test_embedding_errors_timeout_count_and_dimension(self):
        for status in (429, 503):
            scope = f'embed-{status}'
            with self.assertRaises(HTTPError) as caught:
                self.embed(model=f'mock-embedding-{status}', mock_scope=scope)
            self.assertEqual(caught.exception.code, status)
            self.assertEqual(self.records(scope, 1)[0]['faults'], [{'kind': 'http_error', 'status': status}])
        with self.assertRaises(TimeoutError):
            self.embed(model='mock-embedding-timeout', mock_scope='embed-timeout', timeout=0.05)
        self.assertEqual(len(self.embed()['data']), 2)
        for encoding in ('float', 'base64'):
            wrong_count = self.embed(model='mock-embedding-wrong-count', encoding_format=encoding)
            self.assertEqual(len(wrong_count['data']), 1)
            wrong_dimension = self.embed(
                model='mock-embedding-wrong-dimension',
                dimensions=4,
                encoding_format=encoding,
            )
            self.assertEqual([item['index'] for item in wrong_dimension['data']], [0, 1])
            vector = wrong_dimension['data'][0]['embedding']
            self.assertEqual(len(vector) if encoding == 'float' else len(base64.b64decode(vector)) // 4, 3)
        delay = self.records('embed-timeout', 1)[0]['faults'][0]
        self.assertEqual(delay['kind'], 'delay')
        self.assertGreaterEqual(delay['elapsed_seconds'], 2)

    def test_embedding_recovery_scope_does_not_modify_vectors(self):
        expected = self.embed()['data']

        def conversation(scope):
            with self.assertRaises(HTTPError) as caught:
                self.embed(model='mock-embedding-recover-503', mock_scope=scope)
            self.assertEqual(caught.exception.code, 503)
            result = self.embed(model='mock-embedding-recover-503', mock_scope=scope)
            self.assertEqual(result['data'], expected)
            self.assertEqual(self.records(scope, 2)[1]['faults'], [])
            self.release(scope)

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(conversation, ('embed-a', 'embed-b')))

    def test_markers_select_current_scope_and_invalid_input_does_not_advance(self):
        with self.assertRaises(HTTPError) as caught:
            self.post('mock-recover-503', messages=[], mock_scope='marker-current')
        self.assertEqual(caught.exception.code, 400)
        with self.assertRaises(HTTPError) as caught:
            self.post(
                'mock-recover-503',
                messages=[
                    {'role': 'user', 'content': 'LB_MOCK_SCOPE=marker-old'},
                    {'role': 'assistant', 'content': 'prior reply'},
                    {'role': 'user', 'content': [{'type': 'text', 'text': 'LB_MOCK_SCOPE=marker-current'}]},
                ],
            )
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(self.records('marker-current', 1)[0]['attempt'], 1)
        self.assertIn('LANGBOT_RECOVERY_OK', self.post('mock-recover-503', mock_scope='marker-current'))
        self.assertEqual(self.release('marker-current')['released'], 1)
        self.assertEqual(self.release('marker-old')['released'], 0)
        with self.assertRaises(HTTPError) as caught:
            self.embed(model='mock-embedding-recover-503', input=['LB_MOCK_SCOPE=marker-embed'])
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(self.records('marker-embed', 1)[0]['attempt'], 1)
        self.release('marker-embed')

    def test_scope_validation_capacity_expiry_and_cleanup(self):
        for scope in (None, '', [], 'x' * 129, 'bad/scope'):
            with self.subTest(scope=scope), self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', mock_scope=scope)
            self.assertEqual(caught.exception.code, 400)
        with patch.object(mock_llm, 'MAX_FAULT_SCOPES', len(self.server.fault_scopes) + 1):
            with self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', mock_scope='capacity-a')
            self.assertEqual(caught.exception.code, 503)
            with self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', mock_scope='capacity-b')
            self.assertEqual(caught.exception.code, 400)
            self.assertIn('scope limit', caught.exception.read().decode())
            self.assertIn('LANGBOT_RECOVERY_OK', self.post('mock-recover-503', mock_scope='capacity-a'))
            self.assertEqual(self.release('capacity-a')['released'], 1)
            with self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', mock_scope='capacity-b')
            self.assertEqual(caught.exception.code, 503)
            with patch.object(mock_llm, 'FAULT_SCOPE_TTL_SECONDS', 0), self.assertRaises(HTTPError) as caught:
                self.post('mock-recover-503', mock_scope='capacity-b')
            self.assertEqual(caught.exception.code, 503)
        self.assertEqual(self.release('capacity-b')['released'], 1)
        self.assertEqual(self.release('capacity-b')['released'], 0)

    def test_scenario_controls_reject_invalid_values(self):
        for control in (
            {'delay_seconds': 61},
            {'delay_seconds': float('nan')},
            {'delay_seconds': True},
            {'recover_after': 0},
            {'disconnect_after_chunks': -1},
            {'stall_after_chunks': 2},
            {'stall_seconds': 1},
            {'embedding_fault': 'count'},
            {'forbid_prompt': 'not-an-array'},
        ):
            scenario = {'steps': [{'content': 'OK'}], **control}
            if 'forbid_prompt' in control:
                scenario = {'steps': [{'content': 'OK', **control}]}
            with self.subTest(control=control), self.assertRaises(ValueError):
                validate_scenarios({'invalid': scenario})

    def test_errors_and_invalid_requests(self):
        for status in (401, 429, 503):
            with self.subTest(status=status), self.assertRaises(HTTPError) as caught:
                self.post(f'mock-{status}')
            self.assertEqual(caught.exception.code, status)
        for kwargs in (
            {'model': 'unknown'},
            {'messages': []},
            {'stream_options': []},
            {'model': 'mock-box', 'tools': []},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(HTTPError) as caught:
                self.post(**kwargs)
            self.assertEqual(caught.exception.code, 400)
        messages = [
            {'role': 'user', 'content': 'test'},
            {'role': 'assistant', 'tool_calls': [{'id': 'call1'}]},
        ]
        with self.assertRaises(HTTPError) as caught:
            self.post('mock-box', messages=messages)
        self.assertEqual(caught.exception.code, 400)
        messages.append({'role': 'tool', 'tool_call_id': 'call1', 'content': 'wrong output'})
        with self.assertRaises(HTTPError) as caught:
            self.post('mock-box', messages=messages)
        self.assertEqual(caught.exception.code, 400)

    def test_record_omits_authorization(self):
        self.post()
        with self.server.record_lock:
            recorded = self.record.read_text()
        self.assertNotIn('must-not-be-recorded', recorded)
        self.assertIn('"request_id"', recorded)


if __name__ == '__main__':
    unittest.main()
