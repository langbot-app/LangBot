from __future__ import annotations

import asyncio
import logging
import socket
from ...cache.redis_mgr import RedisManager
from langbot.libs.wecom_customer_service_api.api import WecomCSInvalidSyncMsgTokenError
from .message_publisher import WecomCSMessagePublisher
from .message_worker import WecomCSMessageWorker
from .pull_worker import PullLockNotAcquiredError, WecomCSPullWorker
from .state_store import WecomCSStateStore
from .retry_scheduler import WecomCSRetryScheduler
from .stream_keys import (
    build_process_consumer_group_name,
    build_process_stream_name,
    build_pull_consumer_group_name,
    build_pull_stream_name,
    build_retry_zset_key,
)


_logger = logging.getLogger("langbot")


class WecomCSSchedulerRuntime:
    """企业微信客服 Redis 两层 Streams 运行时。"""

    def __init__(self, bot_uuid: str, client, redis_mgr: RedisManager, scheduler_config: dict, persistence_mgr = None):
        self.bot_uuid = bot_uuid
        self.client = client
        self.redis_mgr = redis_mgr
        self.scheduler_config = scheduler_config
        self.running = False
        self.state_store = WecomCSStateStore(
            redis_mgr,
            persistence_mgr,
            message_state_ttl_seconds=int(
                scheduler_config.get('message_state_ttl_seconds', scheduler_config.get('dedupe_ttl_seconds', 604800)) or 604800
            ),
            cursor_bootstrap_mode=str(scheduler_config.get('cursor_bootstrap_mode', 'latest') or 'latest'),
        )
        self.message_publisher = WecomCSMessagePublisher(
            redis_mgr,
            int(scheduler_config.get('process_stream_shard_count', 16) or 16),
        )
        self.message_worker = WecomCSMessageWorker(client, self.state_store, bot_uuid=bot_uuid)
        self.pull_worker = WecomCSPullWorker(
            client,
            self.state_store,
            self._publish_message,
            message_state_ttl_seconds=int(
                scheduler_config.get('message_state_ttl_seconds', scheduler_config.get('dedupe_ttl_seconds', 604800)) or 604800
            ),
            lock_ttl_seconds=int(scheduler_config.get('lock_ttl_seconds', 60) or 60),
            history_message_drop_threshold_seconds=int(scheduler_config.get('history_message_drop_threshold_seconds', 90) or 90),
        )
        self.pull_stream_shard_count = int(scheduler_config.get('pull_stream_shard_count', 8) or 8)
        self.process_stream_shard_count = int(scheduler_config.get('process_stream_shard_count', 16) or 16)
        self.pull_consumer_group = build_pull_consumer_group_name(
            str(scheduler_config.get('pull_consumer_group', 'wecomcs-pull-group') or 'wecomcs-pull-group'),
            bot_uuid,
        )
        self.process_consumer_group = build_process_consumer_group_name(
            str(scheduler_config.get('process_consumer_group', 'wecomcs-process-group') or 'wecomcs-process-group'),
            bot_uuid,
        )
        self.stream_block_ms = int(scheduler_config.get('stream_block_ms', 1000) or 1000)
        self.stream_batch_size = int(scheduler_config.get('stream_batch_size', 10) or 10)
        self.consumer_name = f'{socket.gethostname()}-{self.bot_uuid}'
        self.retry_poll_interval_seconds = int(scheduler_config.get('retry_poll_interval_seconds', 3) or 3)
        self.retry_scheduler = WecomCSRetryScheduler(
            redis_mgr,
            retry_zset_key=build_retry_zset_key(bot_uuid),
            retry_backoff_seconds=list(scheduler_config.get('retry_backoff_seconds', [15, 30, 45]) or [15, 30, 45]),
            retry_max_attempts=int(scheduler_config.get('retry_max_attempts', 3) or 3),
        )

    async def _publish_message(self, msg_data: dict):
        await self.message_publisher.publish_message(self.bot_uuid, msg_data)

    def _pull_streams(self) -> list[str]:
        return [build_pull_stream_name(self.bot_uuid, index) for index in range(self.pull_stream_shard_count)]

    def _process_streams(self) -> list[str]:
        return [build_process_stream_name(self.bot_uuid, index) for index in range(self.process_stream_shard_count)]

    def _matches_runtime_bot(self, fields: dict[str, str]) -> bool:
        payload_bot_uuid = str(fields.get('bot_uuid', '') or '')
        if not payload_bot_uuid:
            return True
        return payload_bot_uuid == self.bot_uuid

    @staticmethod
    def _extract_retry_count(fields: dict[str, str]) -> int:
        try:
            return int(str(fields.get('retry_count', '0') or '0'))
        except (TypeError, ValueError):
            return 0

    async def initialize(self):
        for stream_name in self._pull_streams():
            await self.redis_mgr.xgroup_create(stream_name, self.pull_consumer_group, id='0', mkstream=True)
        for stream_name in self._process_streams():
            await self.redis_mgr.xgroup_create(stream_name, self.process_consumer_group, id='0', mkstream=True)

    async def run(self):
        await self.initialize()
        self.running = True
        _logger.debug(f'[wecomcs][runtime] 启动调度运行时: bot_uuid={self.bot_uuid}, pull_shards={self.pull_stream_shard_count}, process_shards={self.process_stream_shard_count}')
        await asyncio.gather(self._run_pull_loop(), self._run_process_loop(), self._run_retry_loop())

    async def stop(self):
        self.running = False

    async def _run_pull_loop(self):
        streams = {stream_name: '>' for stream_name in self._pull_streams()}
        while self.running:
            entries = await self.redis_mgr.xreadgroup(
                self.pull_consumer_group,
                self.consumer_name,
                streams,
                count=self.stream_batch_size,
                block_ms=self.stream_block_ms,
            )
            if not entries:
                continue

            for stream_name, messages in entries:
                logical_stream_name = stream_name.split(':', 1)[1] if stream_name.startswith(self.redis_mgr.key_prefix + ':') else stream_name
                for message_id, fields in messages:
                    retry_count = self._extract_retry_count(fields)
                    try:
                        _logger.debug(f'[wecomcs][runtime] pull-loop消费消息: stream={logical_stream_name}, message_id={message_id}, bot_uuid={fields.get("bot_uuid")}, open_kfid={fields.get("open_kfid")}')
                        if not self._matches_runtime_bot(fields):
                            _logger.error(
                                f'[wecomcs][runtime] pull-loop检测到跨bot消息，直接跳过: stream={logical_stream_name}, message_id={message_id}, runtime_bot_uuid={self.bot_uuid}, payload_bot_uuid={fields.get("bot_uuid")}'
                            )
                            continue
                        await self.pull_worker.handle_trigger(fields)
                    except PullLockNotAcquiredError as exc:
                        _logger.debug(f'[wecomcs][runtime] pull-loop未拿到锁，安排重试: stream={logical_stream_name}, message_id={message_id}, error={exc}')
                        await self.retry_scheduler.schedule_retry(logical_stream_name, fields, retry_count=retry_count, error=str(exc))
                    except WecomCSInvalidSyncMsgTokenError as exc:
                        _logger.warning(f'[wecomcs][runtime] pull-loop检测到不可重试的invalid msg token，直接ACK等待新webhook: stream={logical_stream_name}, message_id={message_id}, error={exc}')
                    except Exception as exc:
                        _logger.debug(f'[wecomcs][runtime] pull-loop处理异常，安排重试: stream={logical_stream_name}, message_id={message_id}, error={exc}')
                        await self.retry_scheduler.schedule_retry(logical_stream_name, fields, retry_count=retry_count, error=str(exc))
                    finally:
                        await self.redis_mgr.xack(logical_stream_name, self.pull_consumer_group, message_id)
                        _logger.debug(f'[wecomcs][runtime] pull-loop已ACK: stream={logical_stream_name}, message_id={message_id}')

    async def _run_process_loop(self):
        streams = {stream_name: '>' for stream_name in self._process_streams()}
        while self.running:
            entries = await self.redis_mgr.xreadgroup(
                self.process_consumer_group,
                self.consumer_name,
                streams,
                count=self.stream_batch_size,
                block_ms=self.stream_block_ms,
            )
            if not entries:
                continue

            for stream_name, messages in entries:
                logical_stream_name = stream_name.split(':', 1)[1] if stream_name.startswith(self.redis_mgr.key_prefix + ':') else stream_name
                for message_id, fields in messages:
                    retry_count = self._extract_retry_count(fields)
                    try:
                        _logger.debug(f'[wecomcs][runtime] process-loop消费消息: stream={logical_stream_name}, message_id={message_id}')
                        if not self._matches_runtime_bot(fields):
                            _logger.error(
                                f'[wecomcs][runtime] process-loop检测到跨bot消息，直接跳过: stream={logical_stream_name}, message_id={message_id}, runtime_bot_uuid={self.bot_uuid}, payload_bot_uuid={fields.get("bot_uuid")}'
                            )
                            continue
                        handled = await self.message_worker.handle_stream_entry(fields)
                        if not handled:
                            _logger.debug(f'[wecomcs][runtime] process-loop消息无效，直接ACK: stream={logical_stream_name}, message_id={message_id}')
                            await self.redis_mgr.xack(logical_stream_name, self.process_consumer_group, message_id)
                            continue
                    except Exception as exc:
                        _logger.debug(f'[wecomcs][runtime] process-loop处理异常，安排重试: stream={logical_stream_name}, message_id={message_id}, error={exc}')
                        await self.retry_scheduler.schedule_retry(logical_stream_name, fields, retry_count=retry_count, error=str(exc))
                    finally:
                        await self.redis_mgr.xack(logical_stream_name, self.process_consumer_group, message_id)
                        _logger.debug(f'[wecomcs][runtime] process-loop已ACK: stream={logical_stream_name}, message_id={message_id}')


    async def _run_retry_loop(self):
        while self.running:
            replayed = await self.retry_scheduler.replay_due_jobs()
            if replayed > 0:
                _logger.debug(f'[wecomcs][runtime] retry-loop回投完成: bot_uuid={self.bot_uuid}, replayed={replayed}')
            if replayed <= 0:
                await asyncio.sleep(self.retry_poll_interval_seconds)
