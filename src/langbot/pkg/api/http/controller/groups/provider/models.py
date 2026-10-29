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
        @self.route('/_/starred', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def get_starred(request_context: RequestContext) -> str:
            return self.success(
                data={'uuid': await self.call_application('model.llm.starred.get', request_context, {})}
            )

        @self.route('/_/starred', methods=['PUT'], permission=Permission.PROVIDER_SECRET_MANAGE)
        async def set_starred(request_context: RequestContext) -> str:
            body = await quart.request.json
            model_uuid = body.get('uuid')
            if model_uuid is not None and not isinstance(model_uuid, str):
                return self.http_status(400, -1, 'uuid must be a string or null')
            try:
                await self.call_application('model.llm.starred.set', request_context, {'model_uuid': model_uuid})
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={})

        @self.route('/_/default', methods=['GET'], permission=Permission.RESOURCE_MANAGE)
        async def get_default(request_context: RequestContext) -> str:
            return self.success(
                data={'uuid': await self.call_application('model.llm.default.get', request_context, {})}
            )

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
                models = await self.call_application(
                    'model.llm.list_by_provider',
                    request_context,
                    {'provider_uuid': provider_uuid, 'include_secret': include_secret},
                )
            else:
                models = await self.call_application(
                    'model.llm.list', request_context, {'include_secret': include_secret}
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
                model_uuid = await self.call_application(
                    'model.llm.create', request_context, {'model_data': await quart.request.json}
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
            model = await self.call_application(
                'model.llm.get', request_context, {'model_uuid': model_uuid, 'include_secret': include_secret}
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
                await self.call_application(
                    'model.llm.update', request_context, {'model_uuid': model_uuid, 'model_data': json_data}
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            changes = quart.g.operation_log_changes
            rule = settings_service.ACTION_RULES_BY_ACTION.get('update')
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
            await self.call_application('model.llm.delete', request_context, {'model_uuid': model_uuid})
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.call_application(
                    'model.llm.test',
                    request_context,
                    {'model_uuid': model_uuid, 'model_data': await quart.request.json},
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
                models = await self.call_application(
                    'model.embedding.list_by_provider',
                    request_context,
                    {'provider_uuid': provider_uuid, 'include_secret': include_secret},
                )
            else:
                models = await self.call_application(
                    'model.embedding.list', request_context, {'include_secret': include_secret}
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
                model_uuid = await self.call_application(
                    'model.embedding.create', request_context, {'model_data': await quart.request.json}
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
            model = await self.call_application(
                'model.embedding.get', request_context, {'model_uuid': model_uuid, 'include_secret': include_secret}
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
                await self.call_application(
                    'model.embedding.update',
                    request_context,
                    {'model_uuid': model_uuid, 'model_data': await quart.request.json},
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
            await self.call_application('model.embedding.delete', request_context, {'model_uuid': model_uuid})
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.call_application(
                    'model.embedding.test',
                    request_context,
                    {'model_uuid': model_uuid, 'model_data': await quart.request.json},
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
                models = await self.call_application(
                    'model.rerank.list_by_provider',
                    request_context,
                    {'provider_uuid': provider_uuid, 'include_secret': include_secret},
                )
            else:
                models = await self.call_application(
                    'model.rerank.list', request_context, {'include_secret': include_secret}
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
                model_uuid = await self.call_application(
                    'model.rerank.create', request_context, {'model_data': await quart.request.json}
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
            model = await self.call_application(
                'model.rerank.get', request_context, {'model_uuid': model_uuid, 'include_secret': include_secret}
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
                await self.call_application(
                    'model.rerank.update',
                    request_context,
                    {'model_uuid': model_uuid, 'model_data': await quart.request.json},
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
            await self.call_application('model.rerank.delete', request_context, {'model_uuid': model_uuid})
            return self.success()

        @self.route(
            '/<model_uuid>/test',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.PROVIDER_SECRET_MANAGE,
        )
        async def _(model_uuid: str, request_context: RequestContext) -> str:
            try:
                await self.call_application(
                    'model.rerank.test',
                    request_context,
                    {'model_uuid': model_uuid, 'model_data': await quart.request.json},
                )
            except provider_errors.RequesterError as exc:
                return self.http_status(400, MODEL_TEST_ERROR_CODE, str(exc))
            return self.success()
