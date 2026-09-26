import quart

from langbot.pkg.provider.modelmgr import errors as provider_errors
from ....authz import Permission, has_permission
from ....context import RequestContext
from ......operation_trace import service as settings_service
from ... import group
from .query import resolve_include_secret


MODEL_TEST_ERROR_CODE = 'model_test_failed'


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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
            model = await self.ap.llm_model_service.get_llm_model(
                request_context,
                model_uuid,
                include_secret=include_secret,
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
            json_data = await quart.request.json
            try:
                previous = await self.ap.llm_model_service.get_llm_model(request_context, model_uuid)
            except Exception:
                previous = None
            try:
                await self.ap.llm_model_service.update_llm_model(
                    request_context,
                    model_uuid,
                    json_data,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            changes = settings_service.changed_fields(
                previous if isinstance(previous, dict) else {},
                json_data if isinstance(json_data, dict) else {},
                ignore=('uuid', 'created_at', 'updated_at'),
            )
            rule = settings_service.ACTION_RULES_BY_ACTION.get('update')
            quart.g.operation_log_changes = changes
            if rule is not None and changes:
                quart.g.operation_log_summary = settings_service.build_summary(rule, changes)
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
            try:
                await self.ap.llm_model_service.test_llm_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except provider_errors.RequesterError as exc:
                return self.http_status(400, MODEL_TEST_ERROR_CODE, str(exc))
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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
            model = await self.ap.embedding_models_service.get_embedding_model(
                request_context,
                model_uuid,
                include_secret=include_secret,
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
            try:
                await self.ap.embedding_models_service.test_embedding_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except provider_errors.RequesterError as exc:
                return self.http_status(400, MODEL_TEST_ERROR_CODE, str(exc))
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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
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
            include_secret, error = resolve_include_secret(
                quart.request.args.get('include_secret'),
                permitted=has_permission(request_context, Permission.PROVIDER_SECRET_MANAGE),
            )
            if error:
                return self.http_status(400, -1, error)
            model = await self.ap.rerank_models_service.get_rerank_model(
                request_context,
                model_uuid,
                include_secret=include_secret,
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
            try:
                await self.ap.rerank_models_service.test_rerank_model(
                    request_context,
                    model_uuid,
                    await quart.request.json,
                )
            except provider_errors.RequesterError as exc:
                return self.http_status(400, MODEL_TEST_ERROR_CODE, str(exc))
            return self.success()
