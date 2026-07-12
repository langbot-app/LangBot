from __future__ import annotations

import typing
import json


from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.weknora_api import client, errors


@runner.runner_class('weknora-api')
class WeKnoraAPIRunner(runner.RequestRunner):
    """WeKnora API 对话请求器"""

    weknora_client: client.AsyncWeKnoraClient

    def __init__(self, ap: app.Application, pipeline_config: dict):
        super().__init__(ap, pipeline_config)

        valid_app_types = ['chat', 'agent']
        if self.pipeline_config['ai']['weknora-api']['app-type'] not in valid_app_types:
            raise errors.WeKnoraAPIError(
                f'不支持的 WeKnora 应用类型: {self.pipeline_config["ai"]["weknora-api"]["app-type"]}'
            )

        api_key = self.pipeline_config['ai']['weknora-api'].get('api-key', '').strip()
        if not api_key:
            raise errors.WeKnoraAPIError(
                'WeKnora API Key 未配置，请在流水线的 WeKnora API 配置中填入 API Key '
                '(从 WeKnora 前端 设置 → API Keys 生成)'
            )

        base_url = self.pipeline_config['ai']['weknora-api'].get('base-url', '').strip()
        if not base_url:
            raise errors.WeKnoraAPIError('WeKnora Base URL 未配置，请填入服务器地址，例如 http://localhost:8080/api/v1')

        self.weknora_client = client.AsyncWeKnoraClient(
            api_key=api_key,
            base_url=base_url,
        )

    async def _extract_plain_text(self, query: pipeline_query.Query) -> str:
        """从用户消息中提取纯文本内容"""
        plain_text = ''
        if isinstance(query.user_message.content, str):
            plain_text = query.user_message.content
        elif isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text

        if not plain_text:
            plain_text = self.pipeline_config['ai']['weknora-api'].get('base-prompt', '')

        return plain_text

    async def _ensure_session(self, query: pipeline_query.Query) -> str:
        """确保会话存在，如果不存在则创建"""
        session_id = query.session.using_conversation.uuid or ''

        if not session_id:
            user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'
            session_id = await self.weknora_client.create_session(title=f'IM Chat - {user_tag}')
            query.session.using_conversation.uuid = session_id

        return session_id

    async def _agent_chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用 Agent 智能对话（非流式聚合输出）"""
        session_id = await self._ensure_session(query)
        plain_text = await self._extract_plain_text(query)
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        config = self.pipeline_config['ai']['weknora-api']
        agent_id = config.get('agent-id', 'builtin-smart-reasoning')
        knowledge_base_ids = config.get('knowledge-base-ids', [])
        web_search_enabled = config.get('web-search-enabled', False)
        timeout = config.get('timeout', 120)

        full_answer = ''
        chunk = None

        async for chunk in self.weknora_client.agent_chat(
            session_id=session_id,
            query=plain_text,
            user=user_tag,
            agent_id=agent_id,
            knowledge_base_ids=knowledge_base_ids,
            web_search_enabled=web_search_enabled,
            timeout=timeout,
        ):
            self.ap.logger.debug('weknora-agent-chunk: ' + str(chunk))

            response_type = chunk.get('response_type', '')
            content = chunk.get('content', '')

            if response_type == 'tool_call':
                # 工具调用
                tool_data = chunk.get('data', {})
                tool_name = tool_data.get('tool_name', '')
                if tool_name:
                    yield provider_message.Message(
                        role='assistant',
                        tool_calls=[
                            provider_message.ToolCall(
                                id=chunk.get('id', ''),
                                type='function',
                                function=provider_message.FunctionCall(
                                    name=tool_name,
                                    arguments=json.dumps(tool_data.get('arguments', {})),
                                ),
                            )
                        ],
                    )

            elif response_type == 'answer':
                if content:
                    full_answer += content

            elif response_type == 'error':
                raise errors.WeKnoraAPIError(f'WeKnora 服务错误: {content}')

        if chunk is None:
            raise errors.WeKnoraAPIError('WeKnora API 没有返回任何响应，请检查网络连接和API配置')

        if full_answer:
            yield provider_message.Message(
                role='assistant',
                content=full_answer,
            )

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用知识库 RAG 问答（非流式聚合输出）"""
        session_id = await self._ensure_session(query)
        plain_text = await self._extract_plain_text(query)
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        config = self.pipeline_config['ai']['weknora-api']
        agent_id = config.get('agent-id', 'builtin-quick-answer')
        knowledge_base_ids = config.get('knowledge-base-ids', [])
        timeout = config.get('timeout', 120)

        full_answer = ''
        chunk = None

        async for chunk in self.weknora_client.knowledge_chat(
            session_id=session_id,
            query=plain_text,
            user=user_tag,
            agent_id=agent_id,
            knowledge_base_ids=knowledge_base_ids,
            timeout=timeout,
        ):
            self.ap.logger.debug('weknora-chat-chunk: ' + str(chunk))

            response_type = chunk.get('response_type', '')
            content = chunk.get('content', '')

            if response_type == 'answer':
                if content:
                    full_answer += content

            elif response_type == 'error':
                raise errors.WeKnoraAPIError(f'WeKnora 服务错误: {content}')

        if chunk is None:
            raise errors.WeKnoraAPIError('WeKnora API 没有返回任何响应，请检查网络连接和API配置')

        if full_answer:
            yield provider_message.Message(
                role='assistant',
                content=full_answer,
            )

    async def _agent_chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用 Agent 智能对话（流式输出）"""
        session_id = await self._ensure_session(query)
        plain_text = await self._extract_plain_text(query)
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        config = self.pipeline_config['ai']['weknora-api']
        agent_id = config.get('agent-id', 'builtin-smart-reasoning')
        knowledge_base_ids = config.get('knowledge-base-ids', [])
        web_search_enabled = config.get('web-search-enabled', False)
        timeout = config.get('timeout', 120)

        pending_answer = ''
        message_idx = 0
        is_final = False
        chunk = None

        async for chunk in self.weknora_client.agent_chat(
            session_id=session_id,
            query=plain_text,
            user=user_tag,
            agent_id=agent_id,
            knowledge_base_ids=knowledge_base_ids,
            web_search_enabled=web_search_enabled,
            timeout=timeout,
        ):
            self.ap.logger.debug('weknora-agent-chunk: ' + str(chunk))

            response_type = chunk.get('response_type', '')
            content = chunk.get('content', '')
            done = chunk.get('done', False)

            if response_type == 'tool_call':
                tool_data = chunk.get('data', {})
                tool_name = tool_data.get('tool_name', '')
                if tool_name:
                    message_idx += 1
                    yield provider_message.MessageChunk(
                        role='assistant',
                        tool_calls=[
                            provider_message.ToolCall(
                                id=chunk.get('id', ''),
                                type='function',
                                function=provider_message.FunctionCall(
                                    name=tool_name,
                                    arguments=json.dumps(tool_data.get('arguments', {})),
                                ),
                            )
                        ],
                    )

            elif response_type == 'answer':
                message_idx += 1
                if content:
                    pending_answer += content

                if done:
                    is_final = True

                # 每 8 个 chunk 输出一次，或最终输出
                if message_idx % 8 == 0 or is_final:
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=pending_answer,
                        is_final=is_final,
                    )

            elif response_type == 'error':
                raise errors.WeKnoraAPIError(f'WeKnora 服务错误: {content}')

        if chunk is None:
            raise errors.WeKnoraAPIError('WeKnora API 没有返回任何响应，请检查网络连接和API配置')

        # 确保最终消息已发出
        if not is_final and pending_answer:
            yield provider_message.MessageChunk(
                role='assistant',
                content=pending_answer,
                is_final=True,
            )

    async def _chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用知识库 RAG 问答（流式输出）"""
        session_id = await self._ensure_session(query)
        plain_text = await self._extract_plain_text(query)
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        config = self.pipeline_config['ai']['weknora-api']
        agent_id = config.get('agent-id', 'builtin-quick-answer')
        knowledge_base_ids = config.get('knowledge-base-ids', [])
        timeout = config.get('timeout', 120)

        pending_answer = ''
        message_idx = 0
        is_final = False
        chunk = None

        async for chunk in self.weknora_client.knowledge_chat(
            session_id=session_id,
            query=plain_text,
            user=user_tag,
            agent_id=agent_id,
            knowledge_base_ids=knowledge_base_ids,
            timeout=timeout,
        ):
            self.ap.logger.debug('weknora-chat-chunk: ' + str(chunk))

            response_type = chunk.get('response_type', '')
            content = chunk.get('content', '')
            done = chunk.get('done', False)

            if response_type == 'answer':
                message_idx += 1
                if content:
                    pending_answer += content

                if done:
                    is_final = True

                if message_idx % 8 == 0 or is_final:
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=pending_answer,
                        is_final=is_final,
                    )

            elif response_type == 'error':
                raise errors.WeKnoraAPIError(f'WeKnora 服务错误: {content}')

        if chunk is None:
            raise errors.WeKnoraAPIError('WeKnora API 没有返回任何响应，请检查网络连接和API配置')

        if not is_final and pending_answer:
            yield provider_message.MessageChunk(
                role='assistant',
                content=pending_answer,
                is_final=True,
            )

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行请求"""
        app_type = self.pipeline_config['ai']['weknora-api']['app-type']

        if await query.adapter.is_stream_output_supported():
            msg_idx = 0
            if app_type == 'agent':
                async for msg in self._agent_chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif app_type == 'chat':
                async for msg in self._chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            else:
                raise errors.WeKnoraAPIError(f'不支持的 WeKnora 应用类型: {app_type}')
        else:
            if app_type == 'agent':
                async for msg in self._agent_chat_messages(query):
                    yield msg
            elif app_type == 'chat':
                async for msg in self._chat_messages(query):
                    yield msg
            else:
                raise errors.WeKnoraAPIError(f'不支持的 WeKnora 应用类型: {app_type}')
