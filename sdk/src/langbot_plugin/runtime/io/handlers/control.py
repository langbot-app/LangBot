# handle connection from LangBot
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

from langbot_plugin.runtime.io import connection, handler
from langbot_plugin.entities.io.context import (
    ActionContext,
    ActionEnvelopeContext,
    ApplyPluginInstallationRequest,
    InstallationBinding,
    ReconcilePluginInstallationsRequest,
    RemovePluginInstallationRequest,
    RuntimeConfig,
)
from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    LangBotToRuntimeAction,
)
from langbot_plugin.runtime import context as context_module
from langbot_plugin.api.entities.context import EventContext
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.runtime.plugin import mgr as plugin_mgr_module
from langbot_plugin.runtime.io.handler import FILE_STORAGE_DIR
from langbot_plugin.storage import collect_storage_directories, storage_total_bytes

logger = logging.getLogger(__name__)


INSTANCE_SCOPED_CONTROL_ACTIONS = frozenset(
    {
        LangBotToRuntimeAction.RECONCILE_PLUGIN_INSTALLATIONS.value,
        LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value,
        LangBotToRuntimeAction.GET_STORAGE_ANALYSIS.value,
    }
)

# Keep this list explicit. The action-consistency test requires every newly
# added LangBot-to-Runtime action to choose a scope before it can ship.
TENANT_SCOPED_CONTROL_ACTIONS = frozenset(
    {
        LangBotToRuntimeAction.GET_DEBUG_INFO.value,
        LangBotToRuntimeAction.LIST_PLUGINS.value,
        LangBotToRuntimeAction.GET_PLUGIN_INFO.value,
        LangBotToRuntimeAction.GET_PLUGIN_ICON.value,
        LangBotToRuntimeAction.GET_PLUGIN_README.value,
        LangBotToRuntimeAction.GET_PLUGIN_LOGS.value,
        LangBotToRuntimeAction.GET_PLUGIN_ASSETS_FILE.value,
        LangBotToRuntimeAction.INSTALL_PLUGIN.value,
        LangBotToRuntimeAction.RESTART_PLUGIN.value,
        LangBotToRuntimeAction.DELETE_PLUGIN.value,
        LangBotToRuntimeAction.UPGRADE_PLUGIN.value,
        LangBotToRuntimeAction.EMIT_EVENT.value,
        LangBotToRuntimeAction.PLUGIN_DIAGNOSTIC.value,
        LangBotToRuntimeAction.LIST_TOOLS.value,
        LangBotToRuntimeAction.CALL_TOOL.value,
        LangBotToRuntimeAction.LIST_COMMANDS.value,
        LangBotToRuntimeAction.EXECUTE_COMMAND.value,
        LangBotToRuntimeAction.RETRIEVE_KNOWLEDGE.value,
        LangBotToRuntimeAction.LIST_KNOWLEDGE_ENGINES.value,
        LangBotToRuntimeAction.RAG_INGEST_DOCUMENT.value,
        LangBotToRuntimeAction.RAG_DELETE_DOCUMENT.value,
        LangBotToRuntimeAction.RAG_ON_KB_CREATE.value,
        LangBotToRuntimeAction.RAG_ON_KB_DELETE.value,
        LangBotToRuntimeAction.GET_RAG_CREATION_SETTINGS_SCHEMA.value,
        LangBotToRuntimeAction.GET_RAG_RETRIEVAL_SETTINGS_SCHEMA.value,
        LangBotToRuntimeAction.LIST_PARSERS.value,
        LangBotToRuntimeAction.PARSE_DOCUMENT.value,
        LangBotToRuntimeAction.PAGE_API.value,
        LangBotToRuntimeAction.BUILD_PLUGIN_PACKAGE.value,
        LangBotToRuntimeAction.GIT_SYNC_PLUGIN.value,
        LangBotToRuntimeAction.LIST_RUNNERS.value,
        LangBotToRuntimeAction.RUN_RUNNER.value,
        LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION.value,
        LangBotToRuntimeAction.REMOVE_PLUGIN_INSTALLATION.value,
    }
)

