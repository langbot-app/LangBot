"""DeerFlow LangGraph HTTP API 客户端

参考 astrbot 的 deerflow_api_client 实现，使用 httpx 适配 LangBot 风格。
"""

from __future__ import annotations

import codecs
import json
import typing
from collections.abc import AsyncGenerator

import httpx

from .errors import DeerFlowAPIError


SSE_MAX_BUFFER_CHARS = 1_048_576


def _normalize_sse_newlines(text: str) -> str:
    """规范化 CRLF/CR 为 LF，确保 SSE 块分割稳定"""
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _parse_sse_data_lines(data_lines: list[str]) -> typing.Any:
    raw_data = '\n'.join(data_lines)
    try:
        return json.loads(raw_data)
    except json.JSONDecodeError:
        # 某些 LangGraph 兼容服务端会在单个 SSE 事件中用多个 data 行
        # 发送多段 JSON 片段（例如 tuple payload）
        parsed_lines: list[typing.Any] = []
        can_parse_all = True
        for line in data_lines:
            line = line.strip()
            if not line:
                continue
            try:
                parsed_lines.append(json.loads(line))
            except json.JSONDecodeError:
                can_parse_all = False
                break
        if can_parse_all and parsed_lines:
            return parsed_lines[0] if len(parsed_lines) == 1 else parsed_lines
        return raw_data


def _parse_sse_block(block: str) -> dict[str, typing.Any] | None:
    if not block.strip():
        return None

    event_name = 'message'
    data_lines: list[str] = []
    for line in block.splitlines():
        if line.startswith('event:'):
            event_name = line[6:].strip()
        elif line.startswith('data:'):
            data_lines.append(line[5:].lstrip())

    if not data_lines:
        return None
    return {'event': event_name, 'data': _parse_sse_data_lines(data_lines)}


class AsyncDeerFlowClient:
    """DeerFlow LangGraph HTTP API 客户端"""

    api_base: str
    headers: dict[str, str]

    def __init__(
        self,
        api_base: str = 'http://127.0.0.1:2026',
        api_key: str = '',
        auth_header: str = '',
    ) -> None:
        self.api_base = api_base.rstrip('/')
        self.headers: dict[str, str] = {}
        if auth_header:
            self.headers['Authorization'] = auth_header
        elif api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'

    async def create_thread(self, timeout: float = 20) -> dict[str, typing.Any]:
        """创建一个新的 LangGraph thread

        Returns:
            包含 thread_id 等信息的字典
        """
        url = f'{self.api_base}/api/langgraph/threads'
        payload = {'metadata': {}}

        async with httpx.AsyncClient(
            trust_env=True,
            timeout=timeout,
        ) as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=payload,
            )
            if response.status_code not in (200, 201):
                raise DeerFlowAPIError(
                    operation='create thread',
                    status=response.status_code,
                    body=response.text,
                    url=url,
                )
            return response.json()

    async def delete_thread(self, thread_id: str, timeout: float = 20) -> None:
        """删除指定 thread"""
        url = f'{self.api_base}/api/threads/{thread_id}'

        async with httpx.AsyncClient(
            trust_env=True,
            timeout=timeout,
        ) as client:
            response = await client.delete(url, headers=self.headers)
            if response.status_code not in (200, 202, 204, 404):
                raise DeerFlowAPIError(
                    operation='delete thread',
                    status=response.status_code,
                    body=response.text,
                    url=url,
                    thread_id=thread_id,
                )

    async def stream_run(
        self,
        thread_id: str,
        payload: dict[str, typing.Any],
        timeout: float = 120,
    ) -> AsyncGenerator[dict[str, typing.Any], None]:
        """运行一次 LangGraph stream 请求，逐事件 yield

        Yields:
            事件字典 {'event': event_name, 'data': parsed_data}
        """
        url = f'{self.api_base}/api/langgraph/threads/{thread_id}/runs/stream'

        # 流式请求使用单独的 read timeout 控制
        stream_timeout = httpx.Timeout(
            connect=min(timeout, 30),
            read=timeout,
            write=timeout,
            pool=timeout,
        )

        async with httpx.AsyncClient(
            trust_env=True,
            timeout=stream_timeout,
        ) as client:
            async with client.stream(
                'POST',
                url,
                headers={
                    **self.headers,
                    'Accept': 'text/event-stream',
                    'Content-Type': 'application/json',
                },
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise DeerFlowAPIError(
                        operation='runs/stream request',
                        status=resp.status_code,
                        body=body.decode('utf-8', errors='replace'),
                        url=url,
                        thread_id=thread_id,
                    )

                decoder = codecs.getincrementaldecoder('utf-8')('replace')
                buffer = ''

                async for chunk in resp.aiter_bytes(8192):
                    buffer += _normalize_sse_newlines(decoder.decode(chunk))

                    while '\n\n' in buffer:
                        block, buffer = buffer.split('\n\n', 1)
                        parsed = _parse_sse_block(block)
                        if parsed is not None:
                            yield parsed

                    if len(buffer) > SSE_MAX_BUFFER_CHARS:
                        # 缓冲区过大，强制 flush
                        parsed = _parse_sse_block(buffer)
                        if parsed is not None:
                            yield parsed
                        buffer = ''

                # flush 剩余内容
                buffer += _normalize_sse_newlines(decoder.decode(b'', final=True))
                while '\n\n' in buffer:
                    block, buffer = buffer.split('\n\n', 1)
                    parsed = _parse_sse_block(block)
                    if parsed is not None:
                        yield parsed
                if buffer.strip():
                    parsed = _parse_sse_block(buffer)
                    if parsed is not None:
                        yield parsed
