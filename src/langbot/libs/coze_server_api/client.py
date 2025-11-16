import json
import asyncio
import aiohttp
import io
from typing import Dict, List, Any, AsyncGenerator
import os
from pathlib import Path


class AsyncCozeAPIClient:
    def __init__(self, api_key: str, api_base: str = 'https://api.coze.cn'):
        self.api_key = api_key
        self.api_base = api_base
        self.session = None

    async def __aenter__(self):
        """支持异步上下文管理器"""
        await self.coze_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出时自动关闭会话"""
        await self.close()

    async def coze_session(self):
        """确保HTTP session存在"""
        if self.session is None:
            connector = aiohttp.TCPConnector(
                ssl=False if self.api_base.startswith('http://') else True,
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(
                total=120,  # 默认超时时间
                connect=30,
                sock_read=120,
            )
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Accept': 'text/event-stream',
            }
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector)
        return self.session

    async def close(self):
        """显式关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def upload(
        self,
        file,
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

        session = await self.coze_session()
        url = f'{self.api_base}/v1/files/upload'

        try:
            file_io = io.BytesIO(file)
            async with session.post(
                url,
                data={
                    'file': file_io,
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status == 401:
                    raise Exception('Coze API 认证失败，请检查 API Key 是否正确')

                response_text = await response.text()

                if response.status != 200:
                    raise Exception(f'文件上传失败，状态码: {response.status}, 响应: {response_text}')
                try:
                    result = await response.json()
                except json.JSONDecodeError:
                    raise Exception(f'文件上传响应解析失败: {response_text}')

                if result.get('code') != 0:
                    raise Exception(f'文件上传失败: {result.get("msg", "未知错误")}')

                file_id = result['data']['id']
                return file_id

        except asyncio.TimeoutError:
            raise Exception('文件上传超时')
        except Exception as e:
            raise Exception(f'文件上传失败: {str(e)}')

    async def chat_messages(
        self,
        bot_id: str,
        user_id: str,
        additional_messages: List[Dict] | None = None,
        conversation_id: str | None = None,
        auto_save_history: bool = True,
        stream: bool = True,
        timeout: float = 120,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """发送聊天消息并返回流式响应

        Args:
            bot_id: Bot ID
            user_id: 用户ID
            additional_messages: 额外消息列表
            conversation_id: 会话ID
            auto_save_history: 是否自动保存历史
            stream: 是否流式响应
            timeout: 超时时间
        """
        session = await self.coze_session()
        url = f'{self.api_base}/v3/chat'

        payload = {
            'bot_id': bot_id,
            'user_id': user_id,
            'stream': stream,
            'auto_save_history': auto_save_history,
        }

        if additional_messages:
            payload['additional_messages'] = additional_messages

        params = {}
        if conversation_id:
            params['conversation_id'] = conversation_id

        try:
            async with session.post(
                url,
                json=payload,
                params=params,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 401:
                    raise Exception('Coze API 认证失败，请检查 API Key 是否正确')

                if response.status != 200:
                    raise Exception(f'Coze API 流式请求失败，状态码: {response.status}')

                async for chunk in response.content:
                    chunk = chunk.decode('utf-8')
                    if chunk != '\n':
                        if chunk.startswith('event:'):
                            chunk_type = chunk.replace('event:', '', 1).strip()
                        elif chunk.startswith('data:'):
                            chunk_data = chunk.replace('data:', '', 1).strip()
                    else:
                        yield {
                            'event': chunk_type,
                            'data': json.loads(chunk_data) if chunk_data else {},
                        }  # 处理本地部署时，接口返回的data为空值

        except asyncio.TimeoutError:
            raise Exception(f'Coze API 流式请求超时 ({timeout}秒)')
        except Exception as e:
            raise Exception(f'Coze API 流式请求失败: {str(e)}')
