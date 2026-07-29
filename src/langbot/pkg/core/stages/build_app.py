from __future__ import annotations

from .. import stage, app
from ...utils import version, proxy, constants
from ...pipeline import pool, controller, pipelinemgr
from ...pipeline import aggregator as message_aggregator
from ...box import service as box_service
from ...plugin import connector as plugin_connector
from ...command import cmdmgr
from ...provider.session import sessionmgr as llm_session_mgr
from ...provider.modelmgr import modelmgr as llm_model_mgr
from ...provider.tools import toolmgr as llm_tool_mgr
from ...rag.knowledge import kbmgr as rag_mgr
from ...rag.service import RAGRuntimeService
from ...platform import botmgr as im_mgr
from ...platform.webhook_pusher import WebhookPusher
from ...persistence import mgr as persistencemgr
from ...api.http.controller import main as http_controller
from ...api.http.service import user as user_service
from ...api.http.service import space as space_service
from ...api.http.service import model as model_service
from ...api.http.service import provider as provider_service
from ...api.http.service import pipeline as pipeline_service
from ...api.http.service import bot as bot_service
from ...api.http.service import knowledge as knowledge_service
from ...api.http.service import mcp as mcp_service
from ...api.http.service import apikey as apikey_service
from ...api.http.service import webhook as webhook_service
from ...api.http.service import monitoring as monitoring_service
from ...api.http.service import skill as skill_service
from ...skill import manager as skill_mgr
from ...api.http.service import maintenance as maintenance_service
from ...discover import engine as discover_engine
from ...storage import mgr as storagemgr
from ...utils import logcache
from ...vector import mgr as vectordb_mgr
from .. import taskmgr
from ...telemetry import telemetry as telemetry_module
from ...survey import manager as survey_module
from ...workspace import service as workspace_service_module
from ...workspace import collaboration as workspace_collaboration_module
from ...workspace import invitation_delivery as invitation_delivery_module
from ...cloud import bootstrap as cloud_bootstrap
from ...cloud import launch as cloud_launch_module
from ...cloud.directory import directory_projection_limits_from_config
from ...cloud.directory_projection import DirectoryProjectionService
from ...cloud.entitlements import EntitlementResolver
from ...api.http.context import ExecutionContext, PrincipalContext, PrincipalType
from ...api.http.authz import WorkspaceRequiredError


