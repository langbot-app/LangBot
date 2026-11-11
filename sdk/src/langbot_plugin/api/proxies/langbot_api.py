from __future__ import annotations

import base64
import math
from contextlib import aclosing
from typing import Any, get_args

from langbot_plugin.api.entities.builtin.provider.reasoning import ReasoningLevel

from langbot_plugin.api.proxies.invocation import relay_event_origin, run_scoped

from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.resource import tool as resource_tool


SEND_MESSAGE_DEFAULT_TIMEOUT = 60.0
"""Default seconds a plugin waits for ``send_message`` to complete."""


def resolve_send_message_timeout(timeout: float | None) -> float:
    """Return the effective ``send_message`` timeout, validating explicit values."""
    if timeout is None:
        return SEND_MESSAGE_DEFAULT_TIMEOUT
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("send_message timeout must be a positive, finite number")
    return float(timeout)


class LangBotAPIProxy:
    """The proxy for langbot API."""

    plugin_runtime_handler: Handler

    def __init__(self, plugin_runtime_handler: Handler):
        self.plugin_runtime_handler = plugin_runtime_handler

    @property
    def execution(self):
        """Generic ExecutionAPI entry point for Core operations."""
        if not hasattr(self, "_execution_proxy"):
            from langbot_plugin.api.proxies.execution import ExecutionProxy

            self._execution_proxy = ExecutionProxy(self.plugin_runtime_handler)
        return self._execution_proxy

    @property
    def workspace(self):
        """Workspace operations proxy for listing and executing authorized operations."""
        if not hasattr(self, "_workspace_proxy"):
            from langbot_plugin.api.proxies.workspace import WorkspaceOperationsProxy

            self._workspace_proxy = WorkspaceOperationsProxy(
                self.plugin_runtime_handler
            )
        return self._workspace_proxy

    async def _reasoning_payload(self, level: ReasoningLevel | None) -> dict[str, Any]:
        """Keep legacy calls unchanged and reject unsupported explicit options."""
        if level is None:
            return {}
        if level not in get_args(ReasoningLevel):
            raise ValueError("Unsupported reasoning level")
        if not getattr(self, "_supports_reasoning_level", False):
            info = await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_LANGBOT_VERSION, {}
            )
            if "llm.reasoning_level" not in info.get("api_features", []):
                raise RuntimeError(
                    "This LangBot Host does not support reasoning_level; upgrade LangBot or omit the parameter."
                )
            self._supports_reasoning_level = True
        return {"reasoning_level": level}

    @run_scoped
    async def get_box_status(self):
        from langbot_plugin.api.entities.builtin.runner.box import BoxStatus

        return BoxStatus.model_validate(
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_BOX_STATUS, {}
            )
        )

    @run_scoped
    async def list_boxes(self):
        from langbot_plugin.api.entities.builtin.runner.box import BoxSession

        result = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.LIST_BOXES, {}
        )
        return [BoxSession.model_validate(item) for item in result["items"]]

    @run_scoped
    async def acquire_box(self, reuse_key: str, options: dict | None = None):
        from langbot_plugin.api.entities.builtin.runner.box import BoxSession

        return BoxSession.model_validate(
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.ACQUIRE_BOX,
                {"reuse_key": reuse_key, "options": options or {}},
                180,
            )
        )

    @run_scoped
    async def bind_box(self, box_id: str):
        from langbot_plugin.api.entities.builtin.runner.box import BoxBinding

        return BoxBinding.model_validate(
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.BIND_BOX,
                {"box_id": box_id},
                180,
            )
        )

    @run_scoped
    async def import_box_attachments(self, attachment_ids: list[str] | None = None):
        from langbot_plugin.api.entities.builtin.runner.box import BoxFile

        result = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.IMPORT_BOX_ATTACHMENTS,
            {"attachment_ids": attachment_ids},
            180,
        )
        return [BoxFile.model_validate(item) for item in result.get("items", [])]

    @run_scoped
    async def read_input_attachment(self, ref: str):
        """Read the bytes of one current-event attachment by ref."""
        from langbot_plugin.api.entities.builtin.runner.input import (
            InputAttachmentData,
        )

        result = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.READ_INPUT_ATTACHMENT,
            {"ref": ref},
            180,
        )
        return InputAttachmentData(
            ref=str(result.get("ref") or ref),
            name=result.get("name"),
            mime_type=result.get("mime_type"),
            data=base64.b64decode(result["content"], validate=True),
        )

    @run_scoped
    async def export_box_files(self, paths: list[str] | None = None):
        from langbot_plugin.api.entities.builtin.runner.box import BoxFile

        result = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.EXPORT_BOX_FILES,
            {"paths": paths},
            180,
        )
        warning = result.get("warning")
        return [
            BoxFile.model_validate({**item, "warning": warning})
            for item in result.get("items", [])
        ]

    @run_scoped
    async def get_langbot_version(self) -> str:
        """Get the langbot version"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_LANGBOT_VERSION, {}
            )
        )["version"]

    @run_scoped
    async def get_bots(self) -> list[str]:
        """Get all bots"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_BOTS, {}
            )
        )["bots"]

    @run_scoped
    async def get_bot_info(self, bot_uuid: str) -> dict[str, Any]:
        """Get a bot info"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_BOT_INFO, {"bot_uuid": bot_uuid}
            )
        )["bot"]

    @run_scoped
    async def send_message(
        self,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        message_chain: platform_message.MessageChain,
        *,
        timeout: float | None = None,
    ) -> Any:
        """Send a message to a bot

        Args:
            bot_uuid: The UUID of the bot
            target_type: The type of the target, can be "group", "person"
            target_id: The ID of the target
            message_chain: The message chain to send
            timeout: Seconds to wait for the host to finish sending. Defaults to
                ``SEND_MESSAGE_DEFAULT_TIMEOUT`` (60s). Media messages may need
                longer because the platform upload happens before sending. A
                timeout does not cancel a send already in progress on the host.
        """
        effective_timeout = resolve_send_message_timeout(timeout)
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.SEND_MESSAGE,
                relay_event_origin(
                    {
                        "bot_uuid": bot_uuid,
                        "target_type": target_type,
                        "target_id": target_id,
                        "message_chain": message_chain.model_dump(),
                        "timeout": effective_timeout,
                    }
                ),
                timeout=effective_timeout,
            )
        ).get("result")

    @run_scoped
    async def call_platform_api(
        self,
        bot_uuid: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a bot adapter API.

        Args:
            bot_uuid: The UUID of the bot
            action: Adapter API name, such as "get_group_info" or "call_platform_api"
            params: Parameters passed to the adapter API
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.CALL_PLATFORM_API,
                {
                    "bot_uuid": bot_uuid,
                    "action": action,
                    "params": params or {},
                },
            )
        )["result"]

    @run_scoped
    async def get_llm_models(self) -> list[str]:
        """Get all LLM models"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_LLM_MODELS, {}
            )
        )["llm_models"]

    @run_scoped
    async def invoke_llm(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] = [],
        extra_args: dict[str, Any] = {},
        timeout: float | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ) -> provider_message.Message:
        """Invoke an LLM model"""
        result = await self.invoke_llm_with_usage(
            llm_model_uuid=llm_model_uuid,
            messages=messages,
            funcs=funcs,
            extra_args=extra_args,
            **(
                {"reasoning_level": reasoning_level}
                if reasoning_level is not None
                else {}
            ),
            timeout=timeout,
        )
        return result.message

    @run_scoped
    async def invoke_llm_with_usage(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] = [],
        extra_args: dict[str, Any] = {},
        timeout: float | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ) -> provider_message.LLMInvokeResult:
        """Invoke an LLM model and return the message plus optional provider usage."""
        effective_timeout = timeout if timeout is not None else 120.0
        resp = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.INVOKE_LLM,
            relay_event_origin(
                {
                    **(await self._reasoning_payload(reasoning_level)),
                    "llm_model_uuid": llm_model_uuid,
                    "messages": [m.model_dump() for m in messages],
                    "funcs": [f.model_dump() for f in funcs],
                    "extra_args": extra_args,
                    "timeout": effective_timeout,
                }
            ),
            timeout=effective_timeout,
        )

        return provider_message.LLMInvokeResult.model_validate(
            {
                "message": resp["message"],
                "usage": resp.get("usage") if isinstance(resp, dict) else None,
            }
        )

    @run_scoped
    async def invoke_llm_stream(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] = [],
        extra_args: dict[str, Any] = {},
        *,
        reasoning_level: ReasoningLevel | None = None,
    ):
        """Invoke an LLM model with streaming response."""
        async with aclosing(
            self.invoke_llm_stream_events(
                llm_model_uuid=llm_model_uuid,
                messages=messages,
                funcs=funcs,
                extra_args=extra_args,
                **(
                    {"reasoning_level": reasoning_level}
                    if reasoning_level is not None
                    else {}
                ),
            )
        ) as owned_stream:
            async for event in owned_stream:
                if event.chunk is not None:
                    yield event.chunk

    @run_scoped
    async def invoke_llm_stream_events(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] = [],
        extra_args: dict[str, Any] = {},
        *,
        reasoning_level: ReasoningLevel | None = None,
    ):
        """Invoke an LLM model and yield chunks plus optional final usage events."""
        async with aclosing(
            self.plugin_runtime_handler.call_action_generator(
                PluginToRuntimeAction.INVOKE_LLM_STREAM,
                relay_event_origin(
                    {
                        **(await self._reasoning_payload(reasoning_level)),
                        "llm_model_uuid": llm_model_uuid,
                        "messages": [m.model_dump() for m in messages],
                        "funcs": [f.model_dump() for f in funcs],
                        "extra_args": extra_args,
                    }
                ),
            )
        ) as owned_stream:
            async for chunk_data in owned_stream:
                event_data: dict[str, Any] = {}
                if isinstance(chunk_data, dict) and "chunk" in chunk_data:
                    event_data["chunk"] = chunk_data["chunk"]
                if isinstance(chunk_data, dict) and "usage" in chunk_data:
                    event_data["usage"] = chunk_data["usage"]
                if not event_data:
                    event_data["chunk"] = chunk_data["chunk"]
                yield provider_message.LLMStreamEvent.model_validate(event_data)

    @run_scoped
    async def set_plugin_storage(self, key: str, value: bytes) -> None:
        """Set a plugin storage value"""
        encoded = base64.b64encode(value).decode("utf-8")
        await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.SET_PLUGIN_STORAGE,
            {"key": key, "value_base64": encoded},
        )

    @run_scoped
    async def get_plugin_storage(self, key: str) -> bytes:
        """Get a plugin storage value"""
        resp = (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_PLUGIN_STORAGE, {"key": key}
            )
        )["value_base64"]

        return base64.b64decode(resp)

    @run_scoped
    async def get_plugin_storage_keys(self) -> list[str]:
        """Get all plugin storage keys"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS, {}
            )
        )["keys"]

    @run_scoped
    async def delete_plugin_storage(self, key: str) -> None:
        """Delete a plugin storage value"""
        await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.DELETE_PLUGIN_STORAGE, {"key": key}
        )

    @run_scoped
    async def set_workspace_storage(self, key: str, value: bytes) -> None:
        """Set a workspace storage value"""
        encoded = base64.b64encode(value).decode("utf-8")
        await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.SET_WORKSPACE_STORAGE,
            {"key": key, "value_base64": encoded},
        )

    @run_scoped
    async def get_workspace_storage(self, key: str) -> bytes:
        """Get a workspace storage value"""
        resp = (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_WORKSPACE_STORAGE, {"key": key}
            )
        )["value_base64"]

        return base64.b64decode(resp)

    @run_scoped
    async def get_workspace_storage_keys(self) -> list[str]:
        """Get all workspace storage keys"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_WORKSPACE_STORAGE_KEYS, {}
            )
        )["keys"]

    @run_scoped
    async def delete_workspace_storage(self, key: str) -> None:
        """Delete a workspace storage value"""
        await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.DELETE_WORKSPACE_STORAGE, {"key": key}
        )

    @run_scoped
    async def get_config_file(self, file_key: str) -> bytes:
        """Get a config file by file key

        Args:
            file_key: The file key from plugin config (file or array[file] type)

        Returns:
            The file content as bytes
        """
        resp = (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_CONFIG_FILE, {"file_key": file_key}
            )
        )["file_base64"]

        return base64.b64decode(resp)

    @run_scoped
    async def list_plugins_manifest(self) -> list[str]:
        """List all plugins"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_PLUGINS_MANIFEST, {}
            )
        )["plugins"]

    @run_scoped
    async def list_commands(self) -> list[str]:
        """List all commands"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_COMMANDS, {}
            )
        )["commands"]

    @run_scoped
    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools.

        Returns:
            List of tool info dicts, each containing:
            - name: Tool name (plugin_author/plugin_name/tool_name format)
            - label: I18n label dict
            - description: I18n description dict
            - parameters: JSON Schema of tool parameters
            - spec: Full tool spec
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_TOOLS, {}
            )
        )["tools"]

    @run_scoped
    async def get_tool_detail(self, tool_name: str) -> dict[str, Any]:
        """Get detailed information about a specific tool.

        Args:
            tool_name: The name of the tool to get details for.

        Returns:
            Tool detail dict containing name, label, description, parameters, spec.

        Raises:
            Exception: If the tool is not found.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_TOOL_DETAIL, {"tool_name": tool_name}
            )
        )["tool"]

    @run_scoped
    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        session: dict[str, Any] | None = None,
        query_id: int | None = None,
    ) -> dict[str, Any]:
        """Call a specific tool.

        Args:
            tool_name: The name of the tool to call.
            parameters: The parameters to pass to the tool.
            session: The current session dict.
            query_id: The current query ID.

        Returns:
            Tool response dict.
        """
        if session is None or query_id is None:
            raise ValueError(
                "session and query_id are required outside a Runner invocation"
            )
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.CALL_TOOL,
                {
                    "tool_name": tool_name,
                    "tool_parameters": parameters,
                    "session": session,
                    "query_id": query_id,
                },
                timeout=180,
            )
        )["tool_response"]

    # ================= RAG Capability APIs =================

    @run_scoped
    async def invoke_embedding(
        self, embedding_model_uuid: str, texts: list[str]
    ) -> list[list[float]]:
        """Generate embeddings using Host's embedding model.

        Args:
            embedding_model_uuid: The UUID of the embedding model to use.
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.INVOKE_EMBEDDING,
                {"embedding_model_uuid": embedding_model_uuid, "texts": texts},
                timeout=60,
            )
        )["vectors"]

    @run_scoped
    async def invoke_rerank(
        self,
        rerank_model_uuid: str,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        extra_args: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> list[dict[str, Any]]:
        """Rerank documents using Host's rerank model.

        Args:
            rerank_model_uuid: The UUID of the rerank model to use.
            query: Query text used to score document relevance.
            documents: Candidate document texts to rerank.
            top_k: Optional number of scored results to return.
            extra_args: Optional provider-specific arguments.
            timeout: Request timeout in seconds.

        Returns:
            List of score dicts, usually containing ``index`` and
            ``relevance_score``.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.INVOKE_RERANK,
                {
                    "rerank_model_uuid": rerank_model_uuid,
                    "query": query,
                    "documents": documents,
                    "top_k": top_k,
                    "extra_args": extra_args or {},
                },
                timeout=timeout,
            )
        )["results"]

    @run_scoped
    async def vector_upsert(
        self,
        collection_id: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict[str, Any]] | None = None,
        documents: list[str] | None = None,
    ) -> None:
        """Upsert vectors to Host's vector store.

        Args:
            collection_id: Target collection ID.
            vectors: List of vectors.
            ids: List of unique IDs for vectors.
            metadata: Optional list of metadata dicts corresponding to vectors.
            documents: Optional raw text documents. Required for full-text
                and hybrid search in backends that support them.
        """
        data: dict[str, Any] = {
            "collection_id": collection_id,
            "vectors": vectors,
            "ids": ids,
            "metadata": metadata,
        }
        if documents is not None:
            data["documents"] = documents
        await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.VECTOR_UPSERT,
            data,
            timeout=60,
        )

    @run_scoped
    async def vector_search(
        self,
        collection_id: str,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        search_type: str = "vector",
        query_text: str = "",
        vector_weight: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search similar vectors in Host's vector store.

        Args:
            collection_id: Target collection ID.
            query_vector: Query vector for similarity search.
            top_k: Number of results to return.
            filters: Optional metadata filters.
            search_type: One of 'vector', 'full_text', 'hybrid'.
            query_text: Raw query text, used for full_text and hybrid search.
            vector_weight: Weight for vector search in hybrid mode (0.0–1.0).
                ``None`` means use equal weights (backward compatible).

        Returns:
            List of search results (dict with id, distance, metadata).
            Some hosts may also include an optional score field, but distance
            is the stable field and lower values mean more similar results.
        """
        data = {
            "collection_id": collection_id,
            "query_vector": query_vector,
            "top_k": top_k,
            "filters": filters,
            "search_type": search_type,
            "query_text": query_text,
            "vector_weight": vector_weight,
        }
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.VECTOR_SEARCH,
                data,
                timeout=30,
            )
        )["results"]

    @run_scoped
    async def vector_delete(
        self,
        collection_id: str,
        file_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Delete vectors from Host's vector store.

        Args:
            collection_id: Target collection ID.
            file_ids: File IDs whose associated vectors should be deleted.
            filters: Optional metadata filters for deletion.

        Returns:
            Number of deleted items.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.VECTOR_DELETE,
                {
                    "collection_id": collection_id,
                    "file_ids": file_ids,
                    "filters": filters,
                },
                timeout=30,
            )
        )["count"]

    @run_scoped
    async def vector_list(
        self,
        collection_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List vectors from Host's vector store by metadata filter.

        Args:
            collection_id: Target collection ID.
            filters: Optional metadata filters.
            limit: Maximum number of items to return.
            offset: Number of items to skip for pagination.

        Returns:
            Dict with 'items' (list of dicts with id, document, metadata)
            and 'total' (total count matching the filter, best-effort).
        """
        return await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.VECTOR_LIST,
            {
                "collection_id": collection_id,
                "filters": filters,
                "limit": limit,
                "offset": offset,
            },
            timeout=30,
        )

    @run_scoped
    async def get_knowledge_file_stream(self, storage_path: str) -> bytes:
        """Get file content from Host's storage.

        Args:
            storage_path: Logic path in FileObject.

        Returns:
            File content bytes.
        """
        resp = await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_KNOWLEDEGE_FILE_STREAM,
            {"storage_path": storage_path},
        )
        # File was transferred via FILE_CHUNK; read from local temp
        file_key = resp["file_key"]
        file_bytes = await self.plugin_runtime_handler.read_local_file(file_key)
        await self.plugin_runtime_handler.delete_local_file(file_key)
        return file_bytes

    # ================= Knowledge Base APIs =================

    @run_scoped
    async def list_knowledge_bases(self) -> list[dict[str, Any]]:
        """List all knowledge bases available in the LangBot instance.

        Unlike query-based ``list_pipeline_knowledge_bases``, this API is
        globally available and not restricted to a specific pipeline's
        configured knowledge bases.

        Returns:
            List of dicts, each containing:
            - uuid: Knowledge base UUID
            - name: Knowledge base name
            - description: Knowledge base description
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_KNOWLEDGE_BASES, {}
            )
        )["knowledge_bases"]

    @run_scoped
    async def retrieve_knowledge(
        self,
        kb_id: str,
        query_text: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents from any knowledge base.

        Unlike query-based ``retrieve_knowledge``, this API is globally
        available and can access any knowledge base without pipeline
        restrictions.

        Args:
            kb_id: Knowledge base UUID
            query_text: Search query text
            top_k: Number of results to return (default: 5)
            filters: Optional metadata filters for retrieval

        Returns:
            List of retrieval result entries.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.RETRIEVE_KNOWLEDGE,
                {
                    "kb_id": kb_id,
                    "query_text": query_text,
                    "top_k": top_k,
                    "filters": filters or {},
                },
                timeout=30,
            )
        )["results"]

    # ================= Parser Capability APIs =================

    @run_scoped
    async def list_parsers(self, mime_type: str | None = None) -> list[dict[str, Any]]:
        """List available Parser plugins.

        Args:
            mime_type: Optional MIME type to filter parsers by.

        Returns:
            List of parser metadata dicts.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_PARSERS,
                {"mime_type": mime_type},
            )
        )["parsers"]

    @run_scoped
    async def invoke_parser(
        self,
        plugin_author: str,
        plugin_name: str,
        storage_path: str,
        mime_type: str,
        filename: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke a Parser plugin to parse a document.

        Args:
            plugin_author: Author of the parser plugin.
            plugin_name: Name of the parser plugin.
            storage_path: Path to the file in Host's storage system.
            mime_type: MIME type of the file.
            filename: Original filename.
            metadata: Optional extra metadata.

        Returns:
            Parse result dict with text, sections, and metadata.
        """
        return await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.INVOKE_PARSER,
            {
                "plugin_author": plugin_author,
                "plugin_name": plugin_name,
                "storage_path": storage_path,
                "mime_type": mime_type,
                "filename": filename,
                "metadata": metadata or {},
            },
            timeout=300,
        )
