from __future__ import annotations

import asyncio
import json
import os
import typing
from pathlib import Path

import httpx

from .errors import DifyAPIError

_MAX_DIFY_RESPONSE_BYTES = 1024 * 1024
_MAX_DIFY_SSE_LINE_BYTES = 1024 * 1024
_MAX_DIFY_STREAM_BYTES = 16 * 1024 * 1024
_MAX_DIFY_UPLOAD_BYTES = 10 * 1024 * 1024


def _decode_sse_data(line: bytes) -> dict[str, typing.Any] | None:
    data = line[5:].strip()
    if not data or data == b'[DONE]':
        return None
    try:
        payload = json.loads(data.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DifyAPIError('Dify SSE data line is not valid JSON') from exc
    if not isinstance(payload, dict):
        raise DifyAPIError('Dify SSE event is not a JSON object')
    return payload


def _decode_upload_response(body: bytes) -> dict[str, typing.Any]:
    try:
        response = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DifyAPIError('Dify upload response is not valid JSON') from exc
    if not isinstance(response, dict):
        raise DifyAPIError('Dify upload response is not a JSON object')
    payload = response.get('data', response)
    if not isinstance(payload, dict) or not isinstance(payload.get('id'), str) or not payload['id']:
        raise DifyAPIError('Dify upload response does not contain a valid file id')
    return payload


async def _read_limited_response(
    response: httpx.Response,
    *,
    max_bytes: int = _MAX_DIFY_RESPONSE_BYTES,
) -> bytes:
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise DifyAPIError(f'Remote response exceeds the {max_bytes}-byte limit')
        except (TypeError, ValueError):
            pass

    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=8192):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise DifyAPIError(f'Remote response exceeds the {max_bytes}-byte limit')
    return bytes(body)


async def _iter_sse_json(
    response: httpx.Response,
) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
    """Parse Dify's one-JSON-per-data-line SSE without unbounded line buffering."""

    buffer = bytearray()
    total = 0
    async for chunk in response.aiter_bytes(chunk_size=8192):
        total += len(chunk)
        if total > _MAX_DIFY_STREAM_BYTES:
            raise DifyAPIError('Dify SSE stream exceeds the runtime limit')
        buffer.extend(chunk)
        while b'\n' in buffer:
            raw_line, _, remainder = buffer.partition(b'\n')
            buffer = bytearray(remainder)
            if len(raw_line) > _MAX_DIFY_SSE_LINE_BYTES:
                raise DifyAPIError('Dify SSE event exceeds the runtime limit')
            line = raw_line.rstrip(b'\r').strip()
            if not line or not line.startswith(b'data:'):
                continue
            payload = _decode_sse_data(line)
            if payload is not None:
                yield payload
        if len(buffer) > _MAX_DIFY_SSE_LINE_BYTES:
            raise DifyAPIError('Dify SSE event exceeds the runtime limit')

    line = bytes(buffer).rstrip(b'\r').strip()
    if line.startswith(b'data:'):
        payload = _decode_sse_data(line)
        if payload is not None:
            yield payload


def _read_local_file_limited(path: Path) -> bytes:
    if path.stat().st_size > _MAX_DIFY_UPLOAD_BYTES:
        raise ValueError('Dify upload exceeds the size limit')
    with path.open('rb') as handle:
        body = handle.read(_MAX_DIFY_UPLOAD_BYTES + 1)
    if len(body) > _MAX_DIFY_UPLOAD_BYTES:
        raise ValueError('Dify upload exceeds the size limit')
    return body


