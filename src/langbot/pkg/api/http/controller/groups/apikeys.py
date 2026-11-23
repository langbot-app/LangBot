from __future__ import annotations

import datetime

import quart

from ...authz import Permission
from ...context import RequestContext
from .. import group


@group.group_class('apikeys', '/api/v1/apikeys')
class ApiKeysRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], permission=Permission.API_KEY_MANAGE)
        async def _(request_context: RequestContext) -> str:
            keys = await self.ap.apikey_service.get_api_keys(request_context)
            return self.success(data={'keys': keys})

        @self.route('', methods=['POST'], permission=Permission.API_KEY_MANAGE)
        async def _(request_context: RequestContext) -> str:
            json_data = await quart.request.json
            expires_at = json_data.get('expires_at')
            parsed_expiry = None
            if expires_at:
                try:
                    parsed_expiry = datetime.datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
                except ValueError:
                    return self.http_status(400, 'invalid_expiry', 'Invalid API key expiry')
            try:
                key = await self.ap.apikey_service.create_api_key(
                    request_context,
                    json_data.get('name', ''),
                    json_data.get('description', ''),
                    scopes=json_data.get('scopes'),
                    expires_at=parsed_expiry,
                )
            except ValueError as error:
                return self.http_status(400, 'invalid_api_key', str(error))
            return self.success(data={'key': key})

        @self.route('/<int:key_id>', methods=['GET'], permission=Permission.API_KEY_MANAGE)
        async def _(key_id: int, request_context: RequestContext) -> str:
            key = await self.ap.apikey_service.get_api_key(request_context, key_id)
            if key is None:
                return self.http_status(404, 'resource_not_found', 'API key not found')
            return self.success(data={'key': key})

        @self.route('/<int:key_id>', methods=['PUT'], permission=Permission.API_KEY_MANAGE)
        async def _(key_id: int, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            try:
                await self.ap.apikey_service.update_api_key(
                    request_context,
                    key_id,
                    json_data.get('name'),
                    json_data.get('description'),
                )
            except ValueError as error:
                return self.http_status(400, 'invalid_api_key', str(error))
            return self.success()

        @self.route('/<int:key_id>', methods=['DELETE'], permission=Permission.API_KEY_MANAGE)
        async def _(key_id: int, request_context: RequestContext) -> str:
            await self.ap.apikey_service.delete_api_key(request_context, key_id)
            return self.success()
