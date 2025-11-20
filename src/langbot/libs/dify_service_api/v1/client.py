from __future__ import annotations

import httpx
import typing
import json

from .errors import DifyAPIError
from pathlib import Path
import os


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

    async def chat_messages(
        self,
        inputs: dict[str, typing.Any],
        query: str,
        user: str,
        response_mode: str = 'streaming',  # 当前不支持 blocking
        conversation_id: str = '',
        files: list[dict[str, typing.Any]] = [],
        timeout: float = 30.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """发送消息"""
        if response_mode != 'streaming':
            raise DifyAPIError('当前仅支持 streaming 模式')

        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
            async with client.stream(
                'POST',
                '/chat-messages',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'inputs': inputs,
                    'query': query,
                    'user': user,
                    'response_mode': response_mode,
                    'conversation_id': conversation_id,
                    'files': files,
                },
            ) as r:
                async for chunk in r.aiter_lines():
                    if r.status_code != 200:
                        raise DifyAPIError(f'{r.status_code} {chunk}')
                    if chunk.strip() == '':
                        continue
                    if chunk.startswith('data:'):
                        yield json.loads(chunk[5:])

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

        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
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
            ) as r:
                async for chunk in r.aiter_lines():
                    if r.status_code != 200:
                        raise DifyAPIError(f'{r.status_code} {chunk}')
                    if chunk.strip() == '':
                        continue
                    if chunk.startswith('data:'):
                        yield json.loads(chunk[5:])

    async def upload_file(
        self,
        file: httpx._types.FileTypes,
        user: str,
        timeout: float = 30.0,
    ) -> str:
        # 处理 Path 对象
        if isinstance(file, Path):
            if not file.exists():
                raise ValueError(f'File not found: {file}')
            with open(file, 'rb') as f:
                file = f.read()

        # 处理文件路径字符串
        elif isinstance(file, str):
            if not os.path.isfile(file):
                raise ValueError(f'File not found: {file}')
            with open(file, 'rb') as f:
                file = f.read()

        # 处理文件对象
        elif hasattr(file, 'read'):
            file = file.read()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            trust_env=True,
            timeout=timeout,
        ) as client:
            # multipart/form-data
            response = await client.post(
                '/files/upload',
                headers={'Authorization': f'Bearer {self.api_key}'},
                files={
                    'file': file,
                },
                data={
                    'user': (None, user),
                },
            )

            if response.status_code != 201:
                raise DifyAPIError(f'{response.status_code} {response.text}')

            return response.json()
