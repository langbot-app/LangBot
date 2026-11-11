"""Run-scoped LangBot tools exposed to external harnesses."""

from __future__ import annotations

import base64
import copy
import json
import typing

import pydantic

from langbot_plugin.api.agent_tools.decorators import (
    AgentToolSpec,
    agent_tool,
    collect_agent_tools,
)
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.box import BoxAcquireRequest
from langbot_plugin.api.proxies.runner import RunnerAPIProxy


class ExportBoxArgs(pydantic.BaseModel):
    paths: list[str] = pydantic.Field(
        min_length=1, description="Absolute sandbox file paths to export and clean up"
    )


class EmptyArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")


class BindBoxArgs(EmptyArgs):
    box_id: str = pydantic.Field(min_length=1)


class ImportBoxArgs(EmptyArgs):
    attachment_ids: list[str] | None = None


class ReadInputAttachmentArgs(EmptyArgs):
    ref: str = pydantic.Field(min_length=1)


class ReplyFilesArgs(EmptyArgs):
    file_ids: list[str] = pydantic.Field(min_length=1, max_length=100)


class ListAssetsArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    asset_types: list[
        typing.Literal[
            "event",
            "history",
            "knowledge_bases",
            "tools",
            "platform_tools",
            "mcp_tools",
            "skills",
        ]
    ] = pydantic.Field(default_factory=list)
    include_schemas: bool = False


class HistoryPageArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    conversation_id: str | None = None
    before_cursor: str | None = None
    after_cursor: str | None = None
    limit: int = pydantic.Field(default=50, ge=1, le=100)
    direction: str = pydantic.Field(default="backward", pattern="^(backward|forward)$")
    include_attachments: bool = False


class RetrieveKnowledgeArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    kb_id: str
    query_text: str | None = None
    query: str | None = None
    top_k: int = pydantic.Field(default=5, ge=1, le=20)
    filters: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class CallToolArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    tool_name: str
    parameters: dict[str, typing.Any] = pydantic.Field(default_factory=dict)


