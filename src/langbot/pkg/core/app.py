from __future__ import annotations

import logging
import asyncio
import contextlib
import traceback
import os

from ..platform import botmgr as im_mgr
from ..platform.webhook_pusher import WebhookPusher
from ..provider.session import sessionmgr as llm_session_mgr
from ..provider.modelmgr import modelmgr as llm_model_mgr
from ..box import service as box_service_module

from langbot.pkg.provider.tools import toolmgr as llm_tool_mgr
from ..config import manager as config_mgr
from ..command import cmdmgr
from ..plugin import connector as plugin_connector
from ..pipeline import pool
from ..pipeline import controller, pipelinemgr
from ..pipeline import aggregator as message_aggregator
from ..utils import version as version_mgr, proxy as proxy_mgr, httpclient
from ..persistence import mgr as persistencemgr
from ..api.http.controller import main as http_controller
from ..api.http.service import user as user_service
from ..api.http.service import space as space_service
from ..api.http.service import model as model_service
from ..api.http.service import provider as provider_service
from ..api.http.service import pipeline as pipeline_service
from ..api.http.service import bot as bot_service
from ..api.http.service import knowledge as knowledge_service
from ..api.http.service import mcp as mcp_service
from ..api.http.service import apikey as apikey_service
from ..api.http.service import webhook as webhook_service
from ..api.http.service import monitoring as monitoring_service
from ..api.http.service import skill as skill_service
from ..api.http.service import maintenance as maintenance_service
from ..discover import engine as discover_engine
from ..storage import mgr as storagemgr
from ..utils import bounded_executor, event_loop_monitor, logcache
from . import taskmgr
from . import entities as core_entities
from ..rag.knowledge import kbmgr as rag_mgr
from ..rag.service import RAGRuntimeService
from ..vector import mgr as vectordb_mgr
from ..telemetry import telemetry as telemetry_module
from ..survey import manager as survey_module
from ..skill import manager as skill_mgr
from ..workspace import service as workspace_service_module
from ..workspace import collaboration as workspace_collaboration_module
from ..workspace import invitation_delivery as invitation_delivery_module
from ..cloud import bootstrap as cloud_bootstrap_module
from ..cloud import launch as cloud_launch_module
from ..cloud import support_admin as cloud_support_admin_module
from ..cloud import directory_projection as cloud_directory_projection_module
from ..cloud import entitlements as cloud_entitlements_module
from ..api.http.context import ExecutionContext, PrincipalContext, PrincipalType


