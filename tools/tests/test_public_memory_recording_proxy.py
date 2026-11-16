from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.evaluation.recording_proxy import RecordingServer


class UpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers['Content-Length']))
        body = json.loads(raw)
        self.server.received.append((self.path, self.headers.get('Authorization'), body))
        if body.get('stream'):
            chunks = [
                b'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n',
                b'data: {"choices":[{"delta":{"content":"world"}}]}\n\n',
                b'data: {"choices":[],"usage":{"total_tokens":7}}\n\n',
                b'data: [DONE]\n\n',
            ]
            if body.get('incomplete'):
                chunks.pop()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(chunk)
                self.wfile.flush()
        else:
            raw = json.dumps(
                {
                    'choices': [{'message': {'content': 'hello ' + os.environ['EVAL_PROXY_TEST_KEY']}}],
                    'usage': {'total_tokens': 6},
                }
            ).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)


class RecordingProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {'EVAL_PROXY_TEST_KEY': 'upstream-test-secret'})
        self.environment.start()
        self.temp = tempfile.TemporaryDirectory()
        self.record = Path(self.temp.name) / 'requests.jsonl'
        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), UpstreamHandler)
        self.upstream.received = []
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        self.proxy = RecordingServer(
            ('127.0.0.1', 0),
            upstream=f'http://127.0.0.1:{self.upstream.server_port}/v1',
            key_env='EVAL_PROXY_TEST_KEY',
            record=self.record,
            allow_loopback_http=True,
        )
        self.proxy_thread = threading.Thread(target=self.proxy.serve_forever, daemon=True)
        self.proxy_thread.start()

    def tearDown(self) -> None:
        self.proxy.shutdown()
        self.proxy_thread.join()
        self.proxy.server_close()
        self.upstream.shutdown()
        self.upstream_thread.join()
        self.upstream.server_close()
        self.temp.cleanup()
        self.environment.stop()

    def post(self, body: dict) -> bytes:
        request = Request(
            f'http://127.0.0.1:{self.proxy.server_port}/v1/chat/completions',
            data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer client-test-secret'},
        )
        with urlopen(request, timeout=5) as response:
            return response.read()

    def records(self) -> list[dict]:
        # Reading through the proxy's lock waits for any completion append.
        with self.proxy.record_lock:
            return [json.loads(line) for line in self.record.read_text().splitlines()]

    def test_exact_inputs_usage_and_credentials_boundary(self) -> None:
        body = {'model': 'flash', 'messages': [{'role': 'user', 'content': 'public question'}]}
        self.post(body)
        self.proxy.shutdown()
        records = self.records()
        self.assertEqual([record['event'] for record in records], ['request_start', 'request_complete'])
        self.assertEqual(records[0]['request_body'], body)
        self.assertEqual(records[0]['request_id'], records[1]['request_id'])
        self.assertEqual(records[1]['usage'], {'total_tokens': 6})
        self.assertEqual(records[1]['outcome'], 'ok')
        self.assertEqual(self.upstream.received[0][0], '/v1/chat/completions')
        self.assertEqual(self.upstream.received[0][1], 'Bearer upstream-test-secret')
        text = self.record.read_text()
        self.assertNotIn('upstream-test-secret', text)
        self.assertNotIn('client-test-secret', text)
        self.assertNotIn('Authorization', text)
        self.assertEqual(stat.S_IMODE(self.record.stat().st_mode), 0o600)

    def test_stream_chunks_are_forwarded_and_usage_is_recorded(self) -> None:
        raw = self.post({'model': 'flash', 'messages': [], 'stream': True})
        self.proxy.shutdown()
        records = self.records()
        self.assertIn(b'data: [DONE]', raw)
        self.assertEqual(records[1]['content'], 'hello world')
        self.assertEqual(records[1]['usage'], {'total_tokens': 7})
        self.assertEqual(records[1]['response_body_utf8'], raw.decode())
        self.assertTrue(records[1]['stream_done'])

    def test_incomplete_stream_is_explicit_in_record(self) -> None:
        self.post({'model': 'flash', 'messages': [], 'stream': True, 'incomplete': True})
        self.proxy.shutdown()
        records = self.records()
        self.assertEqual(records[1]['outcome'], 'incomplete_stream')
        self.assertFalse(records[1]['stream_done'])

    def test_oversized_response_is_recorded_as_failure(self) -> None:
        self.proxy.max_response_bytes = 8
        with self.assertRaises(HTTPError) as error:
            self.post({'model': 'flash', 'messages': []})
        self.assertEqual(error.exception.code, 502)
        self.proxy.shutdown()
        records = self.records()
        self.assertEqual(records[1]['outcome'], 'error')
        self.assertLessEqual(records[1]['response_bytes'], 8)

    def test_oversized_request_is_rejected_without_upstream_call(self) -> None:
        self.proxy.max_request_bytes = 8
        with self.assertRaises(HTTPError) as error:
            self.post({'messages': ['too large']})
        self.assertEqual(error.exception.code, 413)
        self.assertEqual(self.upstream.received, [])

    def test_server_refuses_external_bind_and_non_https_upstream(self) -> None:
        with self.assertRaises(ValueError):
            RecordingServer(
                ('0.0.0.0', 0),
                upstream='https://api.example.com/v1',
                key_env='EVAL_PROXY_TEST_KEY',
                record=self.record,
            )
        with self.assertRaises(ValueError):
            RecordingServer(
                ('127.0.0.1', 0),
                upstream='http://api.example.com/v1',
                key_env='EVAL_PROXY_TEST_KEY',
                record=self.record,
            )


if __name__ == '__main__':
    unittest.main()
