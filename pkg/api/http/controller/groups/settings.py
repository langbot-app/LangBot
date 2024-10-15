import quart

from .....core import app
from .. import group


@group.group_class('settings', '/api/v1/settings')
class SettingsRouterGroup(group.RouterGroup):
    
    async def initialize(self) -> None:
        
        @self.route('', methods=['GET'])
        async def _() -> str:
            return self.success(
                data={
                    "managers": [
                        {
                            "name": m.name,
                            "description": m.description,
                        }
                        for m in self.ap.settings_mgr.get_manager_list()
                    ]
                }
            )
        
        @self.route('/<manager_name>', methods=['GET'])
        async def _(manager_name: str) -> str:

            manager = self.ap.settings_mgr.get_manager(manager_name)

            return self.success(
                data={
                    "manager": {
                        "name": manager.name,
                        "description": manager.description,
                        "schema": manager.schema,
                        "file": manager.file.config_file_name,
                        "data": manager.data
                    }
                }
            )
        
        @self.route('/<manager_name>/data', methods=['PUT'])
        async def _(manager_name: str) -> str:
            data = await quart.request.json
            manager = self.ap.settings_mgr.get_manager(manager_name)
            manager.data = data['data']
            return self.success(data={
                "data": manager.data
            })
