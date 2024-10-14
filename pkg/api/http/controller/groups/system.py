import quart

from .....core import app
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
