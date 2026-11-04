# handle connection to/from plugin
from __future__ import annotations

from contextlib import aclosing

from typing import Any, AsyncGenerator
import typing
import logging

from langbot_plugin.runtime.io import handler, connection
from langbot_plugin.entities.io.actions.enums import (
    ActionType,
    CommonAction,
    PluginToRuntimeAction,
    RuntimeToPluginAction,
    RuntimeToLangBotAction,
)
from langbot_plugin.runtime import context as context_module
import asyncio
import math

from langbot_plugin.runtime.plugin.logbuffer import PluginLogBuffer
from langbot_plugin.api.proxies.langbot_api import SEND_MESSAGE_DEFAULT_TIMEOUT
from langbot_plugin.entities.io.context import (
    ActionContext,
    ActionEnvelopeContext,
    InstallationBinding,
)

logger = logging.getLogger(__name__)

# Timeout for long-running operations like command execution and tool calls (3 minutes)
LONG_RUNNING_OPERATION_TIMEOUT = 180.0
KNOWLEDGE_RETRIEVAL_TIMEOUT = 120.0

_UNTRUSTED_SCOPE_FIELDS = frozenset(
    {
        "context",
        "action_context",
        "instance_uuid",
        "workspace_uuid",
        "placement_generation",
        "execution_generation",
        "installation_uuid",
        "runtime_revision",
        "artifact_digest",
    }
)


