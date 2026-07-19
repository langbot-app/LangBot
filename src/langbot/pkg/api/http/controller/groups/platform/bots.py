import quart
from sqlalchemy.exc import IntegrityError

from ....authz import Permission, has_permission
from ....context import RequestContext
from ... import group


@group.group_class('bots', '/api/v1/platform/bots')
class BotsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            include_secret = has_permission(request_context, Permission.RESOURCE_MANAGE)
            return self.success(
                data={
                    'bots': await self.ap.bot_service.get_bots(
                        request_context,
                        include_secret=include_secret,
                    )
                }
            )

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            json_data = await quart.request.json
            bot_uuid = await self.ap.bot_service.create_bot(request_context, json_data)
            return self.success(data={'uuid': bot_uuid})

        @self.route(
            '/<bot_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            include_secret = has_permission(request_context, Permission.RESOURCE_MANAGE)
            bot = await self.ap.bot_service.get_runtime_bot_info(
                request_context,
                bot_uuid,
                include_secret=include_secret,
            )
            if bot is None:
                return self.http_status(404, -1, 'bot not found')
            return self.success(data={'bot': bot})

        @self.route(
            '/<bot_uuid>',
            methods=['PUT', 'DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            if quart.request.method == 'PUT':
                json_data = await quart.request.json
                await self.ap.bot_service.update_bot(request_context, bot_uuid, json_data)
            else:
                await self.ap.bot_service.delete_bot(request_context, bot_uuid)
            return self.success()

        @self.route(
            '/<bot_uuid>/logs',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            from_index = json_data.get('from_index', -1)
            max_count = json_data.get('max_count', 10)
            logs, total_count = await self.ap.bot_service.list_event_logs(
                request_context, bot_uuid, from_index, max_count
            )
            return self.success(data={'logs': logs, 'total_count': total_count})

        @self.route(
            '/<bot_uuid>/send_message',
            methods=['POST'],
            auth_type=group.AuthType.API_KEY,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            target_type = json_data.get('target_type')
            target_id = json_data.get('target_id')
            message_chain_data = json_data.get('message_chain')

            if not target_type:
                return self.http_status(400, -1, 'target_type is required')
            if not target_id:
                return self.http_status(400, -1, 'target_id is required')
            if not message_chain_data:
                return self.http_status(400, -1, 'message_chain is required')
            if target_type not in ['person', 'group']:
                return self.http_status(400, -1, 'target_type must be either "person" or "group"')

            await self.ap.bot_service.send_message(
                request_context,
                bot_uuid,
                target_type,
                target_id,
                message_chain_data,
            )
            return self.success(data={'sent': True})

        @self.route(
            '/<bot_uuid>/admins',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            admins = await self.ap.bot_service.get_bot_admins(request_context, bot_uuid)
            return self.success(data={'admins': admins})

        @self.route(
            '/<bot_uuid>/admins',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(bot_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            launcher_type = json_data.get('launcher_type', '').strip()
            launcher_id = str(json_data.get('launcher_id', '')).strip()
            if not launcher_type or not launcher_id:
                return self.http_status(400, -1, 'launcher_type and launcher_id are required')
            try:
                admin_id = await self.ap.bot_service.add_bot_admin(
                    request_context, bot_uuid, launcher_type, launcher_id
                )
                return self.success(data={'id': admin_id})
            except IntegrityError as e:
                return self.http_status(409, -1, str(e))

        @self.route(
            '/<bot_uuid>/admins/<int:admin_id>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(bot_uuid: str, admin_id: int, request_context: RequestContext) -> str:
            await self.ap.bot_service.delete_bot_admin(request_context, bot_uuid, admin_id)
            return self.success()
