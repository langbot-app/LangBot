import os

from langbot_plugin.api.definition.components.page import Page, PageRequest, PageResponse


class ProbePage(Page):
    async def handle_api(self, request: PageRequest) -> PageResponse:
        if request.endpoint != '/state' or request.method not in ('GET', 'POST'):
            return PageResponse.fail('Unsupported lifecycle probe request')
        if request.method == 'POST':
            await self.plugin.set_plugin_storage('probe', request.body['token'].encode())
        token = (await self.plugin.get_plugin_storage('probe')).decode()
        return PageResponse.ok(
            {
                'version': self.plugin.version,
                'token': token,
                'config': self.plugin.get_config(),
                'pid': os.getpid(),
            }
        )