class GetToolDetailArgs(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    tool_name: str


def _dump_jsonable(value: typing.Any) -> typing.Any:
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _dump_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _operation_allowed(operations: list[str], operation: str) -> bool:
    return not operations or operation in operations


def _with_optional_run_token(tool: dict[str, typing.Any]) -> dict[str, typing.Any]:
    data = copy.deepcopy(tool)
    schema = data.setdefault("inputSchema", {})
    if not isinstance(schema, dict):
        schema = {}
        data["inputSchema"] = schema
    properties = schema.setdefault("properties", {})
    if not isinstance(properties, dict):
        properties = {}
        schema["properties"] = properties
    properties.setdefault(
        "run_token",
        {
            "type": "string",
            "description": (
                "Short-lived LangBot run token. Optional when the MCP request "
                "already includes an Authorization bearer token."
            ),
        },
    )
    return data


class AgentRunExternalTools:
    """Annotated tool surface backed by RunnerAPIProxy."""

    def __init__(self, api: RunnerAPIProxy, ctx: RunnerContext) -> None:
        self.api = api
        self.ctx = ctx
        self._tools = collect_agent_tools(self)

    @classmethod
    def all_mcp_tools(
        cls, *, include_run_token: bool = False
    ) -> list[dict[str, typing.Any]]:
        tools: list[dict[str, typing.Any]] = []
        seen: set[str] = set()
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            spec = getattr(attr, "__langbot_agent_tool__", None)
            if not isinstance(spec, AgentToolSpec):
                continue
            if spec.name in seen:
                raise ValueError(f"Duplicate Agent tool name: {spec.name}")
            seen.add(spec.name)
            tools.append(spec.to_mcp_tool())
        if include_run_token:
            return [_with_optional_run_token(tool) for tool in tools]
        return tools

    def _available_tool_names(self) -> set[str]:
        names = {"langbot_get_current_event", "langbot_list_assets"}

        available_apis = self.ctx.context.available_apis
        if available_apis.input_attachments and self.ctx.input.attachments:
            names.add("langbot_read_input_attachment")
        if available_apis.box:
            names.update(
                {
                    "langbot_get_box_status",
                    "langbot_list_boxes",
                    "langbot_acquire_box",
                    "langbot_bind_box",
                    "langbot_import_box_attachments",
                    "langbot_export_box_files",
                }
            )
            if any(
                item.tool_name == "event_reply"
                and _operation_allowed(item.operations, "call")
                for item in self.ctx.resources.tools
            ):
                names.add("langbot_reply_files")
        if available_apis.history_page:
            names.add("langbot_history_page")
        if any(
            _operation_allowed(item.operations, "retrieve")
            for item in self.ctx.resources.knowledge_bases
        ):
            names.add("langbot_retrieve_knowledge")
        if any(
            _operation_allowed(item.operations, "detail")
            for item in self.ctx.resources.tools
        ):
            names.add("langbot_get_tool_detail")
        if any(
            _operation_allowed(item.operations, "call")
            for item in self.ctx.resources.tools
        ):
            names.add("langbot_call_tool")

        return names

    def mcp_tools(
        self,
        *,
        include_unavailable: bool = False,
        include_run_token: bool = False,
    ) -> list[dict[str, typing.Any]]:
        available_names = (
            self._available_tool_names() if not include_unavailable else None
        )
        tools = [
            tool.spec.to_mcp_tool()
            for name, tool in self._tools.items()
            if available_names is None or name in available_names
        ]
        if include_run_token:
            return [_with_optional_run_token(tool) for tool in tools]
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, typing.Any] | None = None
    ) -> typing.Any:
        tool = self._tools.get(name) if name in self._available_tool_names() else None
        if tool is None:
            raise ValueError(f"Unknown LangBot external tool: {name}")
        args = tool.spec.args_model.model_validate(arguments or {})
        return await tool.handler(args)

    async def call_mcp_tool(
        self, name: str, arguments: dict[str, typing.Any] | None = None
    ) -> dict[str, typing.Any]:
        try:
            result = await self.call_tool(name, arguments)
        except Exception as e:
            return {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": str(e),
                    }
                ],
            }

        structured = _dump_jsonable(result)
        if not isinstance(structured, dict):
            structured = {"result": structured}
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(structured, ensure_ascii=False),
                }
            ],
            "structuredContent": structured,
        }

    def _asset_summary(
        self,
        *,
        asset_types: list[str] | None = None,
        include_schemas: bool = False,
    ) -> dict[str, typing.Any]:
        requested = set(asset_types or [])
        include_all = not requested

        data: dict[str, typing.Any] = {
            "run_id": self.ctx.run_id,
            "asset_types": sorted(
                requested
                or {
                    "event",
                    "history",
                    "knowledge_bases",
                    "tools",
                    "platform_tools",
                    "mcp_tools",
                    "skills",
                }
            ),
        }
        if include_all or "event" in requested:
            data["event"] = {
                "available": True,
                "tool_name": "langbot_get_current_event",
            }
        if include_all or "history" in requested:
            data["history"] = {
                "available": bool(self.ctx.context.available_apis.history_page),
                "tool_name": "langbot_history_page",
            }
        if include_all or "knowledge_bases" in requested:
            data["knowledge_bases"] = [
                {
                    "kb_id": item.kb_id,
                    "name": item.kb_name,
                    "type": item.kb_type,
                    "operations": list(item.operations),
                }
                for item in self.ctx.resources.knowledge_bases
            ]
        if include_all or "tools" in requested:
            data["tools"] = [
                {
                    "tool_name": item.tool_name,
                    "type": item.tool_type,
                    "description": item.description,
                    "operations": list(item.operations),
                }
                for item in self.ctx.resources.tools
                if item.tool_type != "platform"
            ]
        if include_all or "platform_tools" in requested:
            data["platform_tools"] = [
                {
                    "tool_name": item.tool_name,
                    "description": item.description,
                    "operations": list(item.operations),
                    **(
                        {"schema": _dump_jsonable(item.parameters or {})}
                        if include_schemas
                        else {}
                    ),
                }
                for item in self.ctx.resources.tools
                if item.tool_type == "platform"
            ]
        if include_all or "mcp_tools" in requested:
            data["mcp_tools"] = [
                {
                    "tool_name": tool["name"],
                    "description": tool.get("description"),
                    **(
                        {"schema": tool.get("inputSchema", {})}
                        if include_schemas
                        else {}
                    ),
                }
                for tool in self.mcp_tools()
            ]
        if include_all or "skills" in requested:
            data["skills"] = [
                {
                    "skill_name": item.skill_name,
                    "display_name": item.display_name,
                    "description": item.description,
                }
                for item in self.ctx.resources.skills
            ]
        return data

    @agent_tool(
        name="langbot_list_assets",
        description="List the LangBot event, history, knowledge bases, ordinary tools, platform action tools, skills, and MCP bridge tools authorized for the current run.",
        args_model=ListAssetsArgs,
        read_only=True,
    )
    async def list_assets(self, args: ListAssetsArgs) -> dict[str, typing.Any]:
        return self._asset_summary(
            asset_types=args.asset_types,
            include_schemas=args.include_schemas,
        )

    @agent_tool(
        name="langbot_get_current_event",
        description="Return the current LangBot event, input, actor, subject, resources, context, state, and runtime snapshot.",
        args_model=EmptyArgs,
        read_only=True,
    )
    async def get_current_event(self, args: EmptyArgs) -> dict[str, typing.Any]:
        input_value = self.ctx.input
        input_text = ""
        if input_value is not None:
            to_text = getattr(input_value, "to_text", None)
            if callable(to_text):
                input_text = to_text()
            else:
                input_text = getattr(input_value, "text", "") or ""

        return {
            "run_id": self.ctx.run_id,
            "trigger": _dump_jsonable(self.ctx.trigger),
            "event": _dump_jsonable(self.ctx.event),
            "conversation": _dump_jsonable(self.ctx.conversation),
            "actor": _dump_jsonable(self.ctx.actor),
            "subject": _dump_jsonable(self.ctx.subject),
            "input": {
                "text": input_text,
                "attachments": _dump_jsonable(getattr(input_value, "attachments", [])),
                "contents": _dump_jsonable(getattr(input_value, "contents", [])),
            },
            "resources": _dump_jsonable(self.ctx.resources),
            "context": _dump_jsonable(self.ctx.context),
            "state": _dump_jsonable(self.ctx.state),
            "runtime": _dump_jsonable(self.ctx.runtime),
        }

    @agent_tool(
        name="langbot_history_page",
        description="Page through authorized LangBot conversation history for the current run.",
        args_model=HistoryPageArgs,
        read_only=True,
    )
    async def history_page(self, args: HistoryPageArgs) -> dict[str, typing.Any]:
        return await self.api.history_page(
            conversation_id=args.conversation_id,
            before_cursor=args.before_cursor,
            after_cursor=args.after_cursor,
            limit=args.limit,
            direction=args.direction,
            include_attachments=args.include_attachments,
        )

    @agent_tool(
        name="langbot_retrieve_knowledge",
        description="Retrieve documents from an authorized LangBot knowledge base for the current run.",
        args_model=RetrieveKnowledgeArgs,
        read_only=True,
    )
    async def retrieve_knowledge(
        self, args: RetrieveKnowledgeArgs
    ) -> list[dict[str, typing.Any]]:
        query_text = (args.query_text or args.query or "").strip()
        if not query_text:
            raise ValueError("query_text is required")
        return await self.api.retrieve_knowledge(
            kb_id=args.kb_id,
            query_text=query_text,
            top_k=args.top_k,
            filters=args.filters,
        )

    @agent_tool(
        name="langbot_get_tool_detail",
        description="Return the parameter schema and description for an authorized LangBot tool in the current run.",
        args_model=GetToolDetailArgs,
        read_only=True,
    )
    async def get_tool_detail(self, args: GetToolDetailArgs) -> dict[str, typing.Any]:
        return await self.api.get_tool_detail(tool_name=args.tool_name)

    @agent_tool(
        name="langbot_call_tool",
        description="Call an authorized LangBot tool for the current run.",
        args_model=CallToolArgs,
    )
    async def call_langbot_tool(self, args: CallToolArgs) -> dict[str, typing.Any]:
        return await self.api.call_tool(
            tool_name=args.tool_name,
            parameters=args.parameters,
        )

    @agent_tool(
        name="langbot_get_box_status",
        description="Check sandbox availability, capacity and required reuse key before acquiring a Box.",
        args_model=EmptyArgs,
        read_only=True,
    )
    async def get_box_status(self, args: EmptyArgs):
        return await self.api.get_box_status()

    @agent_tool(
        name="langbot_list_boxes",
        description="List sandbox sessions accessible to this run.",
        args_model=EmptyArgs,
        read_only=True,
    )
    async def list_boxes(self, args: EmptyArgs):
        return await self.api.list_boxes()

    @agent_tool(
        name="langbot_acquire_box",
        description="Create or reuse a sandbox by reuse_key. Honor required_reuse_key from status. Reusing an existing Box is allowed when capacity is full. Bind the returned Box before using sandbox tools.",
        args_model=BoxAcquireRequest,
    )
    async def acquire_box(self, args: BoxAcquireRequest):
        return await self.api.acquire_box(args.reuse_key, options=args.options)

    @agent_tool(
        name="langbot_bind_box",
        description="Bind a sandbox to this run before exec/read/write/edit/glob/grep. One Box per run. Returns this run's output directory.",
        args_model=BindBoxArgs,
    )
    async def bind_box(self, args: BindBoxArgs):
        return await self.api.bind_box(args.box_id)

    @agent_tool(
        name="langbot_import_box_attachments",
        description="Import current event attachment refs into the bound Box; omit attachment_ids to import all. Returns actual file paths.",
        args_model=ImportBoxArgs,
    )
    async def import_box_attachments(self, args: ImportBoxArgs):
        return await self.api.import_box_attachments(args.attachment_ids)

    @agent_tool(
        name="langbot_read_input_attachment",
        description="Read one current input attachment by ref, such as att-1 from [attachment att-1: ...] in the message. Returns name, mime_type, size and base64 content.",
        args_model=ReadInputAttachmentArgs,
    )
    async def read_input_attachment(self, args: ReadInputAttachmentArgs):
        data = await self.api.read_input_attachment(args.ref)
        return {
            "ref": data.ref,
            "name": data.name,
            "mime_type": data.mime_type,
            "size": data.size,
            "content_base64": base64.b64encode(data.data).decode("ascii"),
        }

    @agent_tool(
        name="langbot_export_box_files",
        description="Validate and export selected sandbox files, then clean up accepted files. Returns file IDs; does not send them to the user.",
        args_model=ExportBoxArgs,
    )
    async def export_box_files(self, args: ExportBoxArgs):
        return await self.api.export_box_files(args.paths)

    @agent_tool(
        name="langbot_reply_files",
        description="Send exported file IDs as a reply to the current event, subject to platform reply authorization.",
        args_model=ReplyFilesArgs,
    )
    async def reply_files(self, args: ReplyFilesArgs):
        return await self.api.reply_files(args.file_ids)