class AsyncDifyServiceClient:
    """Dify Service API 客户端"""

    api_key: str
    base_url: str

    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://api.dify.ai/v1',
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                trust_env=True,
            )
        return self._client

    async def aclose(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            await client.aclose()

    async def chat_messages(
        self,
        inputs: dict[str, typing.Any],
        query: str,
        user: str,
        response_mode: str = 'streaming',  # 当前不支持 blocking
        conversation_id: str = '',
        files: list[dict[str, typing.Any]] = [],
        timeout: float = 30.0,
        model_config: dict[str, typing.Any] | None = None,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """发送消息"""
        if response_mode != 'streaming':
            raise DifyAPIError('当前仅支持 streaming 模式')

        client = self._get_client()
        payload = {
            'inputs': inputs,
            'query': query,
            'user': user,
            'response_mode': response_mode,
            'conversation_id': conversation_id,
            'files': files,
            'model_config': model_config or {},
        }

        async with client.stream(
            'POST',
            '/chat-messages',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json=payload,
            timeout=timeout,
        ) as r:
            if r.status_code != 200:
                body = await _read_limited_response(r)
                raise DifyAPIError(f'{r.status_code} {body.decode(errors="replace")}')
            async for event in _iter_sse_json(r):
                yield event

    async def workflow_run(
        self,
        inputs: dict[str, typing.Any],
        user: str,
        response_mode: str = 'streaming',  # 当前不支持 blocking
        files: list[dict[str, typing.Any]] = [],
        timeout: float = 30.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """运行工作流"""
        if response_mode != 'streaming':
            raise DifyAPIError('当前仅支持 streaming 模式')

        client = self._get_client()
        async with client.stream(
            'POST',
            '/workflows/run',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'inputs': inputs,
                'user': user,
                'response_mode': response_mode,
                'files': files,
            },
            timeout=timeout,
        ) as r:
            if r.status_code != 200:
                body = await _read_limited_response(r)
                raise DifyAPIError(f'{r.status_code} {body.decode(errors="replace")}')
            async for event in _iter_sse_json(r):
                yield event

    async def workflow_submit(
        self,
        form_token: str,
        workflow_run_id: str,
        inputs: dict[str, typing.Any],
        user: str,
        action: str = '',
        timeout: float = 120.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Submit human input to resume a paused workflow, then stream events.

        1. POST /form/human_input/{form_token} to submit the form
        2. GET /workflow/{task_id}/events to stream the resumed workflow events
        """

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        client = self._get_client()
        # Step 1: Submit the form
        payload: dict[str, typing.Any] = {
            'inputs': inputs if isinstance(inputs, dict) else {},
            'user': user,
            'action': action,
        }

        async with client.stream(
            'POST',
            f'/form/human_input/{form_token}',
            headers=headers,
            json=payload,
            timeout=timeout,
        ) as submit_resp:
            submit_body = await _read_limited_response(submit_resp)
            if submit_resp.status_code != 200:
                raise DifyAPIError(f'{submit_resp.status_code} {submit_body.decode(errors="replace")}')

        # Step 2: Stream resumed workflow events
        async with client.stream(
            'GET',
            f'/workflow/{workflow_run_id}/events',
            headers={'Authorization': f'Bearer {self.api_key}'},
            params={'user': user},
            timeout=timeout,
        ) as r:
            if r.status_code != 200:
                body = await _read_limited_response(r)
                raise DifyAPIError(f'{r.status_code} {body.decode(errors="replace")}')
            async for event in _iter_sse_json(r):
                yield event

    async def upload_file(
        self,
        file: httpx._types.FileTypes,
        user: str,
        timeout: float = 30.0,
    ) -> dict[str, typing.Any]:
        # 处理 Path 对象
        if isinstance(file, Path):
            if not file.exists():
                raise ValueError(f'File not found: {file}')
            file = await asyncio.to_thread(_read_local_file_limited, file)

        # 处理文件路径字符串
        elif isinstance(file, str):
            if not os.path.isfile(file):
                raise ValueError(f'File not found: {file}')
            file = await asyncio.to_thread(_read_local_file_limited, Path(file))

        # 处理文件对象
        elif hasattr(file, 'read'):
            file = await asyncio.to_thread(file.read, _MAX_DIFY_UPLOAD_BYTES + 1)
            if len(file) > _MAX_DIFY_UPLOAD_BYTES:
                raise ValueError('Dify upload exceeds the size limit')
        client = self._get_client()
        # multipart/form-data
        async with client.stream(
            'POST',
            '/files/upload',
            headers={'Authorization': f'Bearer {self.api_key}'},
            files={'file': file},
            data={'user': user},
            timeout=timeout,
        ) as response:
            body = await _read_limited_response(response)
            if response.status_code not in (200, 201):
                raise DifyAPIError(f'{response.status_code} {body.decode(errors="replace")}')
        return _decode_upload_response(body)
