from __future__ import annotations

import httpx
import typing
import json

from .errors import WeKnoraAPIError

_MAX_WENKORA_RESPONSE_BYTES = 1024 * 1024
_MAX_WENKORA_STREAM_BYTES = 16 * 1024 * 1024
_MAX_WENKORA_SSE_LINE_BYTES = 1024 * 1024


async def _read_limited_response(response: httpx.Response) -> bytes:
    body = bytearray()
    async for chunk in response.aiter_bytes(chunk_size=8192):
        body.extend(chunk)
        if len(body) > _MAX_WENKORA_RESPONSE_BYTES:
            raise WeKnoraAPIError('WeKnora response exceeds the runtime limit')
    return bytes(body)


async def _iter_sse_json(
    response: httpx.Response,
) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
    buffer = bytearray()
    total = 0
    async for chunk in response.aiter_bytes(chunk_size=8192):
        total += len(chunk)
        if total > _MAX_WENKORA_STREAM_BYTES:
            raise WeKnoraAPIError('WeKnora stream exceeds the runtime limit')
        buffer.extend(chunk)
        while b'\n' in buffer:
            raw_line, _, remainder = buffer.partition(b'\n')
            buffer = bytearray(remainder)
            if len(raw_line) > _MAX_WENKORA_SSE_LINE_BYTES:
                raise WeKnoraAPIError('WeKnora SSE event exceeds the runtime limit')
            line = raw_line.rstrip(b'\r').strip()
            if not line.startswith(b'data:'):
                continue
            try:
                data = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                yield data
        if len(buffer) > _MAX_WENKORA_SSE_LINE_BYTES:
            raise WeKnoraAPIError('WeKnora SSE event exceeds the runtime limit')

    line = bytes(buffer).rstrip(b'\r').strip()
    if line.startswith(b'data:'):
        try:
            data = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            return
        if isinstance(data, dict):
            yield data


class AsyncWeKnoraClient:
    """WeKnora API 客户端"""

    api_key: str
    base_url: str

    def __init__(
        self,
        api_key: str,
        base_url: str = 'http://localhost:80/api/v1',
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url

    async def create_session(
        self,
        title: str = '',
        description: str = '',
        timeout: float = 30.0,
    ) -> str:
        """创建会话，返回 session_id"""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
            payload: dict[str, typing.Any] = {}
            if title:
                payload['title'] = title
            if description:
                payload['description'] = description

            async with client.stream(
                'POST',
                '/sessions',
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json=payload,
            ) as response:
                body = await _read_limited_response(response)
                if response.status_code not in (200, 201):
                    raise WeKnoraAPIError(f'{response.status_code} {body.decode("utf-8", errors="replace")}')
            data = json.loads(body)
            return data['data']['id']

    async def agent_chat(
        self,
        session_id: str,
        query: str,
        user: str,
        agent_id: str = '',
        knowledge_base_ids: list[str] | None = None,
        web_search_enabled: bool = False,
        timeout: float = 120.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """
        Agent 智能对话（SSE 流式）

        响应事件类型:
        - agent_query: Agent 开始处理
        - thinking: 思考过程
        - tool_call: 工具调用
        - tool_result: 工具结果
        - references: 知识库引用
        - answer: 回答内容
        - reflection: 反思
        - session_title: 会话标题
        - error: 错误
        """
        if knowledge_base_ids is None:
            knowledge_base_ids = []

        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
            payload: dict[str, typing.Any] = {
                'query': query,
                'agent_enabled': True,
                'channel': 'im',
            }
            if agent_id:
                payload['agent_id'] = agent_id
            if knowledge_base_ids:
                payload['knowledge_base_ids'] = knowledge_base_ids
            if web_search_enabled:
                payload['web_search_enabled'] = True

            async with client.stream(
                'POST',
                f'/agent-chat/{session_id}',
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json=payload,
            ) as r:
                if r.status_code != 200:
                    body = await _read_limited_response(r)
                    raise WeKnoraAPIError(f'{r.status_code} {body.decode("utf-8", errors="replace")}')
                async for data in _iter_sse_json(r):
                    yield data
                    if data.get('response_type') == 'error':
                        return

    async def knowledge_chat(
        self,
        session_id: str,
        query: str,
        user: str,
        agent_id: str = 'builtin-quick-answer',
        knowledge_base_ids: list[str] | None = None,
        timeout: float = 120.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """
        知识库 RAG 问答（SSE 流式）

        响应事件类型:
        - references: 知识库引用
        - answer: 回答内容
        """
        if knowledge_base_ids is None:
            knowledge_base_ids = []

        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
            payload: dict[str, typing.Any] = {
                'query': query,
                'channel': 'im',
            }
            if agent_id:
                payload['agent_id'] = agent_id
            if knowledge_base_ids:
                payload['knowledge_base_ids'] = knowledge_base_ids

            async with client.stream(
                'POST',
                f'/knowledge-chat/{session_id}',
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json=payload,
            ) as r:
                if r.status_code != 200:
                    body = await _read_limited_response(r)
                    raise WeKnoraAPIError(f'{r.status_code} {body.decode("utf-8", errors="replace")}')
                async for data in _iter_sse_json(r):
                    yield data
                    if data.get('response_type') == 'error':
                        return