class PluginConnectionHandler(handler.Handler):
    """The handler for plugin connection."""

    def _uses_reserved_admission(self, req_data: dict[str, Any]) -> bool:
        return super()._uses_reserved_admission(req_data) or (
            req_data.get("action") == PluginToRuntimeAction.REGISTER_PLUGIN.value
        )

    def _uses_reserved_action_capacity(self, req_data: dict[str, Any]) -> bool:
        is_registration = (
            req_data.get("action") == PluginToRuntimeAction.REGISTER_PLUGIN.value
        )
        if not is_registration or not self._registration_codec_available:
            return False
        self._registration_codec_available = False
        return True

    def _uses_reserved_decode_capacity(self, message: str) -> bool:
        if super()._uses_reserved_decode_capacity(message):
            return True
        if not self._certified_shared_stdio or not self._first_message_decode_available:
            return False
        self._first_message_decode_available = False
        return True

    context: context_module.RuntimeContext

    debug_plugin: bool = False
    """If this plugin is a debug plugin."""

    debug_workspace_binding: ActionContext | None = None
    debug_auth_token: str | None = None

    stdio_process: asyncio.subprocess.Process | None = None
    """The stdio process of the plugin."""

    log_buffer: PluginLogBuffer
    """Ring buffer holding recent log lines (from the plugin's stderr)."""

    subprocess_on_windows_task: asyncio.Task | None = None
    """The task for the subprocess on Windows."""

    def __init__(
        self,
        connection: connection.Connection,
        context: context_module.RuntimeContext,
        stdio_process: asyncio.subprocess.Process | None = None,
        debug_plugin: bool = False,
        *,
        file_storage_dir: str | None = None,
        max_file_bytes: int | None = None,
        certified_shared_stdio: bool = False,
    ):
        async def disconnect_callback(hdl: handler.Handler):
            logger.debug("disconnect_callback")
            if hasattr(self.context.plugin_mgr, "remove_plugin_handler"):
                await self.context.plugin_mgr.remove_plugin_handler(self)
                return
            for plugin_container in self.context.plugin_mgr.plugins:
                if plugin_container._runtime_plugin_handler == self:
                    await self.context.plugin_mgr.remove_plugin_container(
                        plugin_container
                    )
                    return

        super().__init__(
            connection,
            disconnect_callback,
            file_storage_dir=file_storage_dir,
            max_file_bytes=max_file_bytes,
        )
        self.context = context
        self.name = "FromPlugin"
        self.debug_plugin = debug_plugin
        self.debug_auth_token = None
        self._registration_codec_available = True
        self._first_message_decode_available = True
        self._certified_shared_stdio = certified_shared_stdio
        self.stdio_process = stdio_process
        self.shared_pool_digest: str | None = None
        self.shared_registration_generation: int | None = None
        self._shared_pool_bindings: set[InstallationBinding] = set()
        runtime_binding = getattr(self.context, "workspace_binding", None)
        if runtime_binding is not None and not hasattr(self.context, "runtime_profile"):
            # Compatibility for older embedders that predate authenticated
            # registration. A modern WebSocket listener initially accepts
            # both debug clients and Windows production workers; binding it as
            # debug before REGISTER_PLUGIN would make the production worker
            # look already registered.
            self.bind_action_context(runtime_binding)

        # Capture the plugin subprocess's stderr (Python `logging` output) into
        # a per-plugin ring buffer so LangBot can show logs on the detail page.
        self.log_buffer = PluginLogBuffer()
        if self.stdio_process is not None and self.stdio_process.stderr is not None:
            self.log_buffer.start_reader(self.stdio_process.stderr)

        async def call_host_action(
            action,
            data: dict[str, Any],
            timeout: float = 15.0,
            *,
            require_workspace: bool = False,
        ) -> dict[str, Any]:
            """Forward to LangBot using only the trusted connection binding."""

            payload = {
                key: value
                for key, value in data.items()
                if key not in _UNTRUSTED_SCOPE_FIELDS
            }
            binding: ActionContext | None = self.resolve_effective_action_context()
            if require_workspace:
                if binding is None:
                    raise ValueError("Plugin Runtime is not bound to a Workspace")

            cancel_peer_on_cancel = (
                action
                in {
                    PluginToRuntimeAction.CALL_TOOL,
                    PluginToRuntimeAction.REQUEST_INTERACTION,
                }
                and payload.get("run_id") is not None
            )
            if binding is None:
                # Compatibility for non-Workspace APIs used with an older
                # single-tenant host. Workspace storage never takes this path.
                return await self.context.control_handler.call_action(
                    action,
                    payload,
                    timeout=timeout,
                    cancel_peer_on_cancel=cancel_peer_on_cancel,
                )
            return await self.context.control_handler.call_action(
                action,
                payload,
                timeout=timeout,
                action_context=binding,
                cancel_peer_on_cancel=cancel_peer_on_cancel,
            )

        def scoped_plugins():
            binding = self.resolve_effective_action_context()
            if isinstance(binding, InstallationBinding) and hasattr(
                self.context.plugin_mgr,
                "plugins_for_binding",
            ):
                return self.context.plugin_mgr.plugins_for_binding(binding)
            return self.context.plugin_mgr.plugins

        def trusted_plugin_payload(data: dict[str, Any]) -> dict[str, Any]:
            """Attach the caller identity derived from this trusted connection."""

            payload = dict(data)
            payload.pop("caller_plugin_identity", None)
            for plugin_container in scoped_plugins():
                if plugin_container._runtime_plugin_handler == self:
                    payload["caller_plugin_identity"] = (
                        f"{plugin_container.manifest.metadata.author}/"
                        f"{plugin_container.manifest.metadata.name}"
                    )
                    break
            return payload

        async def forward_agent_action(
            action: PluginToRuntimeAction,
            data: dict[str, Any],
            timeout: float,
        ) -> handler.ActionResponse:
            result = await call_host_action(
                action,
                trusted_plugin_payload(data),
                timeout=timeout,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.REGISTER_PLUGIN)
        async def register_plugin(data: dict[str, Any]) -> handler.ActionResponse:
            prod_mode = data.get("prod_mode") is True
            registration_capability = str(
                data.get("registration_capability") or ""
            ).strip()
            if prod_mode:
                if not registration_capability:
                    return handler.ActionResponse.error(
                        "Production plugin registration capability is required"
                    )
                self.debug_plugin = False
            else:
                if not self.debug_plugin:
                    return handler.ActionResponse.error(
                        "Debug plugin registration is not allowed on this connection"
                    )
                # Get the debug key from plugin data
                plugin_debug_key = data.get("plugin_debug_key", "")

                debug_binding = self.context.workspace_debug_tokens.binding_for_token(
                    str(plugin_debug_key)
                )
                if (
                    debug_binding is None
                    or debug_binding != self.debug_workspace_binding
                ):
                    logger.warning(
                        "Plugin debug key verification failed. Expected key does not match."
                    )
                    return handler.ActionResponse.error(
                        "Plugin debug key verification failed"
                    )
                self.bind_action_context(debug_binding)

            await self.context.plugin_mgr.register_plugin(
                self,
                data["plugin_container"],
                self.debug_plugin,
                registration_capability=(
                    registration_capability if prod_mode else None
                ),
            )
            return handler.ActionResponse.success({})

        @self.action(PluginToRuntimeAction.REPLY_MESSAGE)
        async def reply_message(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.REPLY_MESSAGE,
                {
                    **data,
                },
                timeout=180,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_BOT_UUID)
        async def get_bot_uuid(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_BOT_UUID,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.SET_QUERY_VAR)
        async def set_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.SET_QUERY_VAR,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_QUERY_VAR)
        async def get_query_var(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_QUERY_VAR,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_QUERY_VARS)
        async def get_query_vars(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_QUERY_VARS,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.CREATE_NEW_CONVERSATION)
        async def create_new_conversation(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.CREATE_NEW_CONVERSATION,
                {
                    "query_id": data["query_id"],
                    **(
                        {"query_uuid": data["query_uuid"]}
                        if data.get("query_uuid") is not None
                        else {}
                    ),
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_LANGBOT_VERSION)
        async def get_langbot_version(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_LANGBOT_VERSION,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_BOTS)
        async def get_bots(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_BOTS,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_BOT_INFO)
        async def get_bot_info(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_BOT_INFO,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.SEND_MESSAGE)
        async def send_message(data: dict[str, Any]) -> handler.ActionResponse:
            # Older SDKs send no timeout; give them the same 60s budget instead
            # of the generic 15s relay default.
            timeout = data.pop("timeout", None)
            if (
                isinstance(timeout, bool)
                or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout)
                or timeout <= 0
            ):
                timeout = SEND_MESSAGE_DEFAULT_TIMEOUT
            result = await call_host_action(
                PluginToRuntimeAction.SEND_MESSAGE,
                {
                    **data,
                },
                timeout=float(timeout),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.CALL_PLATFORM_API)
        async def call_platform_api(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.CALL_PLATFORM_API,
                data,
                15,
            )

        @self.action(PluginToRuntimeAction.GET_LLM_MODELS)
        async def get_llm_models(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.GET_LLM_MODELS,
                {
                    **data,
                },
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.COUNT_TOKENS)
        async def count_tokens(data: dict[str, Any]) -> handler.ActionResponse:
            timeout = data.pop("timeout", 30.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                timeout = 30.0
            return await forward_agent_action(
                PluginToRuntimeAction.COUNT_TOKENS,
                data,
                float(timeout),
            )

        # @self.action(PluginToRuntimeAction.GET_LLM_MODEL_INFO)
        # async def get_llm_model_info(data: dict[str, Any]) -> handler.ActionResponse:
        #     result = await self.context.control_handler.call_action(
        #         PluginToRuntimeAction.GET_LLM_MODEL_INFO,
        #         {
        #             **data,
        #         },
        #     )
        #     return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.INVOKE_LLM)
        async def invoke_llm(data: dict[str, Any]) -> handler.ActionResponse:
            timeout = data.pop("timeout", 120.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                timeout = 120.0

            result = await call_host_action(
                PluginToRuntimeAction.INVOKE_LLM,
                trusted_plugin_payload(data),
                timeout=float(timeout),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.INVOKE_LLM_STREAM)
        async def invoke_llm_stream(
            data: dict[str, Any],
        ) -> AsyncGenerator[handler.ActionResponse, None]:
            timeout = data.pop("timeout", 120.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                timeout = 120.0
            payload = trusted_plugin_payload(data)
            payload = {
                key: value
                for key, value in payload.items()
                if key not in _UNTRUSTED_SCOPE_FIELDS
            }
            kwargs: dict[str, Any] = {"timeout": float(timeout)}
            binding = self.resolve_effective_action_context()
            if binding is not None:
                kwargs["action_context"] = binding
            async with aclosing(
                self.context.control_handler.call_action_generator(
                    PluginToRuntimeAction.INVOKE_LLM_STREAM,
                    payload,
                    **kwargs,
                )
            ) as owned_stream:
                async for chunk in owned_stream:
                    yield handler.ActionResponse.success(chunk)

        @self.action(PluginToRuntimeAction.INVOKE_EMBEDDING)
        async def invoke_embedding(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.INVOKE_EMBEDDING,
                trusted_plugin_payload(data),
                timeout=60,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.INVOKE_RERANK)
        async def invoke_rerank(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.INVOKE_RERANK,
                trusted_plugin_payload(data),
                timeout=60,
            )
            return handler.ActionResponse.success(result)

        # ================= RAG Capability Handlers (Plugin -> Runtime -> Host) =================

        async def _proxy_rag_action(
            action: PluginToRuntimeAction,
            data: dict[str, Any],
            timeout: float = 30,
        ) -> dict[str, Any]:
            """Proxy a RAG action to the control handler with error handling.

            Raises:
                Exception: Re-raises with context if the upstream call fails.
            """
            try:
                return await call_host_action(
                    action,
                    data,
                    timeout=timeout,
                )
            except Exception as e:
                logger.error(f"RAG proxy error [{action.value}]: {e}")
                raise

        @self.action(PluginToRuntimeAction.VECTOR_UPSERT)
        async def vector_upsert(data: dict[str, Any]) -> handler.ActionResponse:
            result = await _proxy_rag_action(
                PluginToRuntimeAction.VECTOR_UPSERT,
                data,
                timeout=60,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.VECTOR_SEARCH)
        async def vector_search(data: dict[str, Any]) -> handler.ActionResponse:
            result = await _proxy_rag_action(
                PluginToRuntimeAction.VECTOR_SEARCH,
                data,
                timeout=30,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.VECTOR_DELETE)
        async def vector_delete(data: dict[str, Any]) -> handler.ActionResponse:
            result = await _proxy_rag_action(
                PluginToRuntimeAction.VECTOR_DELETE,
                data,
                timeout=30,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.VECTOR_LIST)
        async def vector_list(data: dict[str, Any]) -> handler.ActionResponse:
            result = await _proxy_rag_action(
                PluginToRuntimeAction.VECTOR_LIST,
                data,
                timeout=30,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM)
        async def get_knowledge_file_stream(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            """Forward file stream from LangBot to plugin via chunked transfer."""
            result = await _proxy_rag_action(
                PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM,
                data,
                timeout=60,
            )
            # LangBot sent the file to the control connection's transfer
            # storage. Repackage it into this plugin connection's isolated
            # transfer storage before returning the new key to the plugin.
            file_key = result.get("file_key", "")
            if file_key:
                control_handler = self.context.control_handler
                binding = self.resolve_effective_action_context()
                assert control_handler is not None
                file_bytes = await control_handler.read_local_file(
                    file_key, action_context=binding
                )
                await control_handler.delete_local_file(
                    file_key, action_context=binding
                )
                # Forward to plugin subprocess via chunked transfer
                plugin_file_key = await self.send_file(file_bytes, "")
                return handler.ActionResponse.success({"file_key": plugin_file_key})
            return handler.ActionResponse.success(result)

        # ================= Knowledge Base Query Handlers (Plugin -> Runtime -> Host) =================

        @self.action(PluginToRuntimeAction.LIST_KNOWLEDGE_BASES)
        async def list_knowledge_bases(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.LIST_KNOWLEDGE_BASES,
                data,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE)
        async def retrieve_knowledge(data: dict[str, Any]) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.RETRIEVE_KNOWLEDGE,
                data,
                timeout=KNOWLEDGE_RETRIEVAL_TIMEOUT,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES)
        async def list_pipeline_knowledge_bases(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES,
                data,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE)
        async def retrieve_knowledge_base(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            result = await call_host_action(
                PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
                data,
                timeout=KNOWLEDGE_RETRIEVAL_TIMEOUT,
            )
            return handler.ActionResponse.success(result)

        # ================= Parser Capability Handlers (Plugin -> Runtime -> Host) =================

        @self.action(PluginToRuntimeAction.LIST_PARSERS)
        async def list_parsers(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to list available parser plugins."""
            result = await call_host_action(
                PluginToRuntimeAction.LIST_PARSERS,
                data,
                timeout=30,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.INVOKE_PARSER)
        async def invoke_parser(data: dict[str, Any]) -> handler.ActionResponse:
            """Plugin requests host to invoke a parser plugin."""
            result = await call_host_action(
                PluginToRuntimeAction.INVOKE_PARSER,
                data,
                timeout=300,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.SET_PLUGIN_STORAGE)
        async def set_plugin_storage(data: dict[str, Any]) -> handler.ActionResponse:
            data["owner_type"] = "plugin"

            for plugin_container in scoped_plugins():
                if plugin_container._runtime_plugin_handler == self:
                    data["owner"] = (
                        f"{plugin_container.manifest.metadata.author}/{plugin_container.manifest.metadata.name}"
                    )
                    break

            result = await call_host_action(
                RuntimeToLangBotAction.SET_BINARY_STORAGE,
                trusted_plugin_payload(data),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_PLUGIN_STORAGE)
        async def get_plugin_storage(data: dict[str, Any]) -> handler.ActionResponse:
            data["owner_type"] = "plugin"

            for plugin_container in scoped_plugins():
                if plugin_container._runtime_plugin_handler == self:
                    data["owner"] = (
                        f"{plugin_container.manifest.metadata.author}/{plugin_container.manifest.metadata.name}"
                    )
                    break

            result = await call_host_action(
                RuntimeToLangBotAction.GET_BINARY_STORAGE,
                trusted_plugin_payload(data),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS)
        async def get_plugin_storage_keys(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            data["owner_type"] = "plugin"

            for plugin_container in scoped_plugins():
                if plugin_container._runtime_plugin_handler == self:
                    data["owner"] = (
                        f"{plugin_container.manifest.metadata.author}/{plugin_container.manifest.metadata.name}"
                    )
                    break

            result = await call_host_action(
                RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS,
                trusted_plugin_payload(data),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.DELETE_PLUGIN_STORAGE)
        async def delete_plugin_storage(data: dict[str, Any]) -> handler.ActionResponse:
            data["owner_type"] = "plugin"

            for plugin_container in scoped_plugins():
                if plugin_container._runtime_plugin_handler == self:
                    data["owner"] = (
                        f"{plugin_container.manifest.metadata.author}/{plugin_container.manifest.metadata.name}"
                    )
                    break

            result = await call_host_action(
                RuntimeToLangBotAction.DELETE_BINARY_STORAGE,
                trusted_plugin_payload(data),
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.SET_WORKSPACE_STORAGE)
        async def set_workspace_storage(data: dict[str, Any]) -> handler.ActionResponse:
            binding = self.resolve_effective_action_context()
            if binding is None:
                raise ValueError("Plugin Runtime is not bound to a Workspace")
            payload = {
                **data,
                "owner_type": "workspace",
                "owner": binding.workspace_uuid,
            }

            result = await call_host_action(
                RuntimeToLangBotAction.SET_BINARY_STORAGE,
                payload,
                require_workspace=True,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_WORKSPACE_STORAGE)
        async def get_workspace_storage(data: dict[str, Any]) -> handler.ActionResponse:
            binding = self.resolve_effective_action_context()
            if binding is None:
                raise ValueError("Plugin Runtime is not bound to a Workspace")
            payload = {
                **data,
                "owner_type": "workspace",
                "owner": binding.workspace_uuid,
            }

            result = await call_host_action(
                RuntimeToLangBotAction.GET_BINARY_STORAGE,
                payload,
                require_workspace=True,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_WORKSPACE_STORAGE_KEYS)
        async def get_workspace_storage_keys(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            binding = self.resolve_effective_action_context()
            if binding is None:
                raise ValueError("Plugin Runtime is not bound to a Workspace")
            payload = {
                **data,
                "owner_type": "workspace",
                "owner": binding.workspace_uuid,
            }

            result = await call_host_action(
                RuntimeToLangBotAction.GET_BINARY_STORAGE_KEYS,
                payload,
                require_workspace=True,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.DELETE_WORKSPACE_STORAGE)
        async def delete_workspace_storage(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            binding = self.resolve_effective_action_context()
            if binding is None:
                raise ValueError("Plugin Runtime is not bound to a Workspace")
            payload = {
                **data,
                "owner_type": "workspace",
                "owner": binding.workspace_uuid,
            }

            result = await call_host_action(
                RuntimeToLangBotAction.DELETE_BINARY_STORAGE,
                payload,
                require_workspace=True,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.GET_CONFIG_FILE)
        async def get_config_file(data: dict[str, Any]) -> handler.ActionResponse:
            """Get a config file by file key"""
            payload = trusted_plugin_payload(
                {
                    "file_key": data["file_key"],
                    "run_id": data.get("run_id"),
                }
            )
            payload.setdefault("caller_plugin_identity", None)
            # Forward the request to LangBot
            result = await call_host_action(
                RuntimeToLangBotAction.GET_CONFIG_FILE,
                payload,
            )
            return handler.ActionResponse.success(result)

        @self.action(PluginToRuntimeAction.LIST_COMMANDS)
        async def list_commands(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.LIST_COMMANDS, data, 30
            )

        @self.action(PluginToRuntimeAction.LIST_TOOLS)
        async def list_tools(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.LIST_TOOLS, data, 30
            )

        @self.action(PluginToRuntimeAction.GET_TOOL_DETAIL)
        async def get_tool_detail(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.GET_TOOL_DETAIL,
                data,
                30,
            )

        @self.action(PluginToRuntimeAction.REPLY_STREAM)
        async def reply_stream(data: dict[str, Any]) -> handler.ActionResponse:
            if not data.get("run_id"):
                return handler.ActionResponse.error(
                    "run_id is required for streaming replies"
                )
            return await forward_agent_action(
                PluginToRuntimeAction.REPLY_STREAM, data, 30
            )

        @self.action(PluginToRuntimeAction.CALL_TOOL)
        async def call_tool_from_plugin(data: dict[str, Any]) -> handler.ActionResponse:
            if data.get("run_id") is not None:
                if "parameters" not in data:
                    return handler.ActionResponse.error(
                        "parameters is required for Runner tool calls"
                    )
            elif "tool_parameters" not in data:
                return handler.ActionResponse.error(
                    "tool_parameters is required for legacy tool calls"
                )
            return await forward_agent_action(
                PluginToRuntimeAction.CALL_TOOL,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

        @self.action(PluginToRuntimeAction.REQUEST_INTERACTION)
        async def request_interaction(data: dict[str, Any]) -> handler.ActionResponse:
            if not data.get("run_id"):
                return handler.ActionResponse.error("run_id is required")
            try:
                timeout = float(data["timeout"])
            except (KeyError, TypeError, ValueError):
                return handler.ActionResponse.error(
                    "A valid interaction timeout is required"
                )
            if not 0 < timeout <= 86400:
                return handler.ActionResponse.error(
                    "Interaction timeout exceeds 24 hours"
                )
            return await forward_agent_action(
                PluginToRuntimeAction.REQUEST_INTERACTION,
                data,
                timeout + 25,
            )

        @self.action(PluginToRuntimeAction.LIST_PLUGINS_MANIFEST)
        async def list_plugins_manifest(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.LIST_PLUGINS_MANIFEST, data, 30
            )

        @self.action(PluginToRuntimeAction.HISTORY_PAGE)
        async def history_page(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.HISTORY_PAGE, data, 30
            )

        @self.action(PluginToRuntimeAction.GET_BOX_STATUS)
        async def get_box_status(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.GET_BOX_STATUS,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

        @self.action(PluginToRuntimeAction.LIST_BOXES)
        async def list_boxes(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.LIST_BOXES, data, LONG_RUNNING_OPERATION_TIMEOUT
            )

        @self.action(PluginToRuntimeAction.ACQUIRE_BOX)
        async def acquire_box(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.ACQUIRE_BOX, data, LONG_RUNNING_OPERATION_TIMEOUT
            )

        @self.action(PluginToRuntimeAction.BIND_BOX)
        async def bind_box(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.BIND_BOX, data, LONG_RUNNING_OPERATION_TIMEOUT
            )

        @self.action(PluginToRuntimeAction.IMPORT_BOX_ATTACHMENTS)
        async def import_box_attachments(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.IMPORT_BOX_ATTACHMENTS,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

        @self.action(PluginToRuntimeAction.READ_INPUT_ATTACHMENT)
        async def read_input_attachment(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.READ_INPUT_ATTACHMENT,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

        @self.action(PluginToRuntimeAction.EXPORT_BOX_FILES)
        async def export_box_files(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.EXPORT_BOX_FILES,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

        @self.action(PluginToRuntimeAction.GET_PROMPT)
        async def get_prompt(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.GET_PROMPT, data, 15
            )

        @self.action(PluginToRuntimeAction.HISTORY_SEARCH)
        async def history_search(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.HISTORY_SEARCH, data, 30
            )

        @self.action(PluginToRuntimeAction.EVENT_GET)
        async def event_get(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.EVENT_GET, data, 15)

        @self.action(PluginToRuntimeAction.EVENT_PAGE)
        async def event_page(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.EVENT_PAGE, data, 30
            )

        @self.action(PluginToRuntimeAction.STEERING_PULL)
        async def steering_pull(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.STEERING_PULL, data, 15
            )

        @self.action(PluginToRuntimeAction.STEERING_ACK)
        async def steering_ack(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.STEERING_ACK, data, 15
            )

        @self.action(PluginToRuntimeAction.STATE_GET)
        async def state_get(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.STATE_GET, data, 15)

        @self.action(PluginToRuntimeAction.STATE_SET)
        async def state_set(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.STATE_SET, data, 15)

        @self.action(PluginToRuntimeAction.STATE_DELETE)
        async def state_delete(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.STATE_DELETE, data, 15
            )

        @self.action(PluginToRuntimeAction.STATE_LIST)
        async def state_list(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.STATE_LIST, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_GET)
        async def run_get(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.RUN_GET, data, 15)

        @self.action(PluginToRuntimeAction.RUN_LIST)
        async def run_list(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.RUN_LIST, data, 30)

        @self.action(PluginToRuntimeAction.RUN_EVENTS_PAGE)
        async def run_events_page(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_EVENTS_PAGE, data, 30
            )

        @self.action(PluginToRuntimeAction.RUN_CANCEL)
        async def run_cancel(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_CANCEL, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_CANCEL_ACK)
        async def run_cancel_ack(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_CANCEL_ACK, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_RETRY)
        async def run_retry(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.RUN_RETRY, data, 15)

        @self.action(PluginToRuntimeAction.RUN_RESUME)
        async def run_resume(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_RESUME, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_APPEND_RESULT)
        async def run_append_result(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_APPEND_RESULT, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_FINALIZE)
        async def run_finalize(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_FINALIZE, data, 15
            )

        @self.action(PluginToRuntimeAction.RUNTIME_REGISTER)
        async def runtime_register(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNTIME_REGISTER, data, 15
            )

        @self.action(PluginToRuntimeAction.RUNTIME_HEARTBEAT)
        async def runtime_heartbeat(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNTIME_HEARTBEAT, data, 10
            )

        @self.action(PluginToRuntimeAction.RUNTIME_LIST)
        async def runtime_list(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNTIME_LIST, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_CLAIM)
        async def run_claim(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.RUN_CLAIM, data, 15)

        @self.action(PluginToRuntimeAction.RUN_RENEW_CLAIM)
        async def run_renew_claim(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_RENEW_CLAIM, data, 15
            )

        @self.action(PluginToRuntimeAction.RUN_RELEASE_CLAIM)
        async def run_release_claim(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUN_RELEASE_CLAIM, data, 15
            )

        @self.action(PluginToRuntimeAction.RUNNER_LIST)
        async def runner_list(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNNER_LIST, data, 15
            )

        @self.action(PluginToRuntimeAction.RUNTIME_RECONCILE)
        async def runtime_reconcile(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNTIME_RECONCILE, data, 30
            )

        @self.action(PluginToRuntimeAction.RUN_STATS)
        async def run_stats(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(PluginToRuntimeAction.RUN_STATS, data, 30)

        @self.action(PluginToRuntimeAction.RUNTIME_STATS)
        async def runtime_stats(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNTIME_STATS, data, 15
            )

        @self.action(PluginToRuntimeAction.RUNNER_STATS)
        async def runner_stats(data: dict[str, Any]) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.RUNNER_STATS, data, 30
            )

        @self.action(PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS)
        async def list_application_operations(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.LIST_APPLICATION_OPERATIONS, data, 15
            )

        @self.action(PluginToRuntimeAction.CALL_APPLICATION_OPERATION)
        async def call_application_operation(
            data: dict[str, Any],
        ) -> handler.ActionResponse:
            return await forward_agent_action(
                PluginToRuntimeAction.CALL_APPLICATION_OPERATION,
                data,
                LONG_RUNNING_OPERATION_TIMEOUT,
            )

    def validate_inbound_action_context(
        self,
        action: str,
        action_context: ActionEnvelopeContext | None,
    ) -> ActionEnvelopeContext | None:
        """Fence production worker actions to the consumed launch capability."""

        if self.debug_plugin and not (
            action == PluginToRuntimeAction.REGISTER_PLUGIN.value
            and not self.debug_auth_token
        ):
            if self.debug_auth_token:
                current_binding = self.context.workspace_debug_tokens.binding_for_token(
                    self.debug_auth_token
                )
                if current_binding is None:
                    raise ValueError("Workspace debug credential expired")
                if (
                    self.debug_workspace_binding is None
                    or not self.debug_workspace_binding.same_workspace(current_binding)
                ):
                    raise ValueError("Workspace debug credential was fenced")
            return super().validate_inbound_action_context(action, action_context)

        if action == PluginToRuntimeAction.REGISTER_PLUGIN.value:
            if self.bound_action_context is not None:
                raise ValueError("Plugin worker is already registered")
            if action_context is not None:
                raise ValueError("Plugin registration does not accept action context")
            return None

        if action == CommonAction.PING.value and self.bound_action_context is None:
            if action_context is not None:
                raise ValueError("PING does not accept action context")
            return None

        binding = self.bound_action_context
        if self.shared_pool_digest is not None:
            if not isinstance(action_context, InstallationBinding):
                raise ValueError("Shared pool action requires InstallationBinding")
            if action_context.artifact_digest != self.shared_pool_digest:
                raise ValueError("Shared pool action artifact does not match worker")
            if action_context not in self._shared_pool_bindings:
                raise ValueError("Shared pool installation binding is not attached")
            if not self.context.is_current_installation_binding(action_context):
                raise ValueError("Shared pool installation binding has been revoked")
            return action_context
        if binding is None:
            if getattr(self.context, "runtime_profile", "oss_dev") != "shared":
                return super().validate_inbound_action_context(
                    action,
                    action_context,
                )
            raise ValueError("Plugin worker must register before calling actions")
        if isinstance(binding, InstallationBinding) and not (
            self.context.is_current_installation_binding(binding)
        ):
            raise ValueError("Plugin worker installation binding has been revoked")
        return super().validate_inbound_action_context(action, action_context)

    def set_shared_pool_bindings(
        self,
        digest: str,
        bindings: typing.Iterable[InstallationBinding],
    ) -> None:
        self.shared_pool_digest = digest
        self._shared_pool_bindings = set(bindings)

    async def call_action(
        self,
        action: ActionType,
        data: dict[str, Any],
        timeout: float | None = 15.0,
        action_context: ActionEnvelopeContext | dict[str, Any] | None = None,
        cancel_peer_on_cancel: bool = False,
    ) -> dict[str, Any]:
        """Dispatch to the shared worker with the in-flight installation binding.

        Runtime->plugin dispatches run inside the control handler task, where the
        installation binding is visible. Worker-originated relays run in another
        task and cannot observe that contextvar, so the dispatch itself has to
        carry the binding for the worker to inherit it on its own outbound calls.
        """

        if self.shared_pool_digest is not None and action_context is None:
            control_binding = self.context.plugin_mgr._current_control_binding()
            if control_binding in self._shared_pool_bindings:
                action_context = control_binding
        return await super().call_action(
            action,
            data,
            timeout=timeout,
            action_context=action_context,
            cancel_peer_on_cancel=cancel_peer_on_cancel,
        )

    def resolve_outbound_action_context(
        self,
        action_context: ActionEnvelopeContext | dict[str, Any] | None,
    ) -> ActionEnvelopeContext | None:
        if self.shared_pool_digest is not None and action_context is None:
            # A plugin-originated relay carries the binding the worker derived from
            # the dispatch it is serving. The control-context lookup stays as the
            # fallback for relays that arrive without one, because a worker relay
            # runs in another task and cannot observe that contextvar.
            inbound = self.current_action_context
            if inbound in self._shared_pool_bindings:
                return inbound
            current = self.context.plugin_mgr._current_control_binding()
            if current not in self._shared_pool_bindings:
                raise ValueError(
                    "Shared pool outbound action requires an attached binding"
                )
            return current
        return super().resolve_outbound_action_context(action_context)

    async def initialize_plugin(
        self, plugin_settings: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.INITIALIZE_PLUGIN,
            {"plugin_settings": plugin_settings},
        )

        return resp

    async def initialize_plugin_slot(
        self,
        binding: InstallationBinding,
        plugin_settings: dict[str, Any] | None = None,
        *,
        timeout: float | None = 15.0,
    ) -> dict[str, Any]:
        return await self.call_action(
            RuntimeToPluginAction.ATTACH_PLUGIN_SLOT,
            {"plugin_settings": plugin_settings or {}},
            action_context=binding,
            timeout=timeout,
            cancel_peer_on_cancel=True,
        )

    async def detach_plugin_slot(
        self,
        binding: InstallationBinding,
    ) -> dict[str, Any]:
        return await self.call_action(
            RuntimeToPluginAction.DETACH_PLUGIN_SLOT,
            {},
            action_context=binding,
        )

    async def get_plugin_slot_container(
        self,
        binding: InstallationBinding,
    ) -> dict[str, Any]:
        return await self.call_action(
            RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER,
            {},
            action_context=binding,
        )

    async def get_plugin_container(self) -> dict[str, Any]:
        resp = await self.call_action(RuntimeToPluginAction.GET_PLUGIN_CONTAINER, {})

        return resp

    async def get_plugin_icon(self) -> dict[str, Any]:
        resp = await self.call_action(RuntimeToPluginAction.GET_PLUGIN_ICON, {})
        return resp

    async def get_plugin_readme(self, language: str) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.GET_PLUGIN_README, {"language": language}
        )
        return resp

    async def get_plugin_assets_file(self, file_key: str) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.GET_PLUGIN_ASSETS_FILE, {"file_key": file_key}
        )
        return resp

    async def build_plugin_package(
        self,
        manifest_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask the plugin process to build a ``.lbpkg`` from its working dir."""
        resp = await self.call_action(
            RuntimeToPluginAction.BUILD_PLUGIN_PACKAGE,
            {"manifest_overrides": manifest_overrides or {}},
            timeout=LONG_RUNNING_OPERATION_TIMEOUT,
        )
        return resp

    async def git_sync_plugin(
        self,
        *,
        repo_url: str = "",
        token: str = "",
        branch: str = "",
        commit_message: str = "",
        manifest_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Ask the plugin process to commit and push its working dir to GitHub."""
        resp = await self.call_action(
            RuntimeToPluginAction.GIT_SYNC_PLUGIN,
            {
                "repo_url": repo_url,
                "token": token,
                "branch": branch,
                "commit_message": commit_message,
                "manifest_overrides": manifest_overrides or {},
            },
            timeout=LONG_RUNNING_OPERATION_TIMEOUT,
        )
        return resp

    async def call_page_api(
        self,
        page_id: str,
        endpoint: str,
        method: str,
        body: Any = None,
    ) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.PAGE_API,
            {
                "page_id": page_id,
                "endpoint": endpoint,
                "method": method,
                "body": body,
            },
            timeout=30,
        )
        return resp

    async def emit_event(self, event_context: dict[str, Any]) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.EMIT_EVENT,
            {"event_context": event_context},
            timeout=LONG_RUNNING_OPERATION_TIMEOUT,
        )

        return resp

    async def call_tool(
        self,
        tool_name: str,
        tool_parameters: dict[str, Any],
        session: dict[str, Any],
        query_id: int,
        query_uuid: str | None = None,
    ) -> dict[str, Any]:
        query_ref: dict[str, Any] = {"query_id": query_id}
        if query_uuid is not None:
            query_ref["query_uuid"] = query_uuid
        resp = await self.call_action(
            RuntimeToPluginAction.CALL_TOOL,
            {
                "tool_name": tool_name,
                "tool_parameters": tool_parameters,
                "session": session,
                **query_ref,
            },
            timeout=LONG_RUNNING_OPERATION_TIMEOUT,
        )

        return resp

    async def execute_command(
        self, command_context: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        gen = self.call_action_generator(
            RuntimeToPluginAction.EXECUTE_COMMAND,
            {"command_context": command_context},
            timeout=LONG_RUNNING_OPERATION_TIMEOUT,
        )

        async for resp in gen:
            yield resp

    async def retrieve_knowledge(
        self, retriever_name: str, retrieval_context: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.RETRIEVE_KNOWLEDGE,
            {"retriever_name": retriever_name, "retrieval_context": retrieval_context},
            timeout=KNOWLEDGE_RETRIEVAL_TIMEOUT,
        )
        return resp

    async def shutdown_plugin(self) -> dict[str, Any]:
        """Send shutdown notification to the plugin.

        For debug plugins, this will trigger reconnection.
        For production plugins, this is just a notification before shutdown.
        """
        resp = await self.call_action(
            RuntimeToPluginAction.SHUTDOWN,
            {},
        )
        return resp

    async def notify_plugin_diagnostic(
        self, diagnostic: dict[str, Any]
    ) -> dict[str, Any]:
        resp = await self.call_action(
            RuntimeToPluginAction.PLUGIN_DIAGNOSTIC,
            diagnostic,
            timeout=5,
        )
        return resp

    # ================= Knowledge Engine Methods =================

    async def rag_ingest_document(self, context_data: dict[str, Any]) -> dict[str, Any]:
        """Call plugin to ingest a document."""
        resp = await self.call_action(
            RuntimeToPluginAction.INGEST_DOCUMENT,
            {"context": context_data},
            timeout=1200,  # Ingestion can be slow for large documents
        )
        return resp

    async def rag_delete_document(self, kb_id: str, document_id: str) -> dict[str, Any]:
        """Call plugin to delete a document."""
        resp = await self.call_action(
            RuntimeToPluginAction.DELETE_DOCUMENT,
            {"kb_id": kb_id, "document_id": document_id},
            timeout=30,
        )
        return resp

    async def rag_on_kb_create(
        self, kb_id: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Notify plugin about KB creation."""
        resp = await self.call_action(
            RuntimeToPluginAction.ON_KB_CREATE,
            {"kb_id": kb_id, "config": config},
            timeout=30,
        )
        return resp

    async def rag_on_kb_delete(self, kb_id: str) -> dict[str, Any]:
        """Notify plugin about KB deletion."""
        resp = await self.call_action(
            RuntimeToPluginAction.ON_KB_DELETE, {"kb_id": kb_id}, timeout=30
        )
        return resp

    async def get_rag_capabilities(self) -> dict[str, Any]:
        """Get RAG capabilities from plugin."""
        resp = await self.call_action(
            RuntimeToPluginAction.GET_RAG_CAPABILITIES, {}, timeout=10
        )
        return resp

    # ================= Parser Methods =================

    async def parse_document(
        self, context_data: dict[str, Any], file_bytes: bytes
    ) -> dict[str, Any]:
        """Call plugin to parse a document.

        Sends file content via chunked FILE_CHUNK transfer, then invokes
        the PARSE_DOCUMENT action with a file_key reference.
        """
        file_key = await self.send_file(file_bytes, "")
        context_data["file_key"] = file_key

        resp = await self.call_action(
            RuntimeToPluginAction.PARSE_DOCUMENT,
            {"context": context_data},
            timeout=300,
        )
        return resp
