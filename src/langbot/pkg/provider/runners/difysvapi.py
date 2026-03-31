from __future__ import annotations

import asyncio
import typing
import json
import uuid
import base64
import mimetypes
import time

from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.dify_service_api.v1 import client, errors
from langbot.pkg.provider.conversation.dify_store import (
    DifyConversationStore,
    is_binding_expired,
    normalize_binding_payload,
)
import httpx


@runner.runner_class('dify-service-api')
class DifyServiceAPIRunner(runner.RequestRunner):
    """Dify Service API 对话请求器"""

    _RUNTIME_BINDING_ATTR = 'dify_conversation_binding'
    _RUNTIME_POLICY_VERSION = 2

    dify_client: client.AsyncDifyServiceClient

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config
        self._conversation_store: DifyConversationStore | None = None
        self._conversation_store_initialized = False

        valid_app_types = ['chat', 'agent', 'workflow']
        if self.pipeline_config['ai']['dify-service-api']['app-type'] not in valid_app_types:
            raise errors.DifyAPIError(
                f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
            )

        api_key = self.pipeline_config['ai']['dify-service-api']['api-key']

        self.dify_client = client.AsyncDifyServiceClient(
            api_key=api_key,
            base_url=self.pipeline_config['ai']['dify-service-api']['base-url'],
        )

    @staticmethod
    def _parse_bool_config(value: typing.Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'true', '1', 'yes', 'on'}:
                return True
            if normalized in {'false', '0', 'no', 'off'}:
                return False
            return default
        if isinstance(value, (int, float)):
            return bool(value)
        if value is None:
            return default
        return bool(value)

    def _get_output_misc_config(self) -> dict[str, typing.Any]:
        output_config = self.pipeline_config.get('output')
        if not isinstance(output_config, dict):
            return {}

        misc_config = output_config.get('misc')
        if not isinstance(misc_config, dict):
            return {}
        return misc_config

    def _is_remove_think_enabled(self) -> bool:
        misc_config = self._get_output_misc_config()
        return self._parse_bool_config(misc_config.get('remove-think', False), False)

    def _resolve_conversation_store_config(self) -> dict[str, typing.Any]:
        raw_app_cfg = getattr(getattr(self.ap, 'instance_config', None), 'data', {}) or {}
        app_cfg = raw_app_cfg if isinstance(raw_app_cfg, dict) else {}
        raw_instance_store_cfg = app_cfg.get('dify_conversation_store', {}) or {}
        instance_store_cfg = raw_instance_store_cfg if isinstance(raw_instance_store_cfg, dict) else {}

        pipeline_ai_cfg = self.pipeline_config.get('ai', {}) if isinstance(self.pipeline_config, dict) else {}
        pipeline_ai_cfg = pipeline_ai_cfg if isinstance(pipeline_ai_cfg, dict) else {}
        raw_pipeline_store_cfg = pipeline_ai_cfg.get('dify_conversation_store', {}) or {}
        pipeline_store_cfg = raw_pipeline_store_cfg if isinstance(raw_pipeline_store_cfg, dict) else {}

        # Precedence: defaults -> instance config -> pipeline config.
        store_cfg = {**instance_store_cfg, **pipeline_store_cfg}

        enabled = self._parse_bool_config(store_cfg.get('enabled', True), True)

        try:
            if 'idle_timeout_seconds' in store_cfg:
                idle_timeout_seconds = int(store_cfg.get('idle_timeout_seconds'))
            else:
                idle_timeout_seconds = int(store_cfg.get('ttl_seconds', 43200))
        except (TypeError, ValueError):
            idle_timeout_seconds = 43200
        idle_timeout_seconds = max(1, idle_timeout_seconds)

        try:
            lock_ttl_seconds = int(store_cfg.get('lock_ttl_seconds', 10))
        except (TypeError, ValueError):
            lock_ttl_seconds = 10

        # Keep lock TTL longer than the Dify request window to avoid early lock expiration.
        request_timeout_seconds = 120
        lock_ttl_floor = request_timeout_seconds + 10
        lock_ttl_seconds = max(1, lock_ttl_seconds, lock_ttl_floor)

        try:
            contention_wait_retry_count = int(store_cfg.get('contention_wait_retry_count', 15))
        except (TypeError, ValueError):
            contention_wait_retry_count = 15
        contention_wait_retry_count = max(1, min(60, contention_wait_retry_count))

        try:
            contention_wait_interval_ms = int(store_cfg.get('contention_wait_interval_ms', 500))
        except (TypeError, ValueError):
            contention_wait_interval_ms = 500
        contention_wait_interval_ms = max(50, min(2000, contention_wait_interval_ms))

        return {
            'enabled': enabled,
            'idle_timeout_seconds': idle_timeout_seconds,
            # Keep compatibility for legacy call sites and diagnostics.
            'ttl_seconds': idle_timeout_seconds,
            'lock_ttl_seconds': lock_ttl_seconds,
            'contention_wait_retry_count': contention_wait_retry_count,
            'contention_wait_interval_ms': contention_wait_interval_ms,
        }

    def _get_conversation_store(self) -> DifyConversationStore | None:
        if self._conversation_store_initialized:
            return self._conversation_store

        cfg = self._resolve_conversation_store_config()

        if not cfg['enabled']:
            self._conversation_store_initialized = True
            return None

        redis_mgr = getattr(self.ap, 'redis_mgr', None)
        if redis_mgr is None:
            return None

        self._conversation_store = DifyConversationStore(
            redis_mgr=redis_mgr,
            idle_timeout_seconds=cfg['idle_timeout_seconds'],
            lock_ttl_seconds=cfg['lock_ttl_seconds'],
            enabled=cfg['enabled'],
        )
        self._conversation_store_initialized = True

        return self._conversation_store

    @staticmethod
    def _extract_conversation_id_from_chunk(chunk: typing.Any) -> str | None:
        if not isinstance(chunk, dict):
            return None
        conversation_id = chunk.get('conversation_id')
        if isinstance(conversation_id, str) and conversation_id.strip():
            return conversation_id
        return None

    @staticmethod
    def _normalize_launcher_type(launcher_type: typing.Any) -> str:
        if hasattr(launcher_type, 'value'):
            return str(launcher_type.value)
        return str(launcher_type)

    def _get_conversation_scope(self, query: pipeline_query.Query) -> tuple[str, str, str, str] | None:
        session = getattr(query, 'session', None)
        using_conversation = getattr(session, 'using_conversation', None)

        bot_uuid = getattr(query, 'bot_uuid', None) or getattr(using_conversation, 'bot_uuid', None)
        pipeline_uuid = getattr(query, 'pipeline_uuid', None) or getattr(using_conversation, 'pipeline_uuid', None)
        launcher_type = getattr(session, 'launcher_type', None) or getattr(query, 'launcher_type', None)
        launcher_id = getattr(session, 'launcher_id', None) or getattr(query, 'launcher_id', None)

        if not bot_uuid or not pipeline_uuid or launcher_type is None or launcher_id is None:
            return None

        return (
            str(bot_uuid),
            str(pipeline_uuid),
            self._normalize_launcher_type(launcher_type),
            str(launcher_id),
        )

    @staticmethod
    def _current_unix_timestamp() -> int:
        return int(time.time())

    @classmethod
    def _get_runtime_binding_metadata(cls, using_conversation: typing.Any) -> typing.Any:
        if using_conversation is None:
            return None
        metadata = getattr(using_conversation, cls._RUNTIME_BINDING_ATTR, None)
        if metadata is not None:
            return metadata

        conversation_dict = getattr(using_conversation, '__dict__', None)
        if isinstance(conversation_dict, dict):
            return conversation_dict.get(cls._RUNTIME_BINDING_ATTR)
        return None

    @classmethod
    def _set_runtime_binding_metadata(cls, using_conversation: typing.Any, metadata: dict | None):
        if using_conversation is None:
            return

        try:
            setattr(using_conversation, cls._RUNTIME_BINDING_ATTR, metadata)
            return
        except Exception:
            pass

        conversation_dict = getattr(using_conversation, '__dict__', None)
        if isinstance(conversation_dict, dict):
            if metadata is None:
                conversation_dict.pop(cls._RUNTIME_BINDING_ATTR, None)
            else:
                conversation_dict[cls._RUNTIME_BINDING_ATTR] = metadata

    def _normalize_runtime_conversation_binding(self, query: pipeline_query.Query) -> dict | None:
        session = getattr(query, 'session', None)
        using_conversation = getattr(session, 'using_conversation', None)
        if using_conversation is None:
            return None

        runtime_uuid = getattr(using_conversation, 'uuid', None)
        if not isinstance(runtime_uuid, str) or not runtime_uuid.strip():
            return None
        runtime_uuid = runtime_uuid.strip()

        metadata = self._get_runtime_binding_metadata(using_conversation)
        if not isinstance(metadata, dict):
            return None

        metadata_uuid = metadata.get('uuid')
        if not isinstance(metadata_uuid, str) or not metadata_uuid.strip():
            return None

        payload = {
            'conversation_id': metadata_uuid,
            'created_at': metadata.get('created_at'),
            'last_active_at': metadata.get('last_active_at'),
            'policy_version': metadata.get('policy_version'),
        }
        normalized_binding = normalize_binding_payload(payload)
        if normalized_binding is None:
            return None
        if normalized_binding['conversation_id'] != runtime_uuid:
            return None
        return normalized_binding

    @staticmethod
    def _normalize_store_binding_payload(payload: typing.Any) -> dict | None:
        if not isinstance(payload, dict):
            return None

        if 'conversation_id' not in payload and isinstance(payload.get('uuid'), str):
            payload = {
                'conversation_id': payload.get('uuid'),
                'created_at': payload.get('created_at'),
                'last_active_at': payload.get('last_active_at'),
                'policy_version': payload.get('policy_version'),
            }

        return normalize_binding_payload(payload)

    def _is_binding_expired(self, binding: dict | None) -> bool:
        if not isinstance(binding, dict):
            return True

        cfg = self._resolve_conversation_store_config()
        return is_binding_expired(
            binding,
            now_ts=self._current_unix_timestamp(),
            idle_timeout_seconds=int(cfg.get('idle_timeout_seconds', 43200)),
        )

    def _set_runtime_conversation_binding(self, query: pipeline_query.Query, binding: dict | None):
        session = getattr(query, 'session', None)
        using_conversation = getattr(session, 'using_conversation', None)
        if using_conversation is None:
            return

        if binding is None:
            using_conversation.uuid = None
            self._set_runtime_binding_metadata(using_conversation, None)
            return

        using_conversation.uuid = binding['conversation_id']
        self._set_runtime_binding_metadata(
            using_conversation,
            {
                'uuid': binding['conversation_id'],
                'created_at': binding['created_at'],
                'last_active_at': binding['last_active_at'],
                'policy_version': binding['policy_version'],
            },
        )

    async def _get_binding_from_store(
        self,
        store: DifyConversationStore,
        scope: tuple[str, str, str, str],
    ) -> dict | None:
        if hasattr(store, 'get_conversation_binding'):
            binding_payload = await store.get_conversation_binding(*scope)
            normalized_binding = self._normalize_store_binding_payload(binding_payload)
            if binding_payload is not None and normalized_binding is None:
                self.ap.logger.warning('dify conversation restore skipped malformed store binding payload')
            return normalized_binding

        # Compatibility fallback for tests/legacy mocks that still expose id-only APIs.
        if hasattr(store, 'get_conversation_id'):
            conversation_id = await store.get_conversation_id(*scope)
            if not isinstance(conversation_id, str) or not conversation_id.strip():
                return None
            now_ts = self._current_unix_timestamp()
            return {
                'conversation_id': conversation_id.strip(),
                'created_at': now_ts,
                'last_active_at': now_ts,
                'policy_version': 1,
            }

        return None

    async def _set_binding_to_store(
        self,
        store: DifyConversationStore,
        scope: tuple[str, str, str, str],
        conversation_id: str,
        now_ts: int,
        created_at: int,
    ):
        if hasattr(store, 'set_conversation_binding'):
            await store.set_conversation_binding(
                *scope,
                conversation_id,
                now_ts=now_ts,
                created_at=created_at,
            )
            return

        # Compatibility fallback for tests/legacy mocks that still expose id-only APIs.
        if hasattr(store, 'set_conversation_id'):
            await store.set_conversation_id(*scope, conversation_id)

    async def _delete_binding_from_store(
        self,
        store: DifyConversationStore,
        scope: tuple[str, str, str, str],
    ):
        if hasattr(store, 'delete_conversation_binding'):
            await store.delete_conversation_binding(*scope)
            return

        # Compatibility fallback for tests/legacy mocks that still expose id-only APIs.
        if hasattr(store, 'delete_conversation_id'):
            await store.delete_conversation_id(*scope)

    @staticmethod
    def _is_invalid_conversation_error(exc: Exception) -> bool:
        text_candidates: list[str] = []
        message_attr = getattr(exc, 'message', None)
        if isinstance(message_attr, str):
            text_candidates.append(message_attr)

        exc_text = str(exc)
        if isinstance(exc_text, str) and exc_text:
            text_candidates.append(exc_text)

        if not text_candidates:
            return False

        normalized_text = ' '.join(text_candidates).lower()
        if 'conversation' not in normalized_text:
            return False

        invalid_markers = (
            'conversation_not_found',
            'invalid_conversation',
            'invalid conversation',
            'conversation not found',
            'conversation does not exist',
            'conversation not exist',
        )
        return any(marker in normalized_text for marker in invalid_markers)

    async def _clear_conversation_binding_after_invalid_conversation_error(self, query: pipeline_query.Query):
        # Fail closed: runtime binding must be cleared before retrying without stale conversation_id.
        self._set_runtime_conversation_binding(query, None)

        store = self._get_conversation_store()
        scope = self._get_conversation_scope(query)
        if store is None or scope is None:
            return

        try:
            await self._delete_binding_from_store(store, scope)
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation clear persisted binding failed: {exc}')

    async def _chat_messages_with_invalid_conversation_retry(
        self,
        query: pipeline_query.Query,
        *,
        inputs: dict[str, typing.Any],
        plain_text: str,
        files: list[dict[str, typing.Any]],
        conversation_id: str | None,
        response_mode: str | None = None,
        timeout: int = 120,
        retry_lock_owner_holder: list[str | None] | None = None,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        active_conversation_id = conversation_id
        retried = False

        while True:
            query.variables['conversation_id'] = active_conversation_id
            inputs['conversation_id'] = active_conversation_id
            request_kwargs: dict[str, typing.Any] = {
                'inputs': inputs,
                'query': plain_text,
                'user': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                'conversation_id': active_conversation_id,
                'files': files,
                'timeout': timeout,
            }
            if response_mode is not None:
                request_kwargs['response_mode'] = response_mode

            emitted_any_chunk = False
            try:
                async for chunk in self.dify_client.chat_messages(**request_kwargs):
                    emitted_any_chunk = True
                    yield chunk
                return
            except Exception as exc:
                should_retry = (
                    not retried
                    and not emitted_any_chunk
                    and isinstance(active_conversation_id, str)
                    and active_conversation_id.strip() != ''
                    and self._is_invalid_conversation_error(exc)
                )
                if not should_retry:
                    raise

                self.ap.logger.warning(
                    'dify conversation rejected by upstream, clear stale binding and retry once after re-resolving scope lock'
                )
                await self._clear_conversation_binding_after_invalid_conversation_error(query)
                restored_conversation_id, retry_lock_owner = await self._restore_conversation_id_if_needed(query)
                if retry_lock_owner_holder is not None:
                    retry_lock_owner_holder[0] = retry_lock_owner
                active_conversation_id = restored_conversation_id or ''
                retried = True

    async def _restore_conversation_id_if_needed(self, query: pipeline_query.Query) -> tuple[str | None, str | None]:
        session = getattr(query, 'session', None)
        using_conversation = getattr(session, 'using_conversation', None)
        if using_conversation is None:
            return None, None

        current_runtime_uuid = getattr(using_conversation, 'uuid', None)
        if not isinstance(current_runtime_uuid, str) or not current_runtime_uuid.strip():
            current_runtime_uuid = None
        else:
            current_runtime_uuid = current_runtime_uuid.strip()

        runtime_binding = self._normalize_runtime_conversation_binding(query)
        if runtime_binding and not self._is_binding_expired(runtime_binding):
            self._set_runtime_conversation_binding(query, runtime_binding)
            return runtime_binding['conversation_id'], None

        # Expired/invalid runtime metadata should not remain authoritative.
        if runtime_binding is not None:
            self._set_runtime_conversation_binding(query, None)

        # Runtime UUID without metadata is treated as legacy authority until trusted replacement is found.
        legacy_runtime_uuid = current_runtime_uuid if runtime_binding is None else None

        store = self._get_conversation_store()
        scope = self._get_conversation_scope(query)
        if store is None or scope is None:
            return legacy_runtime_uuid, None

        try:
            restored_binding = await self._get_binding_from_store(store, scope)
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation restore failed: {exc}')
            return legacy_runtime_uuid, None

        if restored_binding and not self._is_binding_expired(restored_binding):
            if legacy_runtime_uuid and restored_binding['conversation_id'] != legacy_runtime_uuid:
                return legacy_runtime_uuid, None
            self._set_runtime_conversation_binding(query, restored_binding)
            return restored_binding['conversation_id'], None

        if legacy_runtime_uuid:
            return legacy_runtime_uuid, None

        try:
            lock_owner = await store.acquire_lock(*scope)
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation lock acquire failed: {exc}')
            return None, None

        if not lock_owner:
            cfg = self._resolve_conversation_store_config()
            retry_count = int(cfg.get('contention_wait_retry_count', 15))
            wait_interval_seconds = int(cfg.get('contention_wait_interval_ms', 500)) / 1000.0

            for _ in range(retry_count):
                await asyncio.sleep(wait_interval_seconds)
                try:
                    restored_binding = await self._get_binding_from_store(store, scope)
                except Exception as exc:
                    self.ap.logger.warning(f'dify conversation contention re-check failed: {exc}')
                    continue

                if restored_binding and not self._is_binding_expired(restored_binding):
                    self._set_runtime_conversation_binding(query, restored_binding)
                    return restored_binding['conversation_id'], None

            self.ap.logger.warning(
                'dify conversation lock contention unresolved after bounded wait, continue without restored conversation id'
            )
            return None, None

        try:
            restored_binding = await self._get_binding_from_store(store, scope)
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation restore re-check failed: {exc}')
            restored_binding = None

        if restored_binding and not self._is_binding_expired(restored_binding):
            self._set_runtime_conversation_binding(query, restored_binding)
            try:
                await store.release_lock(*scope, lock_owner)
            except Exception as exc:
                self.ap.logger.warning(f'dify conversation lock release failed: {exc}')
            return restored_binding['conversation_id'], None

        return None, lock_owner

    async def _release_conversation_lock(self, query: pipeline_query.Query, lock_owner: str | None):
        if not lock_owner:
            return

        store = self._get_conversation_store()
        scope = self._get_conversation_scope(query)
        if store is None or scope is None:
            return

        try:
            await store.release_lock(*scope, lock_owner)
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation lock release failed: {exc}')

    async def _persist_conversation_id(self, query: pipeline_query.Query, conversation_id: str | None):
        if not conversation_id:
            return

        now_ts = self._current_unix_timestamp()
        existing_runtime_binding = self._normalize_runtime_conversation_binding(query)
        created_at = now_ts
        if (
            existing_runtime_binding is not None
            and existing_runtime_binding['conversation_id'] == conversation_id
        ):
            created_at = existing_runtime_binding['created_at']

        runtime_binding = {
            'conversation_id': conversation_id,
            'created_at': created_at,
            'last_active_at': now_ts,
            'policy_version': self._RUNTIME_POLICY_VERSION,
        }
        self._set_runtime_conversation_binding(query, runtime_binding)

        store = self._get_conversation_store()
        scope = self._get_conversation_scope(query)
        if store is None or scope is None:
            return

        try:
            await self._set_binding_to_store(
                store,
                scope,
                conversation_id=conversation_id,
                now_ts=now_ts,
                created_at=created_at,
            )
        except Exception as exc:
            self.ap.logger.warning(f'dify conversation persist failed: {exc}')

    def _process_thinking_content(
        self,
        content: str,
    ) -> tuple[str, str]:
        """处理思维链内容

        Args:
            content: 原始内容
        Returns:
            (处理后的内容, 提取的思维链内容)
        """
        remove_think = self._is_remove_think_enabled()
        thinking_content = ''
        # 从 content 中提取 <think> 标签内容
        if content and '<think>' in content and '</think>' in content:
            import re

            think_pattern = r'<think>(.*?)</think>'
            think_matches = re.findall(think_pattern, content, re.DOTALL)
            if think_matches:
                thinking_content = '\n'.join(think_matches)
                # 移除 content 中的 <think> 标签
                content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()

        # 3. 根据 remove_think 参数决定是否保留思维链
        if remove_think:
            return content, ''
        else:
            # 如果有思维链内容，将其以 <think> 格式添加到 content 开头
            if thinking_content:
                content = f'<think>\n{thinking_content}\n</think>\n{content}'.strip()
            return content, thinking_content

    def _extract_dify_text_output(self, value: typing.Any) -> str:
        """Extract text content from Dify output payload."""
        if value is None:
            return ''
        if isinstance(value, dict):
            content = value.get('content')
            if isinstance(content, str):
                return content
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ''
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return value
            if isinstance(parsed, dict) and isinstance(parsed.get('content'), str):
                return parsed['content']
            return value
        return str(value)

    @staticmethod
    def _get_stream_chunk_batch_size(query: pipeline_query.Query) -> int:
        pipeline_config = getattr(query, 'pipeline_config', {}) or {}
        output_config = pipeline_config.get('output', {}) or {}
        dify_stream_config = output_config.get('dify-stream', {}) or {}
        value = dify_stream_config.get('chunk-batch-size', 8)

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 8
        return max(1, min(20, value))

    @staticmethod
    def _get_stream_flush_window_ms(query: pipeline_query.Query) -> int:
        pipeline_config = getattr(query, 'pipeline_config', {}) or {}
        output_config = pipeline_config.get('output', {}) or {}
        dify_stream_config = output_config.get('dify-stream', {}) or {}
        value = dify_stream_config.get('flush-window-ms', 2000)

        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 2000
        return max(200, min(10000, value))

    @staticmethod
    def _is_stream_flush_window_enabled(query: pipeline_query.Query) -> bool:
        pipeline_config = getattr(query, 'pipeline_config', {}) or {}
        output_config = pipeline_config.get('output', {}) or {}
        dify_stream_config = output_config.get('dify-stream', {}) or {}
        return DifyServiceAPIRunner._parse_bool_config(dify_stream_config.get('flush-window-enabled', False), False)

    @staticmethod
    def _should_emit_stream_snapshot(
        content: str,
        is_final: bool,
        pending_chunk_count: int,
        chunk_batch_size: int,
        flush_window_enabled: bool,
        flush_window_ms: int,
        last_emitted_content: str,
        last_emit_at: float,
    ) -> bool:
        if is_final:
            return True

        if not content or content == last_emitted_content:
            return False

        if last_emitted_content == '':
            return True

        if pending_chunk_count >= chunk_batch_size:
            return True

        if not flush_window_enabled:
            return False

        elapsed_ms = (time.monotonic() - last_emit_at) * 1000
        return elapsed_ms >= flush_window_ms

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[dict]]:
        """预处理用户消息，提取纯文本，并将图片/文件上传到 Dify 服务

        Returns:
            tuple[str, list[dict]]: 纯文本和上传后的文件描述（包含 type 与 id）
        """
        plain_text = ''
        upload_files: list[dict] = []
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        async def upload_file_bytes(file_name: str, file_bytes: bytes, content_type: str) -> str:
            file_name = file_name or 'file'
            content_type = content_type or 'application/octet-stream'
            file = (file_name, file_bytes, content_type)
            resp = await self.dify_client.upload_file(file, user_tag)
            return resp['id']

        async def download_file(file_url: str) -> tuple[bytes, str]:
            """Download file from url (supports data url)."""

            async with httpx.AsyncClient() as client_session:
                resp = await client_session.get(file_url)
                resp.raise_for_status()
                content_type = (
                    resp.headers.get('content-type') or mimetypes.guess_type(file_url)[0] or 'application/octet-stream'
                )
                return resp.content, content_type

        def _detect_file_type(content_type: str) -> str:
            """Map MIME to dify file type."""
            if content_type and content_type.startswith('image/'):
                return 'image'
            if content_type and content_type.startswith('audio/'):
                return 'audio'
            if content_type and content_type.startswith('video/'):
                return 'video'
            return 'document'

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    file_bytes = base64.b64decode(image_b64)
                    image_id = await upload_file_bytes(f'img.{image_format}', file_bytes, f'image/{image_format}')
                    upload_files.append({'type': 'image', 'id': image_id})
                elif ce.type == 'file_url':
                    file_url = getattr(ce, 'file_url', None)
                    file_name = getattr(ce, 'file_name', None) or 'file'
                    try:
                        file_bytes, content_type = await download_file(file_url)
                        file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                        file_type = _detect_file_type(content_type)
                        upload_files.append({'type': file_type, 'id': file_id})
                    except Exception as e:
                        self.ap.logger.warning(f'dify file upload failed: {e}')
                elif ce.type == 'file_base64':
                    file_name = getattr(ce, 'file_name', None) or 'file'

                    header, b64_data = ce.file_base64.split(',', 1)
                    content_type = 'application/octet-stream'
                    if ';' in header:
                        content_type = header.split(';')[0][5:] or content_type
                    file_bytes = base64.b64decode(b64_data)
                    file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                    file_type = _detect_file_type(content_type)
                    upload_files.append({'type': file_type, 'id': file_id})

        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        plain_text = plain_text if plain_text else self.pipeline_config['ai']['dify-service-api']['base-prompt']

        return plain_text, upload_files

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)
        retry_lock_owner_holder = [None]
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        mode = 'basic'  # 标记是基础编排还是工作流编排

        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        try:
            async for chunk in self._chat_messages_with_invalid_conversation_retry(
                query,
                inputs=inputs,
                plain_text=plain_text,
                files=files,
                conversation_id=cov_id,
                timeout=120,
                retry_lock_owner_holder=retry_lock_owner_holder,
            ):
                self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

                if chunk['event'] == 'workflow_started':
                    mode = 'workflow'

                if mode == 'workflow':
                    if chunk['event'] == 'node_finished':
                        if chunk['data']['node_type'] == 'answer':
                            answer = self._extract_dify_text_output(chunk['data']['outputs'].get('answer'))
                            content, _ = self._process_thinking_content(answer)

                            yield provider_message.Message(
                                role='assistant',
                                content=content,
                            )
                elif mode == 'basic':
                    if chunk['event'] == 'message':
                        basic_mode_pending_chunk += chunk['answer']
                    elif chunk['event'] == 'message_end':
                        content, _ = self._process_thinking_content(basic_mode_pending_chunk)
                        yield provider_message.Message(
                            role='assistant',
                            content=content,
                        )
                        basic_mode_pending_chunk = ''

            if chunk is None:
                raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')
            final_conversation_id = self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
            await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)
            await self._release_conversation_lock(query, retry_lock_owner_holder[0])

    async def _agent_chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)
        retry_lock_owner_holder = [None]
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = []

        inputs = {}

        inputs.update(query.variables)

        pending_agent_message = ''

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        try:
            async for chunk in self._chat_messages_with_invalid_conversation_retry(
                query,
                inputs=inputs,
                plain_text=plain_text,
                files=files,
                conversation_id=cov_id,
                response_mode='streaming',
                timeout=120,
                retry_lock_owner_holder=retry_lock_owner_holder,
            ):
                self.ap.logger.debug('dify-agent-chunk: ' + str(chunk))

                if chunk['event'] in ignored_events:
                    continue

                if chunk['event'] == 'agent_message' or chunk['event'] == 'message':
                    pending_agent_message += chunk['answer']
                else:
                    if pending_agent_message.strip() != '':
                        pending_agent_message = pending_agent_message.replace('</details>Action:', '</details>')
                        content, _ = self._process_thinking_content(pending_agent_message)
                        yield provider_message.Message(
                            role='assistant',
                            content=content,
                        )
                    pending_agent_message = ''

                    if chunk['event'] == 'agent_thought':
                        if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                            continue

                        if chunk['tool']:
                            msg = provider_message.Message(
                                role='assistant',
                                tool_calls=[
                                    provider_message.ToolCall(
                                        id=chunk['id'],
                                        type='function',
                                        function=provider_message.FunctionCall(
                                            name=chunk['tool'],
                                            arguments=json.dumps({}),
                                        ),
                                    )
                                ],
                            )
                            yield msg
                    if chunk['event'] == 'message_file':
                        if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                            # 检查URL是否已经是完整的连接
                            if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                                image_url = chunk['url']
                            else:
                                base_url = self.dify_client.base_url

                                if base_url.endswith('/v1'):
                                    base_url = base_url[:-3]

                                image_url = base_url + chunk['url']

                            yield provider_message.Message(
                                role='assistant',
                                content=[provider_message.ContentElement.from_image_url(image_url)],
                            )
                    if chunk['event'] == 'error':
                        raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])

            if chunk is None:
                raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')
            final_conversation_id = self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
            await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)
            await self._release_conversation_lock(query, retry_lock_owner_holder[0])

    async def _workflow_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用工作流"""

        _, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = ['text_chunk', 'workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)

        chunk = None
        workflow_succeeded = False

        try:
            async for chunk in self.dify_client.workflow_run(
                inputs=inputs,
                user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                files=files,
                timeout=120,
            ):
                self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
                if chunk['event'] in ignored_events:
                    continue

                if chunk['event'] == 'node_started':
                    if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                        continue

                    msg = provider_message.Message(
                        role='assistant',
                        content=None,
                        tool_calls=[
                            provider_message.ToolCall(
                                id=chunk['data']['node_id'],
                                type='function',
                                function=provider_message.FunctionCall(
                                    name=chunk['data']['title'],
                                    arguments=json.dumps({}),
                                ),
                            )
                        ],
                    )

                    yield msg

                elif chunk['event'] == 'workflow_finished':
                    if chunk['data']['error']:
                        raise errors.DifyAPIError(chunk['data']['error'])
                    workflow_succeeded = True
                    content, _ = self._process_thinking_content(chunk['data']['outputs']['summary'])

                    msg = provider_message.Message(
                        role='assistant',
                        content=content,
                    )

                    yield msg

            if workflow_succeeded:
                final_conversation_id = (
                    self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
                )
                await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)

    async def _chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)
        retry_lock_owner_holder = [None]
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        mode = 'basic'
        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)
        message_idx = 0

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        is_final = False
        stream_completed = False
        final_snapshot_emitted = False
        think_start = False
        think_end = False
        last_emitted_content = ''
        pending_chunk_count = 0
        last_emit_at = time.monotonic()

        remove_think = self._is_remove_think_enabled()
        chunk_batch_size = self._get_stream_chunk_batch_size(query)
        flush_window_enabled = self._is_stream_flush_window_enabled(query)
        flush_window_ms = self._get_stream_flush_window_ms(query)

        try:
            async for chunk in self._chat_messages_with_invalid_conversation_retry(
                query,
                inputs=inputs,
                plain_text=plain_text,
                files=files,
                conversation_id=cov_id,
                timeout=120,
                retry_lock_owner_holder=retry_lock_owner_holder,
            ):
                self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

                if chunk['event'] == 'workflow_started':
                    mode = 'workflow'
                elif chunk['event'] in ('node_started', 'node_finished', 'workflow_finished'):
                    # Some Dify deployments may omit workflow_started in streamed chunks.
                    mode = 'workflow'

                if chunk['event'] == 'message':
                    answer = chunk.get('answer', '')
                    if answer != '':
                        message_idx += 1
                        pending_chunk_count += 1
                        if remove_think:
                            if '<think>' in answer and not think_start:
                                think_start = True
                                continue
                            if '</think>' in answer and not think_end:
                                import re

                                content = re.sub(r'^\n</think>', '', answer)
                                basic_mode_pending_chunk += content
                                think_end = True
                            elif think_end:
                                basic_mode_pending_chunk += answer
                            if think_start:
                                continue

                        else:
                            basic_mode_pending_chunk += answer

                if chunk['event'] == 'message_end':
                    is_final = True
                    stream_completed = True
                elif chunk['event'] == 'workflow_finished':
                    is_final = True
                    stream_completed = True
                    if chunk['data'].get('error'):
                        raise errors.DifyAPIError(chunk['data']['error'])

                if mode == 'workflow' and chunk['event'] == 'node_finished':
                    if chunk['data'].get('node_type') == 'answer':
                        answer = self._extract_dify_text_output(chunk['data'].get('outputs', {}).get('answer'))
                        if answer:
                            basic_mode_pending_chunk = answer

                if final_snapshot_emitted and is_final:
                    continue

                if self._should_emit_stream_snapshot(
                    content=basic_mode_pending_chunk,
                    is_final=is_final,
                    pending_chunk_count=pending_chunk_count,
                    chunk_batch_size=chunk_batch_size,
                    flush_window_enabled=flush_window_enabled,
                    flush_window_ms=flush_window_ms,
                    last_emitted_content=last_emitted_content,
                    last_emit_at=last_emit_at,
                ):
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=basic_mode_pending_chunk,
                        is_final=is_final,
                    )
                    if is_final:
                        final_snapshot_emitted = True
                    last_emitted_content = basic_mode_pending_chunk
                    pending_chunk_count = 0
                    last_emit_at = time.monotonic()

            if chunk is None:
                raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

            if stream_completed and not final_snapshot_emitted:
                final_content = basic_mode_pending_chunk or last_emitted_content
                if final_content:
                    self.ap.logger.debug('dify-chat-stream: emit final snapshot fallback')
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=final_content,
                        is_final=True,
                    )

            final_conversation_id = (
                self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
            )
            await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)
            await self._release_conversation_lock(query, retry_lock_owner_holder[0])

    async def _agent_chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)
        retry_lock_owner_holder = [None]
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = []

        inputs = {}

        inputs.update(query.variables)

        pending_agent_message = ''

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误
        message_idx = 0
        is_final = False
        stream_completed = False
        final_snapshot_emitted = False
        think_start = False
        think_end = False
        last_emitted_content = ''
        pending_chunk_count = 0
        last_emit_at = time.monotonic()

        remove_think = self._is_remove_think_enabled()
        chunk_batch_size = self._get_stream_chunk_batch_size(query)
        flush_window_enabled = self._is_stream_flush_window_enabled(query)
        flush_window_ms = self._get_stream_flush_window_ms(query)

        try:
            async for chunk in self._chat_messages_with_invalid_conversation_retry(
                query,
                inputs=inputs,
                plain_text=plain_text,
                files=files,
                conversation_id=cov_id,
                response_mode='streaming',
                timeout=120,
                retry_lock_owner_holder=retry_lock_owner_holder,
            ):
                self.ap.logger.debug('dify-agent-chunk: ' + str(chunk))

                if chunk['event'] in ignored_events:
                    continue

                if chunk['event'] == 'agent_message':
                    answer = chunk.get('answer', '')
                    if answer != '':
                        message_idx += 1
                        pending_chunk_count += 1
                        if remove_think:
                            if '<think>' in answer and not think_start:
                                think_start = True
                                continue
                            if '</think>' in answer and not think_end:
                                import re

                                content = re.sub(r'^\n</think>', '', answer)
                                pending_agent_message += content
                                think_end = True
                            elif think_end or not think_start:
                                pending_agent_message += answer
                            if think_start and not think_end:
                                continue

                        else:
                            pending_agent_message += answer
                elif chunk['event'] in ('message_end', 'workflow_finished'):
                    is_final = True
                    stream_completed = True
                else:
                    if chunk['event'] == 'agent_thought':
                        if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                            continue
                        message_idx += 1
                        if chunk['tool']:
                            msg = provider_message.MessageChunk(
                                role='assistant',
                                tool_calls=[
                                    provider_message.ToolCall(
                                        id=chunk['id'],
                                        type='function',
                                        function=provider_message.FunctionCall(
                                            name=chunk['tool'],
                                            arguments=json.dumps({}),
                                        ),
                                    )
                                ],
                            )
                            yield msg
                    if chunk['event'] == 'message_file':
                        message_idx += 1
                        if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                            # 检查URL是否已经是完整的连接
                            if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                                image_url = chunk['url']
                            else:
                                base_url = self.dify_client.base_url

                                if base_url.endswith('/v1'):
                                    base_url = base_url[:-3]

                                image_url = base_url + chunk['url']

                            yield provider_message.MessageChunk(
                                role='assistant',
                                content=[provider_message.ContentElement.from_image_url(image_url)],
                                is_final=is_final,
                            )

                    if chunk['event'] == 'error':
                        raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])
                if self._should_emit_stream_snapshot(
                    content=pending_agent_message,
                    is_final=is_final,
                    pending_chunk_count=pending_chunk_count,
                    chunk_batch_size=chunk_batch_size,
                    flush_window_enabled=flush_window_enabled,
                    flush_window_ms=flush_window_ms,
                    last_emitted_content=last_emitted_content,
                    last_emit_at=last_emit_at,
                ):
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=pending_agent_message,
                        is_final=is_final,
                    )
                    if is_final:
                        final_snapshot_emitted = True
                    last_emitted_content = pending_agent_message
                    pending_chunk_count = 0
                    last_emit_at = time.monotonic()

            if chunk is None:
                raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

            if stream_completed and not final_snapshot_emitted:
                final_content = pending_agent_message or last_emitted_content
                if final_content:
                    self.ap.logger.debug('dify-agent-stream: emit final snapshot fallback')
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=final_content,
                        is_final=True,
                    )

            final_conversation_id = (
                self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
            )
            await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)
            await self._release_conversation_lock(query, retry_lock_owner_holder[0])

    async def _workflow_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用工作流"""

        _, conversation_lock_owner = await self._restore_conversation_id_if_needed(query)

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = ['workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)
        messsage_idx = 0
        is_final = False
        stream_completed = False
        final_snapshot_emitted = False
        think_start = False
        think_end = False
        workflow_contents = ''
        last_emitted_content = ''
        pending_chunk_count = 0
        last_emit_at = time.monotonic()

        remove_think = self._is_remove_think_enabled()
        chunk_batch_size = self._get_stream_chunk_batch_size(query)
        flush_window_enabled = self._is_stream_flush_window_enabled(query)
        flush_window_ms = self._get_stream_flush_window_ms(query)
        chunk = None

        try:
            async for chunk in self.dify_client.workflow_run(
                inputs=inputs,
                user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                files=files,
                timeout=120,
            ):
                self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
                if chunk['event'] in ignored_events:
                    continue
                if chunk['event'] == 'workflow_finished':
                    is_final = True
                    stream_completed = True
                    if chunk['data']['error']:
                        raise errors.DifyAPIError(chunk['data']['error'])

                if chunk['event'] == 'text_chunk':
                    text = chunk['data'].get('text', '')
                    if text != '':
                        messsage_idx += 1
                        pending_chunk_count += 1
                        if remove_think:
                            if '<think>' in text and not think_start:
                                think_start = True
                                continue
                            if '</think>' in text and not think_end:
                                import re

                                content = re.sub(r'^\n</think>', '', text)
                                workflow_contents += content
                                think_end = True
                            elif think_end:
                                workflow_contents += text
                            if think_start:
                                continue

                        else:
                            workflow_contents += text

                if chunk['event'] == 'node_started':
                    if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                        continue
                    messsage_idx += 1
                    msg = provider_message.MessageChunk(
                        role='assistant',
                        content=None,
                        tool_calls=[
                            provider_message.ToolCall(
                                id=chunk['data']['node_id'],
                                type='function',
                                function=provider_message.FunctionCall(
                                    name=chunk['data']['title'],
                                    arguments=json.dumps({}),
                                ),
                            )
                        ],
                    )

                    yield msg

                if self._should_emit_stream_snapshot(
                    content=workflow_contents,
                    is_final=is_final,
                    pending_chunk_count=pending_chunk_count,
                    chunk_batch_size=chunk_batch_size,
                    flush_window_enabled=flush_window_enabled,
                    flush_window_ms=flush_window_ms,
                    last_emitted_content=last_emitted_content,
                    last_emit_at=last_emit_at,
                ):
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=workflow_contents,
                        is_final=is_final,
                    )
                    if is_final:
                        final_snapshot_emitted = True
                    last_emitted_content = workflow_contents
                    pending_chunk_count = 0
                    last_emit_at = time.monotonic()

            if stream_completed and not final_snapshot_emitted:
                final_content = workflow_contents or last_emitted_content
                if final_content:
                    self.ap.logger.debug('dify-workflow-stream: emit final snapshot fallback')
                    yield provider_message.MessageChunk(
                        role='assistant',
                        content=final_content,
                        is_final=True,
                    )

            if stream_completed:
                final_conversation_id = (
                    self._extract_conversation_id_from_chunk(chunk) or query.session.using_conversation.uuid
                )
                await self._persist_conversation_id(query, final_conversation_id)
        finally:
            await self._release_conversation_lock(query, conversation_lock_owner)

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行请求"""
        if await query.adapter.is_stream_output_supported():
            msg_idx = 0
            if self.pipeline_config['ai']['dify-service-api']['app-type'] == 'chat':
                async for msg in self._chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
                async for msg in self._agent_chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
                async for msg in self._workflow_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            else:
                raise errors.DifyAPIError(
                    f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
                )
        else:
            if self.pipeline_config['ai']['dify-service-api']['app-type'] == 'chat':
                async for msg in self._chat_messages(query):
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
                async for msg in self._agent_chat_messages(query):
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
                async for msg in self._workflow_messages(query):
                    yield msg
            else:
                raise errors.DifyAPIError(
                    f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
                )
