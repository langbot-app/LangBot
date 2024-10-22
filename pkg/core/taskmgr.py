from __future__ import annotations

import asyncio
import typing

from . import app


class TaskContext:
    """任务跟踪上下文"""

    current_action: str
    """当前正在执行的动作"""

    log: str
    """记录日志"""

    def __init__(self):
        self.current_action = ""
        self.log = ""

    def log(self, msg: str):
        self.log += msg + "\n"

    def set_current_action(self, action: str):
        self.current_action = action


class TaskWrapper:
    """任务包装器"""

    task_type: str = "system"  # 任务类型: system 或 user
    """任务类型"""

    task_context: TaskContext
    """任务上下文"""

    task: asyncio.Task
    """任务"""

    ap: app.Application
    """应用实例"""

    def __init__(self, ap: app.Application, coro: typing.Coroutine, task_type: str = "system", context: TaskContext = None):
        self.ap = ap
        self.task_context = context or TaskContext()
        self.task = self.ap.event_loop.create_task(coro)
        self.task_type = task_type


class AsyncTaskManager:
    """保存app中的所有异步任务
    包含系统级的和用户级（插件安装、更新等由用户直接发起的）的"""
    
    ap: app.Application

    tasks: list[TaskWrapper]
    """所有任务"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.tasks = []

    def create_task(self, coro: typing.Coroutine, task_type: str = "system", context: TaskContext = None) -> TaskWrapper:
        wrapper = TaskWrapper(self.ap, coro, task_type, context)
        self.tasks.append(wrapper)
        return wrapper

    async def wait_all(self):
        await asyncio.gather(*[t.task for t in self.tasks], return_exceptions=True)

    def get_all_tasks(self) -> list[TaskWrapper]:
        return self.tasks