# These actions operate on the historical global ``data/plugins`` tree and
# may install dependencies into the Runtime interpreter. They remain an OSS
# compatibility surface only; shared installations must use desired state.
LEGACY_OSS_PLUGIN_LIFECYCLE_ACTIONS = frozenset(
    {
        LangBotToRuntimeAction.INSTALL_PLUGIN.value,
        LangBotToRuntimeAction.RESTART_PLUGIN.value,
        LangBotToRuntimeAction.DELETE_PLUGIN.value,
        LangBotToRuntimeAction.UPGRADE_PLUGIN.value,
    }
)


class ControlConnectionHandler(handler.Handler):
    """The handler for control connection."""

    context: context_module.RuntimeContext

    def __init__(
        self, connection: connection.Connection, context: context_module.RuntimeContext
    ):
        super().__init__(connection, cancel_active_tasks_on_close=True)
        self.name = "FromLangBot"
        self.context = context
        self._runtime_configured = False
        self._invalidated = False

        @self.action(CommonAction.PING)
        async def ping(data: dict[str, Any]) -> handler.ActionResponse:
            return handler.ActionResponse.success({"message": "pong"})

        @self.action(LangBotToRuntimeAction.SET_RUNTIME_CONFIG)
        async def set_runtime_config(data: dict[str, Any]) -> handler.ActionResponse:
            self.configure_runtime(RuntimeConfig.model_validate(data))
            return handler.ActionResponse.success({"event_batch": True})

        @self.action(LangBotToRuntimeAction.RECONCILE_PLUGIN_INSTALLATIONS)
        async def reconcile_plugin_installations(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            request = ReconcilePluginInstallationsRequest.model_validate(data)
            result = await self.context.plugin_mgr.reconcile_plugin_installations(
                request.installations
            )
            return handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.GET_STORAGE_ANALYSIS)
        async def get_storage_analysis(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            """Measure directories owned by this Plugin Runtime process."""

            plugin_mgr = self.context.plugin_mgr
            artifact_store = plugin_mgr.artifact_store
            environment_store = plugin_mgr.dependency_environment_store
            directories = await asyncio.to_thread(
                collect_storage_directories,
                (
                    ("legacy_plugins", Path("data/plugins"), "root", None),
                    ("artifacts", artifact_store.artifacts_path, "root", None),
                    (
                        "dependency_environments",
                        environment_store.environments_path,
                        "root",
                        None,
                    ),
                    ("installations", artifact_store.installations_path, "root", None),
                    ("staging", Path("data/.plugin-staging"), "root", None),
                    ("rpc_transfer", Path(FILE_STORAGE_DIR), "root", None),
                ),
            )
            return handler.ActionResponse.success(
                {
                    "size_bytes": storage_total_bytes(directories),
                    "directories": directories,
                }
            )

        @self.action(LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION)
        async def apply_plugin_installation(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            request = ApplyPluginInstallationRequest.model_validate(data)
            binding = self.current_action_context
            if not isinstance(binding, InstallationBinding):  # pragma: no cover
                raise ValueError("APPLY_PLUGIN_INSTALLATION requires binding")
            artifact_package = None
            if request.artifact_file_key is not None:
                artifact_package = await self.read_local_file(request.artifact_file_key)
                await self.delete_local_file(request.artifact_file_key)
            apply_kwargs: dict[str, Any] = {
                "artifact_package": artifact_package,
                "enabled": request.enabled,
            }
            if request.execution_mode.value != "dedicated":
                apply_kwargs["execution_mode"] = request.execution_mode
            result = await self.context.plugin_mgr.apply_plugin_installation(
                binding,
                **apply_kwargs,
            )
            return handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.REMOVE_PLUGIN_INSTALLATION)
        async def remove_plugin_installation(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            RemovePluginInstallationRequest.model_validate(data)
            binding = self.current_action_context
            if not isinstance(binding, InstallationBinding):  # pragma: no cover
                raise ValueError("REMOVE_PLUGIN_INSTALLATION requires binding")
            result = await self.context.plugin_mgr.remove_plugin_installation(binding)
            return handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.LIST_PLUGINS)
        async def list_plugins(data: dict[str, Any]) -> handler.ActionResponse:
            plugins = (
                self.context.plugin_mgr.plugins_for_current_scope()
                if hasattr(self.context.plugin_mgr, "plugins_for_current_scope")
                else self.context.plugin_mgr.plugins
            )
            result = {"plugins": [plugin.model_dump() for plugin in plugins]}

            return handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.GET_PLUGIN_INFO)
        async def get_plugin_info(data: dict[str, Any]) -> handler.ActionResponse:
            author = data["author"]
            plugin_name = data["plugin_name"]
            plugins = (
                self.context.plugin_mgr.plugins_for_current_scope()
                if hasattr(self.context.plugin_mgr, "plugins_for_current_scope")
                else self.context.plugin_mgr.plugins
            )
            for plugin in plugins:
                if (
                    plugin.manifest.metadata.author == author
                    and plugin.manifest.metadata.name == plugin_name
                ):
                    result = {"plugin": plugin.model_dump()}

                    return handler.ActionResponse.success(result)

            return handler.ActionResponse.success({"plugin": None})

        @self.action(LangBotToRuntimeAction.GET_PLUGIN_ICON)
        async def get_plugin_icon(data: dict[str, Any]) -> handler.ActionResponse:
            author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            (
                plugin_icon_bytes,
                mime_type,
            ) = await self.context.plugin_mgr.get_plugin_icon(author, plugin_name)

            plugin_icon_file_key = await self.send_file(plugin_icon_bytes, "")

            return handler.ActionResponse.success(
                {"plugin_icon_file_key": plugin_icon_file_key, "mime_type": mime_type}
            )

        @self.action(LangBotToRuntimeAction.GET_PLUGIN_README)
        async def get_plugin_readme(data: dict[str, Any]) -> handler.ActionResponse:
            author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            language = data.get("language", "en")
            readme_bytes = await self.context.plugin_mgr.get_plugin_readme(
                author, plugin_name, language
            )

            if readme_bytes:
                readme_file_key = await self.send_file(readme_bytes, "md")
                return handler.ActionResponse.success(
                    {"readme_file_key": readme_file_key}
                )
            else:
                return handler.ActionResponse.success({"readme_file_key": None})

        @self.action(LangBotToRuntimeAction.GET_PLUGIN_LOGS)
        async def get_plugin_logs(data: dict[str, Any]) -> handler.ActionResponse:
            author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            limit = int(data.get("limit", 200))
            level = data.get("level") or None
            logs = await self.context.plugin_mgr.get_plugin_logs(
                author, plugin_name, limit=limit, level=level
            )
            return handler.ActionResponse.success({"logs": logs})

        @self.action(LangBotToRuntimeAction.GET_PLUGIN_ASSETS_FILE)
        async def get_plugin_assets_file(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            file_key = data["file_path"]
            (
                file_bytes,
                mime_type,
            ) = await self.context.plugin_mgr.get_plugin_assets_file(
                author, plugin_name, file_key
            )

            if file_bytes:
                file_file_key = await self.send_file(file_bytes, "")
                return handler.ActionResponse.success(
                    {"file_file_key": file_file_key, "mime_type": mime_type}
                )
            else:
                return handler.ActionResponse.success(
                    {"file_file_key": None, "mime_type": None}
                )

        @self.action(LangBotToRuntimeAction.PAGE_API)
        async def page_api(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            for field in (
                "plugin_author",
                "plugin_name",
                "page_id",
                "endpoint",
                "method",
            ):
                if field not in data:
                    return handler.ActionResponse.success(
                        {"data": None, "error": f"Missing required field: {field}"}
                    )
            result = await self.context.plugin_mgr.handle_page_api(
                data["plugin_author"],
                data["plugin_name"],
                data["page_id"],
                data["endpoint"],
                data["method"],
                data.get("body"),
            )
            return handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.INSTALL_PLUGIN)
        async def install_plugin(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            install_source = plugin_mgr_module.PluginInstallSource(
                data["install_source"]
            )
            install_info = {
                key: value
                for key, value in data["install_info"].items()
                if key
                not in {
                    "context",
                    "action_context",
                    "instance_uuid",
                    "workspace_uuid",
                    "placement_generation",
                    "installation_uuid",
                }
            }

            if (
                install_source == plugin_mgr_module.PluginInstallSource.LOCAL
                or install_source == plugin_mgr_module.PluginInstallSource.GITHUB
            ):
                install_info["plugin_file"] = await self.read_local_file(
                    install_info["plugin_file_key"]
                )
                await self.delete_local_file(install_info["plugin_file_key"])

            async for resp in self.context.plugin_mgr.install_plugin(
                install_source, install_info
            ):
                yield handler.ActionResponse.success(resp)
            yield handler.ActionResponse.success({"current_action": "plugin installed"})

        @self.action(LangBotToRuntimeAction.RESTART_PLUGIN)
        async def restart_plugin(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            async for resp in self.context.plugin_mgr.restart_plugin(
                data["plugin_author"], data["plugin_name"]
            ):
                yield handler.ActionResponse.success(resp)
            yield handler.ActionResponse.success({"current_action": "plugin restarted"})

        @self.action(LangBotToRuntimeAction.DELETE_PLUGIN)
        async def remove_plugin(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            async for resp in self.context.plugin_mgr.delete_plugin(
                data["plugin_author"], data["plugin_name"]
            ):
                yield handler.ActionResponse.success(resp)
            yield handler.ActionResponse.success({"current_action": "plugin removed"})

        @self.action(LangBotToRuntimeAction.UPGRADE_PLUGIN)
        async def upgrade_plugin(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            async for resp in self.context.plugin_mgr.upgrade_plugin(
                data["plugin_author"], data["plugin_name"]
            ):
                yield handler.ActionResponse.success(resp)
            yield handler.ActionResponse.success({"current_action": "plugin upgraded"})

        @self.action(LangBotToRuntimeAction.EMIT_EVENT)
        async def emit_event(data: dict[str, Any]) -> handler.ActionResponse:
            event_context_data = data["event_context"]
            event_context = EventContext.model_validate(event_context_data)
            action_context = self.current_action_context
            if action_context is not None:
                event_context.inherit_execution_scope(action_context)
                event_context.event.inherit_execution_scope(action_context)
            include_plugins = data.get("include_plugins")

            bindings = None
            if "installation_bindings" in data:
                raw_bindings = data["installation_bindings"]
                if not isinstance(raw_bindings, list) or not raw_bindings:
                    raise ValueError("Event batch requires a nonempty binding list")
                bindings = [
                    InstallationBinding.model_validate(item) for item in raw_bindings
                ]
                if bindings[0] != action_context:
                    raise ValueError("Event batch must start with its envelope binding")
                if len({binding.installation_uuid for binding in bindings}) != len(
                    bindings
                ):
                    raise ValueError("Event batch contains duplicate installations")
                for binding in bindings:
                    if not action_context.same_workspace(binding):
                        raise ValueError(
                            "Event batch cannot cross Workspace boundaries"
                        )
                    if not self.context.is_current_installation_binding(binding):
                        raise ValueError(
                            "Event batch installation binding is not current"
                        )

            emitted_plugins = []
            response_sources = []
            for binding in bindings if bindings is not None else [action_context]:
                if bindings is not None:
                    # Recheck after each awaited plugin: reconcile or reconnect may fence it.
                    if not self.context.is_current_installation_binding(binding):
                        raise ValueError(
                            "Event batch installation binding is not current"
                        )
                    self.validate_inbound_action_context(
                        LangBotToRuntimeAction.EMIT_EVENT.value, binding
                    )
                token = self._current_action_context.set(binding)
                try:
                    (
                        emitted,
                        event_context,
                        sources,
                    ) = await self.context.plugin_mgr.emit_event(
                        event_context, include_plugins
                    )
                finally:
                    self._current_action_context.reset(token)
                emitted_plugins.extend(emitted)
                response_sources.extend(sources)
                if event_context.is_prevented_postorder():
                    break

            event_context_dump = event_context.model_dump()

            return handler.ActionResponse.success(
                {
                    "emitted_plugins": [
                        plugin.model_dump() for plugin in emitted_plugins
                    ],
                    "response_sources": response_sources,
                    "event_context": event_context_dump,
                }
            )

        @self.action(LangBotToRuntimeAction.PLUGIN_DIAGNOSTIC)
        async def plugin_diagnostic(data: dict[str, Any]) -> handler.ActionResponse:
            await self.context.plugin_mgr.notify_plugin_diagnostic(data)
            return handler.ActionResponse.success({})

        @self.action(LangBotToRuntimeAction.LIST_TOOLS)
        async def list_tools(data: dict[str, Any]) -> handler.ActionResponse:
            include_plugins = data.get("include_plugins")
            tools = await self.context.plugin_mgr.list_tools(include_plugins)
            return handler.ActionResponse.success(
                {"tools": [tool.model_dump() for tool in tools]}
            )

        @self.action(LangBotToRuntimeAction.CALL_TOOL)
        async def call_tool(data: dict[str, Any]) -> handler.ActionResponse:
            tool_name = data["tool_name"]
            tool_parameters = data["tool_parameters"]
            session = data["session"]
            query_id = data["query_id"]
            query_uuid = data.get("query_uuid")
            include_plugins = data.get("include_plugins")

            session_payload = dict(session)
            action_context = self.current_action_context
            if action_context is not None:
                for field_name in (
                    "instance_uuid",
                    "workspace_uuid",
                    "placement_generation",
                ):
                    trusted_value = getattr(action_context, field_name)
                    supplied_value = session_payload.get(field_name)
                    if supplied_value is not None and supplied_value != trusted_value:
                        raise ValueError(
                            f"Session {field_name} does not match action context"
                        )
                    session_payload[field_name] = trusted_value

            if query_uuid is None:
                resp = await self.context.plugin_mgr.call_tool(
                    tool_name,
                    tool_parameters,
                    session_payload,
                    query_id,
                    include_plugins,
                )
            else:
                resp = await self.context.plugin_mgr.call_tool(
                    tool_name,
                    tool_parameters,
                    session_payload,
                    query_id,
                    include_plugins,
                    query_uuid=query_uuid,
                )

            return handler.ActionResponse.success(
                {
                    "tool_response": resp,
                }
            )

        @self.action(LangBotToRuntimeAction.LIST_COMMANDS)
        async def list_commands(data: dict[str, Any]) -> handler.ActionResponse:
            include_plugins = data.get("include_plugins")
            commands = await self.context.plugin_mgr.list_commands(include_plugins)
            return handler.ActionResponse.success(
                {"commands": [command.model_dump() for command in commands]}
            )

        @self.action(LangBotToRuntimeAction.EXECUTE_COMMAND)
        async def execute_command(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            command_context = ExecuteContext.model_validate(data["command_context"])
            action_context = self.current_action_context
            if action_context is not None:
                command_context.inherit_execution_scope(action_context)
                command_context.session.inherit_execution_scope(action_context)
            include_plugins = data.get("include_plugins")
            async for resp in self.context.plugin_mgr.execute_command(
                command_context, include_plugins
            ):
                yield handler.ActionResponse.success(resp.model_dump(mode="json"))

        # Runner actions
        @self.action(LangBotToRuntimeAction.LIST_RUNNERS)
        async def list_runners(data: dict[str, Any]) -> handler.ActionResponse:
            include_plugins = data.get("include_plugins")
            runners = await self.context.plugin_mgr.list_runners(include_plugins)
            return handler.ActionResponse.success({"runners": runners})

        @self.action(LangBotToRuntimeAction.RUN_RUNNER)
        async def run_runner(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            runner_name = data["runner_name"]
            context = data["context"]

            async for result in self.context.plugin_mgr.run_runner(
                plugin_author, plugin_name, runner_name, context
            ):
                yield handler.ActionResponse.success(result)

        @self.action(LangBotToRuntimeAction.RETRIEVE_KNOWLEDGE)
        async def retrieve_knowledge(data: dict[str, Any]) -> handler.ActionResponse:
            """Retrieve knowledge using a KnowledgeEngine instance."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            retriever_name = data["retriever_name"]
            retrieval_context = data["retrieval_context"]

            resp = await self.context.plugin_mgr.retrieve_knowledge(
                plugin_author, plugin_name, retriever_name, retrieval_context
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.GET_DEBUG_INFO)
        async def get_debug_info(data: dict[str, Any]) -> handler.ActionResponse:
            """Get the current Workspace-scoped rotating debug credential."""

            action_context = self.current_action_context
            if action_context is None:
                raise ValueError("GET_DEBUG_INFO requires Workspace context")
            credential = self.context.workspace_debug_tokens.issue(action_context)

            return handler.ActionResponse.success(
                {
                    "plugin_debug_key": credential.token,
                    "expires_at": credential.expires_at,
                    "ws_debug_port": self.context.ws_debug_port,
                    "resources": self.context.get_runtime_resource_stats(),
                }
            )

        @self.action(LangBotToRuntimeAction.BUILD_PLUGIN_PACKAGE)
        async def build_plugin_package(data: dict[str, Any]) -> handler.ActionResponse:
            """Build a ``.lbpkg`` from a debug plugin's live source tree.

            The bytes are relayed back through the Runtime's file-transfer
            channel so the (much larger) package never inflates the control
            JSON payload.
            """

            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            manifest_overrides = data.get("manifest_overrides") or {}
            if not isinstance(manifest_overrides, dict):
                raise ValueError("manifest_overrides must be an object")

            package_bytes, info = await self.context.plugin_mgr.build_plugin_package(
                plugin_author,
                plugin_name,
                manifest_overrides=manifest_overrides,
            )
            package_file_key = await self.send_file(package_bytes, "lbpkg")
            return handler.ActionResponse.success(
                {
                    "package_file_key": package_file_key,
                    "filename": info.get("filename", ""),
                    "metadata": info.get("metadata", {}),
                    "manifest": info.get("manifest", {}),
                    "size": info.get("size", len(package_bytes)),
                }
            )

        @self.action(LangBotToRuntimeAction.GIT_SYNC_PLUGIN)
        async def git_sync_plugin(data: dict[str, Any]) -> handler.ActionResponse:
            """Commit and push a debug plugin's working directory to GitHub."""

            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            manifest_overrides = data.get("manifest_overrides") or {}
            if not isinstance(manifest_overrides, dict):
                raise ValueError("manifest_overrides must be an object")

            result = await self.context.plugin_mgr.git_sync_plugin(
                plugin_author,
                plugin_name,
                repo_url=str(data.get("repo_url") or ""),
                token=str(data.get("token") or ""),
                branch=str(data.get("branch") or ""),
                commit_message=str(data.get("commit_message") or ""),
                manifest_overrides=manifest_overrides,
            )
            return handler.ActionResponse.success(result)

        # ================= Knowledge Engine Actions =================

        @self.action(LangBotToRuntimeAction.LIST_KNOWLEDGE_ENGINES)
        async def list_knowledge_engines(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            """List all available Knowledge Engines from plugins."""
            engines = await self.context.plugin_mgr.list_knowledge_engines()
            return handler.ActionResponse.success({"engines": engines})

        @self.action(LangBotToRuntimeAction.RAG_INGEST_DOCUMENT)
        async def rag_ingest_document(data: dict[str, Any]) -> handler.ActionResponse:
            """Ingest document via RAG plugin."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            context_data = data["context"]

            resp = await self.context.plugin_mgr.rag_ingest_document(
                plugin_author, plugin_name, context_data
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.RAG_DELETE_DOCUMENT)
        async def rag_delete_document(data: dict[str, Any]) -> handler.ActionResponse:
            """Delete document via RAG plugin."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            document_id = data["document_id"]
            kb_id = data["kb_id"]

            resp = await self.context.plugin_mgr.rag_delete_document(
                plugin_author, plugin_name, kb_id, document_id
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.RAG_ON_KB_CREATE)
        async def rag_on_kb_create(data: dict[str, Any]) -> handler.ActionResponse:
            """Notify plugin about KB creation."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            kb_id = data["kb_id"]
            config = data.get("config", {})

            resp = await self.context.plugin_mgr.rag_on_kb_create(
                plugin_author, plugin_name, kb_id, config
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.RAG_ON_KB_DELETE)
        async def rag_on_kb_delete(data: dict[str, Any]) -> handler.ActionResponse:
            """Notify plugin about KB deletion."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            kb_id = data["kb_id"]

            resp = await self.context.plugin_mgr.rag_on_kb_delete(
                plugin_author, plugin_name, kb_id
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.GET_RAG_CREATION_SETTINGS_SCHEMA)
        async def get_rag_creation_settings_schema(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            """Get RAG creation settings schema from plugin."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]

            resp = await self.context.plugin_mgr.get_rag_creation_schema(
                plugin_author, plugin_name
            )
            return handler.ActionResponse.success(resp)

        @self.action(LangBotToRuntimeAction.GET_RAG_RETRIEVAL_SETTINGS_SCHEMA)
        async def get_rag_retrieval_settings_schema(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            """Get RAG retrieval settings schema from plugin."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]

            resp = await self.context.plugin_mgr.get_rag_retrieval_schema(
                plugin_author, plugin_name
            )
            return handler.ActionResponse.success(resp)

        # ================= Parser Actions =================

        @self.action(LangBotToRuntimeAction.LIST_PARSERS)
        async def list_parsers(data: dict[str, Any]) -> handler.ActionResponse:
            """List all available parsers from plugins."""
            parsers = await self.context.plugin_mgr.list_parsers()
            return handler.ActionResponse.success({"parsers": parsers})

        @self.action(LangBotToRuntimeAction.PARSE_DOCUMENT)
        async def parse_document(data: dict[str, Any]) -> handler.ActionResponse:
            """Parse document via Parser plugin."""
            plugin_author = data["plugin_author"]
            plugin_name = data["plugin_name"]
            context_data = data["context"]

            # Read file from local temp storage (transferred via FILE_CHUNK from LangBot)
            file_key = context_data.pop("file_key", "")
            if file_key:
                file_bytes = await self.read_local_file(file_key)
                await self.delete_local_file(file_key)
            else:
                file_bytes = b""

            resp = await self.context.plugin_mgr.parse_document(
                plugin_author, plugin_name, context_data, file_bytes
            )
            return handler.ActionResponse.success(resp)

    @property
    def runtime_configured(self) -> bool:
        return self._runtime_configured

    def _uses_reserved_admission(self, req_data: dict[str, Any]) -> bool:
        # Admission only: _handle_action still validates the full request and
        # enforces active-handler fencing and the tenant-context prohibition.
        return (
            super()._uses_reserved_admission(req_data)
            or req_data.get("action") == CommonAction.PING.value
        )

    def invalidate(self) -> None:
        """Fence this handler synchronously before its transport is closed."""

        self._invalidated = True
        self.cancel_inflight_messages()

    def _require_active_handler(self) -> None:
        if self._invalidated or not self.context.is_active_control_handler(self):
            raise ValueError("Control connection has been superseded")

    def configure_runtime(self, runtime_config: RuntimeConfig | dict) -> RuntimeConfig:
        """Apply the immutable, instance-scoped control handshake."""

        self._require_active_handler()
        config = RuntimeConfig.model_validate(runtime_config)
        self.context.plugin_mgr.configure_worker_runtime(
            config.worker_policy,
            config.runtime_profile,
        )
        self.context.bind_runtime(
            config.runtime_identity,
            config.worker_policy,
            config.runtime_profile,
        )
        self._runtime_configured = True

        # LangBot pushes its configured marketplace URL so this Runtime uses
        # the same trusted source without maintaining another config source.
        if config.cloud_service_url:
            from langbot_plugin.runtime.settings import settings as runtime_settings

            runtime_settings.cloud_service_url = config.cloud_service_url
            logger.info(
                "Runtime cloud_service_url set by LangBot: %s",
                runtime_settings.cloud_service_url,
            )
        return config

    def _authorize_legacy_file_chunk(
        self, action_context: ActionEnvelopeContext | None
    ) -> ActionContext:
        """Accept OSS file replies only for a live, registered connection binding.

        Unlike candidate artifact pretransfer, legacy knowledge transfers have
        no revision/digest tuple. Never synthesize one from request data.
        """
        workspace = self.context.workspace_binding
        identity = self.context.runtime_identity
        if (
            self.context.runtime_profile != "oss_dev"
            or not isinstance(action_context, ActionContext)
            or not action_context.installation_uuid
            or identity is None
            or action_context.instance_uuid != identity.instance_uuid
            or workspace is None
            or not workspace.same_workspace(action_context)
        ):
            raise ValueError(
                "Legacy FILE_CHUNK requires the bound OSS Workspace and installation"
            )

        manager = self.context.plugin_mgr
        for plugin in manager.plugins:
            worker = plugin._runtime_plugin_handler
            if (
                worker is not None
                and worker in manager.plugin_handlers
                and not worker._closed
                and worker.bound_action_context == action_context
            ):
                # Reuse connection validation, including debug-token revocation.
                worker.validate_inbound_action_context(
                    CommonAction.FILE_CHUNK.value, action_context
                )
                return action_context
        raise ValueError(
            "Legacy FILE_CHUNK requires a live registered plugin installation"
        )

    def validate_inbound_action_context(
        self,
        action: str,
        action_context: ActionEnvelopeContext | None,
    ) -> ActionEnvelopeContext | None:
        """Require explicit installation authority for every tenant action."""

        self._require_active_handler()

        if action == CommonAction.PING.value:
            if action_context is not None:
                raise ValueError("PING does not accept tenant context")
            return None

        if action == LangBotToRuntimeAction.SET_RUNTIME_CONFIG.value:
            if action_context is not None:
                raise ValueError("SET_RUNTIME_CONFIG is instance-scoped")
            return None

        if not self._runtime_configured:
            raise ValueError("SET_RUNTIME_CONFIG must complete before control actions")

        if action in INSTANCE_SCOPED_CONTROL_ACTIONS:
            if action_context is not None:
                raise ValueError(f"{action} does not accept tenant context")
            return None

        if action == LangBotToRuntimeAction.GET_DEBUG_INFO.value:
            if not isinstance(action_context, ActionContext) or isinstance(
                action_context, InstallationBinding
            ):
                raise ValueError("GET_DEBUG_INFO requires Workspace context")
            if self.context.runtime_identity is None or (
                action_context.instance_uuid
                != self.context.runtime_identity.instance_uuid
            ):
                raise ValueError("GET_DEBUG_INFO targets another Runtime instance")
            return action_context

        if (
            self.context.runtime_profile == "shared"
            and action in LEGACY_OSS_PLUGIN_LIFECYCLE_ACTIONS
        ):
            raise ValueError(
                f"{action} is unavailable in the shared Runtime profile; "
                "use installation desired state"
            )

        if action == CommonAction.FILE_CHUNK.value and not isinstance(
            action_context, InstallationBinding
        ):
            return self._authorize_legacy_file_chunk(action_context)

        if action in {
            LangBotToRuntimeAction.APPLY_PLUGIN_INSTALLATION.value,
            LangBotToRuntimeAction.REMOVE_PLUGIN_INSTALLATION.value,
            CommonAction.FILE_CHUNK.value,
        }:
            if not isinstance(action_context, InstallationBinding):
                raise ValueError(
                    f"{action} requires a complete InstallationBinding context"
                )
            return self.context.validate_installation_candidate(action_context)

        if action in TENANT_SCOPED_CONTROL_ACTIONS:
            if not isinstance(action_context, InstallationBinding):
                raise ValueError(
                    f"{action} requires a complete InstallationBinding context"
                )
            return self.context.authorize_installation_binding(action_context)

        return super().validate_inbound_action_context(action, action_context)

    def resolve_outbound_action_context(
        self,
        action_context: ActionEnvelopeContext | dict[str, Any] | None,
    ) -> ActionEnvelopeContext | None:
        """Propagate the current tenant tuple across nested control calls."""

        self._require_active_handler()
        if action_context is None:
            current = self.current_action_context
            if current is not None:
                return current

            # Compatibility only: manager-originated calls outside an inbound
            # action still use its fail-closed, single-Workspace fence.
            legacy_binding = self.context.workspace_binding
            if legacy_binding is not None:
                return legacy_binding
        return super().resolve_outbound_action_context(action_context)


# {"action": "ping", "data": {}, "seq_id": 1}
# {"code": 0, "message": "ok", "data": {"msg": "hello"}, "seq_id": 1}
