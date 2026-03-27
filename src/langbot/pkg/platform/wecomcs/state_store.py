from __future__ import annotations

import json
import logging

from .cursor_store import WecomCSCursorStore
from .message_state_store import WecomCSMessageStateStore


_logger = logging.getLogger("langbot")


class WecomCSStateStore:
    """企业微信客服调度状态存储。"""

    def __init__(
        self,
        redis_mgr,
        persistence_mgr = None,
        *,
        cursor_store: WecomCSCursorStore | None = None,
        message_state_ttl_seconds: int = 604800,
        cursor_bootstrap_mode: str = 'latest',
    ):
        self.redis_mgr = redis_mgr
        self.cursor_store = cursor_store or WecomCSCursorStore(persistence_mgr)
        self.message_state_store = WecomCSMessageStateStore(redis_mgr, ttl_seconds=message_state_ttl_seconds)
        self.cursor_bootstrap_mode = cursor_bootstrap_mode

    def _pull_lock_key(self, bot_uuid: str, open_kfid: str) -> str:
        return f"wecomcs:pull_lock:{bot_uuid}:{open_kfid}"

    def _cursor_fallback_key(self, bot_uuid: str, open_kfid: str) -> str:
        return f'wecomcs:cursor_checkpoint:{bot_uuid}:{open_kfid}'

    @staticmethod
    def _checkpoint_cursor(checkpoint) -> str:
        if checkpoint is None:
            return ''
        if isinstance(checkpoint, dict):
            return str(checkpoint.get('cursor', '') or '')
        return str(getattr(checkpoint, 'cursor', '') or '')

    @staticmethod
    def _checkpoint_bootstrapped(checkpoint) -> bool:
        if checkpoint is None:
            return False
        if isinstance(checkpoint, dict):
            return bool(checkpoint.get('bootstrapped', False))
        return bool(getattr(checkpoint, 'bootstrapped', False))

    async def _get_fallback_checkpoint(self, bot_uuid: str, open_kfid: str):
        if not self.redis_mgr or not self.redis_mgr.is_available():
            return None
        raw_value = await self.redis_mgr.get(self._cursor_fallback_key(bot_uuid, open_kfid))
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return None

    async def _save_fallback_checkpoint(self, bot_uuid: str, open_kfid: str, cursor: str, bootstrapped: bool):
        if not self.redis_mgr or not self.redis_mgr.is_available():
            return
        payload = {
            'bot_uuid': bot_uuid,
            'open_kfid': open_kfid,
            'cursor': cursor,
            'bootstrapped': bootstrapped,
        }
        await self.redis_mgr.set(self._cursor_fallback_key(bot_uuid, open_kfid), json.dumps(payload, ensure_ascii=False))


    def _cursor_store_available(self) -> bool:
        if self.cursor_store is None:
            return False
        if hasattr(self.cursor_store, 'is_available'):
            return bool(self.cursor_store.is_available())
        return True
    async def get_checkpoint(self, bot_uuid: str, open_kfid: str):
        if self._cursor_store_available():
            checkpoint = await self.cursor_store.get_checkpoint(bot_uuid, open_kfid)
            if checkpoint is not None:
                return checkpoint
        return await self._get_fallback_checkpoint(bot_uuid, open_kfid)

    async def get_cursor(self, bot_uuid: str, open_kfid: str) -> str:
        checkpoint = await self.get_checkpoint(bot_uuid, open_kfid)
        cursor = self._checkpoint_cursor(checkpoint)
        _logger.debug(f'[wecomcs][state] 读取cursor: bot_uuid={bot_uuid}, open_kfid={open_kfid}, cursor={cursor}')
        return cursor

    async def set_cursor(self, bot_uuid: str, open_kfid: str, cursor: str):
        if self._cursor_store_available():
            await self.cursor_store.save_checkpoint(bot_uuid, open_kfid, cursor, True)
        else:
            await self._save_fallback_checkpoint(bot_uuid, open_kfid, cursor, True)
        _logger.debug(f'[wecomcs][state] 更新cursor: bot_uuid={bot_uuid}, open_kfid={open_kfid}, cursor={cursor}')

    async def is_bootstrapped(self, bot_uuid: str, open_kfid: str) -> bool:
        checkpoint = await self.get_checkpoint(bot_uuid, open_kfid)
        return self._checkpoint_bootstrapped(checkpoint)

    async def mark_bootstrapped(self, bot_uuid: str, open_kfid: str, cursor: str):
        if self._cursor_store_available():
            await self.cursor_store.save_checkpoint(bot_uuid, open_kfid, cursor, True)
        else:
            await self._save_fallback_checkpoint(bot_uuid, open_kfid, cursor, True)
        _logger.debug(f'[wecomcs][state] 标记bootstrap完成: bot_uuid={bot_uuid}, open_kfid={open_kfid}, cursor={cursor}')

    async def clear_checkpoint(self, bot_uuid: str, open_kfid: str):
        if self._cursor_store_available() and hasattr(self.cursor_store, 'delete_checkpoint'):
            await self.cursor_store.delete_checkpoint(bot_uuid, open_kfid)
        else:
            if self.redis_mgr and self.redis_mgr.is_available():
                await self.redis_mgr.delete(self._cursor_fallback_key(bot_uuid, open_kfid))
        _logger.debug(f'[wecomcs][state] 清理cursor检查点: bot_uuid={bot_uuid}, open_kfid={open_kfid}')

    async def acquire_pull_lock(self, bot_uuid: str, open_kfid: str, owner: str, ttl_seconds: int) -> bool:
        if not self.redis_mgr or not self.redis_mgr.is_available():
            return False
        acquired = await self.redis_mgr.set_if_not_exists(
            self._pull_lock_key(bot_uuid, open_kfid),
            owner,
            ex=ttl_seconds,
        )
        _logger.debug(f'[wecomcs][state] 获取pull锁: bot_uuid={bot_uuid}, open_kfid={open_kfid}, owner={owner}, acquired={acquired}')
        return acquired

    async def release_pull_lock(self, bot_uuid: str, open_kfid: str, owner: str) -> bool:
        if not self.redis_mgr or not self.redis_mgr.is_available():
            return False
        lock_key = self._pull_lock_key(bot_uuid, open_kfid)
        current_owner = await self.redis_mgr.get(lock_key)
        if current_owner != owner:
            _logger.debug(f'[wecomcs][state] 释放pull锁失败(所有者不匹配): bot_uuid={bot_uuid}, open_kfid={open_kfid}, owner={owner}, current_owner={current_owner}')
            return False
        await self.redis_mgr.delete(lock_key)
        _logger.debug(f'[wecomcs][state] 释放pull锁成功: bot_uuid={bot_uuid}, open_kfid={open_kfid}, owner={owner}')
        return True

    async def get_message_state(self, bot_uuid: str, open_kfid: str, msgid: str) -> dict | None:
        return await self.message_state_store.get_state(bot_uuid, open_kfid, msgid)

    async def reserve_message_for_queue(self, bot_uuid: str, open_kfid: str, msg_data: dict) -> bool:
        return await self.message_state_store.reserve_for_queue(bot_uuid, open_kfid, msg_data)

    async def mark_message_processing(self, bot_uuid: str, open_kfid: str, msgid: str):
        await self.message_state_store.update_status(bot_uuid, open_kfid, msgid, process_status='processing')

    async def mark_message_done(self, bot_uuid: str, open_kfid: str, msgid: str):
        await self.message_state_store.update_status(bot_uuid, open_kfid, msgid, process_status='done', last_error_stage='', last_error='')

    async def mark_message_failed(self, bot_uuid: str, open_kfid: str, msgid: str, *, stage: str, error: str):
        await self.message_state_store.update_status(
            bot_uuid,
            open_kfid,
            msgid,
            process_status='failed',
            last_error_stage=stage,
            last_error=error,
        )

    async def mark_reply_success(self, bot_uuid: str, open_kfid: str, msgid: str):
        await self.message_state_store.update_status(bot_uuid, open_kfid, msgid, reply_status='success', last_error_stage='', last_error='')

    async def mark_reply_failed(self, bot_uuid: str, open_kfid: str, msgid: str, *, error: str):
        await self.message_state_store.update_status(
            bot_uuid,
            open_kfid,
            msgid,
            reply_status='failed',
            last_error_stage='reply_message',
            last_error=error,
        )

    async def mark_message_once(self, bot_uuid: str, msgid: str, ttl_seconds: int) -> bool:
        # 中文注释：保留旧接口兼容测试和旧逻辑，内部等价于直接写入已处理状态。
        if not self.redis_mgr or not self.redis_mgr.is_available():
            return False
        key = f'wecomcs:legacy_dedupe:{bot_uuid}:{msgid}'
        marked = await self.redis_mgr.set_if_not_exists(key, '1', ex=ttl_seconds)
        _logger.debug(f'[wecomcs][state] 兼容幂等标记: bot_uuid={bot_uuid}, msgid={msgid}, marked={marked}')
        return marked
