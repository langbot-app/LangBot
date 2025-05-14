from __future__ import annotations

import asyncio
import typing
import datetime

from . import app
from . import entities as core_entities


class TaskContext:
    """任务跟踪上下文"""

    current_action: str
    """当前正在执行的动作"""

    log: str
    """记录日志"""

    def __init__(self):
        self.current_action = 'default'
        self.log = ''

    def _log(self, msg: str):
        self.log += msg + '\n'

    def set_current_action(self, action: str):
        self.current_action = action

    def trace(
        self,
        msg: str,
        action: str = None,
    ):
        if action is not None:
            self.set_current_action(action)

        self._log(f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | {self.current_action} | {msg}')

    def to_dict(self) -> dict:
        return {'current_action': self.current_action, 'log': self.log}

    @staticmethod
    def new() -> TaskContext:
        return TaskContext()

    @staticmethod
    def placeholder() -> TaskContext:
        global placeholder_context

        if placeholder_context is None:
            placeholder_context = TaskContext()

        return placeholder_context


placeholder_context: TaskContext | None = None


class TaskWrapper:
    """任务包装器"""

    _id_index: int = 0
    """任务ID索引"""

    id: int
    """任务ID"""

    task_type: str = 'system'  # 任务类型: system 或 user
    """任务类型"""

    kind: str = 'system_task'  # 由发起者确定任务种类，通常同质化的任务种类相同
    """任务种类"""

    name: str = ''
    """任务唯一名称"""

    label: str = ''
    """任务显示名称"""

    task_context: TaskContext
    """任务上下文"""

    task: asyncio.Task
    """任务"""

    task_stack: list = None
    """任务堆栈"""

    ap: app.Application
    """应用实例"""

    scopes: list[core_entities.LifecycleControlScope]
    """任务所属生命周期控制范围"""

    def __init__(
        self,
        ap: app.Application,
        coro: typing.Coroutine,
        task_type: str = 'system',
        kind: str = 'system_task',
        name: str = '',
        label: str = '',
        context: TaskContext = None,
        scopes: list[core_entities.LifecycleControlScope] = [core_entities.LifecycleControlScope.APPLICATION],
    ):
        self.id = TaskWrapper._id_index
        TaskWrapper._id_index += 1
        self.ap = ap
        self.task_context = context or TaskContext()
        self.task = self.ap.event_loop.create_task(coro)
        self.task_type = task_type
        self.kind = kind
        self.name = name
        self.label = label if label != '' else name
        self.task.set_name(name)
        self.scopes = scopes

    def assume_exception(self):
        try:
            exception = self.task.exception()
            if self.task_stack is None:
                self.task_stack = self.task.get_stack()
            return exception
        except Exception:
            return None

    def assume_result(self):
        try:
            return self.task.result()
        except Exception:
            return None

    def to_dict(self) -> dict:
        exception_traceback = None
        if self.assume_exception() is not None:
            exception_traceback = 'Traceback (most recent call last):\n'

            for frame in self.task_stack:
                exception_traceback += (
                    f'  File "{frame.f_code.co_filename}", line {frame.f_lineno}, in {frame.f_code.co_name}\n'
                )

            exception_traceback += f'    {self.assume_exception().__str__()}\n'

        return {
            'id': self.id,
            'task_type': self.task_type,
            'kind': self.kind,
            'name': self.name,
            'label': self.label,
            'scopes': [scope.value for scope in self.scopes],
            'task_context': self.task_context.to_dict(),
            'runtime': {
                'done': self.task.done(),
                'state': self.task._state,
                'exception': self.assume_exception().__str__() if self.assume_exception() is not None else None,
                'exception_traceback': exception_traceback,
                'result': self.assume_result().__str__() if self.assume_result() is not None else None,
            },
        }

    def cancel(self):
        self.task.cancel()


class AsyncTaskManager:
    """保存app中的所有异步任务
    包含系统级的和用户级（插件安装、更新等由用户直接发起的）的"""

    ap: app.Application

    tasks: list[TaskWrapper]
    """所有任务"""

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.tasks = []

    def create_task(
        self,
        coro: typing.Coroutine,
        task_type: str = 'system',
        kind: str = 'system-task',
        name: str = '',
        label: str = '',
        context: TaskContext = None,
        scopes: list[core_entities.LifecycleControlScope] = [core_entities.LifecycleControlScope.APPLICATION],
    ) -> TaskWrapper:
        wrapper = TaskWrapper(self.ap, coro, task_type, kind, name, label, context, scopes)
        self.tasks.append(wrapper)
        return wrapper

    def create_user_task(
        self,
        coro: typing.Coroutine,
        kind: str = 'user-task',
        name: str = '',
        label: str = '',
        context: TaskContext = None,
        scopes: list[core_entities.LifecycleControlScope] = [core_entities.LifecycleControlScope.APPLICATION],
    ) -> TaskWrapper:
        return self.create_task(coro, 'user', kind, name, label, context, scopes)

    async def wait_all(self):
        await asyncio.gather(*[t.task for t in self.tasks], return_exceptions=True)

    def get_all_tasks(self) -> list[TaskWrapper]:
        return self.tasks

    def get_tasks_dict(
        self,
        type: str = None,
    ) -> dict:
        return {
            'tasks': [t.to_dict() for t in self.tasks if type is None or t.task_type == type],
            'id_index': TaskWrapper._id_index,
        }

    def get_task_by_id(self, id: int) -> TaskWrapper | None:
        for t in self.tasks:
            if t.id == id:
                return t
        return None

    def cancel_by_scope(self, scope: core_entities.LifecycleControlScope):
        for wrapper in self.tasks:
            if not wrapper.task.done() and scope in wrapper.scopes:
                wrapper.task.cancel()

    def cancel_task(self, task_id: int):
        for wrapper in self.tasks:
            if wrapper.id == task_id:
                if not wrapper.task.done():
                    wrapper.task.cancel()
                return
