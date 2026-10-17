import quart
from urllib.parse import unquote

from .....application import (
    ApplicationAPI,
    ApplicationAPIException,
    KnowledgeEngineListInput,
    KnowledgeEngineSchemaInput,
)
from ....authz import Permission
from ....context import RequestContext
from ... import group


def _application_api(ap) -> ApplicationAPI:
    application_api = getattr(ap, 'application_api', None)
    return application_api if isinstance(application_api, ApplicationAPI) else ApplicationAPI(ap)


@group.group_class('knowledge_engines', '/api/v1/knowledge/engines')
class KnowledgeEnginesRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def list_knowledge_engines(request_context: RequestContext) -> quart.Response:
            """List all available Knowledge Engines from plugins.

            Returns a list of Knowledge Engines with their capabilities and configuration schemas.
            This is used by the frontend to render the knowledge base creation wizard.
            """
            try:
                output = await _application_api(self.ap).execute(
                    'knowledge.engine.list',
                    request_context,
                    KnowledgeEngineListInput(),
                )
            except ApplicationAPIException as exc:
                return self.http_status(exc.error.status_code, exc.error.code, exc.error.message)
            return self.success(data={'engines': output.engines})

        @self.route(
            '/<path:plugin_id>/creation-schema',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_engine_creation_schema(
            plugin_id: str,
            request_context: RequestContext,
        ) -> quart.Response:
            """Get creation settings schema for a specific Knowledge Engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            if '/' not in plugin_id:
                return self.http_status(400, -1, 'Invalid plugin_id format. Expected author/name.')
            try:
                output = await _application_api(self.ap).execute(
                    'knowledge.engine.schema.get',
                    request_context,
                    KnowledgeEngineSchemaInput(plugin_id=plugin_id, kind='creation'),
                )
            except ApplicationAPIException as exc:
                return self.http_status(exc.error.status_code, exc.error.code, exc.error.message)
            schema = output.schema
            return self.success(data={'schema': schema})

        @self.route(
            '/<path:plugin_id>/retrieval-schema',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def get_engine_retrieval_schema(
            plugin_id: str,
            request_context: RequestContext,
        ) -> quart.Response:
            """Get retrieval settings schema for a specific Knowledge Engine.

            plugin_id is in 'author/name' format, captured via <path:> converter.
            """
            plugin_id = unquote(plugin_id)
            if '/' not in plugin_id:
                return self.http_status(400, -1, 'Invalid plugin_id format. Expected author/name.')
            try:
                output = await _application_api(self.ap).execute(
                    'knowledge.engine.schema.get',
                    request_context,
                    KnowledgeEngineSchemaInput(plugin_id=plugin_id, kind='retrieval'),
                )
            except ApplicationAPIException as exc:
                return self.http_status(exc.error.status_code, exc.error.code, exc.error.message)
            schema = output.schema
            return self.success(data={'schema': schema})
