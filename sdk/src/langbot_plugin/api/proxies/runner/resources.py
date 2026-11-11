"""Run-scoped resource APIs for Runner components."""

from __future__ import annotations

from contextlib import aclosing

import base64
from copy import deepcopy
from typing import Any

from langbot_plugin.api.entities.builtin.provider.reasoning import ReasoningLevel

from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.entities.builtin.resource import tool as resource_tool
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction


class AgentRunResourceAPIMixin:
    def get_allowed_models(self) -> list[Any]:
        """Get the list of models authorized for this run."""
        return deepcopy(self._granted_resources.models)

    def get_allowed_tools(self) -> list[Any]:
        """Get the list of tools authorized for this run."""
        return deepcopy(self._granted_resources.tools)

    def get_allowed_knowledge_bases(self) -> list[Any]:
        """Get the list of knowledge bases authorized for this run."""
        return deepcopy(self._granted_resources.knowledge_bases)

    async def get_llm_models(self) -> list[str]:
        """List model IDs granted to this invocation."""
        return [model.model_id for model in self.get_allowed_models()]

    async def list_tools(self) -> list[dict[str, Any]]:
        """List callable tools, including event and platform APIs, from frozen grants."""
        return [
            {
                "name": tool.tool_name,
                "description": tool.description,
                "parameters": tool.parameters,
                "type": tool.tool_type,
                "operations": sorted(self._allowed_tool_operations[tool.tool_name]),
            }
            for tool in self.get_allowed_tools()
            if "call" in self._allowed_tool_operations[tool.tool_name]
        ]

    async def list_knowledge_bases(self) -> list[dict[str, Any]]:
        """List knowledge bases granted to this invocation."""
        return [
            {"uuid": kb.kb_id, "name": kb.kb_name, "type": kb.kb_type}
            for kb in self.get_allowed_knowledge_bases()
            if "list" in self._allowed_kb_operations[kb.kb_id]
        ]

    # ================= Permission Validation =================

    async def count_tokens(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] | None = None,
        extra_args: dict[str, Any] | None = None,
        timeout: float | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ) -> int:
        """Count model input tokens with Host provider/tokenizer settings."""
        self._validate_model_access(llm_model_uuid, "count_tokens")
        effective_timeout = self._bounded_timeout(default=30.0, requested=timeout)
        funcs = funcs or []
        extra_args = extra_args or {}
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.COUNT_TOKENS,
            {
                "run_id": self.run_id,
                **(await self._api._reasoning_payload(reasoning_level)),
                "llm_model_uuid": llm_model_uuid,
                "messages": [m.model_dump() for m in messages],
                "funcs": [f.model_dump() for f in funcs],
                "extra_args": extra_args,
                "timeout": effective_timeout,
            },
            effective_timeout,
        )
        tokens = self._expect_key(resp, "tokens", PluginToRuntimeAction.COUNT_TOKENS)
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise ValueError(
                f"{PluginToRuntimeAction.COUNT_TOKENS.value} response field tokens must be an integer"
            )
        return tokens

    async def invoke_llm(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] | None = None,
        extra_args: dict[str, Any] | None = None,
        timeout: float | None = None,
        remove_think: bool | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ) -> provider_message.Message:
        """Invoke an LLM model with permission validation."""
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
            remove_think=remove_think,
        )
        return result.message

    async def invoke_llm_with_usage(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] | None = None,
        extra_args: dict[str, Any] | None = None,
        timeout: float | None = None,
        remove_think: bool | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ) -> provider_message.LLMInvokeResult:
        """Invoke an LLM model and return the message plus optional provider usage."""
        self._validate_model_access(llm_model_uuid, "invoke")
        effective_timeout = self._bounded_timeout(default=120.0, requested=timeout)
        funcs = funcs or []
        extra_args = extra_args or {}
        payload = {
            **(await self._api._reasoning_payload(reasoning_level)),
            "run_id": self.run_id,
            "llm_model_uuid": llm_model_uuid,
            "messages": [m.model_dump() for m in messages],
            "funcs": [f.model_dump() for f in funcs],
            "extra_args": extra_args,
            "timeout": effective_timeout,
        }
        if remove_think is not None:
            payload["remove_think"] = remove_think
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.INVOKE_LLM,
            payload,
            effective_timeout,
        )
        return provider_message.LLMInvokeResult.model_validate(
            {
                "message": self._expect_key(
                    resp,
                    "message",
                    PluginToRuntimeAction.INVOKE_LLM,
                ),
                "usage": resp.get("usage") if isinstance(resp, dict) else None,
            }
        )

    async def invoke_llm_stream(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] | None = None,
        extra_args: dict[str, Any] | None = None,
        remove_think: bool | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ):
        """Invoke an LLM model with streaming, permission validation."""
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
                remove_think=remove_think,
            )
        ) as owned_stream:
            async for event in owned_stream:
                if event.chunk is not None:
                    yield event.chunk

    async def invoke_llm_stream_events(
        self,
        llm_model_uuid: str,
        messages: list[provider_message.Message],
        funcs: list[resource_tool.LLMTool] | None = None,
        extra_args: dict[str, Any] | None = None,
        remove_think: bool | None = None,
        *,
        reasoning_level: ReasoningLevel | None = None,
    ):
        """Invoke an LLM model and yield chunks plus optional final usage events."""
        self._validate_model_access(llm_model_uuid, "stream")
        effective_timeout = self._bounded_timeout(default=120.0)
        funcs = funcs or []
        extra_args = extra_args or {}
        payload = {
            **(await self._api._reasoning_payload(reasoning_level)),
            "run_id": self.run_id,
            "llm_model_uuid": llm_model_uuid,
            "messages": [m.model_dump() for m in messages],
            "funcs": [f.model_dump() for f in funcs],
            "extra_args": extra_args,
            "timeout": effective_timeout,
        }
        if remove_think is not None:
            payload["remove_think"] = remove_think
        async with aclosing(
            self._api.plugin_runtime_handler.call_action_generator(
                PluginToRuntimeAction.INVOKE_LLM_STREAM,
                payload,
                effective_timeout,
            )
        ) as owned_stream:
            async for chunk_data in owned_stream:
                event_data: dict[str, Any] = {}
                if isinstance(chunk_data, dict) and "chunk" in chunk_data:
                    event_data["chunk"] = chunk_data["chunk"]
                if isinstance(chunk_data, dict) and "usage" in chunk_data:
                    event_data["usage"] = chunk_data["usage"]
                if not event_data:
                    event_data["chunk"] = self._expect_key(
                        chunk_data,
                        "chunk",
                        PluginToRuntimeAction.INVOKE_LLM_STREAM,
                    )
                yield provider_message.LLMStreamEvent.model_validate(event_data)

    # ================= Tool APIs (delegated with validation) =================

    async def get_tool_detail(self, tool_name: str) -> dict[str, Any]:
        """Get tool detail with permission validation.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool detail dict containing:
            - name: Tool name
            - description: Tool description for LLM
            - parameters: JSON schema of parameters

        Raises:
            PermissionDeniedError: Tool not authorized for this run
        """
        self._validate_tool_access(tool_name, "detail")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_TOOL_DETAIL,
            {
                "run_id": self.run_id,
                "tool_name": tool_name,
            },
            timeout,
        )
        return self._expect_key(resp, "tool", PluginToRuntimeAction.GET_TOOL_DETAIL)

    async def call_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool with permission validation."""
        self._validate_tool_access(tool_name, "call")
        if tool_name == "request_interaction":
            from langbot_plugin.api.entities.builtin.runner.interaction import (
                InteractionRequest,
            )

            request = InteractionRequest.model_validate(
                {
                    key: value
                    for key, value in parameters.items()
                    if key
                    not in {
                        "expires_in_seconds",
                        "timeout",
                        "on_unsupported",
                        "responders",
                    }
                }
            )
            result = await self.request_interaction(
                request,
                timeout=parameters.get(
                    "timeout", parameters.get("expires_in_seconds", 600)
                ),
                on_unsupported=parameters.get("on_unsupported", "degrade"),
                responders=parameters.get("responders", "actor"),
            )
            return result.model_dump(mode="json")
        timeout = self._bounded_timeout(default=180.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.CALL_TOOL,
            {
                "run_id": self.run_id,
                "tool_name": tool_name,
                "parameters": parameters,
            },
            timeout,
            cancel_peer_on_cancel=True,
        )
        return self._expect_key(resp, "result", PluginToRuntimeAction.CALL_TOOL)

    # ================= Knowledge Base API (delegated with validation) =================

    async def retrieve_knowledge(
        self,
        kb_id: str,
        query_text: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve from knowledge base with permission validation."""
        self._validate_knowledge_base_access(kb_id, "retrieve")
        timeout = self._bounded_timeout(default=30.0)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
            {
                "run_id": self.run_id,
                "kb_id": kb_id,
                "query_text": query_text,
                "top_k": top_k,
                "filters": filters or {},
            },
            timeout,
        )
        return self._expect_key(
            resp,
            "results",
            PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
        )

    # ================= Storage APIs (delegated with validation) =================

    async def set_plugin_storage(self, key: str, value: bytes) -> None:
        """Set a plugin storage value with permission validation."""
        self._validate_plugin_storage_access()
        await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.SET_PLUGIN_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
                "value_base64": base64.b64encode(value).decode("utf-8"),
            },
            self._bounded_timeout(default=15.0),
        )

    async def get_plugin_storage(self, key: str) -> bytes:
        """Get a plugin storage value with permission validation."""
        self._validate_plugin_storage_access()
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_PLUGIN_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
            },
            self._bounded_timeout(default=15.0),
        )
        encoded = self._expect_key(
            resp,
            "value_base64",
            PluginToRuntimeAction.GET_PLUGIN_STORAGE,
        )
        return base64.b64decode(encoded)

    async def get_plugin_storage_keys(self) -> list[str]:
        """Get all plugin storage keys with permission validation."""
        self._validate_plugin_storage_access()
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS,
            {
                "run_id": self.run_id,
            },
            self._bounded_timeout(default=15.0),
        )
        return self._expect_key(
            resp,
            "keys",
            PluginToRuntimeAction.GET_PLUGIN_STORAGE_KEYS,
        )

    async def delete_plugin_storage(self, key: str) -> None:
        """Delete a plugin storage value with permission validation."""
        self._validate_plugin_storage_access()
        await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.DELETE_PLUGIN_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
            },
            self._bounded_timeout(default=15.0),
        )

    async def set_workspace_storage(self, key: str, value: bytes) -> None:
        """Set a workspace storage value with permission validation."""
        self._validate_workspace_storage_access()
        await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.SET_WORKSPACE_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
                "value_base64": base64.b64encode(value).decode("utf-8"),
            },
            self._bounded_timeout(default=15.0),
        )

    async def get_workspace_storage(self, key: str) -> bytes:
        """Get a workspace storage value with permission validation."""
        self._validate_workspace_storage_access()
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
            },
            self._bounded_timeout(default=15.0),
        )
        encoded = self._expect_key(
            resp,
            "value_base64",
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE,
        )
        return base64.b64decode(encoded)

    async def get_workspace_storage_keys(self) -> list[str]:
        """Get all workspace storage keys with permission validation."""
        self._validate_workspace_storage_access()
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE_KEYS,
            {
                "run_id": self.run_id,
            },
            self._bounded_timeout(default=15.0),
        )
        return self._expect_key(
            resp,
            "keys",
            PluginToRuntimeAction.GET_WORKSPACE_STORAGE_KEYS,
        )

    async def delete_workspace_storage(self, key: str) -> None:
        """Delete a workspace storage value with permission validation."""
        self._validate_workspace_storage_access()
        await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.DELETE_WORKSPACE_STORAGE,
            {
                "run_id": self.run_id,
                "key": key,
            },
            self._bounded_timeout(default=15.0),
        )

    # ================= Version API (no authorization needed, delegated) =================

    async def get_langbot_version(self) -> str:
        """Get the LangBot version (no authorization needed)."""
        return await self._api.get_langbot_version()

    # ================= Rerank API (Runner-specific, not in LangBotAPIProxy) =================

    async def invoke_embedding(
        self, embedding_model_uuid: str, texts: list[str]
    ) -> list[list[float]]:
        """Invoke only an embedding model explicitly granted to this run."""
        self._validate_model_access(embedding_model_uuid, "invoke")
        response = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.INVOKE_EMBEDDING,
            {
                "run_id": self.run_id,
                "embedding_model_uuid": embedding_model_uuid,
                "texts": texts,
            },
            self._bounded_timeout(default=60.0),
        )
        return self._expect_key(
            response, "vectors", PluginToRuntimeAction.INVOKE_EMBEDDING
        )

    async def invoke_rerank(
        self,
        rerank_model_uuid: str,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        extra_args: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Invoke a rerank model to re-score documents.

        Args:
            rerank_model_uuid: UUID of the rerank model
            query: The query text for reranking
            documents: List of document texts to rerank
            top_k: Optional number of top results to return
            extra_args: Optional provider-specific options
            timeout: Request timeout in seconds

        Returns:
            List of dicts with 'index' and 'relevance_score' keys,
            sorted by relevance_score descending

        Example:
            results = await api.invoke_rerank(
                rerank_model_uuid="xxx-xxx",
                query="What is machine learning?",
                documents=["Doc 1 text", "Doc 2 text", "Doc 3 text"],
                top_k=5,
            )
            # results = [
            #     {"index": 2, "relevance_score": 0.95},
            #     {"index": 0, "relevance_score": 0.82},
            #     ...
            # ]
        """
        self._validate_model_access(rerank_model_uuid, "rerank")
        effective_timeout = self._bounded_timeout(default=30.0, requested=timeout)
        resp = await self._api.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.INVOKE_RERANK,
            {
                "run_id": self.run_id,
                "rerank_model_uuid": rerank_model_uuid,
                "query": query,
                "documents": documents,
                "top_k": top_k,
                "extra_args": extra_args or {},
            },
            timeout=effective_timeout,
        )
        return self._expect_key(resp, "results", PluginToRuntimeAction.INVOKE_RERANK)

    # ================= History APIs (run-scoped, conversation-scoped) =================
