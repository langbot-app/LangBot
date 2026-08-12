from __future__ import annotations
import asyncio
from collections import OrderedDict
import time
import typing
from .. import algo
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from ...pool import get_query_execution_context


_MAX_SESSION_CONTAINERS = 10000
_MIN_CONTAINER_TTL_SECONDS = 300
_CLEANUP_INTERVAL_SECONDS = 60
_MAX_EVICTION_PROBES = 64


# 固定窗口算法
class SessionContainer:
    wait_lock: asyncio.Lock

    records: dict[int, int]
    """访问记录，key为每窗口长度的起始时间戳，value为访问次数"""

    def __init__(self, ttl_seconds: int = _MIN_CONTAINER_TTL_SECONDS):
        self.wait_lock = asyncio.Lock()
        self.records = {}
        self.last_accessed = time.monotonic()
        self.ttl_seconds = ttl_seconds


@algo.algo_class('fixwin')
class FixedWindowAlgo(algo.ReteLimitAlgo):
    containers_lock: asyncio.Lock
    """访问记录容器锁"""

    containers: dict[str, SessionContainer]
    """访问记录容器，key为launcher_type launcher_id"""

    async def initialize(self):
        self.containers_lock = asyncio.Lock()
        self.containers = OrderedDict()
        self._last_cleanup = time.monotonic()

    async def require_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ) -> bool:
        # 加锁，找容器
        container: SessionContainer = None

        execution_context = get_query_execution_context(query)
        session_name = ':'.join(
            (
                execution_context.instance_uuid,
                execution_context.workspace_uuid,
                str(execution_context.placement_generation),
                str(getattr(query, 'bot_uuid', '')),
                str(getattr(query, 'pipeline_uuid', '')),
                str(launcher_type),
                str(launcher_id),
            )
        )

        async with self.containers_lock:
            container = self.containers.get(session_name)

            if container is None:
                window_size = query.pipeline_config['safety']['rate-limit']['window-length']
                ttl_seconds = max(int(window_size) * 2, _MIN_CONTAINER_TTL_SECONDS)
                now_monotonic = time.monotonic()
                if now_monotonic - self._last_cleanup >= _CLEANUP_INTERVAL_SECONDS:
                    self._last_cleanup = now_monotonic
                    for key, candidate in tuple(self.containers.items()):
                        if (
                            not candidate.wait_lock.locked()
                            and now_monotonic - candidate.last_accessed >= candidate.ttl_seconds
                        ):
                            self.containers.pop(key, None)

                if len(self.containers) >= _MAX_SESSION_CONTAINERS:
                    for _ in range(min(_MAX_EVICTION_PROBES, len(self.containers))):
                        oldest_key = next(iter(self.containers))
                        oldest = self.containers[oldest_key]
                        if oldest.wait_lock.locked():
                            self.containers.move_to_end(oldest_key)
                            continue
                        self.containers.pop(oldest_key, None)
                        break
                if len(self.containers) >= _MAX_SESSION_CONTAINERS:
                    # Every retained session is actively waiting. Reject this
                    # admission instead of growing an attacker-controlled map.
                    return False
                container = SessionContainer(ttl_seconds=ttl_seconds)
                self.containers[session_name] = container
            else:
                self.containers.move_to_end(session_name)
            container.last_accessed = time.monotonic()

        # 等待锁
        async with container.wait_lock:
            # 获取窗口大小和限制
            window_size = query.pipeline_config['safety']['rate-limit']['window-length']
            limitation = query.pipeline_config['safety']['rate-limit']['limitation']

            # TODO revert it
            # if session_name in self.ap.pipeline_cfg.data['rate-limit']['fixwin']:
            #     window_size = self.ap.pipeline_cfg.data['rate-limit']['fixwin'][session_name]['window-size']
            #     limitation = self.ap.pipeline_cfg.data['rate-limit']['fixwin'][session_name]['limit']

            # 获取当前时间戳
            now = int(time.time())

            # 获取当前窗口的起始时间戳
            now = now - now % window_size

            # 获取当前窗口的访问次数
            count = container.records.get(now, 0)

            # 如果访问次数超过了限制
            if count >= limitation:
                if query.pipeline_config['safety']['rate-limit']['strategy'] == 'drop':
                    return False
                elif query.pipeline_config['safety']['rate-limit']['strategy'] == 'wait':
                    # 等待下一窗口
                    await asyncio.sleep(window_size - time.time() % window_size)

                    now = int(time.time())
                    now = now - now % window_size

            if now not in container.records:
                container.records = {}
                container.records[now] = 1
            else:
                # 访问次数加一
                container.records[now] = count + 1

            # 返回True
            container.last_accessed = time.monotonic()
            return True

    async def release_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ):
        pass
