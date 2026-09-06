import quart

from ....authz import Permission, has_permission
from ....context import RequestContext
from ... import group


@group.group_class('models/providers', '/api/v1/provider/providers')
class ModelProvidersRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        # Subscription authorization is an interactive, browser-user-only surface.
        @self.route(
            '/<provider_uuid>/codex/status',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def codex_status(provider_uuid: str, request_context: RequestContext):
            try:
                return self.success(
                    data=await self.ap.provider_service.codex_auth.status(request_context, provider_uuid)
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<provider_uuid>/codex/device',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def codex_device(provider_uuid: str, request_context: RequestContext):
            try:
                return self.success(
                    data=await self.ap.provider_service.codex_auth.start(request_context, provider_uuid)
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<provider_uuid>/codex/device/poll',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def codex_poll(provider_uuid: str, request_context: RequestContext):
            body = await quart.request.get_json()
            if not isinstance(body, dict):
                return self.http_status(400, -1, 'JSON object required')
            try:
                return self.success(
                    data=await self.ap.provider_service.codex_auth.poll(
                        request_context, provider_uuid, body.get('authorization_id')
                    )
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<provider_uuid>/codex/auth',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def codex_disconnect(provider_uuid: str, request_context: RequestContext):
            try:
                await self.ap.provider_service.codex_auth.disconnect(request_context, provider_uuid)
                return self.success()
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '/<provider_uuid>/codex/device/<authorization_id>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def codex_cancel(provider_uuid: str, authorization_id: str, request_context: RequestContext):
            try:
                await self.ap.provider_service.codex_auth.cancel(request_context, provider_uuid, authorization_id)
                return self.success()
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))

        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            providers = await self.ap.provider_service.get_providers(
                request_context,
                include_secret=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            for provider in providers:
                counts = await self.ap.provider_service.get_provider_model_counts(request_context, provider['uuid'])
                provider['llm_count'] = counts['llm_count']
                provider['embedding_count'] = counts['embedding_count']
                provider['rerank_count'] = counts['rerank_count']
            return self.success(data={'providers': providers})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            json_data = await quart.request.json
            try:
                provider_uuid = await self.ap.provider_service.create_provider(request_context, json_data)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': provider_uuid})

        @self.route(
            '/<provider_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(provider_uuid: str, request_context: RequestContext) -> str:
            provider = await self.ap.provider_service.get_provider(
                request_context,
                provider_uuid,
                include_secret=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if provider is None:
                return self.http_status(404, -1, 'provider not found')
            counts = await self.ap.provider_service.get_provider_model_counts(request_context, provider_uuid)
            provider['llm_count'] = counts['llm_count']
            provider['embedding_count'] = counts['embedding_count']
            provider['rerank_count'] = counts['rerank_count']
            return self.success(data={'provider': provider})

        @self.route(
            '/<provider_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(provider_uuid: str, request_context: RequestContext) -> str:
            json_data = await quart.request.json
            try:
                await self.ap.provider_service.update_provider(request_context, provider_uuid, json_data)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success()

        @self.route(
            '/<provider_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(provider_uuid: str, request_context: RequestContext) -> str:
            try:
                cascade_values = quart.request.args.getlist('cascade')
                if cascade_values:
                    if len(cascade_values) != 1 or cascade_values[0] not in ('true', 'false'):
                        return self.http_status(400, -1, 'cascade must be a single true or false value')
                    await self.ap.provider_service.delete_provider(
                        request_context, provider_uuid, cascade=cascade_values[0] == 'true'
                    )
                else:
                    await self.ap.provider_service.delete_provider(request_context, provider_uuid)
                return self.success()
            except ValueError as e:
                return self.http_status(400, -1, str(e))

        @self.route(
            '/<provider_uuid>/scan-models',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(provider_uuid: str, request_context: RequestContext) -> str:
            try:
                model_type = quart.request.args.get('type')
                result = await self.ap.provider_service.scan_provider_models(request_context, provider_uuid, model_type)
                return self.success(data=result)
            except ValueError as e:
                return self.http_status(400, -1, str(e))
