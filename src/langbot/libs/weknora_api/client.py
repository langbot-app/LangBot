from __future__ import annotations

import httpx
import typing
import json

from .errors import WeKnoraAPIError


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

            response = await client.post(
                '/sessions',
                headers={
                    'X-API-Key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json=payload,
            )

            if response.status_code not in (200, 201):
                raise WeKnoraAPIError(f'{response.status_code} {response.text}')

            data = response.json()
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
                async for chunk in r.aiter_lines():
                    if r.status_code != 200:
                        raise WeKnoraAPIError(f'{r.status_code} {chunk}')
                    if chunk.strip() == '':
                        continue
                    if chunk.startswith('data:'):
                        try:
                            data = json.loads(chunk[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        yield data
                        # 收到 error 事件后主动结束流，避免上层未 raise 时持续等待
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
                async for chunk in r.aiter_lines():
                    if r.status_code != 200:
                        raise WeKnoraAPIError(f'{r.status_code} {chunk}')
                    if chunk.strip() == '':
                        continue
                    if chunk.startswith('data:'):
                        try:
                            data = json.loads(chunk[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        yield data
                        # 收到 error 事件后主动结束流，避免上层未 raise 时持续等待
                        if data.get('response_type') == 'error':
                            return
