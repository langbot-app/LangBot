"""Exercise the real HTTP server without LangBot, credentials or dependencies."""

from concurrent.futures import ThreadPoolExecutor
import base64
import json
from pathlib import Path
import tempfile
import struct
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mock_llm import MockServer


class MockLLMTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.record = Path(cls.tmp.name) / 'requests.jsonl'
        scenarios = json.loads(Path(__file__).with_name('mock_llm_scenarios.json').read_text())
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

    def post(self, model='mock-chat', **kwargs):
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
        with urlopen(request, timeout=5) as response:
            return response.read().decode()

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

    def test_embedding_http_float_base64_and_validation(self):
        def embed(**patch):
            body = {'model': 'mock-embedding', 'input': ['repeatable fixture', 'another fixture'], **patch}
            request = Request(
                self.url + '/v1/embeddings',
                data=json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'},
            )
            with urlopen(request, timeout=5) as response:
                return json.load(response)

        first = embed()['data']
        self.assertEqual(first, embed()['data'])
        self.assertEqual([item['index'] for item in first], [0, 1])
        self.assertEqual(len(first[0]['embedding']), 384)
        self.assertAlmostEqual(sum(value * value for value in first[0]['embedding']), 1)
        encoded = embed(encoding_format='base64')['data'][0]['embedding']
        decoded = struct.unpack('<384f', base64.b64decode(encoded))
        for actual, expected in zip(decoded, first[0]['embedding']):
            self.assertAlmostEqual(actual, expected, places=6)
        for patch in ({'input': []}, {'dimensions': 0}, {'encoding_format': 'bad'}, {'model': 'unknown'}):
            with self.subTest(patch=patch), self.assertRaises(HTTPError) as caught:
                embed(**patch)
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
