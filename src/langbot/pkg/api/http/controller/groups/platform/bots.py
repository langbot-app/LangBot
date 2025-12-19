import quart

from ... import group


@group.group_class('bots', '/api/v1/platform/bots')
class BotsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _() -> str:
            if quart.request.method == 'GET':
                return self.success(data={'bots': await self.ap.bot_service.get_bots()})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                bot_uuid = await self.ap.bot_service.create_bot(json_data)
                return self.success(data={'uuid': bot_uuid})

        @self.route('/<bot_uuid>', methods=['GET', 'PUT', 'DELETE'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(bot_uuid: str) -> str:
            if quart.request.method == 'GET':
                # 返回运行时信息，包括webhook地址等
                bot = await self.ap.bot_service.get_runtime_bot_info(bot_uuid)
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

        @self.route('/<bot_uuid>/logs', methods=['POST'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _(bot_uuid: str) -> str:
            json_data = await quart.request.json
            from_index = json_data.get('from_index', -1)
            max_count = json_data.get('max_count', 10)
            logs, total_count = await self.ap.bot_service.list_event_logs(bot_uuid, from_index, max_count)
            return self.success(
                data={
                    'logs': logs,
                    'total_count': total_count,
                }
            )

        @self.route('/<bot_uuid>/send_message', methods=['POST'], auth_type=group.AuthType.API_KEY)
        async def _(bot_uuid: str) -> str:
            """Send message to a specific target via bot"""
            json_data = await quart.request.json
            target_type = json_data.get('target_type')
            target_id = json_data.get('target_id')
            message_chain_data = json_data.get('message_chain')

            # Validate required fields
            if not target_type:
                return self.http_status(400, -1, 'target_type is required')
            if not target_id:
                return self.http_status(400, -1, 'target_id is required')
            if not message_chain_data:
                return self.http_status(400, -1, 'message_chain is required')

            # Validate target_type
            if target_type not in ['person', 'group']:
                return self.http_status(400, -1, 'target_type must be either "person" or "group"')

            try:
                await self.ap.bot_service.send_message(bot_uuid, target_type, target_id, message_chain_data)
                return self.success(data={'sent': True})
            except Exception as e:
                import traceback

                traceback.print_exc()
                return self.http_status(500, -1, f'Failed to send message: {str(e)}')
