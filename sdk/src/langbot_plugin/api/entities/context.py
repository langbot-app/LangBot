from __future__ import annotations

from typing import Any
import weakref

import pydantic

from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.events import BaseEventModel
from langbot_plugin.api.entities.execution import WorkspaceExecutionScope
import langbot_plugin.api.entities.events as events_module


global_eid_index = 0

cached_event_contexts: weakref.WeakValueDictionary[int, EventContext] = (
    weakref.WeakValueDictionary()
)


class EventContext(WorkspaceExecutionScope):
    """事件上下文, 保存此次事件运行的信息"""

    query_id: int = 0
    """请求ID"""

    query_uuid: str | None = None
    """Opaque query identifier preferred by multi-tenant Hosts."""

    eid: int = 0
    """事件编号"""

    event_name: str
    """事件名称"""

    event: pydantic.SerializeAsAny[BaseEventModel]
    """此次事件的对象，具体类型为handler注册时指定监听的类型，可查看events.py中的定义"""

    is_prevent_default: bool = False
    """是否阻止默认行为"""

    is_prevent_postorder: bool = False
    """是否阻止后续插件的执行"""

    origin_attribution: bool = False
    """Set by Hosts that accept ``origin_query_uuid`` on plugin actions.

    When true, plugin-level calls made while handling this event report the
    event's ``query_uuid`` so the Host can attribute monitoring records to the
    triggering message. Older Hosts never set it and receive no extra field.
    """

    # ========== APIs for plugins ==========

    ## ========= Query-based APIs =========

    async def reply(
        self, message_chain: platform_message.MessageChain, quote_origin: bool = False
    ):
        """Reply to the message request

        Args:
            message_chain (platform.types.MessageChain): LangBot message chain
            quote_origin (bool): Whether to quote the original message
        """

    async def get_bot_uuid(self) -> str:
        """Get the bot uuid"""

    async def set_query_var(self, key: str, value: Any):
        """Set a query variable"""

    async def get_query_var(self, key: str) -> Any:
        """Get a query variable"""

    async def get_query_vars(self) -> dict[str, Any]:
        """Get all query variables"""

    ## ========= Event-based APIs from plugin to use =========

    def prevent_default(self):
        """Prevent default behavior"""
        self.is_prevent_default = True

    def prevent_postorder(self):
        """Prevent subsequent plugin execution"""
        self.is_prevent_postorder = True

    # ========== The following methods are reserved for internal use, and plugins should not call them directly ==========

    def is_prevented_default(self):
        """Whether to prevent default behavior"""
        return self.is_prevent_default

    def is_prevented_postorder(self):
        """Whether to prevent subsequent plugin execution"""
        return self.is_prevent_postorder

    @classmethod
    def from_event(cls, event: BaseEventModel) -> EventContext:
        global global_eid_index
        query = event.query
        query_id = query.query_id if query else 0
        eid = global_eid_index
        event = event
        event_name = event.__class__.__name__
        is_prevent_default = False
        is_prevent_postorder = False

        obj = cls(
            instance_uuid=query.instance_uuid if query else event.instance_uuid,
            workspace_uuid=query.workspace_uuid if query else event.workspace_uuid,
            placement_generation=(
                query.placement_generation if query else event.placement_generation
            ),
            query_id=query_id,
            query_uuid=query.query_uuid if query else event.query_uuid,
            eid=eid,
            event_name=event_name,
            event=event,
            is_prevent_default=is_prevent_default,
            is_prevent_postorder=is_prevent_postorder,
        )

        cached_event_contexts[eid] = obj

        global_eid_index += 1

        return obj

    @pydantic.model_validator(mode="after")
    def align_event_execution_scope(self) -> EventContext:
        self.inherit_execution_scope(self.event)
        self.event.inherit_execution_scope(self)
        if self.query_uuid is None:
            self.query_uuid = self.event.query_uuid
        elif (
            self.event.query_uuid is not None
            and self.query_uuid != self.event.query_uuid
        ):
            raise ValueError("EventContext query_uuid does not match Event query_uuid")
        if self.event.query_uuid is None:
            self.event.query_uuid = self.query_uuid
        return self

    @pydantic.field_validator("event", mode="before")
    def validate_event(cls, v):
        if isinstance(v, BaseEventModel):
            return v

        event_name = v["event_name"]
        event_class = getattr(events_module, event_name)
        event = event_class.model_validate(v)
        return event