class Application:
    """Runtime application object and context"""

    event_loop: asyncio.AbstractEventLoop = None

    # asyncio_tasks: list[asyncio.Task] = []
    task_mgr: taskmgr.AsyncTaskManager = None

    discover: discover_engine.ComponentDiscoveryEngine = None

    platform_mgr: im_mgr.PlatformManager = None

    webhook_pusher: WebhookPusher = None

    cmd_mgr: cmdmgr.CommandManager = None

    sess_mgr: llm_session_mgr.SessionManager = None

    model_mgr: llm_model_mgr.ModelManager = None

    rag_mgr: rag_mgr.RAGManager = None
    rag_runtime_service: RAGRuntimeService = None

    # TODO move to pipeline
    tool_mgr: llm_tool_mgr.ToolManager = None
    box_service: box_service_module.BoxService = None

    # ======= Config manager =======

    command_cfg: config_mgr.ConfigManager = None  # deprecated

    pipeline_cfg: config_mgr.ConfigManager = None  # deprecated

    platform_cfg: config_mgr.ConfigManager = None  # deprecated

    provider_cfg: config_mgr.ConfigManager = None  # deprecated

    system_cfg: config_mgr.ConfigManager = None  # deprecated

    instance_config: config_mgr.ConfigManager = None

    instance_id: config_mgr.ConfigManager = None  # used to identify the instance

    # ======= Metadata config manager =======

    sensitive_meta: config_mgr.ConfigManager = None

    pipeline_config_meta_trigger: config_mgr.ConfigManager = None
    pipeline_config_meta_safety: config_mgr.ConfigManager = None
    pipeline_config_meta_ai: config_mgr.ConfigManager = None
    pipeline_config_meta_output: config_mgr.ConfigManager = None

    # =========================

    plugin_connector: plugin_connector.PluginRuntimeConnector = None

    query_pool: pool.QueryPool = None

    msg_aggregator: message_aggregator.MessageAggregator = None

    ctrl: controller.Controller = None

    pipeline_mgr: pipelinemgr.PipelineManager = None

    ver_mgr: version_mgr.VersionManager = None

    proxy_mgr: proxy_mgr.ProxyManager = None

    logger: logging.Logger = None

    persistence_mgr: persistencemgr.PersistenceManager = None

    workspace_service: workspace_service_module.WorkspaceService = None

    workspace_collaboration_service: workspace_collaboration_module.WorkspaceCollaborationService = None

    invitation_delivery_service: invitation_delivery_module.InvitationDeliveryService = None

    space_launch_service: cloud_launch_module.SpaceLaunchService = None

    support_admin_session_service: cloud_support_admin_module.SupportAdminSessionService = None

    deployment: cloud_bootstrap_module.OpenSourceDeployment | cloud_bootstrap_module.VerifiedCloudDeployment = None

    deployment_admission: cloud_bootstrap_module.DeploymentAdmissionGuard = None

    manifest_refresh_service: cloud_bootstrap_module.CloudManifestRefreshService | None = None

    entitlement_resolver: cloud_entitlements_module.EntitlementResolver | None = None

    directory_projection_service: cloud_directory_projection_module.DirectoryProjectionService | None = None

    vector_db_mgr: vectordb_mgr.VectorDBManager = None

    http_ctrl: http_controller.HTTPController = None

    log_cache: logcache.LogCache = None

    storage_mgr: storagemgr.StorageMgr = None

    # ========= HTTP Services =========

    user_service: user_service.UserService = None

    space_service: space_service.SpaceService = None

    llm_model_service: model_service.LLMModelsService = None

    embedding_models_service: model_service.EmbeddingModelsService = None

    rerank_models_service: model_service.RerankModelsService = None

    provider_service: provider_service.ModelProviderService = None

    pipeline_service: pipeline_service.PipelineService = None

    bot_service: bot_service.BotService = None

    knowledge_service: knowledge_service.KnowledgeService = None

    mcp_service: mcp_service.MCPService = None

    apikey_service: apikey_service.ApiKeyService = None

    webhook_service: webhook_service.WebhookService = None

    telemetry: telemetry_module.TelemetryManager = None

    survey: survey_module.SurveyManager = None

    monitoring_service: monitoring_service.MonitoringService = None

    skill_service: skill_service.SkillService = None

    skill_mgr: skill_mgr.SkillManager = None

    maintenance_service: maintenance_service.MaintenanceService = None

    blocking_executor: bounded_executor.BoundedThreadPoolExecutor | None = None
    event_loop_monitor: event_loop_monitor.EventLoopLagMonitor

    def __init__(self):
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_complete = False
        self._shutdown_task: asyncio.Task | None = None
        self.event_loop_monitor = event_loop_monitor.EventLoopLagMonitor()

    def get_runtime_resource_stats(self) -> dict[str, object]:
        """Return aggregate O(1) counters for liveness and soak validation."""

        try:
            asyncio_tasks = len(asyncio.all_tasks(self.event_loop))
        except (RuntimeError, TypeError):
            asyncio_tasks = 0

        task_stats = self.task_mgr.get_stats() if self.task_mgr is not None else {}
        query_pool_stats = {}
        if self.query_pool is not None:
            query_pool_stats = {
                'queued': len(self.query_pool.queries),
                'cached': len(self.query_pool.cached_queries),
                'active_workspaces': len(self.query_pool.active_query_count_by_workspace),
            }

        model_stats = {}
        if self.model_mgr is not None:
            model_stats = {
                'providers': len(self.model_mgr.provider_dict),
                'llms': len(self.model_mgr.llm_model_dict),
                'embeddings': len(self.model_mgr.embedding_model_dict),
                'rerankers': len(self.model_mgr.rerank_model_dict),
            }

        runtime_stats = {
            'bots': len(getattr(self.platform_mgr, '_bots_by_key', {})),
            'pipelines': len(getattr(self.pipeline_mgr, '_pipelines_by_key', {})),
            'knowledge_bases': len(getattr(self.rag_mgr, 'knowledge_bases', {})),
            'message_aggregation_buffers': len(getattr(self.msg_aggregator, 'buffers', {})),
            'message_aggregation_scopes': len(
                getattr(
                    self.msg_aggregator,
                    '_buffer_counts_by_scope',
                    {},
                )
            ),
            'plugin_installations': len(
                getattr(
                    self.plugin_connector,
                    '_known_desired_states',
                    {},
                )
            ),
        }
        mcp_loader = getattr(self.tool_mgr, 'mcp_tool_loader', None)
        runtime_stats.update(
            {
                'mcp_sessions': len(getattr(mcp_loader, '_sessions', {})),
                'mcp_host_tasks': len(getattr(mcp_loader, '_hosted_mcp_tasks', ())),
                'mcp_dispatch_tasks': len(getattr(mcp_loader, '_host_dispatch_tasks', ())),
                'mcp_projection_retirements': len(getattr(mcp_loader, '_pending_projection_retirements', ())),
                'mcp_projection_reconcile_active': int(
                    (
                        projection_task := getattr(
                            mcp_loader,
                            '_projection_reconcile_task',
                            None,
                        )
                    )
                    is not None
                    and not projection_task.done()
                ),
            }
        )

        directory_stats = {}
        directory_snapshot = getattr(self.directory_projection_service, 'resource_snapshot', None)
        if callable(directory_snapshot):
            directory_stats = directory_snapshot()

        database_stats = {}
        database_snapshot = getattr(self.persistence_mgr, 'get_resource_stats', None)
        if callable(database_snapshot):
            database_stats = database_snapshot()

        return {
            'asyncio_tasks': asyncio_tasks,
            'event_loop': self.event_loop_monitor.snapshot(),
            'blocking_executor': (self.blocking_executor.snapshot() if self.blocking_executor is not None else {}),
            'application_tasks': task_stats,
            'database_pool': database_stats,
            'directory': directory_stats,
            'query_pool': query_pool_stats,
            'models': model_stats,
            'runtimes': runtime_stats,
            'telemetry_tasks': len(getattr(self.telemetry, 'send_tasks', ())),
        }

    async def initialize(self):
        pass

    async def run(self):
        self.event_loop_monitor.start()
        try:
            if self.directory_projection_service is not None:
                self.task_mgr.create_task(
                    self.directory_projection_service.run(),
                    name='cloud-directory-projection',
                    scopes=[core_entities.LifecycleControlScope.APPLICATION],
                )
            if self.manifest_refresh_service is not None:
                self.task_mgr.create_task(
                    self.manifest_refresh_service.run(),
                    name='cloud-manifest-refresh',
                    scopes=[core_entities.LifecycleControlScope.APPLICATION],
                )
            await self.plugin_connector.initialize_plugins()

            # 后续可能会允许动态重启其他任务
            # 故为了防止程序在非 Ctrl-C 情况下退出，这里创建一个不会结束的协程
            async def never_ending():
                while True:
                    await asyncio.sleep(1)

            self.task_mgr.create_task(
                self.platform_mgr.run(),
                name='platform-manager',
                scopes=[
                    core_entities.LifecycleControlScope.APPLICATION,
                    core_entities.LifecycleControlScope.PLATFORM,
                ],
            )
            self.task_mgr.create_task(
                self.ctrl.run(),
                name='query-controller',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )
            self.task_mgr.create_task(
                self.http_ctrl.run(),
                name='http-api-controller',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )

            # Telemetry instance heartbeat (startup + daily); respects
            # space.disable_telemetry via TelemetryManager.send().
            if self.telemetry is not None:
                from ..telemetry import heartbeat as telemetry_heartbeat

                self.task_mgr.create_task(
                    telemetry_heartbeat.heartbeat_loop(self),
                    name='telemetry-heartbeat',
                    scopes=[core_entities.LifecycleControlScope.APPLICATION],
                )

            monitoring_cfg = self.instance_config.data.get('monitoring', {})
            auto_cleanup_cfg = monitoring_cfg.get('auto_cleanup', {})
            monitoring_enabled = auto_cleanup_cfg.get('enabled', True)
            retention_days = self._get_positive_int_config(
                auto_cleanup_cfg.get('retention_days', 30),
                default=30,
                name='monitoring.auto_cleanup.retention_days',
            )
            delete_batch_size = self._get_positive_int_config(
                auto_cleanup_cfg.get('delete_batch_size', 1000),
                default=1000,
                name='monitoring.auto_cleanup.delete_batch_size',
            )
            monitoring_interval_seconds = (
                self._get_positive_float_config(
                    auto_cleanup_cfg.get('check_interval_hours', 1),
                    default=1,
                    name='monitoring.auto_cleanup.check_interval_hours',
                )
                * 3600
            )

            storage_cleanup_cfg = self.instance_config.data.get('storage', {}).get('cleanup', {})
            storage_enabled = storage_cleanup_cfg.get('enabled', True) and self.maintenance_service is not None
            storage_interval_seconds = (
                self._get_positive_float_config(
                    storage_cleanup_cfg.get('check_interval_hours', 1),
                    default=1,
                    name='storage.cleanup.check_interval_hours',
                )
                * 3600
            )

            maintenance_intervals: dict[str, float] = {}
            if monitoring_enabled:
                maintenance_intervals['monitoring'] = monitoring_interval_seconds
            if storage_enabled:
                maintenance_intervals['storage'] = storage_interval_seconds
            if self.workspace_collaboration_service is not None:
                maintenance_intervals['invitations'] = 3600.0

            if maintenance_intervals:

                async def resource_maintenance_loop():
                    """Share tenant discovery and serialize periodic maintenance."""

                    loop = asyncio.get_running_loop()
                    started_at = loop.time()
                    next_due = {name: started_at + interval for name, interval in maintenance_intervals.items()}
                    while True:
                        await asyncio.sleep(max(min(next_due.values()) - loop.time(), 0.0))
                        observed_at = loop.time()
                        due = {name for name, due_at in next_due.items() if due_at <= observed_at}
                        if not due:
                            continue
                        try:
                            bindings = await self.workspace_service.list_active_execution_bindings()
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self.logger.warning(f'Resource maintenance Workspace discovery failed: {exc}')
                        else:
                            for binding in bindings:
                                context = ExecutionContext(
                                    instance_uuid=binding.instance_uuid,
                                    workspace_uuid=binding.workspace_uuid,
                                    placement_generation=binding.placement_generation,
                                    trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
                                )
                                if 'monitoring' in due:
                                    try:
                                        deleted = await self.monitoring_service.cleanup_expired_records(
                                            context,
                                            retention_days,
                                            batch_size=delete_batch_size,
                                        )
                                        total_deleted = sum(deleted.values())
                                        if total_deleted > 0:
                                            self.logger.info(
                                                f'Monitoring auto-cleanup: deleted {total_deleted} expired records '
                                                f'for Workspace {context.workspace_uuid} '
                                                f'(retention={retention_days}d): {deleted}'
                                            )
                                    except asyncio.CancelledError:
                                        raise
                                    except Exception as exc:
                                        self.logger.warning(
                                            f'Monitoring auto-cleanup failed for '
                                            f'Workspace {context.workspace_uuid}: {exc}'
                                        )
                                if 'storage' in due:
                                    try:
                                        deleted = await self.maintenance_service.cleanup_expired_files(context)
                                        total_deleted = sum(deleted.values())
                                        if total_deleted > 0:
                                            self.logger.info(
                                                f'Storage maintenance for Workspace {context.workspace_uuid}: '
                                                f'deleted expired files: {deleted}'
                                            )
                                    except asyncio.CancelledError:
                                        raise
                                    except Exception as exc:
                                        self.logger.warning(
                                            f'Storage maintenance failed for Workspace {context.workspace_uuid}: {exc}'
                                        )
                            if 'invitations' in due:
                                try:
                                    await self.workspace_collaboration_service.cleanup_expired_invitations(
                                        active_bindings=bindings,
                                    )
                                except asyncio.CancelledError:
                                    raise
                                except Exception as exc:
                                    self.logger.warning(f'Expired Workspace invitation cleanup failed: {exc}')

                        completed_at = loop.time()
                        for name in due:
                            next_due[name] = completed_at + maintenance_intervals[name]

                self.task_mgr.create_task(
                    resource_maintenance_loop(),
                    name='resource-maintenance',
                    scopes=[core_entities.LifecycleControlScope.APPLICATION],
                )

            self.task_mgr.create_task(
                never_ending(),
                name='never-ending-task',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )

            await self.print_web_access_info()
            await self.task_mgr.wait_all()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f'Application runtime fatal exception: {e}')
            self.logger.debug(f'Traceback: {traceback.format_exc()}')

    def _get_positive_int_config(self, value, default: int, name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            self.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        if parsed < 1:
            self.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        return parsed

    def _get_positive_float_config(self, value, default: float, name: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            self.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        if parsed <= 0:
            self.logger.warning(f'Invalid {name}: {value!r}, using {default}')
            return default
        return parsed

    async def shutdown(self):
        """Stop application work and deterministically release runtime resources."""
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            if self.task_mgr is not None:
                self.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.APPLICATION)
            with contextlib.suppress(Exception):
                await self.event_loop_monitor.stop()
            mcp_mount = getattr(self.http_ctrl, 'mcp_mount', None)
            if mcp_mount is not None:
                with contextlib.suppress(Exception):
                    await mcp_mount.stop_session_manager()
            if self.platform_mgr is not None:
                with contextlib.suppress(Exception):
                    await self.platform_mgr.shutdown()
            if self.tool_mgr is not None:
                with contextlib.suppress(Exception):
                    await self.tool_mgr.shutdown()
            if self.model_mgr is not None:
                with contextlib.suppress(Exception):
                    await self.model_mgr.shutdown()
            if self.box_service is not None:
                with contextlib.suppress(Exception):
                    await self.box_service.shutdown()
            if self.plugin_connector is not None:
                with contextlib.suppress(Exception):
                    await self.plugin_connector.aclose()
            if self.telemetry is not None:
                with contextlib.suppress(Exception):
                    await self.telemetry.shutdown()
            if self.vector_db_mgr is not None:
                with contextlib.suppress(Exception):
                    await self.vector_db_mgr.shutdown()
            if self.storage_mgr is not None:
                with contextlib.suppress(Exception):
                    await self.storage_mgr.shutdown()
            manifest_provider = getattr(self.deployment, 'manifest_provider', None)
            if manifest_provider is not None:
                with contextlib.suppress(Exception):
                    await manifest_provider.aclose()

            if self.task_mgr is not None:
                tasks = [wrapper.task for wrapper in self.task_mgr.tasks if not wrapper.task.done()]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(Exception):
                await httpclient.close_all()
            persistence_shutdown = getattr(self.persistence_mgr, 'shutdown', None)
            if callable(persistence_shutdown):
                with contextlib.suppress(Exception):
                    await persistence_shutdown()
            else:
                # Compatibility for lightweight test/application doubles.
                persistence_db = getattr(self.persistence_mgr, 'db', None)
                persistence_engine = getattr(persistence_db, 'engine', None)
                if persistence_engine is not None:
                    with contextlib.suppress(Exception):
                        await persistence_engine.dispose()
            self._shutdown_complete = True

    def dispose(self):
        """Compatibility wrapper for callers that cannot await shutdown."""
        if self._shutdown_complete:
            return
        loop = self.event_loop
        if loop is not None and not loop.is_closed():
            if self._shutdown_task is None or self._shutdown_task.done():
                self._shutdown_task = loop.create_task(self.shutdown())
            return
        if self.plugin_connector is not None:
            self.plugin_connector.dispose()
        if self.box_service is not None:
            self.box_service.dispose()

    async def print_web_access_info(self):
        """Print access webui tips"""

        from ..utils import paths

        frontend_path = paths.get_frontend_path()

        if not os.path.exists(frontend_path):
            self.logger.warning('WebUI 文件缺失，请根据文档部署：https://docs.langbot.app/zh')
            self.logger.warning(
                'WebUI files are missing, please deploy according to the documentation: https://docs.langbot.app/en'
            )
            return

        host_ip = '127.0.0.1'

        port = self.instance_config.data['api']['port']

        tips = f"""
=======================================
✨ Access WebUI / 访问管理面板

🏠 Local Address: http://{host_ip}:{port}/
🌐 Public Address: http://<Your Public IP>:{port}/

📌 Running this program in a container? Please ensure that the {port} port is exposed
=======================================
""".strip()
        for line in tips.split('\n'):
            self.logger.info(line)
