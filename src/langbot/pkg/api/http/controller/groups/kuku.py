from __future__ import annotations

import quart

from .. import group


@group.group_class('kuku', '/api/v1/kuku')
class KukuRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/personas', methods=['GET'], auth_type=group.AuthType.USER_TOKEN_OR_API_KEY)
        async def _personas() -> str:
            return self.success(data={'personas': await self.ap.kuku_service.list_personas()})

        @self.route(
            '/groups/<bot_uuid>/<platform>/<group_id>',
            methods=['GET', 'PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
        )
        async def _group(bot_uuid: str, platform: str, group_id: str) -> str:
            if quart.request.method == 'GET':
                try:
                    group_settings = await self.ap.kuku_service.get_group_settings(bot_uuid, platform, group_id)
                except ValueError as exc:
                    if str(exc) == 'Bot not found':
                        return self.http_status(404, 404, str(exc))
                    return self.http_status(400, 400, str(exc))

                if group_settings is None:
                    return self.http_status(404, 404, 'Group settings not found')

                return self.success(data={'group': group_settings})

            data = await quart.request.json
            if data is None or not isinstance(data, dict):
                return self.http_status(400, 400, 'JSON body required')

            payload = dict(data)
            payload.update(
                {
                    'bot_uuid': bot_uuid,
                    'platform': platform,
                    'group_id': group_id,
                }
            )

            try:
                group_settings = await self.ap.kuku_service.upsert_group_settings(payload)
            except ValueError as exc:
                if str(exc) == 'Bot not found':
                    return self.http_status(404, 404, str(exc))
                return self.http_status(400, 400, str(exc))

            return self.success(data={'group': group_settings})
