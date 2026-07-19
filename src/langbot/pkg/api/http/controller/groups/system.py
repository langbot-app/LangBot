import json

import quart
import sqlalchemy

from .. import group
from .....utils import constants
from .....entity.persistence.metadata import WorkspaceMetadata
from ...authz import Permission
from ...context import RequestContext
from .....provider.tools.loaders.mcp_policy import stdio_mcp_enabled


@group.group_class('system', '/api/v1/system')
class SystemRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
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
                        result = await self.ap.persistence_mgr.execute_async(
                            sqlalchemy.select(WorkspaceMetadata).where(
                                WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                                WorkspaceMetadata.key.in_(['wizard_status', 'wizard_progress']),
                            )
                        )
                        for row in result:
                            if row.key == 'wizard_status':
                                wizard_status = row.value
                            elif row.key == 'wizard_progress':
                                try:
                                    wizard_progress = json.loads(row.value)
                                except (json.JSONDecodeError, TypeError):
                                    wizard_progress = None
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

            return self.success(
                data={
                    'version': constants.semantic_version,
                    'debug': constants.debug_mode,
                    'edition': constants.edition,
                    'enable_marketplace': self.ap.instance_config.data.get('plugin', {}).get(
                        'enable_marketplace', True
                    ),
                    'cloud_service_url': (
                        self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app')
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
            """Mark wizard status in metadata table and clear progress.

            Accepts JSON body: { "status": "skipped" | "completed" }
            """
            data = await quart.request.get_json(silent=True) or {}
            status = data.get('status', 'completed')
            if status not in ('skipped', 'completed'):
                return self.http_status(400, 400, f'Invalid wizard status: {status}')

            try:
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(WorkspaceMetadata).where(
                        WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                        WorkspaceMetadata.key == 'wizard_status',
                    )
                )
                if result.first():
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.update(WorkspaceMetadata)
                        .where(
                            WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                            WorkspaceMetadata.key == 'wizard_status',
                        )
                        .values(value=status)
                    )
                else:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.insert(WorkspaceMetadata).values(
                            workspace_uuid=request_context.workspace_uuid,
                            key='wizard_status',
                            value=status,
                        )
                    )

                # Clear wizard progress when wizard is completed/skipped
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.delete(WorkspaceMetadata).where(
                        WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                        WorkspaceMetadata.key == 'wizard_progress',
                    )
                )
            except Exception:
                raise

            return self.success(data={})

        @self.route(
            '/wizard/progress',
            methods=['PUT'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.WORKSPACE_UPDATE,
        )
        async def _(request_context: RequestContext) -> str:
            """Save wizard progress to metadata table.

            Accepts JSON body with wizard state fields:
            { "step": int, "selected_adapter": str|null, "created_bot_uuid": str|null,
              "bot_saved": bool, "selected_runner": str|null }
            """
            data = await quart.request.get_json(silent=True) or {}
            progress_json = json.dumps(data, ensure_ascii=False)

            try:
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(WorkspaceMetadata).where(
                        WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                        WorkspaceMetadata.key == 'wizard_progress',
                    )
                )
                if result.first():
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.update(WorkspaceMetadata)
                        .where(
                            WorkspaceMetadata.workspace_uuid == request_context.workspace_uuid,
                            WorkspaceMetadata.key == 'wizard_progress',
                        )
                        .values(value=progress_json)
                    )
                else:
                    await self.ap.persistence_mgr.execute_async(
                        sqlalchemy.insert(WorkspaceMetadata).values(
                            workspace_uuid=request_context.workspace_uuid,
                            key='wizard_progress',
                            value=progress_json,
                        )
                    )
            except Exception:
                raise

            return self.success(data={})

        @self.route(
            '/tasks',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            task_type = quart.request.args.get('type')
            task_kind = quart.request.args.get('kind')

            if task_type == '':
                task_type = None
            if task_kind == '':
                task_kind = None

            return self.success(
                data=self.ap.task_mgr.get_tasks_dict(
                    task_type,
                    task_kind,
                    instance_uuid=request_context.instance_uuid,
                    workspace_uuid=request_context.workspace_uuid,
                    placement_generation=request_context.placement_generation,
                )
            )

        @self.route(
            '/tasks/<task_id>',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(task_id: str, request_context: RequestContext) -> str:
            task = self.ap.task_mgr.get_task_by_id(
                int(task_id),
                instance_uuid=request_context.instance_uuid,
                workspace_uuid=request_context.workspace_uuid,
                placement_generation=request_context.placement_generation,
            )

            if task is None:
                return self.http_status(404, 404, 'Task not found')

            return self.success(data=task.to_dict())

        @self.route(
            '/storage-analysis',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.ap.maintenance_service.get_storage_analysis(request_context))

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
            await self.ap.plugin_connector.require_workspace_context(request_context)
            plugin_connector_error = 'ok'
            is_connected = True

            try:
                await self.ap.plugin_connector.ping_plugin_runtime()
            except Exception as e:
                plugin_connector_error = str(e)
                is_connected = False

            return self.success(
                data={
                    'is_enable': self.ap.plugin_connector.is_enable_plugin,
                    'is_connected': is_connected,
                    'plugin_connector_error': plugin_connector_error,
                }
            )
