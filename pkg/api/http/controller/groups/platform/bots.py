import quart

from ... import group


@group.group_class('bots', '/api/v1/platform/bots')
class BotsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'])
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'bots': await self.ap.bot_service.get_bots()})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                bot_uuid = await self.ap.bot_service.create_bot(json_data)
                return self.success(data={'uuid': bot_uuid})

        @self.route('/<bot_uuid>', methods=['GET', 'PUT', 'DELETE'])
        async def _(bot_uuid: str) -> str:
            if quart.request.method == 'GET':
                bot = await self.ap.bot_service.get_bot(bot_uuid)
                if bot is None:
                    return self.http_status(404, -1, 'bot not found')
                return self.success(data={'bot': bot})
            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.bot_service.update_bot(bot_uuid, json_data)
                return self.success()
            elif quart.request.method == 'DELETE':
                await self.ap.bot_service.delete_bot(bot_uuid)
                return self.success()
