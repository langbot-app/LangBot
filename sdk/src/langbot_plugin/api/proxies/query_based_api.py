from __future__ import annotations

from typing import Any

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.runtime.io.handler import Handler
import pydantic


class QueryBasedAPIProxy(pydantic.BaseModel):
    """The proxy for query based API."""

    query_id: int

    query_uuid: str | None = None

    plugin_runtime_handler: Handler = pydantic.Field(exclude=True)

    def _query_ref(self) -> dict[str, int | str]:
        payload: dict[str, int | str] = {"query_id": self.query_id}
        if self.query_uuid is not None:
            payload["query_uuid"] = self.query_uuid
        return payload

    def model_dump(self, **kwargs):
        payload = super().model_dump(**kwargs)
        if self.query_uuid is None:
            payload.pop("query_uuid", None)
        return payload

    async def reply(
        self, message_chain: platform_message.MessageChain, quote_origin: bool = False
    ):
        """Reply to the message sender"""
        return await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.REPLY_MESSAGE,
            {
                **self._query_ref(),
                "message_chain": message_chain.model_dump(mode="json"),
                "quote_origin": quote_origin,
            },
            timeout=180,
        )

    async def get_bot_uuid(self) -> str:
        """Get the bot uuid"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_BOT_UUID,
                self._query_ref(),
            )
        )["bot_uuid"]

    async def set_query_var(self, key: str, value: Any):
        """Set a query variable"""
        return await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.SET_QUERY_VAR,
            {
                **self._query_ref(),
                "key": key,
                "value": value,
            },
        )

    async def get_query_var(self, key: str) -> Any:
        """Get a query variable"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_QUERY_VAR,
                {
                    **self._query_ref(),
                    "key": key,
                },
            )
        )["value"]

    async def get_query_vars(self) -> dict[str, Any]:
        """Get all query variables"""
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.GET_QUERY_VARS,
                self._query_ref(),
            )
        )["vars"]

    async def create_new_conversation(self) -> dict[str, Any]:
        """Create a new conversation"""
        return await self.plugin_runtime_handler.call_action(
            PluginToRuntimeAction.CREATE_NEW_CONVERSATION,
            self._query_ref(),
        )

    async def list_pipeline_knowledge_bases(self) -> list[dict[str, Any]]:
        """List knowledge bases configured for the current pipeline.

        Returns a list of dicts, each containing:
        - uuid: Knowledge base UUID
        - name: Knowledge base name
        - description: Knowledge base description
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.LIST_PIPELINE_KNOWLEDGE_BASES,
                self._query_ref(),
            )
        )["knowledge_bases"]

    async def retrieve_knowledge(
        self,
        kb_id: str,
        query_text: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents from a knowledge base.

        The kb_id must be in the current pipeline's configured knowledge bases,
        otherwise an error is returned.

        Args:
            kb_id: Knowledge base UUID (from list_pipeline_knowledge_bases result)
            query_text: Search query text
            top_k: Number of results to return (default: 5)
            filters: Optional metadata filters for retrieval

        Returns a list of retrieval result entries.
        """
        return (
            await self.plugin_runtime_handler.call_action(
                PluginToRuntimeAction.RETRIEVE_KNOWLEDGE_BASE,
                {
                    **self._query_ref(),
                    "kb_id": kb_id,
                    "query_text": query_text,
                    "top_k": top_k,
                    "filters": filters or {},
                },
            )
        )["results"]

    class Config:
        arbitrary_types_allowed = True
