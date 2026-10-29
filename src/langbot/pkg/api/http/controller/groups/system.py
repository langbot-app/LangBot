import quart

from .. import group
from .....utils import constants
from .....cloud.banner import resolve_cloud_banner
from ...authz import Permission
from ...context import RequestContext
from .....provider.tools.loaders.mcp_policy import stdio_mcp_enabled
from .....workspace.invitation_delivery import InvitationDeliveryService


SYSTEM_CAPABILITY_OPERATIONS = (
    'knowledge_engine.list',
    'knowledge_engine.creation_schema',
    'knowledge_engine.retrieval_schema',
    'knowledge_parser.list',
    'pipeline.extensions.get',
    'pipeline.extensions.update',
    'pipeline.run',
    'monitoring.messages',
    'monitoring.llm_calls',
    'monitoring.tool_calls',
    'monitoring.embedding_calls',
    'monitoring.sessions',
    'monitoring.errors',
    'monitoring.message_details',
    'monitoring.session_analysis',
    'sandbox.status',
    'sandbox.sessions',
    'sandbox.errors',
    'bot.list',
    'bot.get',
    'bot.create',
    'bot.update',
    'bot.delete',
    'pipeline.list',
    'pipeline.get',
    'pipeline.create',
    'pipeline.update',
    'pipeline.delete',
    'pipeline.copy',
    'task.list',
    'task.get',
    'knowledge_base.list',
    'knowledge_base.get',
    'knowledge_base.create',
    'knowledge_base.update',
    'knowledge_base.delete',
    'knowledge_base.file.list',
    'knowledge_base.file.store',
    'knowledge_base.file.delete',
    'knowledge_base.retrieve',
    'file.document.upload',
    'plugin.install.github',
    'plugin.install.marketplace',
    'plugin.install.local',
    'plugin.upgrade',
    'plugin.space_upload',
    'plugin.get',
    'plugin.list',
    'plugin.config.get',
    'plugin.config.update',
    'plugin.logs',
    'plugin.delete',
    'provider.list',
    'provider.get',
    'provider.create',
    'provider.update',
    'provider.delete',
    'provider.scan_models',
    'model.llm.list',
    'model.llm.get',
    'model.llm.create',
    'model.llm.update',
    'model.llm.delete',
    'model.llm.test',
    'model.embedding.list',
    'model.embedding.get',
    'model.embedding.create',
    'model.embedding.update',
    'model.embedding.delete',
    'model.embedding.test',
    'model.rerank.list',
    'model.rerank.get',
    'model.rerank.create',
    'model.rerank.update',
    'model.rerank.delete',
    'model.rerank.test',
    'skill.list',
    'skill.get',
    'skill.create',
    'skill.update',
    'skill.delete',
    'skill.files.list',
    'skill.files.read',
    'skill.files.write',
    'skill.preview',
    'skill.install.github',
    'skill.install.upload',
    'mcp_server.list',
    'mcp_server.get',
    'mcp_server.create',
    'mcp_server.update',
    'mcp_server.delete',
    'mcp_server.resources',
    'mcp_server.resource_templates',
    'mcp_server.resource_read',
    'mcp_server.logs',
    'mcp_server.test',
)


