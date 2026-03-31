from __future__ import annotations

import uuid
import logging
from collections.abc import Awaitable, Callable

from langbot.libs.wecom_customer_service_api.api import WecomCSInvalidSyncMsgTokenError

from .state_store import WecomCSStateStore


_logger = logging.getLogger("langbot")


class PullLockNotAcquiredError(Exception):
    """Raised when pull lock is not acquired for an open_kfid."""


class WecomCSPullWorker:
    """企业微信客服第一层拉取 worker。"""

    def __init__(
        self,
        client,
        state_store: WecomCSStateStore,
        on_message: Callable[[dict], Awaitable[None]],
        *,
        message_state_ttl_seconds: int = 604800,
        lock_ttl_seconds: int = 60,
        history_message_drop_threshold_seconds: int = 90,
    ):
        self.client = client
        self.state_store = state_store
        self.on_message = on_message
        self.message_state_ttl_seconds = message_state_ttl_seconds
        self.lock_ttl_seconds = lock_ttl_seconds
        self.history_message_drop_threshold_seconds = max(0, history_message_drop_threshold_seconds)


    @staticmethod
    def _normalize_timestamp_seconds(timestamp_value) -> int | None:
        try:
            normalized = int(str(timestamp_value or '').strip())
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        # 中文注释：企业微信不同场景可能返回秒或毫秒时间戳，这里统一折算成秒。
        return normalized // 1000 if normalized > 10**12 else normalized

    def _filter_bootstrap_messages_by_time_window(self, msg_list: list[dict], webhook_received_at: int | None) -> list[dict]:
        if self.history_message_drop_threshold_seconds <= 0 or webhook_received_at is None:
            return msg_list

        keep_messages: list[dict] = []
        dropped_count = 0
        lower_bound = webhook_received_at - self.history_message_drop_threshold_seconds
        for msg_data in msg_list:
            send_time = self._normalize_timestamp_seconds(msg_data.get('send_time'))
            if send_time is None or send_time >= lower_bound:
                keep_messages.append(msg_data)
                continue
            dropped_count += 1

        if dropped_count > 0:
            _logger.debug(
                f'[wecomcs][pull-worker] bootstrap时间窗口过滤历史消息: kept={len(keep_messages)}, dropped={dropped_count}, webhook_received_at={webhook_received_at}, threshold_seconds={self.history_message_drop_threshold_seconds}'
            )
        return keep_messages

    async def _dispatch_messages(self, bot_uuid: str, open_kfid: str, msg_list: list[dict]) -> int:
        processed_count = 0
        for msg_data in msg_list:
            msgid = str(msg_data.get('msgid', '') or '')
            if not msgid:
                continue

            # 中文注释：第一层只负责保序投递到第二层，重复消息依赖状态机提前拦截。
            reserved = await self.state_store.reserve_message_for_queue(bot_uuid, open_kfid, msg_data)
            if not reserved:
                _logger.debug(
                    f'[wecomcs][pull-worker] 跳过重复消息: bot_uuid={bot_uuid}, open_kfid={open_kfid}, msgid={msgid}'
                )
                continue

            try:
                await self.on_message(msg_data)
            except Exception as exc:
                await self.state_store.mark_message_failed(
                    bot_uuid,
                    open_kfid,
                    msgid,
                    stage='publish_process_stream',
                    error=str(exc),
                )
                raise

            processed_count += 1
            _logger.debug(f'[wecomcs][pull-worker] 已转发消息到第二层: bot_uuid={bot_uuid}, open_kfid={open_kfid}, msgid={msgid}')

        return processed_count

    async def _bootstrap_latest_cursor(self, bot_uuid: str, open_kfid: str, callback_token: str, webhook_received_at: int | None = None) -> tuple[str, list[dict]]:
        current_cursor = ''
        final_cursor = ''
        latest_page_messages: list[dict] = []

        while True:
            _logger.debug(
                f'[wecomcs][pull-worker] 执行latest bootstrap: bot_uuid={bot_uuid}, open_kfid={open_kfid}, cursor={current_cursor}'
            )
            page = await self.client.fetch_sync_msg_page(
                callback_token=callback_token,
                open_kfid=open_kfid,
                cursor=current_cursor or None,
            )
            msg_list = page.get('msg_list') or []
            next_cursor = str(page.get('next_cursor') or '')
            has_more = bool(page.get('has_more', False))
            latest_page_messages = msg_list
            if next_cursor:
                final_cursor = next_cursor

            if not has_more or not next_cursor:
                if not final_cursor:
                    final_cursor = current_cursor
                break

            current_cursor = next_cursor

        # 中文注释：latest 模式仍跳过更早历史页，但保留 bootstrap 末页中的最近消息，避免吞掉用户首条真实消息。
        latest_page_messages = self._filter_bootstrap_messages_by_time_window(latest_page_messages, webhook_received_at)
        return final_cursor, latest_page_messages

    async def handle_trigger(self, trigger_payload: dict) -> int:
        bot_uuid = str(trigger_payload.get('bot_uuid', '') or '')
        open_kfid = str(trigger_payload.get('open_kfid', '') or '')
        callback_token = str(trigger_payload.get('callback_token', '') or '')
        webhook_received_at = self._normalize_timestamp_seconds(trigger_payload.get('webhook_received_at'))
        if not bot_uuid or not open_kfid or not callback_token:
            raise ValueError('bot_uuid, open_kfid and callback_token are required')

        _logger.debug(f'[wecomcs][pull-worker] 开始处理trigger: bot_uuid={bot_uuid}, open_kfid={open_kfid}')

        lock_owner = str(uuid.uuid4())
        acquired = await self.state_store.acquire_pull_lock(
            bot_uuid,
            open_kfid,
            lock_owner,
            self.lock_ttl_seconds,
        )
        if not acquired:
            raise PullLockNotAcquiredError(f"pull lock not acquired: {bot_uuid}:{open_kfid}")

        try:
            current_cursor = await self.state_store.get_cursor(bot_uuid, open_kfid)
            is_bootstrapped = await self.state_store.is_bootstrapped(bot_uuid, open_kfid)
            if not current_cursor and self.state_store.cursor_bootstrap_mode == 'latest':
                # English comment: Some sync_msg batches are single-page and never return a resumable cursor.
                # In that case we must keep using latest-bootstrap mode, otherwise the next webhook would replay full history.
                _logger.debug(
                    f'[wecomcs][pull-worker] 使用latest bootstrap处理空cursor检查点: bot_uuid={bot_uuid}, open_kfid={open_kfid}, already_bootstrapped={is_bootstrapped}'
                )
                final_cursor, latest_messages = await self._bootstrap_latest_cursor(bot_uuid, open_kfid, callback_token, webhook_received_at)
                processed_count = await self._dispatch_messages(bot_uuid, open_kfid, latest_messages)
                await self.state_store.mark_bootstrapped(bot_uuid, open_kfid, final_cursor)
                _logger.debug(
                    f'[wecomcs][pull-worker] latest bootstrap完成，保留末页消息: bot_uuid={bot_uuid}, open_kfid={open_kfid}, processed_count={processed_count}, final_cursor={final_cursor}'
                )
                return processed_count

            final_cursor = current_cursor
            processed_count = 0

            while True:
                _logger.debug(f'[wecomcs][pull-worker] 拉取消息页: bot_uuid={bot_uuid}, open_kfid={open_kfid}, cursor={current_cursor}')
                try:
                    page = await self.client.fetch_sync_msg_page(
                        callback_token=callback_token,
                        open_kfid=open_kfid,
                        cursor=current_cursor or None,
                    )
                except WecomCSInvalidSyncMsgTokenError:
                    if current_cursor:
                        _logger.warning(
                            f'[wecomcs][pull-worker] 检测到失效cursor/token组合，清理检查点并改用当前webhook重新拉取: bot_uuid={bot_uuid}, open_kfid={open_kfid}, stale_cursor={current_cursor}'
                        )
                        await self.state_store.clear_checkpoint(bot_uuid, open_kfid)
                        current_cursor = ''
                        final_cursor = ''
                        if self.state_store.cursor_bootstrap_mode == 'latest':
                            final_cursor, latest_messages = await self._bootstrap_latest_cursor(bot_uuid, open_kfid, callback_token, webhook_received_at)
                            processed_count += await self._dispatch_messages(bot_uuid, open_kfid, latest_messages)
                            await self.state_store.mark_bootstrapped(bot_uuid, open_kfid, final_cursor)
                            _logger.debug(
                                f'[wecomcs][pull-worker] 失效cursor恢复完成，保留末页消息: bot_uuid={bot_uuid}, open_kfid={open_kfid}, processed_count={processed_count}, final_cursor={final_cursor}'
                            )
                            return processed_count
                        continue
                    raise

                msg_list = page.get('msg_list') or []
                _logger.debug(f'[wecomcs][pull-worker] 拉取结果: bot_uuid={bot_uuid}, open_kfid={open_kfid}, msg_count={len(msg_list)}, next_cursor={page.get("next_cursor", "")}, has_more={page.get("has_more", False)}')
                next_cursor = str(page.get('next_cursor') or '')
                has_more = bool(page.get('has_more', False))

                processed_count += await self._dispatch_messages(bot_uuid, open_kfid, msg_list)

                if next_cursor:
                    final_cursor = next_cursor
                    current_cursor = next_cursor

                if not has_more or not next_cursor:
                    break

            await self.state_store.mark_bootstrapped(bot_uuid, open_kfid, final_cursor)

            _logger.debug(f'[wecomcs][pull-worker] trigger处理完成: bot_uuid={bot_uuid}, open_kfid={open_kfid}, processed_count={processed_count}, final_cursor={final_cursor}')
            return processed_count
        finally:
            await self.state_store.release_pull_lock(bot_uuid, open_kfid, lock_owner)
