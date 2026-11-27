"""Loopback HTTP execution through Core, LangRAG and the configured vector DB."""

from http.client import HTTPConnection
from ipaddress import ip_address
import json
import re
from time import monotonic
from urllib.parse import urlsplit
from uuid import uuid4

KB = '/api/v1/knowledge/bases'
ARTIFACTS = '/api/v1/artifacts'
LANGRAG = 'langbot-team/LangRAG'
PARSER = 'langbot-team/GeneralParsers'
RETRIEVAL = {'search_type': 'vector', 'query_rewrite': 'off', 'rerank': 'off'}
IDENT = re.compile(r'[A-Za-z0-9_-]{1,128}\Z')


def checked_id(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise ValueError('Malformed resource identity')
    return value


class CoreHTTP:
    def __init__(self, endpoint, workspace, token, timeout):
        url = urlsplit(endpoint)
        if (
            url.scheme != 'http'
            or not url.hostname
            or not ip_address(url.hostname).is_loopback
            or url.username
            or url.password
            or url.path not in ('', '/')
            or url.query
            or url.fragment
            or url.port is None
        ):
            raise ValueError('Use an explicit loopback HTTP address with a port, e.g. http://127.0.0.1:5300')
        if not token or not isinstance(token, str) or not token.isascii() or any(c.isspace() for c in token):
            raise ValueError('A valid disposable QA bearer token is required')
        self.host, self.port = url.hostname, url.port
        self.headers = {'Authorization': 'Bearer ' + token, 'X-Workspace-Id': checked_id(workspace)}
        self.timeout = timeout

    def request(self, method, path, payload=None, *, raw=None, content_type=None, expected=200, timeout=None):
        if not path.startswith('/api/v1/') or path.startswith('//'):
            raise ValueError('Core API path must be local to the API')
        header = dict(self.headers)
        if payload is not None:
            raw, content_type = json.dumps(payload, allow_nan=False).encode(), 'application/json'
        if content_type:
            header['Content-Type'] = content_type
        connection = HTTPConnection(self.host, self.port, timeout=self.timeout if timeout is None else timeout)
        try:
            connection.request(method, path, body=raw, headers=header)
            response = connection.getresponse()
            # Do not print response bodies: they may contain sensitive diagnostics.
            if response.status != expected:
                raise ValueError(f'{method} Core API returned HTTP {response.status}, expected {expected}')
            body = response.read(16 * 1024 * 1024 + 1)
            if len(body) > 16 * 1024 * 1024:
                raise ValueError('Core API response exceeded benchmark limit')
            result = json.loads(body)
            if not isinstance(result, dict) or (expected == 200 and result.get('code') != 0):
                raise ValueError(f'{method} Core API did not return a successful JSON envelope')
            return result.get('data')
        finally:
            connection.close()

    def upload(self, filename, text):
        boundary = 'benchmark-' + uuid4().hex
        payload = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f'Content-Type: text/plain\r\n\r\n{text}\r\n--{boundary}--\r\n'
        ).encode()
        return checked_id(
            self.request('POST', ARTIFACTS, raw=payload, content_type=f'multipart/form-data; boundary={boundary}')['id']
        )


def write_json(path, value):
    partial = path.with_suffix('.tmp')
    partial.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    partial.replace(path)


def write_row(file, row):
    file.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
    file.flush()


def elapsed_ms(begin):
    return (monotonic() - begin) * 1000


def remaining(deadline, maximum):
    seconds = deadline - monotonic()
    if seconds <= 0:
        raise TimeoutError('Index or visibility deadline exhausted')
    return min(maximum, seconds)


def bounded_error(exc):
    # Never print remote payloads or arbitrary connection diagnostics.
    return str(exc) if type(exc) is ValueError else type(exc).__name__
