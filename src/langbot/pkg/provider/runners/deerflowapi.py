"""DeerFlow LangGraph API Runner

参考 astrbot 的 deerflow_agent_runner 实现，适配 LangBot 的 Runner 接口。

特点：
- 使用 LangGraph HTTP API 接入 deer-flow 后端
- 自动管理 thread_id（按 session 隔离）
- 支持 SSE 流式响应解析
- 支持 streaming/非流式两种输出
- 处理 values / messages-tuple / custom 三种事件
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import typing
from collections import deque
from dataclasses import dataclass, field


from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.deerflow_api import client, errors, stream_utils


# TODO(agent-runner): Keep this legacy RequestRunner implementation until
# DeerFlow is migrated to an official AgentRunner plugin.
_MAX_VALUES_HISTORY = 200


@dataclass
class _StreamState:
    """流式状态跟踪"""

    latest_text: str = ''
    prev_text_for_streaming: str = ''
    clarification_text: str = ''
    task_failures: list[str] = field(default_factory=list)
    seen_message_ids: set[str] = field(default_factory=set)
    seen_message_order: deque[str] = field(default_factory=deque)
    no_id_message_fingerprints: dict[int, str] = field(default_factory=dict)
    baseline_initialized: bool = False
    has_values_text: bool = False
    run_values_messages: list[dict[str, typing.Any]] = field(default_factory=list)
    timed_out: bool = False


@runner.runner_class('deerflow-api')
class DeerFlowAPIRunner(runner.RequestRunner):
    """DeerFlow LangGraph API 对话请求器"""

    deerflow_client: client.AsyncDeerFlowClient

    def __init__(self, ap: app.Application, pipeline_config: dict):
        super().__init__(ap, pipeline_config)

        cfg = self.pipeline_config['ai']['deerflow-api']

        api_base = cfg.get('api-base', '').strip()
        if not api_base or not api_base.startswith(('http://', 'https://')):
            raise errors.DeerFlowAPIError(
                message='DeerFlow API Base URL 格式错误，必须以 http:// 或 https:// 开头',
            )

        self.api_base = api_base
        self.api_key = cfg.get('api-key', '')
        self.auth_header = cfg.get('auth-header', '')
        self.assistant_id = cfg.get('assistant-id', 'lead_agent')
        self.model_name = cfg.get('model-name', '')
        self.thinking_enabled = bool(cfg.get('thinking-enabled', False))
        self.plan_mode = bool(cfg.get('plan-mode', False))
        self.subagent_enabled = bool(cfg.get('subagent-enabled', False))
        self.max_concurrent_subagents = int(cfg.get('max-concurrent-subagents', 3))
        self.timeout = int(cfg.get('timeout', 300))
        self.recursion_limit = int(cfg.get('recursion-limit', 1000))

        self.deerflow_client = client.AsyncDeerFlowClient(
            api_base=self.api_base,
            api_key=self.api_key,
            auth_header=self.auth_header,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _fingerprint_message(self, message: dict[str, typing.Any]) -> str:
        try:
            raw = json.dumps(message, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            raw = repr(message)
        return hashlib.sha1(raw.encode('utf-8', errors='ignore')).hexdigest()

    def _remember_seen_message_id(self, state: _StreamState, msg_id: str) -> None:
        if not msg_id or msg_id in state.seen_message_ids:
            return
        state.seen_message_ids.add(msg_id)
        state.seen_message_order.append(msg_id)
        while len(state.seen_message_order) > _MAX_VALUES_HISTORY:
            dropped = state.seen_message_order.popleft()
            state.seen_message_ids.discard(dropped)

    def _extract_new_messages_from_values(
        self,
        values_messages: list[typing.Any],
        state: _StreamState,
    ) -> list[dict[str, typing.Any]]:
        new_messages: list[dict[str, typing.Any]] = []
        no_id_indexes_seen: set[int] = set()
        for idx, msg in enumerate(values_messages):
            if not isinstance(msg, dict):
                continue
            msg_id = stream_utils.get_message_id(msg)
            if msg_id:
                if msg_id in state.seen_message_ids:
                    continue
                self._remember_seen_message_id(state, msg_id)
                new_messages.append(msg)
                continue

            no_id_indexes_seen.add(idx)
            fp = self._fingerprint_message(msg)
            if state.no_id_message_fingerprints.get(idx) == fp:
                continue
            state.no_id_message_fingerprints[idx] = fp
            new_messages.append(msg)

        for idx in list(state.no_id_message_fingerprints.keys()):
            if idx not in no_id_indexes_seen:
                state.no_id_message_fingerprints.pop(idx, None)
        return new_messages

    # ------------------------------------------------------------------
    # 用户输入处理
    # ------------------------------------------------------------------

    def _build_user_content(
        self,
        prompt: str,
        image_urls: list[str],
    ) -> typing.Any:
        """构建 LangGraph 兼容的 user content（支持多模态）"""
        if not image_urls:
            return prompt

        content: list[dict[str, typing.Any]] = []
        if prompt:
            content.append({'type': 'text', 'text': prompt})
        for url in image_urls:
            if not isinstance(url, str):
                continue
            url = url.strip()
            if not url:
                continue
            if url.startswith(('http://', 'https://', 'data:')):
                content.append({'type': 'image_url', 'image_url': {'url': url}})
        return content if content else prompt

    def _preprocess_user_message(
        self,
        query: pipeline_query.Query,
    ) -> tuple[str, list[str]]:
        """提取用户消息的纯文本与图片 URL 列表"""
        plain_text = ''
        image_urls: list[str] = []

        if isinstance(query.user_message.content, str):
            plain_text = query.user_message.content
        elif isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    # 转换为 data URI 形式
                    b64 = getattr(ce, 'image_base64', '')
                    if b64:
                        if not b64.startswith('data:'):
                            b64 = f'data:image/png;base64,{b64}'
                        image_urls.append(b64)
                elif ce.type == 'image_url':
                    url = getattr(ce, 'image_url', '')
                    if url:
                        image_urls.append(url)

        return plain_text, image_urls

    # ------------------------------------------------------------------
    # 请求构造
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        prompt: str,
        image_urls: list[str],
        system_prompt: str = '',
    ) -> list[dict[str, typing.Any]]:
        messages: list[dict[str, typing.Any]] = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append(
            {
                'role': 'user',
                'content': self._build_user_content(prompt, image_urls),
            }
        )
        return messages

    def _build_runtime_configurable(self, thread_id: str) -> dict[str, typing.Any]:
        cfg: dict[str, typing.Any] = {
            'thread_id': thread_id,
            'thinking_enabled': self.thinking_enabled,
            'is_plan_mode': self.plan_mode,
            'subagent_enabled': self.subagent_enabled,
        }
        if self.subagent_enabled:
            cfg['max_concurrent_subagents'] = self.max_concurrent_subagents
        if self.model_name:
            cfg['model_name'] = self.model_name
        return cfg

    def _build_payload(
        self,
        thread_id: str,
        prompt: str,
        image_urls: list[str],
        system_prompt: str = '',
    ) -> dict[str, typing.Any]:
        runtime_configurable = self._build_runtime_configurable(thread_id)
        return {
            'assistant_id': self.assistant_id,
            'input': {
                'messages': self._build_messages(prompt, image_urls, system_prompt),
            },
            'stream_mode': ['values', 'messages-tuple', 'custom'],
            # DeerFlow 2.0 从 config.configurable 读取运行时覆盖
            # 同时保留 context 字段做向后兼容
            'context': dict(runtime_configurable),
            'config': {
                'recursion_limit': self.recursion_limit,
                'configurable': runtime_configurable,
            },
        }

    # ------------------------------------------------------------------
    # Session/Thread 管理
    # ------------------------------------------------------------------

    async def _ensure_thread_id(self, query: pipeline_query.Query) -> str:
        """从 query.session 取/创建 deerflow thread_id

        LangBot 使用 `query.session.using_conversation.uuid` 持久化 conversation id，
        我们复用这个字段存储 deerflow thread_id（与 Dify Runner 同样做法）。
        """
        thread_id = query.session.using_conversation.uuid or ''
        if thread_id:
            return thread_id

        thread = await self.deerflow_client.create_thread(timeout=min(30, self.timeout))
        thread_id = thread.get('thread_id', '')
        if not thread_id:
            raise errors.DeerFlowAPIError(message=f'DeerFlow create thread 返回数据缺少 thread_id: {thread}')

        query.session.using_conversation.uuid = thread_id
        return thread_id

    # ------------------------------------------------------------------
    # 流式事件处理
    # ------------------------------------------------------------------

    def _handle_values_event(
        self,
        data: typing.Any,
        state: _StreamState,
    ) -> str | None:
        """处理 values 事件，返回新的完整文本（增量基础上的全量）"""
        values_messages = stream_utils.extract_messages_from_values_data(data)
        if not values_messages:
            return None

        new_messages: list[dict[str, typing.Any]] = []
        if not state.baseline_initialized:
            state.baseline_initialized = True
            for idx, msg in enumerate(values_messages):
                if not isinstance(msg, dict):
                    continue
                new_messages.append(msg)
                msg_id = stream_utils.get_message_id(msg)
                if msg_id:
                    self._remember_seen_message_id(state, msg_id)
                    continue
                state.no_id_message_fingerprints[idx] = self._fingerprint_message(msg)
        else:
            new_messages = self._extract_new_messages_from_values(values_messages, state)

        latest_text = ''
        if new_messages:
            state.run_values_messages.extend(new_messages)
            if len(state.run_values_messages) > _MAX_VALUES_HISTORY:
                state.run_values_messages = state.run_values_messages[-_MAX_VALUES_HISTORY:]
            latest_text = stream_utils.extract_latest_ai_text(state.run_values_messages)
            if latest_text:
                state.has_values_text = True
            latest_clarification = stream_utils.extract_latest_clarification_text(
                state.run_values_messages,
            )
            if latest_clarification:
                state.clarification_text = latest_clarification

        return latest_text or None

    def _handle_message_event(
        self,
        data: typing.Any,
        state: _StreamState,
    ) -> str | None:
        """处理 messages-tuple 事件，返回增量文本

        当 values 事件已经提供完整文本时，跳过 messages-tuple 的增量
        """
        delta = stream_utils.extract_ai_delta_from_event_data(data)
        if delta and not state.has_values_text:
            state.latest_text += delta
            return delta

        maybe_clar = stream_utils.extract_clarification_from_event_data(data)
        if maybe_clar:
            state.clarification_text = maybe_clar
        return None

    def _build_final_text(self, state: _StreamState) -> str:
        """构建最终输出文本"""
        if state.clarification_text:
            return state.clarification_text

        # 优先使用最后一条 AI message 的文本
        latest_ai = stream_utils.extract_latest_ai_message(state.run_values_messages)
        if latest_ai:
            text = stream_utils.extract_text(latest_ai.get('content'))
            if text:
                if state.timed_out:
                    text += f'\n\nDeerFlow stream 在 {self.timeout}s 后超时，返回部分结果。'
                return text

        if state.latest_text:
            text = state.latest_text
            if state.timed_out:
                text += f'\n\nDeerFlow stream 在 {self.timeout}s 后超时，返回部分结果。'
            return text

        # 提取任务失败信息作兜底
        failure_text = stream_utils.build_task_failure_summary(state.task_failures)
        if failure_text:
            return failure_text

        return 'DeerFlow 返回空响应'

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    async def _stream_messages_chunk(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """流式输出生成器"""
        plain_text, image_urls = self._preprocess_user_message(query)

        system_prompt = ''
        # LangBot 的 pipeline 通常通过 prompt-preprocess 已注入 system prompt
        # 这里保持空，让 prompt-preprocess 的内容作为 user message 一并送给 deerflow

        thread_id = await self._ensure_thread_id(query)
        payload = self._build_payload(
            thread_id=thread_id,
            prompt=plain_text or 'continue',
            image_urls=image_urls,
            system_prompt=system_prompt,
        )

        state = _StreamState()
        prev_text = ''
        message_idx = 0

        try:
            async for event in self.deerflow_client.stream_run(
                thread_id=thread_id,
                payload=payload,
                timeout=self.timeout,
            ):
                event_type = event.get('event')
                data = event.get('data')

                if event_type == 'values':
                    new_full = self._handle_values_event(data, state)
                    if new_full and new_full != prev_text:
                        delta = new_full[len(prev_text) :] if new_full.startswith(prev_text) else new_full
                        prev_text = new_full
                        if delta:
                            message_idx += 1
                            yield provider_message.MessageChunk(
                                role='assistant',
                                content=new_full,
                                is_final=False,
                            )
                    continue

                if event_type in {'messages-tuple', 'messages', 'message'}:
                    delta = self._handle_message_event(data, state)
                    if delta:
                        prev_text = state.latest_text
                        message_idx += 1
                        yield provider_message.MessageChunk(
                            role='assistant',
                            content=prev_text,
                            is_final=False,
                        )
                    continue

                if event_type == 'custom':
                    state.task_failures.extend(
                        stream_utils.extract_task_failures_from_custom_event(data),
                    )
                    continue

                if event_type == 'error':
                    raise errors.DeerFlowAPIError(message=f'DeerFlow stream error event: {data}')

                if event_type == 'end':
                    break
        except (asyncio.TimeoutError, TimeoutError):
            self.ap.logger.warning(f'DeerFlow stream timed out after {self.timeout}s for thread_id={thread_id}')
            state.timed_out = True

        # 最终消息
        final_text = self._build_final_text(state)
        yield provider_message.MessageChunk(
            role='assistant',
            content=final_text,
            is_final=True,
        )

    async def _messages(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """非流式聚合输出"""
        plain_text, image_urls = self._preprocess_user_message(query)

        thread_id = await self._ensure_thread_id(query)
        payload = self._build_payload(
            thread_id=thread_id,
            prompt=plain_text or 'continue',
            image_urls=image_urls,
        )

        state = _StreamState()

        try:
            async for event in self.deerflow_client.stream_run(
                thread_id=thread_id,
                payload=payload,
                timeout=self.timeout,
            ):
                event_type = event.get('event')
                data = event.get('data')

                if event_type == 'values':
                    self._handle_values_event(data, state)
                    continue

                if event_type in {'messages-tuple', 'messages', 'message'}:
                    self._handle_message_event(data, state)
                    continue

                if event_type == 'custom':
                    state.task_failures.extend(
                        stream_utils.extract_task_failures_from_custom_event(data),
                    )
                    continue

                if event_type == 'error':
                    raise errors.DeerFlowAPIError(message=f'DeerFlow stream error event: {data}')

                if event_type == 'end':
                    break
        except (asyncio.TimeoutError, TimeoutError):
            self.ap.logger.warning(f'DeerFlow stream timed out after {self.timeout}s for thread_id={thread_id}')
            state.timed_out = True

        final_text = self._build_final_text(state)
        yield provider_message.Message(
            role='assistant',
            content=final_text,
        )

    async def run(
        self,
        query: pipeline_query.Query,
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """主入口：根据 adapter 是否支持流式输出，选择流式或非流式"""
        if await query.adapter.is_stream_output_supported():
            msg_idx = 0
            async for msg in self._stream_messages_chunk(query):
                msg_idx += 1
                msg.msg_sequence = msg_idx
                yield msg
        else:
            async for msg in self._messages(query):
                yield msg