@stage.stage_class('BuildAppStage')
class BuildAppStage(stage.BootingStage):
    """Build LangBot application"""

    async def run(self, ap: app.Application):
        """Build LangBot application"""
        # Multi-Workspace mode is selected only by an installed closed
        # bootstrap that returns a verified Manifest receipt. Mutable values
        # such as system.edition are intentionally absent from this boundary.
        deployment = await cloud_bootstrap.resolve_deployment(
            instance_uuid=constants.instance_id,
            instance_config=ap.instance_config.data,
        )
        ap.deployment = deployment
        ap.deployment_admission = cloud_bootstrap.DeploymentAdmissionGuard(
            constants.instance_id,
            deployment,
        )
        ap.manifest_refresh_service = (
            cloud_bootstrap.CloudManifestRefreshService(
                ap.deployment_admission,
                deployment.manifest_provider,
                ap.logger,
            )
            if deployment.multi_workspace_enabled
            else None
        )
        ap.entitlement_resolver = (
            EntitlementResolver(
                constants.instance_id,
                deployment.entitlement_provider,
                deployment_admission=ap.deployment_admission.require_active,
            )
            if deployment.multi_workspace_enabled
            else None
        )

        ap.task_mgr = taskmgr.AsyncTaskManager(ap)

        discover = discover_engine.ComponentDiscoveryEngine(ap)
        discover.discover_blueprint('templates/components.yaml')
        ap.discover = discover

        space_service_inst = space_service.SpaceService(ap)
        ap.space_service = space_service_inst

        llm_model_service_inst = model_service.LLMModelsService(ap)
        ap.llm_model_service = llm_model_service_inst

        embedding_models_service_inst = model_service.EmbeddingModelsService(ap)
        ap.embedding_models_service = embedding_models_service_inst

        rerank_models_service_inst = model_service.RerankModelsService(ap)
        ap.rerank_models_service = rerank_models_service_inst

        provider_service_inst = provider_service.ModelProviderService(ap)
        ap.provider_service = provider_service_inst

        pipeline_service_inst = pipeline_service.PipelineService(ap)
        ap.pipeline_service = pipeline_service_inst

        bot_service_inst = bot_service.BotService(ap)
        ap.bot_service = bot_service_inst

        knowledge_service_inst = knowledge_service.KnowledgeService(ap)
        ap.knowledge_service = knowledge_service_inst

        mcp_service_inst = mcp_service.MCPService(ap)
        ap.mcp_service = mcp_service_inst

        apikey_service_inst = apikey_service.ApiKeyService(ap)
        ap.apikey_service = apikey_service_inst

        webhook_service_inst = webhook_service.WebhookService(ap)
        ap.webhook_service = webhook_service_inst

        skill_service_inst = skill_service.SkillService(ap)
        ap.skill_service = skill_service_inst

        proxy_mgr = proxy.ProxyManager(ap)
        await proxy_mgr.initialize()
        ap.proxy_mgr = proxy_mgr

        ver_mgr = version.VersionManager(ap)
        await ver_mgr.initialize()
        ap.ver_mgr = ver_mgr

        log_cache = logcache.LogCache()
        ap.log_cache = log_cache

        storage_mgr_inst = storagemgr.StorageMgr(ap)
        ap.storage_mgr = storage_mgr_inst
        await storage_mgr_inst.initialize()

        persistence_mgr_inst = persistencemgr.PersistenceManager(
            ap,
            mode=persistencemgr.PersistenceMode(deployment.persistence_mode),
        )
        ap.persistence_mgr = persistence_mgr_inst
        await persistence_mgr_inst.initialize()

        if deployment.multi_workspace_enabled:
            directory_projection_service = DirectoryProjectionService(
                ap,
                deployment.directory_provider,
                constants.instance_id,
                limits=directory_projection_limits_from_config(ap.instance_config.data),
            )
            await directory_projection_service.initialize()
            ap.directory_projection_service = directory_projection_service

        workspace_policy = deployment.workspace_policy
        workspace_service_inst = workspace_service_module.WorkspaceService(
            ap,
            policy=workspace_policy,
        )
        if not workspace_policy.multi_workspace_enabled:
            await workspace_service_inst.ensure_singleton_workspace()
        ap.workspace_service = workspace_service_inst
        if workspace_policy.multi_workspace_enabled:
            # Directory refresh starts in Application.run(), after this serial
            # build graph. Share one validated immutable binding snapshot
            # across model/platform/pipeline/RAG/plugin initialization instead
            # of repeating tenant validation for every manager.
            await workspace_service_inst.prime_startup_execution_bindings()

        ap.workspace_collaboration_service = workspace_collaboration_module.WorkspaceCollaborationService(
            ap,
            workspace_service_inst,
        )
        ap.invitation_delivery_service = invitation_delivery_module.InvitationDeliveryService(ap)
        ap.space_launch_service = cloud_launch_module.SpaceLaunchService(ap)

        user_service_inst = user_service.UserService(ap)
        ap.user_service = user_service_inst

        async def resolve_singleton_execution_context() -> ExecutionContext:
            if workspace_policy.multi_workspace_enabled:
                raise WorkspaceRequiredError('Cloud runtime work requires an explicit Workspace context')
            binding = await workspace_service_inst.get_local_execution_binding()
            return ExecutionContext(
                instance_uuid=binding.instance_uuid,
                workspace_uuid=binding.workspace_uuid,
                placement_generation=binding.placement_generation,
                trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
            )

        concurrency_config = ap.instance_config.data.get('concurrency', {})
        ap.query_pool = pool.QueryPool(
            singleton_context_resolver=resolve_singleton_execution_context,
            max_queries=int(concurrency_config.get('pending_queries', 1000)),
            max_queries_per_workspace=int(concurrency_config.get('pending_queries_per_workspace', 100)),
        )

        # Telemetry manager: attach to app so other components can call via self.ap.telemetry
        telemetry_inst = telemetry_module.TelemetryManager(ap)
        ap.telemetry = telemetry_inst
        await telemetry_inst.initialize()

        # Survey manager
        survey_inst = survey_module.SurveyManager(ap)
        await survey_inst.initialize()
        ap.survey = survey_inst

        cmd_mgr_inst = cmdmgr.CommandManager(ap)
        await cmd_mgr_inst.initialize()
        ap.cmd_mgr = cmd_mgr_inst

        llm_model_mgr_inst = llm_model_mgr.ModelManager(ap)
        ap.model_mgr = llm_model_mgr_inst
        await llm_model_mgr_inst.initialize()

        llm_session_mgr_inst = llm_session_mgr.SessionManager(ap)
        await llm_session_mgr_inst.initialize()
        ap.sess_mgr = llm_session_mgr_inst

        box_service_inst = box_service.BoxService(ap)
        ap.box_service = box_service_inst
        await box_service_inst.initialize()

        llm_tool_mgr_inst = llm_tool_mgr.ToolManager(ap)
        ap.tool_mgr = llm_tool_mgr_inst
        await llm_tool_mgr_inst.initialize()

        im_mgr_inst = im_mgr.PlatformManager(ap=ap)
        ap.platform_mgr = im_mgr_inst
        await im_mgr_inst.initialize()

        # Initialize webhook pusher
        webhook_pusher_inst = WebhookPusher(ap)
        ap.webhook_pusher = webhook_pusher_inst

        pipeline_mgr = pipelinemgr.PipelineManager(ap)
        await pipeline_mgr.initialize()
        ap.pipeline_mgr = pipeline_mgr

        # Initialize message aggregator (after pipeline_mgr, as it needs pipeline config)
        msg_aggregator_inst = message_aggregator.MessageAggregator(ap)
        ap.msg_aggregator = msg_aggregator_inst

        # Initialize skill manager
        skill_mgr_inst = skill_mgr.SkillManager(ap)
        await skill_mgr_inst.initialize()
        ap.skill_mgr = skill_mgr_inst

        rag_mgr_inst = rag_mgr.RAGManager(ap)
        await rag_mgr_inst.initialize()
        ap.rag_mgr = rag_mgr_inst

        # Initialize RAG Runtime Service for plugins
        ap.rag_runtime_service = RAGRuntimeService(ap)

        # 初始化向量数据库管理器
        vectordb_mgr_inst = vectordb_mgr.VectorDBManager(ap)
        ap.vector_db_mgr = vectordb_mgr_inst
        await vectordb_mgr_inst.initialize()

        http_ctrl = http_controller.HTTPController(ap)
        ap.http_ctrl = http_ctrl
        await http_ctrl.initialize()

        monitoring_service_inst = monitoring_service.MonitoringService(ap)
        ap.monitoring_service = monitoring_service_inst

        maintenance_service_inst = maintenance_service.MaintenanceService(ap)
        ap.maintenance_service = maintenance_service_inst

        async def runtime_disconnect_callback(connector: plugin_connector.PluginRuntimeConnector) -> None:
            connector.schedule_reconnect()

        plugin_connector_inst = plugin_connector.PluginRuntimeConnector(ap, runtime_disconnect_callback)
        try:
            await plugin_connector_inst.initialize()
        except Exception as exc:
            # Keep the API/UI available while an external or managed runtime is
            # starting, then recover in the background with bounded backoff.
            ap.logger.warning(f'Plugin runtime unavailable during startup; reconnecting in background: {exc}')
            plugin_connector_inst.schedule_reconnect()
        ap.plugin_connector = plugin_connector_inst
        workspace_service_inst.release_startup_execution_bindings()

        ctrl = controller.Controller(ap)
        ap.ctrl = ctrl
