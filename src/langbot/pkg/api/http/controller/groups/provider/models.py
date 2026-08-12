import quart

from ....authz import Permission, has_permission
from ....context import RequestContext
from ... import group


@group.group_class('models/llm', '/api/v1/provider/models/llm')
class LLMModelsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            provider_uuid = quart.request.args.get('provider_uuid')
            include_secret = has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE)
            if provider_uuid:
                models = await self.ap.llm_model_service.get_llm_models_by_provider(
                    request_context,
                    provider_uuid,
                    include_secret=include_secret,
                )
            else:
                models = await self.ap.llm_model_service.get_llm_models(
                    request_context,
                    include_secret=include_secret,
                )
            return self.success(data={'models': models})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                model_uuid = await self.ap.llm_model_service.create_llm_model(
                    request_context,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': model_uuid})

        @self.route(
            '/<model_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            model = await self.ap.llm_model_service.get_llm_model(
                request_context,
                model_uuid,
                include_secret=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if model is None:
                return self.http_status(404, -1, 'model not found')
            return self.success(data={'model': model})

        @self.route(
            '/<model_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.llm_model_service.update_llm_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success()

        @self.route(
            '/<model_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.llm_model_service.delete_llm_model(request_context, model_uuid)
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.llm_model_service.test_llm_model(request_context, model_uuid, await quart.request.json)
            return self.success()


@group.group_class('models/embedding', '/api/v1/provider/models/embedding')
class EmbeddingModelsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            provider_uuid = quart.request.args.get('provider_uuid')
            include_secret = has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE)
            if provider_uuid:
                models = await self.ap.embedding_models_service.get_embedding_models_by_provider(
                    request_context,
                    provider_uuid,
                    include_secret=include_secret,
                )
            else:
                models = await self.ap.embedding_models_service.get_embedding_models(
                    request_context,
                    include_secret=include_secret,
                )
            return self.success(data={'models': models})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                model_uuid = await self.ap.embedding_models_service.create_embedding_model(
                    request_context,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': model_uuid})

        @self.route(
            '/<model_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            model = await self.ap.embedding_models_service.get_embedding_model(
                request_context,
                model_uuid,
                include_secret=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if model is None:
                return self.http_status(404, -1, 'model not found')
            return self.success(data={'model': model})

        @self.route(
            '/<model_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.embedding_models_service.update_embedding_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success()

        @self.route(
            '/<model_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.embedding_models_service.delete_embedding_model(request_context, model_uuid)
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.embedding_models_service.test_embedding_model(
                request_context, model_uuid, await quart.request.json
            )
            return self.success()


@group.group_class('models/rerank', '/api/v1/provider/models/rerank')
class RerankModelsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            provider_uuid = quart.request.args.get('provider_uuid')
            include_secret = has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE)
            if provider_uuid:
                models = await self.ap.rerank_models_service.get_rerank_models_by_provider(
                    request_context,
                    provider_uuid,
                    include_secret=include_secret,
                )
            else:
                models = await self.ap.rerank_models_service.get_rerank_models(
                    request_context,
                    include_secret=include_secret,
                )
            return self.success(data={'models': models})

        @self.route(
            '',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                model_uuid = await self.ap.rerank_models_service.create_rerank_model(
                    request_context,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'uuid': model_uuid})

        @self.route(
            '/<model_uuid>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            model = await self.ap.rerank_models_service.get_rerank_model(
                request_context,
                model_uuid,
                include_secret=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if model is None:
                return self.http_status(404, -1, 'model not found')
            return self.success(data={'model': model})

        @self.route(
            '/<model_uuid>',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.ap.rerank_models_service.update_rerank_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success()

        @self.route(
            '/<model_uuid>',
            methods=['DELETE'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.rerank_models_service.delete_rerank_model(request_context, model_uuid)
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            await self.ap.rerank_models_service.test_rerank_model(request_context, model_uuid, await quart.request.json)
            return self.success()
