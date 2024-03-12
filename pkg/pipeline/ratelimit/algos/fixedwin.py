# 固定窗口算法
from __future__ import annotations

import asyncio
import time

from .. import algo


class SessionContainer:
    
    wait_lock: asyncio.Lock

    records: dict[int, int]
    """访问记录，key为每分钟的起始时间戳，value为访问次数"""

    def __init__(self):
        self.wait_lock = asyncio.Lock()
        self.records = {}


@algo.algo_class("fixwin")
class FixedWindowAlgo(algo.ReteLimitAlgo):

    containers_lock: asyncio.Lock
    """访问记录容器锁"""

    containers: dict[str, SessionContainer]
    """访问记录容器，key为launcher_type launcher_id"""

    async def initialize(self):
        self.containers_lock = asyncio.Lock()
        self.containers = {}

    async def require_access(self, launcher_type: str, launcher_id: int) -> bool:
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
            # 获取当前时间戳
            now = int(time.time())

            # 获取当前分钟的起始时间戳
            now = now - now % 60

            # 获取当前分钟的访问次数
            count = container.records.get(now, 0)

            limitation = self.ap.pipeline_cfg.data['rate-limit']['fixwin']['default']

            if session_name in self.ap.pipeline_cfg.data['rate-limit']['fixwin']:
                limitation = self.ap.pipeline_cfg.data['rate-limit']['fixwin'][session_name]

            # 如果访问次数超过了限制
            if count >= limitation:
                if self.ap.pipeline_cfg.data['rate-limit']['strategy'] == 'drop':
                    return False
                elif self.ap.pipeline_cfg.data['rate-limit']['strategy'] == 'wait':
                    # 等待下一分钟
                    await asyncio.sleep(60 - time.time() % 60)
    
                    now = int(time.time())
                    now = now - now % 60
            
            if now not in container.records:
                container.records = {}
                container.records[now] = 1
            else:
                # 访问次数加一
                container.records[now] = count + 1

            # 返回True
            return True
        
    async def release_access(self, launcher_type: str, launcher_id: int):
        pass
