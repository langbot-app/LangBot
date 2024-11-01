import quart
import asyncio

from .....core import app, taskmgr
from .. import group
from .....utils import constants


@group.group_class('system', '/api/v1/system')
class SystemRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        @self.route('/info', methods=['GET'])
        async def _() -> str:
            return self.success(
                data={
                    "version": constants.semantic_version,
                    "debug": constants.debug_mode
                }
            )

        @self.route('/tasks', methods=['GET'])
        async def _() -> str:
            task_type = quart.request.args.get("type")

            if task_type == '':
                task_type = None

            return self.success(
                data=self.ap.task_mgr.get_tasks_dict(task_type)
            )
        
        @self.route('/tasks/<task_id>', methods=['GET'])
        async def _(task_id: str) -> str:
            task = self.ap.task_mgr.get_task_by_id(int(task_id))

            if task is None:
                return self.http_status(404, 404, "Task not found")
            
            return self.success(data=task.to_dict())
