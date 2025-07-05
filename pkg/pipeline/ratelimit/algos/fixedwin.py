from __future__ import annotations
import asyncio
import time
import typing
from .. import algo
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


# 固定窗口算法
class SessionContainer:
    wait_lock: asyncio.Lock

    records: dict[int, int]
    """访问记录，key为每窗口长度的起始时间戳，value为访问次数"""

    def __init__(self):
        self.wait_lock = asyncio.Lock()
        self.records = {}


@algo.algo_class('fixwin')
class FixedWindowAlgo(algo.ReteLimitAlgo):
    containers_lock: asyncio.Lock
    """访问记录容器锁"""

    containers: dict[str, SessionContainer]
    """访问记录容器，key为launcher_type launcher_id"""

    async def initialize(self):
        self.containers_lock = asyncio.Lock()
        self.containers = {}

    async def require_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ) -> bool:
        # 加锁，找容器
        container: SessionContainer = None

        session_name = f'{launcher_type}_{launcher_id}'

        async with self.containers_lock:
            container = self.containers.get(session_name)

            if container is None:
                container = SessionContainer()
                self.containers[session_name] = container

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
            return True

    async def release_access(
        self,
        query: pipeline_query.Query,
        launcher_type: str,
        launcher_id: typing.Union[int, str],
    ):
        pass