@group.group_class('system', '/api/v1/system')
class SystemRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/context', methods=['GET'], auth_type=group.AuthType.API_KEY)
        async def _(request_context: RequestContext) -> str:
            return self.success(
                data={
                    'instance_uuid': request_context.instance_uuid,
                    'workspace_uuid': request_context.workspace_uuid,
                    'api_key_id': request_context.principal.api_key_uuid,
                    'permissions': sorted(request_context.workspace.permissions),
                }
            )

        @self.route('/capabilities', methods=['GET'], auth_type=group.AuthType.API_KEY)
        async def _() -> str:
            return self.success(
                data={
                    'schema_version': 1,
                    'operations': {operation: {'supported': True} for operation in SYSTEM_CAPABILITY_OPERATIONS},
                }
            )

        @self.route('/info', methods=['GET'], auth_type=group.AuthType.NONE)
        async def _() -> str:
            # Read wizard_status and wizard_progress from metadata table
            wizard_status = 'none'
            wizard_progress = None
            try:
                authorization = quart.request.headers.get('Authorization', '')
                if authorization.startswith('Bearer '):
                    account, _ = await self._authenticate_account(authorization.removeprefix('Bearer '))
                    request_context = await self._resolve_account_context(account, group.AuthType.USER_TOKEN)
                    if request_context is not None:
                        wizard = await self.call_application('system.wizard.get', request_context, {})
                        wizard_status = wizard['status'] or 'none'
                        wizard_progress = wizard['progress']
            except Exception:
                pass

            # ``system.outbound_ips`` may be a comma-separated string instead of
            # a list when injected via the SYSTEM__OUTBOUND_IPS env var into a
            # pre-existing data/config.yaml that lacks the key (env overrides
            # only coerce to list when the key already holds one).
            outbound_ips = self.ap.instance_config.data.get('system', {}).get('outbound_ips', [])
            if isinstance(outbound_ips, str):
                outbound_ips = [ip.strip() for ip in outbound_ips.split(',') if ip.strip()]
            elif isinstance(outbound_ips, list):
                outbound_ips = [str(ip).strip() for ip in outbound_ips if str(ip).strip()]
            else:
                outbound_ips = []

            invitation_delivery_service = getattr(self.ap, 'invitation_delivery_service', None)
            if invitation_delivery_service is None:
                invitation_delivery_service = InvitationDeliveryService(self.ap)

            # Release channel is independent of diagnostics or usage telemetry.
            from packaging.version import Version, InvalidVersion

            try:
                release = Version(constants.semantic_version)
                is_beta = bool(release.pre and release.pre[0] == 'b' and not release.local)
            except InvalidVersion:
                is_beta = False

            # Detect Cloud deployment mode
            is_cloud = getattr(getattr(self.ap, 'deployment', None), 'mode', 'oss') == 'cloud'

            return self.success(
                data={
                    'version': constants.semantic_version,
                    'debug': constants.debug_mode,
                    'edition': constants.edition,
                    'beta': is_beta,
                    'deployment_mode': 'cloud' if is_cloud else 'oss',
                    # Cloud-only instance notice. None on OSS deployments so a
                    # self-hosted copy of config.yaml can never surface it.
                    'cloud_banner': resolve_cloud_banner(self.ap),
                    'enable_marketplace': self.ap.instance_config.data.get('plugin', {}).get(
                        'enable_marketplace', True
                    ),
                    'cloud_service_url': (
                        self.ap.instance_config.data.get('space', {}).get(
                            'web_url',
                            self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app'),
                        )
                    ),
                    'allow_modify_login_info': self.ap.instance_config.data.get('system', {}).get(
                        'allow_modify_login_info', True
                    ),
                    'disable_models_service': self.ap.instance_config.data.get('space', {}).get(
                        'disable_models_service', False
                    ),
                    # Exposed independently of Box status so the WebUI cannot
                    # infer stdio permission from sandbox availability.
                    'mcp_stdio_enabled': stdio_mcp_enabled(self.ap),
                    'limitation': self.ap.instance_config.data.get('system', {}).get('limitation', {}),
                    'outbound_ips': outbound_ips,
                    'invitation_delivery': invitation_delivery_service.capability(),
                    'wizard_status': wizard_status,
                    'wizard_progress': wizard_progress,
                }
            )

        @self.route(
            '/wizard/completed',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.WORKSPACE_UPDATE,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.get_json(silent=True) or {}
            status = data.get('status', 'completed')
            if status not in ('skipped', 'completed'):
                return self.http_status(400, 400, f'Invalid wizard status: {status}')
            await self.call_application('system.wizard.complete', request_context, {'status': status})
            return self.success(data={})

        @self.route(
            '/wizard/progress',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.WORKSPACE_UPDATE,
        )
        async def _(request_context: RequestContext) -> str:
            data = await quart.request.get_json(silent=True) or {}
            await self.call_application('system.wizard.progress.update', request_context, data)
            return self.success(data={})

        @self.route(
            '/wizard/recommended-model',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(request_context: RequestContext) -> str:
            """Resolve Space's best available chat model to this Workspace."""
            try:
                model = await self.call_application('system.model.recommended', request_context, {})
            except ValueError as exc:
                return self.http_status(503, -1, str(exc))
            return self.success(data=model)

        @self.route(
            '/model-availability',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            """Expose Space's latest persisted model probes to the WebUI."""
            try:
                models = await self.call_application('system.model.availability', request_context, {})
            except Exception as exc:
                self.ap.logger.warning(f'Failed to load LangBot Models availability: {exc}')
                return self.http_status(503, -1, 'Model availability is unavailable')
            return self.success(data={'models': models})

        @self.route(
            '/tasks',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(
                data=await self.call_application(
                    'task.list',
                    request_context,
                    {
                        'task_type': quart.request.args.get('type') or None,
                        'task_kind': quart.request.args.get('kind') or None,
                    },
                )
            )

        @self.route(
            '/tasks/<task_id>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN_OR_API_KEY,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(task_id: str, request_context: RequestContext) -> str:
            try:
                task_index = int(task_id)
                if task_index < 0:
                    return self.http_status(404, 404, 'Task not found')
                task = await self.call_application('task.get', request_context, {'task_id': task_index})
            except (TypeError, ValueError, FileNotFoundError):
                return self.http_status(404, 404, 'Task not found')
            return self.success(data=task)

        @self.route(
            '/storage-analysis',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.call_application('system.storage.analysis', request_context, {}))

        @self.route(
            '/debug/plugin/action',
            methods=['POST'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RUNTIME_OPERATE,
        )
        async def _(request_context: RequestContext) -> str:
            if not constants.debug_mode:
                return self.http_status(403, 403, 'Forbidden')

            await self.ap.plugin_connector.require_workspace_context(request_context)

            data = await quart.request.json

            class AnoymousAction:
                value = 'anonymous_action'

                def __init__(self, value: str):
                    self.value = value

            resp = await self.ap.plugin_connector.handler.call_action(
                AnoymousAction(data['action']),
                data['data'],
                timeout=data.get('timeout', 10),
                action_context=self.ap.plugin_connector.handler.require_bound_action_context().without_installation(),
            )

            return self.success(data=resp)

        @self.route(
            '/status/plugin-system',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.call_application('system.plugin.status', request_context, {}))
