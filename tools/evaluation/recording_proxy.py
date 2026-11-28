"""Record public-test model inputs while forwarding OpenAI chat completions.

Run on loopback with the upstream API key supplied by an environment variable.
The JSONL contains public-test prompts and responses, and must be kept private
until its contents have been reviewed for publication.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _response_details(raw: bytes, *, stream: bool) -> dict[str, Any]:
    text = raw.decode('utf-8', errors='replace')
    usage: dict[str, Any] = {}
    content: list[str] = []
    if stream:
        values = []
        for line in text.splitlines():
            if not line.startswith('data:'):
                continue
            try:
                values.append(json.loads(line[5:].strip()))
            except json.JSONDecodeError:
                continue
    else:
        try:
            values = [json.loads(text)]
        except json.JSONDecodeError:
            values = []
    for value in values:
        if not isinstance(value, dict):
            continue
        if isinstance(value.get('usage'), dict):
            usage = value['usage']
        choices = value.get('choices')
        for choice in choices if isinstance(choices, list) else []:
            if not isinstance(choice, dict):
                continue
            message = choice.get('delta' if stream else 'message') or {}
            if not isinstance(message, dict):
                continue
            if isinstance(message.get('content'), str):
                content.append(message['content'])
    return {'response_body_utf8': text, 'content': ''.join(content), 'usage': usage}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RecordingServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        upstream: str,
        key_env: str,
        record: Path,
        timeout: float = 180.0,
        max_request_bytes: int = 4 * 1024 * 1024,
        max_response_bytes: int = 16 * 1024 * 1024,
        allow_loopback_http: bool = False,
    ) -> None:
        if address[0] != '127.0.0.1':
            raise ValueError('the recording proxy must bind to 127.0.0.1')
        parsed = urlsplit(upstream)
        local_http = allow_loopback_http and parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
        if parsed.scheme != 'https' and not local_http:
            raise ValueError('upstream must use HTTPS')
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('upstream must be a credential-free base URL')
        key = os.environ.get(key_env)
        if not key:
            raise ValueError(f'upstream key environment variable is missing: {key_env}')
        if timeout <= 0 or max_request_bytes <= 0 or max_response_bytes <= 0:
            raise ValueError('timeouts and byte limits must be positive')
        self.upstream = upstream.rstrip('/') + '/chat/completions'
        self.key = key
        self.timeout = timeout
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.opener = build_opener(_NoRedirect())
        self.record_lock = threading.Lock()
        record.parent.mkdir(parents=True, exist_ok=True)
        self.record_fd = os.open(record, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.chmod(record, 0o600)
        try:
            super().__init__(address, RecordingHandler)
        except Exception:
            os.close(self.record_fd)
            raise

    def append_record(self, value: dict[str, Any]) -> None:
        serialized = json.dumps(value, ensure_ascii=False).replace(self.key, '[REDACTED]') + '\n'
        raw = serialized.encode('utf-8')
        with self.record_lock:
            position = 0
            while position < len(raw):
                position += os.write(self.record_fd, raw[position:])

    def server_close(self) -> None:
        super().server_close()
        os.close(self.record_fd)


class RecordingHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server: RecordingServer

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def do_GET(self) -> None:
        if self.path == '/healthz':
            self._json(200, {'status': 'ok'})
        else:
            self._json(404, {'error': 'unsupported_path'})

    def do_POST(self) -> None:
        if self.path not in {'/v1/chat/completions', '/chat/completions'}:
            self._json(404, {'error': 'unsupported_path'})
            return
        request_id = str(uuid.uuid4())
        started = time.monotonic()
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if length < 0 or self.headers.get('Transfer-Encoding'):
            self._json(411, {'error': 'content_length_required'})
            return
        if length > self.server.max_request_bytes:
            self._json(413, {'error': 'request_limit_exceeded'})
            return
        self.connection.settimeout(self.server.timeout)
        raw_request = self.rfile.read(length)
        try:
            body = json.loads(raw_request)
            if not isinstance(body, dict):
                raise ValueError('body must be an object')
        except (ValueError, UnicodeDecodeError):
            self._json(400, {'error': 'invalid_json_object'})
            return
        self.server.append_record(
            {
                'event': 'request_start',
                'request_id': request_id,
                'timestamp': _now(),
                'request_body': body,
                'request_body_utf8': raw_request.decode('utf-8'),
            }
        )
        recorded = bytearray()
        status: int | None = None
        headers_sent = False
        outcome = 'error'
        error_type: str | None = None
        is_stream = bool(body.get('stream'))
        try:
            upstream_request = Request(
                self.server.upstream,
                data=raw_request,
                headers={'Authorization': f'Bearer {self.server.key}', 'Content-Type': 'application/json'},
                method='POST',
            )
            try:
                response = self.server.opener.open(upstream_request, timeout=self.server.timeout)
            except HTTPError as exc:
                response = exc
            with response:
                status = response.status
                content_type = response.headers.get('Content-Type', 'application/json')
                if is_stream and status == 200:
                    self.send_response(status)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Connection', 'close')
                    self.send_header('X-LangBot-Eval-Request-ID', request_id)
                    self.end_headers()
                    headers_sent = True
                while True:
                    if time.monotonic() - started >= self.server.timeout:
                        raise TimeoutError('upstream total deadline exceeded')
                    chunk = response.read1(min(8192, self.server.max_response_bytes - len(recorded) + 1))
                    if not chunk:
                        break
                    if len(recorded) + len(chunk) > self.server.max_response_bytes:
                        raise ValueError('response_limit_exceeded')
                    recorded.extend(chunk)
                    if headers_sent:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                if not headers_sent:
                    self.send_response(status)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(recorded)))
                    self.send_header('Connection', 'close')
                    self.send_header('X-LangBot-Eval-Request-ID', request_id)
                    self.end_headers()
                    headers_sent = True
                    self.wfile.write(recorded)
                outcome = 'ok' if 200 <= status < 300 else 'upstream_error'
                if is_stream and status == 200 and b'data: [DONE]' not in recorded:
                    outcome = 'incomplete_stream'
                    error_type = 'StreamIncomplete'
        except Exception as exc:
            error_type = type(exc).__name__
            if not headers_sent:
                self._json(502, {'error': 'upstream_failure', 'request_id': request_id})
        finally:
            self.close_connection = True
            self.server.append_record(
                {
                    'event': 'request_complete',
                    'request_id': request_id,
                    'timestamp': _now(),
                    'duration_seconds': time.monotonic() - started,
                    'upstream_status': status,
                    'outcome': outcome,
                    'error_type': error_type,
                    'stream': is_stream,
                    'stream_done': b'data: [DONE]' in recorded if is_stream else None,
                    'response_bytes': len(recorded),
                    **_response_details(bytes(recorded), stream=is_stream),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1', choices=('127.0.0.1',))
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--key-env', default='DEEPSEEK_API_KEY')
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=180.0)
    args = parser.parse_args()
    with RecordingServer(
        (args.host, args.port),
        upstream=args.upstream,
        key_env=args.key_env,
        record=args.record,
        timeout=args.timeout,
    ) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
