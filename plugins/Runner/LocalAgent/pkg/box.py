"""LocalAgent's sandbox policy and explicit file preparation/delivery."""

import asyncio
import json
import re
from inspect import signature
from string import Formatter

from langbot_plugin.api.entities.builtin.provider.message import ContentElement
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.errors import AgentAPIException

from .agent_core.types import NonRetryableToolError

SANDBOX_TOOLS = frozenset({"exec", "read", "write", "edit", "glob", "grep"})


def resolve_reuse_key(ctx, template: str) -> str:
    if not isinstance(template, str) or not template.strip():
        raise ValueError("Box reuse template must not be empty")
    conversation = ctx.conversation
    target = ctx.delivery.reply_target or {}
    variables = {
        **ctx.variables,
        "global": "global",
        "run_id": ctx.run_id,
        "query_id": ctx.variables.get("query_id", ctx.run_id),
        "event_id": ctx.event.event_id,
        "event_type": ctx.event.event_type,
        "launcher_type": (conversation.launcher_type if conversation else None) or target.get("target_type"),
        "launcher_id": (conversation.launcher_id if conversation else None) or target.get("target_id"),
        "sender_id": (conversation.sender_id if conversation else None) or (ctx.actor.actor_id if ctx.actor else None),
        "conversation_id": ctx.variables.get("conversation_id")
        or (conversation.conversation_id if conversation else None),
        "bot_id": (conversation.bot_id if conversation else None) or ctx.event.data.get("bot_uuid"),
    }
    # Interpolate named scalar fields, never Python expressions or object access.
    for _, name, spec, conversion in Formatter().parse(template):
        if name is not None and (name not in variables or variables[name] is None or spec or conversion):
            raise ValueError(f"Unavailable or invalid Box template variable: {name}")
    key = template.format_map(variables)
    if not key.strip() or len(key) > 1024:
        raise ValueError("Box reuse key must contain 1 to 1024 characters")
    return key


class LocalAgentBox:
    def __init__(self, ctx, api):
        self.ctx = ctx
        self.api = api
        self.binding = None
        self.file_ids = []
        self._delivered = set()
        self._delivery_failure = None
        self._export_lock = asyncio.Lock()
        self._prepare_lock = asyncio.Lock()
        self._prepared = False

    def install_tool(self, assembly):
        from langbot_plugin.api.entities.builtin.resource.tool import LLMTool

        description = "Export selected absolute sandbox file paths. Validates all files, accepts attachments, then cleans up selected files. Required for file delivery."
        assembly.tools.append(
            LLMTool(
                name="export_box_files",
                human_desc=description,
                description=description,
                parameters={
                    "type": "object",
                    "properties": {
                        "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20}
                    },
                    "required": ["paths"],
                    "additionalProperties": False,
                },
                func=self.export_files,
            )
        )
        assembly.tool_executor.allowed_tools.add("export_box_files")
        assembly.tool_executor.local_tools["export_box_files"] = self.export_files

    async def export_files(self, paths):
        # Parallel tool calls share this run's delivery state.
        async with self._export_lock:
            if self._delivery_failure is not None:
                raise self._delivery_failure
            await self.prepare()
            try:
                files = await self.ctx.export_box_files(paths)
            except PermissionError as exc:
                raise NonRetryableToolError(str(exc)) from exc
            except Exception as exc:
                error = exc.error.model_dump() if isinstance(exc, AgentAPIException) else {}
                # SDK 0.7.13's relay retains the versioned frame in message text.
                frame = re.fullmatch(
                    r"(?:(?:ActionCallError|BoxExportError|BoxValidationError): )*LANGBOT_EXPORT_V1:(\{.*\})",
                    str(exc)[:16384],
                    re.DOTALL,
                )
                if frame:
                    try:
                        error = json.loads(frame[1])
                    except ValueError:
                        pass
                if isinstance(error, dict) and error.get("code") == "box.export.invalid_response":
                    raise NonRetryableToolError(str(error.get("message", exc))) from exc
                raise
            ids = [item.id for item in files if item.id not in self._delivered]
            if self.ctx.delivery.automatic_reply:
                self.file_ids = list(dict.fromkeys(self.file_ids + ids))
            elif ids:
                try:
                    await self.ctx.reply_files(ids)
                except BaseException as exc:
                    if isinstance(exc, Exception):
                        self._delivery_failure = NonRetryableToolError(
                            "Files were accepted by Core, but platform delivery failed; do not regenerate or resend them. "
                            + str(exc)
                        )
                    else:
                        self._delivery_failure = exc
                    raise self._delivery_failure from exc
                self._delivered.update(ids)
            return {"status": "accepted", "items": [item.model_dump() for item in files]}

    def needed(self):
        tools = {t.tool_name for t in self.api.get_allowed_tools()}
        return (
            self.ctx.config.get("box-enabled", True)
            and bool(tools.intersection(SANDBOX_TOOLS))
            and self.ctx.context.available_apis.box
        )

    async def prepare(self):
        async with self._prepare_lock:
            if self._prepared:
                return
            await self._prepare()
            self._prepared = True

    async def call_tool(self, tool_name, parameters):
        if tool_name in SANDBOX_TOOLS:
            await self.prepare()
        result = await self.api.call_tool(tool_name=tool_name, parameters=parameters)
        if tool_name in SANDBOX_TOOLS:
            payload = result if isinstance(result, dict) else {"result": result}
            result = {**payload, "sandbox_instructions": self._instructions(), "sandbox_outbox": self.binding.outbox}
        return result

    def _instructions(self):
        return (
            f"Prefer storing generated artifacts in {self.binding.outbox}/; create it if needed. "
            "To deliver files, explicitly call export_box_files with their absolute paths and confirm success before finishing. "
            "Writing a file does not deliver it. Fix reported errors and retry the tool; no automatic export occurs."
        )

    async def _prepare(self):
        if "paths" not in signature(RunnerContext.export_box_files).parameters:
            raise RuntimeError(
                "Explicit file export requires a matching Core and Plugin Runtime SDK; upgrade them together."
            )
        status = await self.api.get_box_status()
        if not status.available:
            raise RuntimeError(status.reason or "Box is unavailable")
        template = self.ctx.config.get("box-session-id-template", "{launcher_type}_{launcher_id}")
        key = status.required_reuse_key or resolve_reuse_key(self.ctx, template)
        # Always try acquisition even at zero remaining capacity: reuse does not consume another slot.
        box = await self.api.acquire_box(key)
        self.binding = await self.ctx.bind_box(box.id)
        files = await self.ctx.import_box_attachments() if self.ctx.input.attachments else []
        by_ref = {item.id: item for item in files}
        for attachment in self.ctx.input.attachments:
            if attachment.ref in by_ref:
                item = by_ref[attachment.ref]
                attachment.path, attachment.size = item.path, item.size
        if files:
            self.ctx.input.contents = [c for c in self.ctx.input.contents if c.type not in {"file_url", "file_base64"}]
        self.ctx.input.contents.append(ContentElement.from_text(self._instructions()))
